#!/usr/bin/env python3
"""Bridge the Go2 Livox PointCloud2 layout into FAST-LIO's expected layout."""

from __future__ import annotations

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import PointCloud2, PointField

from .pointcloud_conversion import FASTLIO_FIELD_LAYOUT, FASTLIO_POINT_STEP, convert_livox_cloud


SENSOR_QOS = QoSProfile(
    history=HistoryPolicy.KEEP_LAST,
    depth=5,
    reliability=ReliabilityPolicy.BEST_EFFORT,
    durability=DurabilityPolicy.VOLATILE,
)


class LivoxPointcloudCompatBridge(Node):
    """Convert `/livox/lidar` fields and per-point time for stable FAST-LIO input."""

    def __init__(self) -> None:
        super().__init__("livox_pointcloud_compat_bridge")
        self.declare_parameter("input_topic", "/livox/lidar")
        self.declare_parameter("output_topic", "/unitree/slam_lidar/points")
        self.declare_parameter("log_every_n_frames", 100)

        input_topic = str(self.get_parameter("input_topic").value)
        output_topic = str(self.get_parameter("output_topic").value)
        self.log_every_n_frames = max(1, int(self.get_parameter("log_every_n_frames").value))
        self.frame_count = 0
        self.drop_count = 0

        self.publisher = self.create_publisher(PointCloud2, output_topic, SENSOR_QOS)
        self.subscription = self.create_subscription(
            PointCloud2,
            input_topic,
            self.cloud_callback,
            SENSOR_QOS,
        )
        self.get_logger().info(
            f"Livox compatibility bridge: {input_topic} -> {output_topic} "
            "(line->ring, absolute timestamp->relative nanoseconds). "
            "FAST-LIO must subscribe to the native /livox/imu directly."
        )

    def cloud_callback(self, msg: PointCloud2) -> None:
        """Convert and publish one Livox cloud, dropping malformed frames."""
        try:
            converted, span_ns = convert_livox_cloud(
                data=msg.data,
                fields=msg.fields,
                width=msg.width,
                height=msg.height,
                point_step=msg.point_step,
                row_step=msg.row_step,
                is_bigendian=msg.is_bigendian,
            )
        except (TypeError, ValueError) as exc:
            self.drop_count += 1
            self.get_logger().error(f"Dropping incompatible Livox cloud: {exc}", throttle_duration_sec=5.0)
            return

        output = PointCloud2()
        output.header = msg.header
        output.height = msg.height
        output.width = msg.width
        output.fields = [
            PointField(name=name, offset=offset, datatype=datatype, count=1)
            for name, offset, datatype in FASTLIO_FIELD_LAYOUT
        ]
        output.is_bigendian = False
        output.point_step = FASTLIO_POINT_STEP
        output.row_step = output.width * output.point_step
        output.data = converted
        output.is_dense = msg.is_dense
        self.publisher.publish(output)

        self.frame_count += 1
        if self.frame_count % self.log_every_n_frames == 0:
            self.get_logger().info(
                f"Converted {self.frame_count} frames; last frame {msg.width * msg.height} points, "
                f"span {span_ns / 1e6:.3f} ms, drops {self.drop_count}"
            )


def main(args=None) -> None:
    """Run the ROS 2 compatibility bridge."""
    rclpy.init(args=args)
    node = LivoxPointcloudCompatBridge()
    try:
        rclpy.spin(node)
    except (ExternalShutdownException, KeyboardInterrupt):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
