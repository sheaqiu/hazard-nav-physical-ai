"""Strict mission protocol shared by the LLM planner and robot executor.

This module intentionally has no ROS or API dependencies.  It is the trust
boundary between probabilistic language planning and deterministic control.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import json
import math
from typing import Any


class MissionValidationError(ValueError):
    """Raised when a mission contains an unsupported or unsafe value."""


class ActionType(str, Enum):
    MOVE_DISTANCE = "move_distance"
    TURN = "turn"
    MOVE_UNTIL_WALL = "move_until_wall"
    MOVE_UNTIL_JUNCTION = "move_until_junction"
    FOLLOW_WALL = "follow_wall"
    STOP = "stop"


_STEP_KEYS = {
    "type",
    "description",
    "distance_m",
    "angle_deg",
    "direction",
    "clearance_m",
    "side",
    "speed_mps",
    "angular_speed_rps",
    "max_duration_s",
}


def _optional_number(
    raw: dict[str, Any],
    name: str,
    *,
    minimum: float,
    maximum: float,
) -> float | None:
    value = raw.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MissionValidationError(f"{name} must be a number")
    value = float(value)
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise MissionValidationError(
            f"{name} must be between {minimum} and {maximum}; got {value}"
        )
    return value


@dataclass(frozen=True)
class MissionStep:
    type: ActionType
    description: str
    distance_m: float | None = None
    angle_deg: float | None = None
    direction: str | None = None
    clearance_m: float | None = None
    side: str | None = None
    speed_mps: float | None = None
    angular_speed_rps: float | None = None
    max_duration_s: float = 30.0

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "MissionStep":
        if not isinstance(raw, dict):
            raise MissionValidationError("each action must be an object")

        unknown = set(raw) - _STEP_KEYS
        if unknown:
            raise MissionValidationError(
                f"unsupported action fields: {', '.join(sorted(unknown))}"
            )

        try:
            action_type = ActionType(raw.get("type"))
        except (TypeError, ValueError) as exc:
            raise MissionValidationError(
                f"unsupported action type: {raw.get('type')!r}"
            ) from exc

        description = raw.get("description")
        if not isinstance(description, str) or not description.strip():
            raise MissionValidationError("description must be a non-empty string")

        distance_m = _optional_number(
            raw, "distance_m", minimum=0.10, maximum=12.0
        )
        angle_deg = _optional_number(raw, "angle_deg", minimum=5.0, maximum=180.0)
        clearance_m = _optional_number(
            raw, "clearance_m", minimum=0.25, maximum=1.50
        )
        speed_mps = _optional_number(raw, "speed_mps", minimum=0.05, maximum=0.35)
        angular_speed_rps = _optional_number(
            raw, "angular_speed_rps", minimum=0.15, maximum=1.20
        )
        max_duration_s = _optional_number(
            raw, "max_duration_s", minimum=1.0, maximum=120.0
        )
        if max_duration_s is None:
            max_duration_s = 30.0

        direction = raw.get("direction")
        if direction is not None and direction not in {"left", "right"}:
            raise MissionValidationError("direction must be left or right")

        side = raw.get("side")
        if side is not None and side not in {"left", "right", "any"}:
            raise MissionValidationError("side must be left, right, or any")

        if action_type is ActionType.MOVE_DISTANCE and distance_m is None:
            raise MissionValidationError("move_distance requires distance_m")
        if action_type is ActionType.TURN:
            if angle_deg is None or direction is None:
                raise MissionValidationError("turn requires angle_deg and direction")
        if action_type is ActionType.MOVE_UNTIL_WALL and clearance_m is None:
            raise MissionValidationError("move_until_wall requires clearance_m")
        if action_type is ActionType.MOVE_UNTIL_JUNCTION and side is None:
            raise MissionValidationError("move_until_junction requires side")
        if action_type is ActionType.FOLLOW_WALL:
            if side not in {"left", "right"}:
                raise MissionValidationError("follow_wall requires left or right side")
            if distance_m is None or clearance_m is None:
                raise MissionValidationError(
                    "follow_wall requires distance_m and clearance_m"
                )

        moving = {
            ActionType.MOVE_DISTANCE,
            ActionType.MOVE_UNTIL_WALL,
            ActionType.MOVE_UNTIL_JUNCTION,
            ActionType.FOLLOW_WALL,
        }
        if action_type in moving and speed_mps is None:
            speed_mps = 0.18
        if action_type is ActionType.TURN and angular_speed_rps is None:
            angular_speed_rps = 0.55

        return cls(
            type=action_type,
            description=description.strip(),
            distance_m=distance_m,
            angle_deg=angle_deg,
            direction=direction,
            clearance_m=clearance_m,
            side=side,
            speed_mps=speed_mps,
            angular_speed_rps=angular_speed_rps,
            max_duration_s=max_duration_s,
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["type"] = self.type.value
        return {key: item for key, item in value.items() if item is not None}


@dataclass(frozen=True)
class MissionPlan:
    mission_name: str
    intent: str
    actions: tuple[MissionStep, ...]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "MissionPlan":
        if not isinstance(raw, dict):
            raise MissionValidationError("mission plan must be an object")
        unknown = set(raw) - {"mission_name", "intent", "actions"}
        if unknown:
            raise MissionValidationError(
                f"unsupported mission fields: {', '.join(sorted(unknown))}"
            )

        name = raw.get("mission_name")
        intent = raw.get("intent")
        actions = raw.get("actions")
        if not isinstance(name, str) or not name.strip():
            raise MissionValidationError("mission_name must be a non-empty string")
        if not isinstance(intent, str) or not intent.strip():
            raise MissionValidationError("intent must be a non-empty string")
        if not isinstance(actions, list) or not 1 <= len(actions) <= 20:
            raise MissionValidationError("actions must contain between 1 and 20 steps")

        return cls(
            mission_name=name.strip(),
            intent=intent.strip(),
            actions=tuple(MissionStep.from_dict(item) for item in actions),
        )

    @classmethod
    def from_json(cls, payload: str) -> "MissionPlan":
        try:
            raw = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise MissionValidationError(f"mission is not valid JSON: {exc}") from exc
        return cls.from_dict(raw)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_name": self.mission_name,
            "intent": self.intent,
            "actions": [step.to_dict() for step in self.actions],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"))

