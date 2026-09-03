import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "service" / "unitree_native_slam" / "autonomy_mid360" / "scripts" / "check_vgraph_ready.py"
PRIOR_GRAPH_PATH = (
    ROOT / "service" / "unitree_native_slam" / "autonomy_mid360" / "prior_graphs" / "my_prior_graph_final.vgh"
)

SPEC = importlib.util.spec_from_file_location("check_vgraph_ready", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

GraphNodeSnapshot = MODULE.GraphNodeSnapshot
component_sizes = MODULE.component_sizes
evaluate_graph_readiness = MODULE.evaluate_graph_readiness
parse_prior_graph = MODULE.parse_prior_graph


def _node(node_id, x, connections):
    return GraphNodeSnapshot(node_id=node_id, position=(float(x), 0.0, 0.0), connections=tuple(connections))


def test_company_prior_graph_main_component_size_is_stable():
    nodes = parse_prior_graph(PRIOR_GRAPH_PATH)

    assert len(nodes) == 599
    assert component_sizes(nodes)[:4] == [458, 24, 14, 14]


def test_graph_is_ready_when_robot_is_near_the_large_component():
    nodes = [
        _node(1, 0.0, [2]),
        _node(2, 1.0, [1, 3]),
        _node(3, 2.0, [2, 4]),
        _node(4, 3.0, [3]),
        _node(10, 10.0, [11]),
        _node(11, 11.0, [10]),
    ]

    result = evaluate_graph_readiness(
        nodes,
        (0.1, 0.0, 0.0),
        required_component_size=4,
        max_robot_node_distance=1.0,
    )

    assert result.ready is True
    assert result.robot_component_size == 4
    assert result.component_count == 2
    assert result.attachment_node_id == 1


def test_graph_is_not_ready_when_robot_is_only_attached_to_an_island():
    nodes = [
        _node(1, 0.0, [2]),
        _node(2, 1.0, [1, 3]),
        _node(3, 2.0, [2, 4]),
        _node(4, 3.0, [3]),
        _node(10, 10.0, [11]),
        _node(11, 11.0, [10]),
    ]

    result = evaluate_graph_readiness(
        nodes,
        (10.1, 0.0, 0.0),
        required_component_size=4,
        max_robot_node_distance=1.0,
    )

    assert result.ready is False
    assert result.robot_component_size == 2
    assert "requires at least 4" in result.reason


def test_graph_is_not_ready_when_robot_has_no_nearby_finalized_node():
    result = evaluate_graph_readiness(
        [_node(1, 0.0, [2]), _node(2, 1.0, [1])],
        (5.0, 0.0, 0.0),
        required_component_size=2,
        max_robot_node_distance=1.0,
    )

    assert result.ready is False
    assert result.attachment_node_distance == 4.0
    assert "from nearest finalized V-Graph node" in result.reason


def test_nearby_main_component_wins_over_a_closer_island_node():
    nodes = [
        _node(1, 0.8, [2]),
        _node(2, 1.8, [1, 3]),
        _node(3, 2.8, [2, 4]),
        _node(4, 3.8, [3]),
        _node(10, 0.1, [11]),
        _node(11, 0.2, [10]),
    ]

    result = evaluate_graph_readiness(
        nodes,
        (0.0, 0.0, 0.0),
        required_component_size=4,
        max_robot_node_distance=1.0,
    )

    assert result.ready is True
    assert result.attachment_node_id == 1
    assert result.attachment_node_distance == 0.8
    assert result.nearby_node_count == 3
