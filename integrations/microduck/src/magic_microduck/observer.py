"""Render actual simulator joint states as a follow view and a head camera."""

import argparse
import os
import time

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rcl_interfaces.srv import GetParameters
from sensor_msgs.msg import Image
from std_msgs.msg import Float64MultiArray

from microduck_sim.camera_node import pick_gl_backend, _stamp


class Observer(Node):
    def __init__(self, scene, rate, head=True):
        super().__init__("magic_microduck_observer")
        # Read the actual scene, including optional balls, before making a visual replica.
        client = self.create_client(GetParameters, "/microduck_sim/get_parameters")
        if not client.wait_for_service(timeout_sec=25):
            raise RuntimeError("Simulator parameters unavailable; start the simulator first")
        request = GetParameters.Request(names=["scene", "microduck_rl_path", "add_ball", "ball_x", "ball_y"])
        future = client.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=8)
        if not future.done() or len(future.result().values) != 5:
            raise RuntimeError("Cannot read the simulator scene parameters")
        values = future.result().values
        scene, model_root = values[0].string_value, values[1].string_value
        add_ball, ball_xy = values[2].bool_value, (values[3].double_value, values[4].double_value)
        self.destroy_client(client)
        backend = pick_gl_backend()
        if backend is None:
            raise RuntimeError("No usable MuJoCo rendering backend")
        os.environ["MUJOCO_GL"] = backend
        import mujoco
        from microduck_sim.engine import load_scene_spec
        from microduck_sim.urdf import resolve_scene

        self.mj = mujoco
        self.with_head = head
        self.model = load_scene_spec(resolve_scene(scene, model_root), add_ball, ball_xy).compile()
        self.model.vis.map.znear = 0.01 / self.model.stat.extent
        self.model.vis.map.zfar = 20 / self.model.stat.extent
        # Software EGL: avoid multisample and shadow-map passes on every live frame.
        self.model.vis.quality.offsamples = 0
        self.data = mujoco.MjData(self.model)
        self.renderer = mujoco.Renderer(self.model, 360, 640)
        self.renderer.scene.flags[mujoco.mjtRndFlag.mjRND_SHADOW] = False
        self.renderer.scene.flags[mujoco.mjtRndFlag.mjRND_REFLECTION] = False
        self.follow = mujoco.MjvCamera()
        self.follow.type = mujoco.mjtCamera.mjCAMERA_FREE
        self.follow.distance, self.follow.azimuth, self.follow.elevation = 0.9, 90, -35
        self.walls = set()
        for i in range(self.model.ngeom):
            name = mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_GEOM, i) or ""
            material_id = self.model.geom_matid[i]
            material = (
                mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_MATERIAL, material_id)
                if material_id >= 0
                else ""
            ) or ""
            if "wall" in name or material.startswith("wall_"):
                self.walls.add(i)
        self.latest = None
        self.rendered = None
        self.head_pub = self.create_publisher(Image, "/camera/image_raw", qos_profile_sensor_data)
        self.follow_pub = self.create_publisher(
            Image, "/magic_microduck/view/image_raw", qos_profile_sensor_data
        )
        self.create_subscription(Float64MultiArray, "/microduck/sim_qpos", self.receive, 1)
        self.create_timer(1 / rate, self.render)
        self.get_logger().info(f"Live observer: {scene}, 640x360, {rate} Hz, {backend}")

    def receive(self, msg):
        if len(msg.data) != self.model.nq + 1:
            self.get_logger().error(
                "Scene mismatch: observer and simulator must use identical models", throttle_duration_sec=5
            )
            return
        self.latest = (np.asarray(msg.data), time.monotonic())

    def publish(self, publisher, rgb, stamp, frame_id):
        msg = Image()
        msg.header.stamp, msg.header.frame_id = _stamp(stamp), frame_id
        msg.height, msg.width = rgb.shape[:2]
        msg.encoding, msg.step, msg.data = "rgb8", rgb.shape[1] * 3, rgb.tobytes()
        publisher.publish(msg)

    def render(self):
        if self.latest is None or time.monotonic() - self.latest[1] > 2:
            return
        values, _ = self.latest
        if values[0] == self.rendered:
            return
        self.data.qpos[:] = values[1:]
        self.mj.mj_forward(self.model, self.data)
        if self.with_head:
            self.renderer.update_scene(self.data, camera="head_camera")
            self.publish(self.head_pub, self.renderer.render(), values[0], "head_camera_optical_frame")
        # Cutaway walls only affect this observer replica, never physics or the head camera.
        self.follow.lookat[:] = self.data.qpos[:3] + [0, 0, 0.08]
        self.renderer.update_scene(self.data, camera=self.follow)
        for geom in self.renderer.scene.geoms[: self.renderer.scene.ngeom]:
            if geom.objtype == self.mj.mjtObj.mjOBJ_GEOM and geom.objid in self.walls:
                geom.rgba[3] = 0.08
        self.publish(self.follow_pub, self.renderer.render(), values[0], "magic_follow_view")
        self.rendered = values[0]

    def destroy_node(self):
        self.renderer.close()
        super().destroy_node()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", choices=("flat", "apartment"), default="apartment")
    parser.add_argument("--fps", type=float, default=6)
    parser.add_argument("--no-head", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.fps <= 15:
        parser.error("fps must be between 1 and 15")
    rclpy.init()
    node = Observer(args.scene, args.fps, not args.no_head)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
