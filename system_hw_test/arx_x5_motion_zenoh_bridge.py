#!/usr/bin/env python3
"""
Bridge ARX_X5 motion/state between Zenoh and ROS2.

Run this script in the Python 3.8 ROS2 environment after sourcing:
    source /opt/ros/foxy/setup.bash
    source /path/to/arx_x5_workspace/install/setup.bash

Default mode connects as a Zenoh client to tcp/127.0.0.1:7447:
    python3.8 system_hw_test/arx_x5_motion_zenoh_bridge.py

Standalone local testing listens on tcp/127.0.0.1:7447 with multicast scouting off:
    python3.8 system_hw_test/arx_x5_motion_zenoh_bridge.py --standalone-discovery

Request topic: arx_x5/motion/request
State topic:   arx_x5/state
Status topic:  arx_x5/motion/status

Motion request examples:
    {"action": "publish_end_pose", "end_pos": [x, y, z, r, p, y], "gripper": 2.0}
    {"action": "move_end_pose", "target_pose": [x, y, z, r, p, y], "gripper": 2.0}
    {"action": "publish_joints", "joint_pos": [j1, j2, j3, j4, j5, j6], "gripper": 0.02}
    {"action": "move_joints", "target_joints": [j1, j2, j3, j4, j5, j6], "gripper": 0.02}
    {"action": "stop"}
"""

import argparse
import json
import logging
import threading
import time
from queue import Empty, Queue

import rclpy
import zenoh
from rclpy.node import Node
from zenoh import ZBytes

from arx5_arm_msg.msg import RobotCmd, RobotStatus


END_CONTROL_MODE = 4
POSITION_CONTROL_MODE = 5


def open_zenoh_session(
    *,
    endpoint="tcp/127.0.0.1:7447",
    standalone_discovery=False,
    standalone_listen="tcp/127.0.0.1:7447",
):
    """
    Open a Zenoh session for the bridge.

    Default client mode attaches to an existing local OM1/router endpoint without
    multicast scouting. Standalone mode listens on TCP only, also without multicast
    scouting, so it does not bind UDP scout ports used by other peers.
    """
    if standalone_discovery:
        logging.info(
            "Standalone Zenoh session: listen=%s, multicast scouting off.",
            standalone_listen,
        )
        cfg = zenoh.Config()
        cfg.insert_json5("scouting/multicast/enabled", "false")
        cfg.insert_json5("listen/endpoints", f'["{standalone_listen}"]')
        try:
            session = zenoh.open(cfg)
        except Exception as e:
            raise RuntimeError(
                f"Standalone Zenoh listen failed ({standalone_listen}): {e}\n"
                "  Choose another TCP port via --zenoh-standalone-listen and ensure "
                "OM1 clients target the same endpoint."
            ) from e
        logging.info("Zenoh standalone session opened (TCP listen only).")
        return session

    cfg = zenoh.Config()
    cfg.insert_json5("mode", '"client"')
    cfg.insert_json5("connect/endpoints", f'["{endpoint}"]')
    cfg.insert_json5("scouting/multicast/enabled", "false")
    try:
        session = zenoh.open(cfg)
    except Exception as e:
        raise RuntimeError(
            f"Zenoh client could not connect to {endpoint}: {e}\n"
            "  Start OM1 / a local Zenoh router first, or run this bridge with "
            "--standalone-discovery and let OM1 connect to it."
        ) from e
    logging.info("Zenoh client session opened, endpoint=%s", endpoint)
    return session


def _as_float_list(values, *, name, min_len=6):
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{name} must be a list")
    if len(values) < min_len:
        raise ValueError(f"{name} must contain at least {min_len} values")
    try:
        return [float(value) for value in values[:min_len]]
    except (TypeError, ValueError) as e:
        raise ValueError(f"{name} must contain numeric values") from e


def _linspace(start, end, steps):
    steps = int(steps)
    if steps <= 1:
        yield list(end)
        return

    for index in range(steps):
        ratio = float(index) / float(steps - 1)
        yield [
            float(s) + (float(e) - float(s)) * ratio
            for s, e in zip(start, end)
        ]


class ARXX5MotionZenohBridge(Node):
    """
    ROS2 node that exposes ARX_X5 state and motion commands through Zenoh.
    """

    def __init__(
        self,
        request_topic,
        state_topic,
        status_topic,
        robot_status_topic,
        robot_cmd_topic,
        state_publish_hz,
        default_steps,
        default_sleep_seconds,
        default_joint_step_size,
        max_steps,
        zenoh_endpoint,
        zenoh_standalone_discovery,
        zenoh_standalone_listen,
    ):
        super().__init__("arx_x5_motion_zenoh_bridge")

        self.request_topic = request_topic
        self.state_topic = state_topic
        self.status_topic = status_topic
        self.default_steps = int(default_steps)
        self.default_sleep_seconds = float(default_sleep_seconds)
        self.default_joint_step_size = float(default_joint_step_size)
        self.max_steps = int(max_steps)

        self._state_lock = threading.Lock()
        self._latest_robot_status = None
        self._latest_state_received_at = None
        self._last_state_publish_at = 0.0
        self._state_publish_interval = 0.0
        if float(state_publish_hz) > 0.0:
            self._state_publish_interval = 1.0 / float(state_publish_hz)

        self._stop_event = threading.Event()
        self._cancel_motion_event = threading.Event()
        self._command_queue = Queue()
        self._worker_thread = threading.Thread(target=self._command_worker, daemon=True)

        self.create_subscription(
            RobotStatus,
            robot_status_topic,
            self._robot_status_callback,
            10,
        )
        self.robot_cmd_publisher = self.create_publisher(RobotCmd, robot_cmd_topic, 10)
        self.get_logger().info(
            f"Subscribed to ROS2 {robot_status_topic} and publishing to {robot_cmd_topic}"
        )

        self.zenoh_session = open_zenoh_session(
            endpoint=zenoh_endpoint,
            standalone_discovery=zenoh_standalone_discovery,
            standalone_listen=zenoh_standalone_listen,
        )
        self._state_pub = self.zenoh_session.declare_publisher(state_topic)
        self._status_pub = self.zenoh_session.declare_publisher(status_topic)
        self._subscriber = self.zenoh_session.declare_subscriber(request_topic, self._on_zenoh_request)
        self.get_logger().info(
            f"Listening on Zenoh {request_topic}; publishing state={state_topic}, status={status_topic}"
        )

        self._worker_thread.start()

    def _robot_status_callback(self, msg):
        payload = {
            "header": {
                "stamp": {
                    "sec": int(msg.header.stamp.sec),
                    "nanosec": int(msg.header.stamp.nanosec),
                },
                "frame_id": str(msg.header.frame_id),
            },
            "end_pos": list(msg.end_pos),
            "joint_pos": list(msg.joint_pos),
            "joint_vel": list(msg.joint_vel),
            "joint_cur": list(msg.joint_cur),
            "received_at": time.time(),
        }
        with self._state_lock:
            self._latest_robot_status = payload
            self._latest_state_received_at = payload["received_at"]

        self._publish_state_if_due(payload)

    def _publish_state_if_due(self, payload):
        if self._state_publish_interval <= 0.0:
            return

        now = time.time()
        if now - self._last_state_publish_at < self._state_publish_interval:
            return

        self._last_state_publish_at = now
        self._put_json(self._state_pub, payload, "state")

    def _on_zenoh_request(self, sample):
        try:
            payload = sample.payload.to_bytes().decode("utf-8")
            request = json.loads(payload)
        except Exception as e:
            self.get_logger().error(f"Failed to decode Zenoh motion request: {e}")
            return

        action = str(request.get("action", "")).strip().lower()
        if action == "stop":
            self._cancel_motion_event.set()
            self._clear_pending_requests()
            self._publish_status("stopping", request)
            return

        self._command_queue.put(request)
        self._publish_status("queued", request)
        self.get_logger().info(
            f"Queued Zenoh motion request (queue_size={self._command_queue.qsize()}): {request}"
        )

    def _clear_pending_requests(self):
        while True:
            try:
                self._command_queue.get_nowait()
                self._command_queue.task_done()
            except Empty:
                return

    def _command_worker(self):
        while not self._stop_event.is_set():
            try:
                request = self._command_queue.get(timeout=0.2)
            except Empty:
                continue
            except Exception as e:
                self.get_logger().error(f"Command worker queue failure: {e}")
                continue

            try:
                self._cancel_motion_event.clear()
                self._execute_request(request)
            except Exception as e:
                self.get_logger().error(f"Unexpected motion bridge error: {e}")
                self._publish_status("failed", request, error=str(e))
            finally:
                self._command_queue.task_done()

    def _execute_request(self, request):
        action = str(request.get("action", "")).strip().lower()
        self._publish_status("running", request)

        if action == "publish_end_pose":
            pose = _as_float_list(
                request.get("end_pos", request.get("pose")),
                name="end_pos",
            )
            gripper = self._required_gripper(request)
            self._publish_end_pose(pose, gripper)
        elif action == "move_end_pose":
            target_pose = _as_float_list(
                request.get("target_pose", request.get("end_pos")),
                name="target_pose",
            )
            current_pose = request.get("current_pose")
            if current_pose is None:
                current_pose = self._current_end_pose()
            else:
                current_pose = _as_float_list(current_pose, name="current_pose")
            gripper = self._required_gripper(request)
            steps = self._steps_from_request(request)
            sleep_seconds = self._sleep_from_request(request)
            self._move_end_pose(current_pose, target_pose, gripper, steps, sleep_seconds)
        elif action == "publish_joints":
            joints = _as_float_list(
                request.get("joint_pos", request.get("joints")),
                name="joint_pos",
            )
            gripper = self._required_gripper(request)
            self._publish_joints(joints, gripper)
        elif action == "move_joints":
            target_joints = _as_float_list(
                request.get("target_joints", request.get("joint_pos")),
                name="target_joints",
            )
            current_joints = request.get("current_joints")
            if current_joints is None:
                current_joints = self._current_joints()
            else:
                current_joints = _as_float_list(current_joints, name="current_joints")
            gripper = self._required_gripper(request)
            sleep_seconds = self._sleep_from_request(request)
            step_size = self._joint_step_size_from_request(request)
            self._move_joints(current_joints, target_joints, gripper, step_size, sleep_seconds)
        elif action == "raw_robot_cmd":
            self._publish_raw_robot_cmd(request)
        else:
            self._publish_status("rejected", request, error=f"Unsupported action: {action}")
            return

        if self._cancel_motion_event.is_set():
            self._publish_status("stopped", request)
        else:
            self._publish_status("completed", request)

    def _required_gripper(self, request):
        if "gripper" not in request:
            raise ValueError("gripper is required for motion requests")
        try:
            return float(request["gripper"])
        except (TypeError, ValueError) as e:
            raise ValueError("gripper must be numeric") from e

    def _steps_from_request(self, request):
        steps = int(request.get("steps", self.default_steps))
        return max(1, min(steps, self.max_steps))

    def _sleep_from_request(self, request):
        value = float(request.get("sleep_seconds", request.get("sleep_s", self.default_sleep_seconds)))
        return max(0.0, value)

    def _joint_step_size_from_request(self, request):
        value = float(request.get("step_size", self.default_joint_step_size))
        if value <= 0.0:
            raise ValueError("step_size must be positive")
        return value

    def _current_robot_status(self):
        with self._state_lock:
            robot_status = self._latest_robot_status
            received_at = self._latest_state_received_at

        if robot_status is None:
            raise RuntimeError("No ARX_X5 robot state received yet")

        if received_at is not None:
            age = max(0.0, time.time() - received_at)
            self.get_logger().info(f"Using robot state captured {age:.3f}s ago")

        return robot_status

    def _current_end_pose(self):
        robot_status = self._current_robot_status()
        return _as_float_list(robot_status.get("end_pos"), name="current end_pos")

    def _current_joints(self):
        robot_status = self._current_robot_status()
        return _as_float_list(robot_status.get("joint_pos"), name="current joint_pos")

    def _publish_end_pose(self, pose, gripper):
        msg = RobotCmd()
        msg.mode = END_CONTROL_MODE
        msg.end_pos = list(pose[:6])
        msg.joint_pos = [0.0] * 6
        msg.gripper = float(gripper)
        self.robot_cmd_publisher.publish(msg)

    def _publish_joints(self, joints, gripper):
        msg = RobotCmd()
        msg.mode = POSITION_CONTROL_MODE
        msg.joint_pos = list(joints[:6])
        msg.gripper = float(gripper)
        self.robot_cmd_publisher.publish(msg)

    def _move_end_pose(self, current_pose, target_pose, gripper, steps, sleep_seconds):
        self.get_logger().info(
            f"Moving end pose with steps={steps}, sleep_seconds={sleep_seconds}, gripper={gripper}"
        )
        for pose in _linspace(current_pose, target_pose, steps):
            if self._should_cancel_motion():
                return
            self._publish_end_pose(pose, gripper)
            if self._cancel_motion_event.wait(timeout=sleep_seconds):
                return
        self._publish_end_pose(target_pose, gripper)

    def _move_joints(self, current_joints, target_joints, gripper, step_size, sleep_seconds):
        max_diff = max(abs(float(end) - float(start)) for start, end in zip(current_joints, target_joints))
        steps = max(1, min(int((max_diff / step_size) + 0.999999), self.max_steps))
        self.get_logger().info(
            f"Moving joints with steps={steps}, step_size={step_size}, "
            f"sleep_seconds={sleep_seconds}, gripper={gripper}"
        )
        for joints in _linspace(current_joints, target_joints, steps):
            if self._should_cancel_motion():
                return
            self._publish_joints(joints, gripper)
            if self._cancel_motion_event.wait(timeout=sleep_seconds):
                return
        self._publish_joints(target_joints, gripper)

    def _publish_raw_robot_cmd(self, request):
        mode = int(request.get("mode"))
        msg = RobotCmd()
        msg.mode = mode
        if "end_pos" in request:
            msg.end_pos = _as_float_list(request["end_pos"], name="end_pos")
        if "joint_pos" in request:
            msg.joint_pos = _as_float_list(request["joint_pos"], name="joint_pos")
        if "gripper" in request:
            msg.gripper = float(request["gripper"])
        self.robot_cmd_publisher.publish(msg)

    def _should_cancel_motion(self):
        return self._stop_event.is_set() or self._cancel_motion_event.is_set()

    def _put_json(self, publisher, payload, label):
        try:
            publisher.put(ZBytes(json.dumps(payload)))
        except Exception as e:
            self.get_logger().warning(f"Failed to publish Zenoh {label}: {e}")

    def _publish_status(self, status, request, **extra):
        payload = {
            "status": status,
            "request": request,
            "queue_size": self._command_queue.qsize(),
            "timestamp": time.time(),
        }
        payload.update(extra)
        self.get_logger().info(f"ARXX5 motion bridge status: {payload}")
        self._put_json(self._status_pub, payload, "status")

    def destroy_node(self):
        self._stop_event.set()
        self._cancel_motion_event.set()
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5)

        if getattr(self, "_subscriber", None) is not None:
            self._subscriber.undeclare()

        if getattr(self, "zenoh_session", None) is not None:
            self.zenoh_session.close()

        super().destroy_node()


def parse_args():
    parser = argparse.ArgumentParser(description="Bridge ARX_X5 motion/state between Zenoh and ROS2")
    parser.add_argument("--request-topic", default="arx_x5/motion/request")
    parser.add_argument("--state-topic", default="arx_x5/state")
    parser.add_argument("--status-topic", default="arx_x5/motion/status")
    parser.add_argument("--robot-status-topic", default="arm_status")
    parser.add_argument("--robot-cmd-topic", default="arm_cmd")
    parser.add_argument("--state-publish-hz", type=float, default=20.0)
    parser.add_argument("--default-steps", type=int, default=100)
    parser.add_argument("--default-sleep-seconds", type=float, default=0.03)
    parser.add_argument("--default-joint-step-size", type=float, default=0.02)
    parser.add_argument("--max-steps", type=int, default=1000)
    parser.add_argument(
        "--zenoh-endpoint",
        default="tcp/127.0.0.1:7447",
        help="Client connect target when not using --standalone-discovery.",
    )
    parser.add_argument(
        "--standalone-discovery",
        action="store_true",
        help="Listen on TCP only and disable multicast scouting.",
    )
    parser.add_argument(
        "--zenoh-standalone-listen",
        default="tcp/127.0.0.1:7447",
        metavar="ENDPOINT",
        help="Only with --standalone-discovery: TCP listen endpoint for Zenoh clients.",
    )
    return parser.parse_args()


def main(args=None):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    cli_args = parse_args()

    rclpy.init(args=args)
    node = ARXX5MotionZenohBridge(
        request_topic=cli_args.request_topic,
        state_topic=cli_args.state_topic,
        status_topic=cli_args.status_topic,
        robot_status_topic=cli_args.robot_status_topic,
        robot_cmd_topic=cli_args.robot_cmd_topic,
        state_publish_hz=cli_args.state_publish_hz,
        default_steps=cli_args.default_steps,
        default_sleep_seconds=cli_args.default_sleep_seconds,
        default_joint_step_size=cli_args.default_joint_step_size,
        max_steps=cli_args.max_steps,
        zenoh_endpoint=cli_args.zenoh_endpoint,
        zenoh_standalone_discovery=cli_args.standalone_discovery,
        zenoh_standalone_listen=cli_args.zenoh_standalone_listen,
    )

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
