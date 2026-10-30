"""Interactive text operator station for development and demonstrations."""

from __future__ import annotations

import threading

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class OperatorConsoleNode(Node):
    def __init__(self) -> None:
        super().__init__("operator_console")
        self.publisher = self.create_publisher(String, "/hazard/command_text", 10)
        self._thread = threading.Thread(target=self._input_loop, daemon=True)
        self._thread.start()
        self.get_logger().info("type a mission and press Enter")

    def _input_loop(self) -> None:
        while rclpy.ok():
            try:
                command = input("hazard-operator> ").strip()
            except EOFError:
                return
            if not command:
                continue
            message = String()
            message.data = command
            self.publisher.publish(message)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = OperatorConsoleNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()

