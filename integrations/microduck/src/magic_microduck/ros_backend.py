"""ROS implementation. Imported only by the Microduck Python 3.12 process."""

import base64
import io
import math
import threading
import time
from collections import deque
from pathlib import Path
from uuid import uuid4

import numpy as np
import yaml
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import Twist
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry
from PIL import Image as PILImage
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_msgs.msg import Float64MultiArray, String
from std_srvs.srv import Trigger

from .contracts import ControlError

LOOK = {
    "left": [0, 0, 0.5, 0],
    "right": [0, 0, -0.5, 0],
    "up": [0, -0.35, 0, 0],
    "down": [0, 0.35, 0, 0],
    "center": [0, 0, 0, 0],
}


def yaw(q):
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


class RosBackend(Node):
    def __init__(self, places_file, image_dir):
        super().__init__("magic_microduck_bridge")
        self.places_file, self.image_dir = Path(places_file), Path(image_dir)
        self.image_dir.mkdir(parents=True, exist_ok=True)
        self.state_lock = threading.RLock()
        self.jpeg_lock = threading.Lock()
        self.jpeg_cache = {}
        self.latest, self.received = {}, {}
        self.transitions = deque(maxlen=100)
        self.cb = ReentrantCallbackGroup()
        for topic, typ, key, qos in [
            ("/odom", Odometry, "odom", 10),
            ("/microduck/policy_state", String, "policy", 10),
            ("/microduck/sim_qpos", Float64MultiArray, "qpos", 10),
            ("/camera/image_raw", Image, "image", qos_profile_sensor_data),
            ("/magic_microduck/view/image_raw", Image, "follow_image", qos_profile_sensor_data),
        ]:
            self.create_subscription(
                typ, topic, lambda msg, k=key: self._receive(k, msg), qos, callback_group=self.cb
            )
        self.velocity = self.create_publisher(Twist, "/cmd_vel", 10)
        self.head = self.create_publisher(Float64MultiArray, "/microduck/head_cmd", 10)
        self.nav = ActionClient(self, NavigateToPose, "navigate_to_pose", callback_group=self.cb)
        self._trigger_clients = {}
        self._nav_handle = self._nav_pending = self._nav_result = None
        self._nav_abandon = threading.Event()
        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self)
        self.thread = threading.Thread(target=self._executor.spin, daemon=True)
        self.thread.start()

    def _receive(self, key, msg):
        with self.state_lock:
            now = time.monotonic()
            if key == "policy" and (key not in self.latest or self.latest[key].data != msg.data):
                self.transitions.append((now, msg.data))
            self.latest[key], self.received[key] = msg, now

    def fresh(self, key, max_age=2):
        with self.state_lock:
            if key not in self.latest or time.monotonic() - self.received[key] > max_age:
                raise ControlError(
                    f"No fresh {key}; is the simulator running?", "stale_observation", "UNKNOWN"
                )
            return self.latest[key]

    def pose(self):
        msg = self.fresh("odom")
        p = msg.pose.pose
        return p.position.x, p.position.y, yaw(p.orientation)

    def places(self):
        if not self.places_file.exists():
            return {}
        return (yaml.safe_load(self.places_file.read_text()) or {}).get("places", {})

    def state(self):
        # Never hold the observation lock while calling DDS or reading the filesystem.
        with self.state_lock:
            latest, received = dict(self.latest), dict(self.received)
        ages = {k: round(time.monotonic() - v, 3) for k, v in received.items()}
        result = {
            "ready": ages.get("odom", 99) < 2 and ages.get("policy", 99) < 2,
            "ages_seconds": ages,
            "places": self.places(),
            "frame": "odom (map mode: map=odom)",
            "navigation_available": self.nav.server_is_ready(),
        }
        if ages.get("odom", 99) < 2:
            pose = latest["odom"].pose.pose
            result["pose"] = dict(
                x=pose.position.x, y=pose.position.y, yaw_degrees=math.degrees(yaw(pose.orientation))
            )
        if "policy" in latest:
            result["policy_state"] = latest["policy"].data
        if ages.get("qpos", 99) < 2:
            result["trunk_z_m"] = float(latest["qpos"].data[3])
        return result

    def drive(self, vx=0.0, wz=0.0):
        msg = Twist()
        msg.linear.x, msg.angular.z = float(vx), float(wz)
        self.velocity.publish(msg)

    def zero(self):
        self.drive()

    def stopped(self, timeout=3):
        """Observe negligible translation and yaw after zero commands; no hardware guarantee."""
        end, stable, last = time.monotonic() + timeout, None, self.pose()
        while time.monotonic() < end:
            self.zero()
            time.sleep(0.1)
            cur = self.pose()
            quiet = (
                math.hypot(cur[0] - last[0], cur[1] - last[1]) < 0.004 and abs(wrap(cur[2] - last[2])) < 0.04
            )
            stable = (stable or time.monotonic()) if quiet else None
            if stable and time.monotonic() - stable > 0.4:
                return
            last = cur
        raise ControlError("Stop not confirmed by odometry", "stop_unconfirmed", "UNKNOWN")

    def trigger(self, name):
        if name not in self._trigger_clients:
            self._trigger_clients[name] = self.create_client(Trigger, name, callback_group=self.cb)
        client = self._trigger_clients[name]
        if not client.wait_for_service(timeout_sec=2):
            raise ControlError(f"{name} unavailable", "service_unavailable")
        future = client.call_async(Trigger.Request())
        end = time.monotonic() + 5
        while not future.done() and time.monotonic() < end:
            time.sleep(0.02)
        if not future.done():
            raise ControlError("Service receipt missing", "receipt_timeout", "UNKNOWN")
        result = future.result()
        if not result.success:
            raise ControlError(result.message, "service_rejected")
        return result.message

    def request_stop(self):
        self._nav_abandon.set()
        if self._nav_handle is not None and self._nav_result is not None and not self._nav_result.done():
            self._nav_handle.cancel_goal_async()
        self.zero()

    def reset(self):
        self.request_stop()
        deadline = time.monotonic() + 6
        while (self._nav_pending is not None and not self._nav_pending.done()) or (
            self._nav_result is not None and not self._nav_result.done()
        ):
            if time.monotonic() >= deadline:
                raise ControlError(
                    "Cannot reset while Nav2 stop is unconfirmed", "cancel_unconfirmed", "UNKNOWN"
                )
            time.sleep(0.05)
        self.zero()
        self.trigger("/microduck/reset")
        self.head.publish(Float64MultiArray(data=[0.0] * 4))
        time.sleep(0.7)
        self.fresh("odom")

    def _motion_ready(self):
        self.pose()
        if self.fresh("policy").data not in ("walk", "stand"):
            raise ControlError("Stand up and finish the current skill first", "posture_blocked")

    def execute(self, skill, arguments, cancel):
        if cancel.is_set():
            raise ControlError("Cancelled before dispatch", "cancelled", "CANCELLED")
        if skill in ("walk", "turn"):
            return self.move(skill, arguments, cancel)
        if skill in ("navigate", "navigate_to"):
            if skill == "navigate":
                name = arguments["place"].strip().lower()
                places = self.places()
                if name not in places:
                    raise ControlError(f"Unknown place {name}; available: {list(places)}", "unknown_place")
                point = places[name]
                return self.navigate(float(point["x"]), float(point["y"]), cancel)
            return self.navigate(arguments["x"], arguments["y"], cancel)
        if skill == "do_skill":
            return self.skill(arguments["skill"])
        if skill == "look":
            self.fresh("policy")
            self.head.publish(Float64MultiArray(data=[float(x) for x in LOOK[arguments["direction"]]]))
            time.sleep(0.9)
            return {
                "head_command": arguments["direction"],
                "verification": "command sent; posture not measured",
            }
        if skill == "snapshot":
            return self.snapshot()
        raise ValueError(skill)

    def move(self, skill, args, cancel):
        self._motion_ready()
        start = last = self.pose()
        target = args["distance_m"] if skill == "walk" else math.radians(args["degrees"])
        progress = 0.0
        end = time.monotonic() + (abs(target) / (0.12 if skill == "walk" else 0.5)) + 8
        try:
            while progress < abs(target):
                if cancel.is_set():
                    self.stopped()
                    raise ControlError("Movement stopped and observed stationary", "cancelled", "CANCELLED")
                if time.monotonic() >= end:
                    self.stopped()
                    raise ControlError("Target not reached before deadline", "motion_timeout")
                if skill == "walk":
                    self.drive(vx=math.copysign(0.3, target))
                else:
                    self.drive(wz=math.copysign(1.0, target))
                time.sleep(0.05)
                pose = self.pose()
                if skill == "walk":
                    # Signed displacement along the initial heading, not a sideways drift.
                    along = (pose[0] - start[0]) * math.cos(start[2]) + (pose[1] - start[1]) * math.sin(
                        start[2]
                    )
                    progress = along * (1 if target >= 0 else -1)
                else:
                    progress += wrap(pose[2] - last[2]) * (1 if target >= 0 else -1)
                last = pose
            self.stopped()
            return {
                "target": target,
                "progress": progress,
                "pose": self.state()["pose"],
                "verification": "signed odometry progress and stopped",
            }
        finally:
            self.zero()

    def skill(self, name):
        self.pose()
        before = self.fresh("policy").data
        if name == "sit" and before == "sit" or name == "stand" and before in ("walk", "stand"):
            return {"policy_state": before, "already_in_state": True, "verification": "fresh policy state"}
        started = time.monotonic()
        service = f"/microduck/{name}" if name in ("sit", "stand") else f"/microduck/skill/{name}"
        self.trigger(service)
        expected = "rise" if name == "stand" else name
        seen = False
        while time.monotonic() - started < 20:
            state = self.fresh("policy").data
            with self.state_lock:
                seen |= any(t >= started and v == expected for t, v in self.transitions)
            settled = (
                state == "sit" and time.monotonic() - started >= 2.5
                if name == "sit"
                else state in ("walk", "stand")
            )
            if seen and settled:
                return {
                    "policy_state": state,
                    "observed_transition": expected,
                    "verification": "policy transition and completion/settling interval",
                }
            time.sleep(0.05)
        raise ControlError("Skill completion not observed", "skill_timeout", "UNKNOWN")

    def navigate(self, x, y, cancel):
        self._motion_ready()
        if not self.nav.wait_for_server(timeout_sec=2):
            raise ControlError("Nav2 unavailable; start nav mode", "navigation_unavailable")
        pose = self.pose()
        angle = math.atan2(y - pose[1], x - pose[0])
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = "map"
        goal.pose.pose.position.x, goal.pose.pose.position.y = float(x), float(y)
        goal.pose.pose.orientation.z, goal.pose.pose.orientation.w = math.sin(angle / 2), math.cos(angle / 2)
        self._nav_abandon.clear()
        future = self._nav_pending = self.nav.send_goal_async(goal)

        def cancel_late_acceptance(done):
            if self._nav_abandon.is_set():
                handle = done.result()
                if handle.accepted:
                    self._nav_handle = handle
                    self._nav_result = handle.get_result_async()
                    handle.cancel_goal_async()

        future.add_done_callback(cancel_late_acceptance)
        deadline = time.monotonic() + 8
        while not future.done() and time.monotonic() < deadline:
            time.sleep(0.02)
        if not future.done():
            self._nav_abandon.set()
            raise ControlError("Nav2 goal acceptance unknown", "navigation_receipt_missing", "UNKNOWN")
        handle = future.result()
        self._nav_handle = handle
        if not handle.accepted:
            raise ControlError("Nav2 rejected goal", "navigation_rejected")
        result = self._nav_result = handle.get_result_async()
        deadline, cancelling, cancel_deadline = time.monotonic() + 180, False, None
        try:
            while not result.done():
                if (cancel.is_set() or time.monotonic() > deadline) and not cancelling:
                    handle.cancel_goal_async()
                    cancelling, cancel_deadline = True, time.monotonic() + 6
                if cancelling:
                    self.zero()
                    if time.monotonic() > cancel_deadline:
                        raise ControlError("Nav2 cancellation unconfirmed", "cancel_unconfirmed", "UNKNOWN")
                time.sleep(0.05)
            status = result.result().status
            self.stopped()
            if status == GoalStatus.STATUS_CANCELED:
                raise ControlError("Nav2 cancelled and motion stopped", "cancelled", "CANCELLED")
            if status != GoalStatus.STATUS_SUCCEEDED:
                raise ControlError(f"Nav2 result status {status}", "navigation_failed")
            pose = self.pose()
            error = math.hypot(pose[0] - x, pose[1] - y)
            if error > 0.3:
                raise ControlError(f"Arrival position differs by {error:.3f} m", "arrival_not_verified")
            return {
                "target": {"x": x, "y": y},
                "error_m": error,
                "pose": self.state()["pose"],
                "verification": "Nav2 SUCCEEDED and fresh odometry within 0.3 m",
            }
        finally:
            if not result.done():
                handle.cancel_goal_async()
            self.zero()

    def frame(self, view="head"):
        if view not in ("head", "follow"):
            raise ValueError("view must be head or follow")
        key = "image" if view == "head" else "follow_image"
        with self.state_lock:
            msg = self.fresh(key, max_age=2)
            received = self.received[key]
        with self.jpeg_lock:
            cached = self.jpeg_cache.get(key)
            if cached and cached[0] == received:
                return cached[1]
            value = self._encode_frame(msg, received)
            self.jpeg_cache[key] = (received, value)
            return value

    @staticmethod
    def _encode_frame(msg, received):
        # Respect row stride, including potential row padding.
        rows = np.frombuffer(bytes(msg.data), np.uint8).reshape(msg.height, msg.step)
        if msg.encoding != "rgb8":
            raise ControlError(f"Unsupported encoding {msg.encoding}", "image_encoding")
        array = rows[:, : msg.width * 3].reshape(msg.height, msg.width, 3)
        image = PILImage.fromarray(array)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        return {
            "jpeg": buffer.getvalue(),
            "width": msg.width,
            "height": msg.height,
            "observed_at": time.time() - (time.monotonic() - received),
        }

    def snapshot(self):
        frame = self.frame("head")
        path = self.image_dir / f"{uuid4().hex}.jpg"
        path.write_bytes(frame["jpeg"])
        return {
            "path": str(path),
            "width": frame["width"],
            "height": frame["height"],
            "observed_at": frame["observed_at"],
            "verification": "fresh ROS camera frame saved",
        }

    def image(self):
        result = self.snapshot()
        result["base64"] = base64.b64encode(Path(result["path"]).read_bytes()).decode()
        return result

    def close(self):
        self.zero()
        self._executor.shutdown(timeout_sec=3)
        self.thread.join(timeout=3)
        self.destroy_node()
