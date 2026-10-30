"""ROS 2 adapter around the deterministic mission engine."""

from __future__ import annotations

import json
import math

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String

from .mission_engine import EngineState, MissionEngine, MotionCommand, Pose2D, ScanFrame
from .mission_models import MissionPlan, MissionValidationError
from .scan_geometry import summarize_scan


def quaternion_to_yaw(x: float, y: float, z: float, w: float) -> float:
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(siny_cosp, cosy_cosp)


class MissionExecutorNode(Node):
    def __init__(self) -> None:
        super().__init__("mission_executor")
        self.declare_parameter("control_rate_hz", 20.0)
        self.declare_parameter("emergency_stop_m", 0.18)
        self.declare_parameter("junction_open_m", 1.15)

        self.engine = MissionEngine(
            emergency_stop_m=float(self.get_parameter("emergency_stop_m").value),
            junction_open_m=float(self.get_parameter("junction_open_m").value),
        )
        self.pose: Pose2D | None = None
        self.scan: ScanFrame | None = None
        self._last_status_payload = ""

        self.cmd_pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.status_pub = self.create_publisher(String, "/hazard/mission_status", 10)
        self.create_subscription(
            String, "/hazard/mission_plan", self._on_plan, 10
        )
        self.create_subscription(
            Odometry, "/odom", self._on_odom, qos_profile_sensor_data
        )
        self.create_subscription(
            LaserScan, "/scan", self._on_scan, qos_profile_sensor_data
        )

        rate = float(self.get_parameter("control_rate_hz").value)
        self.create_timer(1.0 / rate, self._control_tick)
        self.get_logger().info("mission executor ready")

    def _on_plan(self, message: String) -> None:
        try:
            plan = MissionPlan.from_json(message.data)
        except MissionValidationError as exc:
            self.get_logger().error(f"rejected mission: {exc}")
            self._publish_status(extra={"rejected": str(exc)})
            return

        if self.engine.state is EngineState.RUNNING:
            self.get_logger().warning("replacing an active mission with a new plan")
            self._publish_motion(MotionCommand())
        self.engine.load(plan)
        self.get_logger().info(
            f"accepted mission '{plan.mission_name}' with {len(plan.actions)} steps"
        )
        self._publish_status()

    def _on_odom(self, message: Odometry) -> None:
        position = message.pose.pose.position
        orientation = message.pose.pose.orientation
        self.pose = Pose2D(
            x=float(position.x),
            y=float(position.y),
            yaw=quaternion_to_yaw(
                orientation.x,
                orientation.y,
                orientation.z,
                orientation.w,
            ),
        )

    def _on_scan(self, message: LaserScan) -> None:
        try:
            self.scan = summarize_scan(
                message.ranges,
                float(message.angle_min),
                float(message.angle_increment),
                float(message.range_max),
            )
        except ValueError as exc:
            self.get_logger().error(f"invalid LaserScan: {exc}")
            self.scan = None

    def _control_tick(self) -> None:
        if self.pose is None or self.scan is None:
            self._publish_motion(MotionCommand())
            return

        now_s = self.get_clock().now().nanoseconds / 1_000_000_000.0
        command = self.engine.update(self.pose, self.scan, now_s)
        self._publish_motion(command)
        self._publish_status()

    def _publish_motion(self, command: MotionCommand) -> None:
        message = Twist()
        message.linear.x = float(command.linear_x)
        message.angular.z = float(command.angular_z)
        self.cmd_pub.publish(message)

    def _publish_status(self, extra: dict[str, str] | None = None) -> None:
        status = self.engine.status
        payload: dict[str, object] = {
            "state": status.state.value,
            "mission_name": status.mission_name,
            "step_index": status.step_index,
            "step_count": status.step_count,
            "detail": status.detail,
        }
        if extra:
            payload.update(extra)
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        if encoded == self._last_status_payload:
            return
        self._last_status_payload = encoded
        message = String()
        message.data = encoded
        self.status_pub.publish(message)
        self.get_logger().info(encoded)

    def stop_robot(self) -> None:
        self._publish_motion(MotionCommand())


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = MissionExecutorNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    except RuntimeError:
        if rclpy.ok():
            raise
    finally:
        if rclpy.ok():
            node.stop_robot()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()

