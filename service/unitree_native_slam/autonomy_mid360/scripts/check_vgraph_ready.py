#!/usr/bin/env python3
"""Wait until the robot is attached to the loaded FAR V-Graph main component."""

from __future__ import annotations

import argparse
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


@dataclass(frozen=True)
class GraphNodeSnapshot:
    """Minimal graph node representation used by the readiness check."""

    node_id: int
    position: tuple[float, float, float]
    connections: tuple[int, ...]


@dataclass(frozen=True)
class GraphReadinessResult:
    """Readiness result for one V-Graph sample."""

    ready: bool
    reason: str
    graph_size: int
    component_count: int
    robot_component_size: int
    required_component_size: int
    attachment_node_id: int | None
    attachment_node_distance: float
    nearby_node_count: int


def parse_prior_graph(path: Path) -> list[GraphNodeSnapshot]:
    """Parse the connectivity fields needed from a FAR ``.vgh`` graph file."""
    nodes: list[GraphNodeSnapshot] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        fields = line.split("|", maxsplit=1)[0].split()
        if len(fields) < 15:
            raise ValueError(f"invalid prior graph line {line_number}: expected at least 15 fields")
        try:
            nodes.append(
                GraphNodeSnapshot(
                    node_id=int(fields[0]),
                    position=(float(fields[2]), float(fields[3]), float(fields[4])),
                    connections=tuple(int(value) for value in fields[15:]),
                )
            )
        except ValueError as exc:
            raise ValueError(f"invalid prior graph line {line_number}: {exc}") from exc
    if not nodes:
        raise ValueError(f"prior graph is empty: {path}")
    return nodes


def _adjacency(nodes: Iterable[GraphNodeSnapshot]) -> dict[int, set[int]]:
    by_id = {node.node_id: node for node in nodes}
    adjacency = {node_id: set() for node_id in by_id}
    for node in by_id.values():
        for neighbor_id in node.connections:
            if neighbor_id not in by_id or neighbor_id == node.node_id:
                continue
            adjacency[node.node_id].add(neighbor_id)
            adjacency[neighbor_id].add(node.node_id)
    return adjacency


def component_sizes(nodes: Sequence[GraphNodeSnapshot]) -> list[int]:
    """Return undirected connected-component sizes, largest first."""
    adjacency = _adjacency(nodes)
    unseen = set(adjacency)
    sizes: list[int] = []
    while unseen:
        start = unseen.pop()
        stack = [start]
        size = 0
        while stack:
            node_id = stack.pop()
            size += 1
            new_neighbors = adjacency[node_id] & unseen
            unseen.difference_update(new_neighbors)
            stack.extend(new_neighbors)
        sizes.append(size)
    return sorted(sizes, reverse=True)


def _components_by_node(adjacency: dict[int, set[int]]) -> tuple[dict[int, int], list[int]]:
    unseen = set(adjacency)
    component_by_node: dict[int, int] = {}
    sizes: list[int] = []
    while unseen:
        start = unseen.pop()
        stack = [start]
        members: list[int] = []
        while stack:
            node_id = stack.pop()
            members.append(node_id)
            new_neighbors = adjacency[node_id] & unseen
            unseen.difference_update(new_neighbors)
            stack.extend(new_neighbors)
        component_index = len(sizes)
        sizes.append(len(members))
        for node_id in members:
            component_by_node[node_id] = component_index
    return component_by_node, sizes


def evaluate_graph_readiness(
    nodes: Sequence[GraphNodeSnapshot],
    robot_position: tuple[float, float, float],
    *,
    required_component_size: int,
    max_robot_node_distance: float,
) -> GraphReadinessResult:
    """Check whether any nearby graph node belongs to a large component."""
    if not nodes:
        return GraphReadinessResult(
            ready=False,
            reason="V-Graph has no encoded nodes",
            graph_size=0,
            component_count=0,
            robot_component_size=0,
            required_component_size=required_component_size,
            attachment_node_id=None,
            attachment_node_distance=math.inf,
            nearby_node_count=0,
        )

    by_id = {node.node_id: node for node in nodes}
    adjacency = _adjacency(nodes)
    component_by_node, sizes = _components_by_node(adjacency)
    distances = {node.node_id: math.dist(node.position, robot_position) for node in by_id.values()}
    nearby_nodes = [node for node in by_id.values() if distances[node.node_id] <= max_robot_node_distance]
    nearest = min(by_id.values(), key=lambda node: distances[node.node_id])

    if not nearby_nodes:
        attachment = nearest
        attachment_component_size = sizes[component_by_node[attachment.node_id]]
        reason = (
            f"robot is {distances[nearest.node_id]:.3f}m from nearest finalized V-Graph node "
            f"(limit {max_robot_node_distance:.3f}m)"
        )
        ready = False
    else:
        attachment = max(
            nearby_nodes,
            key=lambda node: (sizes[component_by_node[node.node_id]], -distances[node.node_id]),
        )
        attachment_component_size = sizes[component_by_node[attachment.node_id]]

    if nearby_nodes and attachment_component_size < required_component_size:
        reason = (
            f"largest component reachable within {max_robot_node_distance:.3f}m has "
            f"{attachment_component_size} nodes; requires at least {required_component_size}"
        )
        ready = False
    elif nearby_nodes:
        reason = "robot is attached to the loaded V-Graph main component"
        ready = True

    return GraphReadinessResult(
        ready=ready,
        reason=reason,
        graph_size=len(by_id),
        component_count=len(sizes),
        robot_component_size=attachment_component_size,
        required_component_size=required_component_size,
        attachment_node_id=attachment.node_id,
        attachment_node_distance=distances[attachment.node_id],
        nearby_node_count=len(nearby_nodes),
    )


def _snapshot_graph(message: object) -> list[GraphNodeSnapshot]:
    return [
        GraphNodeSnapshot(
            node_id=int(node.id),
            position=(float(node.position.x), float(node.position.y), float(node.position.z)),
            connections=tuple(int(node_id) for node_id in node.connect_nodes),
        )
        for node in message.nodes
    ]


def _format_result(result: GraphReadinessResult) -> str:
    attachment_id = "none" if result.attachment_node_id is None else str(result.attachment_node_id)
    attachment_distance = (
        "inf" if not math.isfinite(result.attachment_node_distance) else f"{result.attachment_node_distance:.3f}m"
    )
    return (
        f"graph={result.graph_size}, components={result.component_count}, "
        f"robot_component={result.robot_component_size}/{result.required_component_size}, "
        f"nearby_nodes={result.nearby_node_count}, attachment_node={attachment_id}, "
        f"attachment_distance={attachment_distance}: {result.reason}"
    )


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _ratio(value: str) -> float:
    parsed = float(value)
    if not 0 < parsed <= 1:
        raise argparse.ArgumentTypeError("must be greater than zero and at most one")
    return parsed


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prior-graph", type=Path, required=True)
    parser.add_argument("--graph-topic", default="/robot_vgraph")
    parser.add_argument("--pose-topic", default="/baselink2map")
    parser.add_argument("--timeout", type=_positive_float, default=30.0)
    parser.add_argument("--consecutive-samples", type=int, default=3)
    parser.add_argument("--sample-interval", type=float, default=1.0)
    parser.add_argument("--min-prior-component-ratio", type=_ratio, default=0.9)
    parser.add_argument("--max-robot-node-distance", type=_positive_float, default=1.0)
    args = parser.parse_args()
    if args.consecutive_samples < 1:
        parser.error("--consecutive-samples must be at least one")
    if args.sample_interval < 0:
        parser.error("--sample-interval cannot be negative")
    return args


def main() -> int:
    """Run the ROS readiness probe until it passes or times out."""
    args = _parse_args()
    if not args.prior_graph.is_file():
        print(f"ERROR: prior graph is missing: {args.prior_graph}", file=sys.stderr)
        return 2

    try:
        prior_nodes = parse_prior_graph(args.prior_graph)
    except (OSError, ValueError) as exc:
        print(f"ERROR: could not parse prior graph: {exc}", file=sys.stderr)
        return 2

    prior_components = component_sizes(prior_nodes)
    prior_main_component_size = prior_components[0]
    required_component_size = max(1, math.ceil(prior_main_component_size * args.min_prior_component_ratio))

    try:
        import rclpy
        from nav_msgs.msg import Odometry
        from visibility_graph_msg.msg import Graph
    except ImportError as exc:
        print(f"ERROR: ROS V-Graph Python packages are unavailable: {exc}", file=sys.stderr)
        return 2

    rclpy.init()
    node = rclpy.create_node("magic_mini_vgraph_readiness")
    latest_graph: list[object | None] = [None]
    latest_pose: list[tuple[float, float, float] | None] = [None]
    graph_sequence = [0]

    def graph_callback(message: object) -> None:
        latest_graph[0] = message
        graph_sequence[0] += 1

    def pose_callback(message: object) -> None:
        position = message.pose.pose.position
        latest_pose[0] = (float(position.x), float(position.y), float(position.z))

    node.create_subscription(Graph, args.graph_topic, graph_callback, 5)
    node.create_subscription(Odometry, args.pose_topic, pose_callback, 5)

    deadline = time.monotonic() + args.timeout
    last_evaluated_sequence = -1
    last_evaluated_at = -math.inf
    consecutive = 0
    last_result: GraphReadinessResult | None = None
    try:
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=min(0.2, max(0.0, deadline - time.monotonic())))
            now = time.monotonic()
            if latest_graph[0] is None or latest_pose[0] is None:
                continue
            if graph_sequence[0] == last_evaluated_sequence:
                continue
            if now - last_evaluated_at < args.sample_interval:
                continue

            last_evaluated_sequence = graph_sequence[0]
            last_evaluated_at = now
            last_result = evaluate_graph_readiness(
                _snapshot_graph(latest_graph[0]),
                latest_pose[0],
                required_component_size=required_component_size,
                max_robot_node_distance=args.max_robot_node_distance,
            )
            consecutive = consecutive + 1 if last_result.ready else 0
            print(
                f"V-Graph readiness sample {consecutive}/{args.consecutive_samples}: " f"{_format_result(last_result)}",
                flush=True,
            )
            if consecutive >= args.consecutive_samples:
                print(
                    f"V-Graph ready: prior_main_component={prior_main_component_size}, "
                    f"required_component={required_component_size}",
                    flush=True,
                )
                return 0
    finally:
        node.destroy_node()
        rclpy.shutdown()

    if last_result is None:
        detail = f"no synchronized {args.graph_topic} and {args.pose_topic} samples received"
    else:
        detail = _format_result(last_result)
    print(
        f"ERROR: V-Graph readiness timed out after {args.timeout:.1f}s; {detail}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
