"""Publish a validated mission JSON file for deterministic baseline tests."""

from __future__ import annotations

import os
import time

from ament_index_python.packages import get_package_share_directory
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from .mission_models import MissionPlan


class MissionFileNode(Node):
    def __init__(self) -> None:
        super().__init__("mission_file")
        default_path = os.path.join(
            get_package_share_directory("hazard_nav"),
            "missions",
            "safe_route.json",
        )
        self.declare_parameter("mission_file", default_path)
        self.publisher = self.create_publisher(String, "/hazard/mission_plan", 10)
        self.published = False
        self.timer = self.create_timer(0.25, self._publish_once)

    def _publish_once(self) -> None:
        if self.publisher.get_subscription_count() == 0:
            return
        self.timer.cancel()
        path = str(self.get_parameter("mission_file").value)
        with open(path, "r", encoding="utf-8") as handle:
            plan = MissionPlan.from_json(handle.read())
        message = String()
        message.data = plan.to_json()
        self.publisher.publish(message)
        self.published = True
        self.get_logger().info(
            f"published mission '{plan.mission_name}' from {path}"
        )


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = MissionFileNode()
    try:
        discovery_deadline = time.monotonic() + 5.0
        while not node.published and time.monotonic() < discovery_deadline:
            rclpy.spin_once(node, timeout_sec=0.25)
        if not node.published:
            raise RuntimeError("no mission-plan subscriber discovered within 5 seconds")

        flush_deadline = time.monotonic() + 0.75
        while time.monotonic() < flush_deadline:
            rclpy.spin_once(node, timeout_sec=0.10)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()

