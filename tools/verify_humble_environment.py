#!/usr/bin/env python3
"""Stage-based acceptance checks for the Ubuntu 22.04/Humble deployment."""
# ruff: noqa: D101, D102, D103

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import os
import platform
import shlex
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import json5


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "service" / "unitree_native_slam" / "autonomy_mid360"
CONFIG = ROOT / "config" / "unitree_go2_koala_nav_vision_no_arm.json5"
EXPECTED_MAP_SHA256 = "596e9376ad48bc688133f8864122fabda76305c09e82a1f5e567b7805067057c"
EXPECTED_PRIOR_SHA256 = "760ac228a30e26e92ecebbf1d1b9e637bd8e74f63aaa8eb6eb35944afa06ed3b"
SAFE_STAGES = ("host", "python", "dds", "realsense", "fastlio", "localization", "no-motion-nav", "audio")


@dataclass
class Check:
    stage: str
    name: str
    status: str
    detail: str
    metrics: dict[str, Any] = field(default_factory=dict)


class Report:
    def __init__(self) -> None:
        self.started_at = datetime.now().astimezone().isoformat()
        self.checks: list[Check] = []

    def add(self, stage: str, name: str, status: str, detail: str, **metrics: Any) -> None:
        self.checks.append(Check(stage, name, status, detail, metrics))
        marker = {"pass": "PASS", "fail": "FAIL", "blocked": "BLOCKED", "warn": "WARN"}[status]
        print(f"[{marker}] {stage}/{name}: {detail}")

    def write(self, output_dir: Path) -> tuple[Path, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = output_dir / f"humble_verification_{stamp}.json"
        markdown_path = output_dir / f"humble_verification_{stamp}.md"
        summary = {
            status: sum(check.status == status for check in self.checks)
            for status in ("pass", "fail", "blocked", "warn")
        }
        payload = {
            "started_at": self.started_at,
            "finished_at": datetime.now().astimezone().isoformat(),
            "summary": summary,
            "checks": [asdict(check) for check in self.checks],
        }
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        lines = [
            "# MAGIC_MINI Humble Verification",
            "",
            f"- Started: {payload['started_at']}",
            f"- Finished: {payload['finished_at']}",
        ]
        lines.append("- Summary: " + ", ".join(f"{key}={value}" for key, value in summary.items()))
        lines.extend(["", "| Stage | Check | Status | Detail |", "| --- | --- | --- | --- |"])
        for check in self.checks:
            detail = check.detail.replace("|", "\\|").replace("\n", " ")
            if check.metrics:
                detail += "; " + json.dumps(check.metrics, ensure_ascii=False, sort_keys=True)
            lines.append(f"| {check.stage} | {check.name} | {check.status.upper()} | {detail} |")
        markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return json_path, markdown_path


def load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


def run(command: list[str], timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def docker_command(*args: str) -> list[str]:
    return [*shlex.split(os.environ.get("DOCKER_CMD", "docker")), *args]


def container_name() -> str:
    return os.environ.get("MID360_CONTAINER", "magic_mini_mid360_nav")


def container_ready() -> tuple[bool, str]:
    try:
        result = run(docker_command("inspect", "-f", "{{.State.Running}}", container_name()), timeout=5)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    return result.returncode == 0 and result.stdout.strip() == "true", (result.stderr.strip() or result.stdout.strip())


def container_shell(command: str, timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
    setup = (
        "set -e; set +u; source /opt/ros/humble/setup.bash; "
        "source /opt/unitree_native_slam/install/setup.bash; set -u; "
        "export RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION:-rmw_cyclonedds_cpp}; "
    )
    return run(docker_command("exec", container_name(), "bash", "-lc", setup + command), timeout=timeout)


def container_python(code: str, *args: str, timeout: float = 30.0) -> dict[str, Any]:
    command = "python3 -c " + shlex.quote(code)
    if args:
        command += " " + " ".join(shlex.quote(arg) for arg in args)
    result = container_shell(command, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip()[-1200:])
    for line in reversed(result.stdout.splitlines()):
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    raise RuntimeError(f"probe returned no JSON: {result.stdout[-800:]}")


CLOUD_PROBE = r"""
import json, sys, time
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import PointCloud2

topic, wanted, timeout_s, time_field = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
messages, receipts = [], []
rclpy.init()
node = Node("magic_cloud_acceptance_probe")
def callback(msg):
    messages.append(msg)
    receipts.append(time.monotonic())
sub = node.create_subscription(PointCloud2, topic, callback, qos_profile_sensor_data)
deadline = time.monotonic() + timeout_s
while rclpy.ok() and len(messages) < wanted and time.monotonic() < deadline:
    rclpy.spin_once(node, timeout_sec=0.1)
if not messages:
    raise RuntimeError("no messages received")
msg = messages[-1]
field_map = {field.name: field for field in msg.fields}
formats = {1:"i1",2:"u1",3:"i2",4:"u2",5:"i4",6:"u4",7:"f4",8:"f8"}
span_ms = None
if time_field in field_map:
    field = field_map[time_field]
    dtype = np.dtype({"names":[time_field], "formats":["<"+formats[field.datatype]], "offsets":[field.offset], "itemsize":msg.point_step})
    values = np.ndarray((msg.height, msg.width), dtype=dtype, buffer=msg.data, strides=(msg.row_step,msg.point_step))[time_field]
    values = values[np.isfinite(values)]
    if values.size:
        span_ms = float((values.max()-values.min())/1e6)
rate = (len(receipts)-1)/(receipts[-1]-receipts[0]) if len(receipts)>1 and receipts[-1]>receipts[0] else 0.0
print(json.dumps({"frames":len(messages),"rate_hz":rate,"fields":[field.name for field in msg.fields],"offsets":{field.name:field.offset for field in msg.fields},"point_step":msg.point_step,"points":msg.width*msg.height,"span_ms":span_ms}))
node.destroy_node(); rclpy.shutdown()
"""


RATE_PROBE = r"""
import json, sys, time
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rosidl_runtime_py.utilities import get_message
topic, type_name, wanted, timeout_s = sys.argv[1], sys.argv[2], int(sys.argv[3]), float(sys.argv[4])
receipts=[]
rclpy.init(); node=Node("magic_rate_acceptance_probe")
sub=node.create_subscription(get_message(type_name),topic,lambda msg: receipts.append(time.monotonic()),qos_profile_sensor_data)
deadline=time.monotonic()+timeout_s
while rclpy.ok() and len(receipts)<wanted and time.monotonic()<deadline: rclpy.spin_once(node,timeout_sec=0.05)
rate=(len(receipts)-1)/(receipts[-1]-receipts[0]) if len(receipts)>1 and receipts[-1]>receipts[0] else 0.0
print(json.dumps({"messages":len(receipts),"rate_hz":rate}))
node.destroy_node(); rclpy.shutdown()
"""


ODOM_PROBE = r"""
import json, math, sys, time
import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
topic, duration = sys.argv[1], float(sys.argv[2])
samples=[]
rclpy.init(); node=Node("magic_odom_acceptance_probe")
def cb(msg):
    p,q=msg.pose.pose.position,msg.pose.pose.orientation
    yaw=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))
    samples.append((time.monotonic(),p.x,p.y,p.z,yaw))
sub=node.create_subscription(Odometry,topic,cb,20)
deadline=time.monotonic()+duration
while rclpy.ok() and time.monotonic()<deadline: rclpy.spin_once(node,timeout_sec=0.1)
if not samples: raise RuntimeError("no odometry received")
first=samples[0]
drifts=[math.dist((s[1],s[2],s[3]),(first[1],first[2],first[3])) for s in samples]
yaw_deltas=[abs(math.atan2(math.sin(s[4]-first[4]),math.cos(s[4]-first[4]))) for s in samples]
rate=(len(samples)-1)/(samples[-1][0]-samples[0][0]) if len(samples)>1 else 0.0
print(json.dumps({"samples":len(samples),"rate_hz":rate,"drift_m":max(drifts),"yaw_drift_deg":math.degrees(max(yaw_deltas)),"first_pose":[first[1],first[2],first[3],first[4]],"last_pose":[samples[-1][1],samples[-1][2],samples[-1][3],samples[-1][4]]}))
node.destroy_node(); rclpy.shutdown()
"""


LOCALIZATION_PROBE = r"""
import json, math, statistics, sys, time
import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import Float32
duration=float(sys.argv[1]); confidence=[]; poses=[]
rclpy.init(); node=Node("magic_localization_acceptance_probe")
node.create_subscription(Float32,"/localization_3d_confidence",lambda msg: confidence.append(float(msg.data)),5)
def pose_cb(msg):
    p,q=msg.pose.pose.position,msg.pose.pose.orientation
    yaw=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))
    poses.append((p.x,p.y,p.z,yaw))
node.create_subscription(Odometry,"/baselink2map",pose_cb,10)
deadline=time.monotonic()+duration
while rclpy.ok() and time.monotonic()<deadline: rclpy.spin_once(node,timeout_sec=0.1)
if not confidence or not poses: raise RuntimeError("confidence or baselink2map is missing")
position_jumps=[math.dist(poses[i][:3],poses[i-1][:3]) for i in range(1,len(poses))]
yaw_jumps=[abs(math.atan2(math.sin(poses[i][3]-poses[i-1][3]),math.cos(poses[i][3]-poses[i-1][3]))) for i in range(1,len(poses))]
origin_distance=math.hypot(poses[0][0],poses[0][1])
print(json.dumps({"confidence_samples":len(confidence),"confidence_median":statistics.median(confidence),"confidence_min":min(confidence),"pose_samples":len(poses),"max_position_jump_m":max(position_jumps,default=0.0),"max_yaw_jump_deg":math.degrees(max(yaw_jumps,default=0.0)),"origin_distance_m":origin_distance,"origin_yaw_deg":math.degrees(poses[0][3])}))
node.destroy_node(); rclpy.shutdown()
"""


CMD_VEL_PROBE = r"""
import json, math, sys, time
import rclpy
from geometry_msgs.msg import TwistStamped
from rclpy.node import Node
duration=float(sys.argv[1]); samples=[]
rclpy.init(); node=Node("magic_cmd_vel_acceptance_probe")
node.create_subscription(TwistStamped,"/cmd_vel",lambda msg: samples.append((msg.twist.linear.x,msg.twist.linear.y,msg.twist.angular.z)),10)
deadline=time.monotonic()+duration
while rclpy.ok() and time.monotonic()<deadline: rclpy.spin_once(node,timeout_sec=0.1)
if not samples: raise RuntimeError("no /cmd_vel received")
print(json.dumps({"samples":len(samples),"max_planar_mps":max(math.hypot(x,y) for x,y,_ in samples),"max_yaw_deg_s":math.degrees(max(abs(yaw) for _,_,yaw in samples))}))
node.destroy_node(); rclpy.shutdown()
"""


def check_host(report: Report) -> None:
    stage = "host"
    os_release = {}
    for line in Path("/etc/os-release").read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            os_release[key] = value.strip('"')
    host_ok = (
        os_release.get("ID") == "ubuntu" and os_release.get("VERSION_ID") == "22.04" and platform.machine() == "aarch64"
    )
    report.add(
        stage,
        "platform",
        "pass" if host_ok else "fail",
        os_release.get("PRETTY_NAME", "unknown"),
        architecture=platform.machine(),
    )
    report.add(
        stage,
        "ros_humble",
        "pass" if Path("/opt/ros/humble/setup.bash").is_file() else "fail",
        "/opt/ros/humble/setup.bash",
    )

    interface = os.environ.get("CYCLONEDDS_INTERFACE", os.environ.get("UNITREE_ETHERNET", "eno1"))
    ip_result = run(["ip", "-j", "addr", "show", "dev", interface], timeout=5)
    report.add(
        stage,
        "dds_interface",
        "pass" if ip_result.returncode == 0 else "fail",
        interface,
        output=ip_result.stdout.strip()[-500:],
    )

    cyclone_home = Path(os.environ.get("CYCLONEDDS_HOME", "/home/nvidia/cyclonedds/install"))
    libraries = list((cyclone_home / "lib").glob("libddsc.so*")) if (cyclone_home / "lib").is_dir() else []
    report.add(
        stage,
        "cyclonedds",
        "pass" if libraries else "fail",
        str(cyclone_home),
        libraries=[str(path) for path in libraries],
    )

    config = json5.loads(CONFIG.read_text(encoding="utf-8"))
    labels = {action.get("llm_label") for action in config["agent_actions"]}
    background_types = {entry["type"] for entry in config.get("backgrounds", [])}
    no_arm = labels == {"speak", "navigate_location"} and "ARXX5YoloGraspExecutor" not in background_types
    report.add(
        stage,
        "no_arm_config",
        "pass" if no_arm else "fail",
        f"actions={sorted(labels)}; backgrounds={sorted(background_types)}",
    )

    maps_dir = Path(os.environ.get("MID360_MAPS_DIR", str(ROOT / "service" / "unitree_native_slam")))
    map_path = maps_dir / "aaa-fuck-magic-company_20260630_100336.pcd"
    prior_path = SERVICE / "prior_graphs" / "my_prior_graph_final.vgh"
    for name, path, expected in (
        ("map", map_path, EXPECTED_MAP_SHA256),
        ("prior_graph", prior_path, EXPECTED_PRIOR_SHA256),
    ):
        if not path.is_file():
            report.add(stage, name, "fail", f"missing: {path}")
            continue
        actual = sha256(path)
        report.add(
            stage, name, "pass" if actual == expected else "fail", str(path), sha256=actual, bytes=path.stat().st_size
        )

    docker = run(docker_command("info"), timeout=8)
    report.add(
        stage,
        "docker_access",
        "pass" if docker.returncode == 0 else "blocked",
        (docker.stderr or docker.stdout).strip()[-500:] or "Docker accessible",
    )
    if docker.returncode == 0:
        image = os.environ.get("MID360_IMAGE", "magic-mini-mid360-nav:humble")
        image_result = run(docker_command("image", "inspect", image), timeout=8)
        report.add(stage, "navigation_image", "pass" if image_result.returncode == 0 else "blocked", image)


def check_python(report: Report) -> None:
    stage = "python"
    version_ok = sys.version_info[:2] == (3, 12)
    report.add(stage, "version", "pass" if version_ok else "fail", platform.python_version(), executable=sys.executable)
    for module in ("json5", "jsonschema", "numpy", "pydantic", "cyclonedds", "sherpa_onnx"):
        try:
            importlib.import_module(module)
            distribution = module.replace("_", "-")
            try:
                detail = importlib.metadata.version(distribution)
            except importlib.metadata.PackageNotFoundError:
                detail = "imported"
            report.add(stage, f"import_{module}", "pass", detail)
        except Exception as exc:
            report.add(stage, f"import_{module}", "fail", str(exc))

    realsense_path = Path(
        os.environ.get("REALSENSE_PYTHONPATH", str(ROOT / ".local/librealsense-2.57.7/lib/python3.12/site-packages"))
    )
    if realsense_path.is_dir() and str(realsense_path) not in sys.path:
        sys.path.insert(0, str(realsense_path))
    try:
        import pyrealsense2 as rs  # type: ignore

        count = len(list(rs.context().query_devices()))
        report.add(stage, "pyrealsense2", "pass", f"imported; {count} device(s)", path=str(realsense_path))
    except Exception as exc:
        report.add(stage, "pyrealsense2", "blocked", str(exc), path=str(realsense_path))


def check_dds(report: Report) -> None:
    stage = "dds"
    ready, detail = container_ready()
    if not ready:
        report.add(stage, "container", "blocked", detail or f"{container_name()} is not running")
        return
    report.add(stage, "container", "pass", container_name())

    probes = (
        ("raw_lidar", "/livox/lidar", "timestamp", {"x", "y", "z", "intensity", "tag", "line", "timestamp"}),
        ("adapted_lidar", "/unitree/slam_lidar/points", "time", {"x", "y", "z", "intensity", "ring", "time"}),
    )
    for name, topic, time_field, expected_fields in probes:
        try:
            metrics = container_python(CLOUD_PROBE, topic, "30", "8", time_field, timeout=15)
            fields_ok = expected_fields.issubset(metrics["fields"])
            rate_ok = 18.0 <= metrics["rate_hz"] <= 22.0
            span_ok = metrics["span_ms"] is not None and 45.0 <= metrics["span_ms"] <= 55.0
            passed = fields_ok and rate_ok and span_ok
            report.add(stage, name, "pass" if passed else "fail", topic, **metrics)
        except Exception as exc:
            report.add(stage, name, "blocked", str(exc))

    # FAST-LIO subscribes to the Go2 publisher directly. Relaying IMU in the
    # Python point converter measurably drops samples under load.
    for name, topic in (("fastlio_imu", "/livox/imu"),):
        try:
            metrics = container_python(RATE_PROBE, topic, "sensor_msgs/msg/Imu", "200", "5", timeout=10)
            passed = 180.0 <= metrics["rate_hz"] <= 220.0
            report.add(stage, name, "pass" if passed else "fail", topic, **metrics)
        except Exception as exc:
            report.add(stage, name, "blocked", str(exc))


def check_realsense(report: Report, frame_count: int) -> None:
    stage = "realsense"
    realsense_path = Path(
        os.environ.get("REALSENSE_PYTHONPATH", str(ROOT / ".local/librealsense-2.57.7/lib/python3.12/site-packages"))
    )
    if realsense_path.is_dir() and str(realsense_path) not in sys.path:
        sys.path.insert(0, str(realsense_path))
    try:
        import numpy as np
        import pyrealsense2 as rs  # type: ignore
    except Exception as exc:
        report.add(stage, "capture", "blocked", f"pyrealsense2 unavailable: {exc}")
        return

    expected_serial = os.environ.get("REALSENSE_SERIAL", "254843066143")
    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_device(expected_serial)
    config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 15)
    config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 15)
    align = rs.align(rs.stream.color)
    valid_frames = 0
    valid_depth = []
    started = None
    try:
        pipeline.start(config)
        for index in range(frame_count):
            frames = align.process(pipeline.wait_for_frames(5000))
            color = frames.get_color_frame()
            depth = frames.get_depth_frame()
            if not color or not depth:
                continue
            if started is None:
                started = time.monotonic()
            valid_frames += 1
            if index % 10 == 0:
                depth_array = np.asanyarray(depth.get_data())
                valid_depth.append(float(np.count_nonzero(depth_array) / depth_array.size))
        elapsed = max(0.001, time.monotonic() - (started or time.monotonic()))
        fps = max(0.0, (valid_frames - 1) / elapsed)
        depth_fraction = statistics.mean(valid_depth) if valid_depth else 0.0
        passed = valid_frames == frame_count and fps >= 12.0 and depth_fraction >= 0.30
        report.add(
            stage,
            "aligned_rgbd",
            "pass" if passed else "fail",
            f"serial={expected_serial}",
            requested_frames=frame_count,
            valid_frames=valid_frames,
            fps=fps,
            valid_depth_fraction=depth_fraction,
        )
    except Exception as exc:
        report.add(stage, "aligned_rgbd", "blocked", str(exc), serial=expected_serial)
    finally:
        try:
            pipeline.stop()
        except Exception:
            pass


def check_fastlio(report: Report, duration: float) -> None:
    stage = "fastlio"
    ready, detail = container_ready()
    if not ready:
        report.add(stage, "container", "blocked", detail)
        return
    try:
        metrics = container_python(ODOM_PROBE, "/Odometry_loc", str(duration), timeout=duration + 15)
        passed = metrics["rate_hz"] >= 18.0 and metrics["drift_m"] <= 0.10 and metrics["yaw_drift_deg"] <= 2.0
        report.add(
            stage, "stationary_drift", "pass" if passed else "fail", f"{duration:.0f}s stationary sample", **metrics
        )
    except Exception as exc:
        report.add(stage, "stationary_drift", "blocked", str(exc))


def check_localization(report: Report, duration: float) -> None:
    stage = "localization"
    ready, detail = container_ready()
    if not ready:
        report.add(stage, "container", "blocked", detail)
        return
    try:
        metrics = container_python(LOCALIZATION_PROBE, str(duration), timeout=duration + 15)
        passed = (
            metrics["confidence_median"] >= 0.85
            and metrics["confidence_min"] >= 0.80
            and metrics["max_position_jump_m"] <= 0.25
            and metrics["max_yaw_jump_deg"] <= 5.0
        )
        report.add(stage, "map_reuse", "pass" if passed else "fail", f"{duration:.0f}s localization sample", **metrics)
    except Exception as exc:
        report.add(stage, "map_reuse", "blocked", str(exc))


def check_no_motion_nav(report: Report, origin_confirmed: bool) -> None:
    stage = "no-motion-nav"
    ready, detail = container_ready()
    if not ready:
        report.add(stage, "container", "blocked", detail)
        return
    parameter = container_shell("ros2 param get /pathFollower is_real_robot", timeout=8)
    if parameter.returncode != 0:
        report.add(stage, "real_robot_gate", "blocked", (parameter.stderr or parameter.stdout).strip())
        return
    is_false = "false" in parameter.stdout.lower()
    report.add(stage, "real_robot_gate", "pass" if is_false else "fail", parameter.stdout.strip())
    if not is_false:
        report.add(
            stage, "planning", "blocked", "refusing no-motion test because pathFollower is_real_robot is not false"
        )
        return

    command = [
        "env",
        f"CONTAINER_NAME={container_name()}",
        "bash",
        str(SERVICE / "scripts" / "publish_goal.sh"),
        "--check-only",
        "0",
        "0",
        "0",
    ]
    result = run(command, timeout=45)
    report.add(
        stage,
        "guarded_readiness",
        "pass" if result.returncode == 0 else "fail",
        (result.stderr or result.stdout).strip()[-1000:],
    )
    if result.returncode != 0:
        report.add(stage, "planning", "blocked", "readiness failed; no planning goal was published")
        return
    if not origin_confirmed:
        report.add(
            stage,
            "planning",
            "warn",
            "readiness passed; rerun with --origin-confirmed after placing the robot at the original mapping origin",
        )
        return

    goal_command = [
        "env",
        f"CONTAINER_NAME={container_name()}",
        "bash",
        str(SERVICE / "scripts" / "publish_goal.sh"),
        "--force",
        "--wait",
        "20",
        "0.5",
        "0",
        "0",
    ]
    try:
        goal_result = run(goal_command, timeout=50)
        report.add(
            stage,
            "planning",
            "pass" if goal_result.returncode == 0 else "fail",
            (goal_result.stderr or goal_result.stdout).strip()[-1200:],
            goal_map=[0.5, 0.0, 0.0],
        )
        if goal_result.returncode == 0:
            metrics = container_python(CMD_VEL_PROBE, "5", timeout=12)
            within_limits = metrics["max_planar_mps"] <= 0.051 and metrics["max_yaw_deg_s"] <= 10.1
            report.add(
                stage,
                "simulated_command_limits",
                "pass" if within_limits else "fail",
                "pathFollower remains disconnected from Go2 sport commands",
                **metrics,
            )
    except Exception as exc:
        report.add(stage, "simulated_command_limits", "blocked", str(exc))
    finally:
        container_shell(
            "ros2 topic pub --once /far_reach_goal_status std_msgs/msg/Bool '{data: true}' >/dev/null",
            timeout=8,
        )


def check_audio(report: Report) -> None:
    stage = "audio"
    arecord = run(["arecord", "-l"], timeout=5)
    aplay = run(["aplay", "-l"], timeout=5)
    capture_card = os.environ.get("ASR_ALSA_CARD", "MINI")
    playback_device = os.environ.get("QWEN_TTS_ALSA_DEVICE", "plughw:CARD=UACDemoV10,DEV=0")
    playback_card = (
        playback_device.split("CARD=", 1)[1].split(",", 1)[0] if "CARD=" in playback_device else playback_device
    )
    capture_ok = arecord.returncode == 0 and capture_card.lower() in arecord.stdout.lower()
    playback_ok = aplay.returncode == 0 and playback_card.lower() in aplay.stdout.lower()
    report.add(
        stage, "capture_device", "pass" if capture_ok else "blocked", capture_card, devices=arecord.stdout[-1200:]
    )
    report.add(
        stage, "playback_device", "pass" if playback_ok else "blocked", playback_device, devices=aplay.stdout[-1200:]
    )
    if not capture_ok or not playback_ok:
        report.add(
            stage,
            "full_audio_chain",
            "blocked",
            "connect the configured USB microphone and speaker before KWS/ASR/TTS acceptance",
        )
        return
    report.add(
        stage,
        "full_audio_chain",
        "warn",
        "devices are present; run the supervised 5-attempt wake-word, ASR, TTS, and echo-suppression checklist",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", action="append", choices=SAFE_STAGES, help="check stage; may be repeated")
    parser.add_argument("--all-safe", action="store_true", help="run every non-moving stage")
    parser.add_argument("--duration", type=float, default=60.0, help="FAST-LIO/localization sample duration")
    parser.add_argument("--camera-frames", type=int, default=300)
    parser.add_argument(
        "--origin-confirmed",
        action="store_true",
        help="allow the non-moving 0.5 m planning test after the robot is placed at the original map origin",
    )
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".runtime" / "verification")
    parser.add_argument(
        "--real-nav-test", action="store_true", help="reserved for supervised low-speed motion acceptance"
    )
    parser.add_argument(
        "--confirm-motion", action="store_true", help="second acknowledgement required with --real-nav-test"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv()
    report = Report()
    stages = list(SAFE_STAGES if args.all_safe else (args.stage or ["host", "python"]))

    handlers = {
        "host": lambda: check_host(report),
        "python": lambda: check_python(report),
        "dds": lambda: check_dds(report),
        "realsense": lambda: check_realsense(report, args.camera_frames),
        "fastlio": lambda: check_fastlio(report, args.duration),
        "localization": lambda: check_localization(report, args.duration),
        "no-motion-nav": lambda: check_no_motion_nav(report, args.origin_confirmed),
        "audio": lambda: check_audio(report),
    }
    for stage in stages:
        try:
            handlers[stage]()
        except Exception as exc:
            report.add(stage, "unexpected_error", "fail", f"{type(exc).__name__}: {exc}")

    if args.real_nav_test:
        if not args.confirm_motion:
            report.add("real-nav", "motion_confirmation", "blocked", "--confirm-motion is required")
        else:
            report.add(
                "real-nav",
                "supervised_motion",
                "blocked",
                "automatic physical motion is not started by this tool; use the documented 0.05 m/s supervised procedure after all safe stages pass",
            )

    json_path, markdown_path = report.write(args.output_dir)
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")
    if any(check.status == "fail" for check in report.checks):
        return 1
    if any(check.status == "blocked" for check in report.checks):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
