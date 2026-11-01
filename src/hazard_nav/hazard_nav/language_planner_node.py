"""ROS 2 node that turns natural-language commands into strict missions."""

from __future__ import annotations

import math
from typing import Any, Literal

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from pydantic import BaseModel, ConfigDict, Field

from .ai_gateway import create_ai_client, load_ai_settings
from .mission_models import MissionPlan, MissionValidationError


ActionName = Literal[
    "move_distance",
    "turn",
    "move_until_wall",
    "move_until_junction",
    "follow_wall",
    "stop",
]


class PlannedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ActionName = Field(description="One action from the supported action set")
    description: str = Field(description="Brief Chinese description of this action")
    distance_m: float | None = Field(
        default=None,
        ge=0.10,
        le=12.0,
        description="Travel distance for distance-based actions",
    )
    angle_deg: float | None = Field(
        default=None,
        ge=5.0,
        le=180.0,
        description="Turn angle from 5 to 180 degrees",
    )
    direction: Literal["left", "right"] | None = None
    clearance_m: float | None = Field(
        default=None,
        ge=0.25,
        le=1.50,
        description="Desired distance from a wall in metres",
    )
    side: Literal["left", "right", "any"] | None = Field(
        default=None, description="Wall side or junction side"
    )
    speed_mps: float | None = Field(
        default=None,
        ge=0.05,
        le=0.35,
        description="Linear speed from 0.05 to 0.35 metres per second",
    )
    angular_speed_rps: float | None = Field(
        default=None,
        ge=0.15,
        le=1.20,
        description="Angular speed from 0.15 to 1.20 radians per second",
    )
    max_duration_s: float = Field(
        default=30.0,
        ge=1.0,
        le=120.0,
        description="Hard timeout from 1 to 120 seconds; use 2 seconds for stop",
    )


class PlannedMission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mission_name: str
    intent: str
    actions: list[PlannedAction]


SYSTEM_INSTRUCTIONS = """
You are the high-level mission planner for a differential-drive rescue robot in
a fire-damaged building. Convert Chinese, Japanese, or English operator speech
into one short, deterministic mission.

The robot has LiDAR and odometry. It does not have a manipulator and cannot
invent map locations. Use only these actions:

- move_distance: requires distance_m; use speed_mps between 0.05 and 0.35.
- turn: requires direction and angle_deg; use angular_speed_rps.
- move_until_wall: requires clearance_m and speed_mps.
- move_until_junction: requires side (left, right, or any) and speed_mps.
- follow_wall: requires side (left or right), clearance_m, distance_m, speed_mps.
- stop: stops the robot; set max_duration_s to 2.

Timeouts are hard safety limits, not ideal travel times. They must include
margin for acceleration, steering correction, and slow simulation. Never use
distance divided by speed as the timeout without additional margin.

Preserve the exact order and measurable conditions in the operator's request.
Never generate source code, shell commands, topic names, or unsupported actions.
Never infer a left/right choice that the operator did not provide. If a command
contains an impossible capability, return a single stop action and explain the
unsupported request in intent. Keep every action within the documented numeric
limits. Add a final stop action unless the mission already ends with stop.
""".strip()


def add_execution_timeout_margin(plan: PlannedMission) -> dict[str, Any]:
    """Guarantee that model-proposed timeouts are physically achievable."""
    payload = plan.model_dump()
    for action in payload["actions"]:
        action_type = action["type"]

        if action_type == "stop":
            action["max_duration_s"] = 2.0
            continue

        if action_type == "move_distance":
            speed = min(0.32, max(float(action["speed_mps"]), 0.30))
            action["speed_mps"] = speed
            distance = float(action["distance_m"])
            minimum = (distance / speed) * 2.0 + 10.0
        elif action_type == "follow_wall":
            speed = min(0.26, max(float(action["speed_mps"]), 0.22))
            action["speed_mps"] = speed
            distance = float(action["distance_m"])
            minimum = (distance / speed) * 2.0 + 10.0
        elif action_type == "turn":
            angular_speed = min(
                0.80, max(float(action["angular_speed_rps"]), 0.65)
            )
            action["angular_speed_rps"] = angular_speed
            angle_rad = math.radians(float(action["angle_deg"]))
            minimum = (angle_rad / angular_speed) * 2.0 + 6.0
        elif action_type in {"move_until_wall", "move_until_junction"}:
            action["speed_mps"] = min(
                0.28, max(float(action["speed_mps"]), 0.22)
            )
            minimum = 60.0
        else:
            minimum = 30.0

        proposed = float(action.get("max_duration_s") or 0.0)
        action["max_duration_s"] = round(min(120.0, max(proposed, minimum)), 1)

    return payload


class LanguagePlannerNode(Node):
    def __init__(self) -> None:
        super().__init__("language_planner")
        self.ai = load_ai_settings()
        self.declare_parameter("model", self.ai.planner_model)
        self.model = self.get_parameter("model").value
        self.client = create_ai_client(self.ai)
        self.plan_pub = self.create_publisher(String, "/hazard/mission_plan", 10)
        self.status_pub = self.create_publisher(String, "/hazard/planner_status", 10)
        self.create_subscription(
            String, "/hazard/command_text", self._on_command, 10
        )
        self.get_logger().info(
            f"language planner ready; provider={self.ai.provider}; "
            f"model={self.model}"
        )

    def _on_command(self, message: String) -> None:
        command = message.data.strip()
        if not command:
            self._publish_status("rejected: empty operator command")
            return

        self.get_logger().info(f"planning command: {command}")
        try:
            response = self.client.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_INSTRUCTIONS},
                    {"role": "user", "content": command},
                ],
                response_format=PlannedMission,
                extra_body=self.ai.request_extra_body,
            )
            parsed = response.choices[0].message.parsed
            if parsed is None:
                raise RuntimeError("model returned no structured mission")
            plan = MissionPlan.from_dict(add_execution_timeout_margin(parsed))
        except MissionValidationError as exc:
            self.get_logger().error(f"model produced an invalid mission: {exc}")
            self._publish_status(f"invalid_mission: {exc}")
            return
        except Exception as exc:
            self.get_logger().error(f"planning failed: {exc}")
            self._publish_status(f"planning_failed: {type(exc).__name__}: {exc}")
            return

        output = String()
        output.data = plan.to_json()
        self.plan_pub.publish(output)
        self._publish_status(
            f"planned: {plan.mission_name}; {len(plan.actions)} actions"
        )
        self.get_logger().info(output.data)

    def _publish_status(self, status: str) -> None:
        message = String()
        message.data = status
        self.status_pub.publish(message)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = LanguagePlannerNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()

