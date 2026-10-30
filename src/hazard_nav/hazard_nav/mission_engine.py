"""Deterministic closed-loop executor for a hazardous-area mission plan."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math

from .mission_models import ActionType, MissionPlan, MissionStep


def normalize_angle(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


@dataclass(frozen=True)
class Pose2D:
    x: float
    y: float
    yaw: float


@dataclass(frozen=True)
class ScanFrame:
    front_m: float
    left_m: float
    right_m: float
    front_left_m: float
    front_right_m: float
    left_open_m: float
    right_open_m: float


@dataclass(frozen=True)
class MotionCommand:
    linear_x: float = 0.0
    angular_z: float = 0.0


class EngineState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class EngineStatus:
    state: EngineState
    mission_name: str | None
    step_index: int
    step_count: int
    detail: str


class MissionEngine:
    """Executes one validated mission against odometry and LiDAR summaries."""

    def __init__(
        self,
        *,
        emergency_stop_m: float = 0.18,
        junction_open_m: float = 1.15,
        junction_confirmations: int = 4,
    ) -> None:
        self.emergency_stop_m = emergency_stop_m
        self.junction_open_m = junction_open_m
        self.junction_confirmations = junction_confirmations
        self.plan: MissionPlan | None = None
        self.state = EngineState.IDLE
        self.step_index = 0
        self.detail = "waiting for mission"
        self._step_started_at: float | None = None
        self._step_start_pose: Pose2D | None = None
        self._last_yaw: float | None = None
        self._turned_rad = 0.0
        self._junction_hits = 0
        self._avoidance_direction = 0.0
        self._avoidance_phase: str | None = None
        self._avoidance_start_pose: Pose2D | None = None
        self._avoidance_start_yaw: float | None = None

    @property
    def status(self) -> EngineStatus:
        return EngineStatus(
            state=self.state,
            mission_name=self.plan.mission_name if self.plan else None,
            step_index=self.step_index,
            step_count=len(self.plan.actions) if self.plan else 0,
            detail=self.detail,
        )

    def load(self, plan: MissionPlan) -> None:
        self.plan = plan
        self.state = EngineState.RUNNING
        self.step_index = 0
        self.detail = f"mission accepted: {plan.mission_name}"
        self._reset_step()

    def cancel(self, reason: str) -> None:
        if self.state is EngineState.RUNNING:
            self.state = EngineState.FAILED
            self.detail = f"mission cancelled: {reason}"

    def update(self, pose: Pose2D, scan: ScanFrame, now_s: float) -> MotionCommand:
        if self.state is not EngineState.RUNNING or self.plan is None:
            return MotionCommand()

        if self.step_index >= len(self.plan.actions):
            self.state = EngineState.SUCCEEDED
            self.detail = "all mission steps completed"
            return MotionCommand()

        step = self.plan.actions[self.step_index]
        if self._step_started_at is None:
            self._start_step(step, pose, now_s)

        assert self._step_started_at is not None
        if now_s - self._step_started_at > step.max_duration_s:
            return self._fail(
                f"step {self.step_index + 1} timed out after {step.max_duration_s:.1f}s"
            )

        command, complete = self._execute_step(step, pose, scan)
        if complete:
            self.detail = f"completed step {self.step_index + 1}: {step.description}"
            self.step_index += 1
            self._reset_step()
            if self.step_index >= len(self.plan.actions):
                self.state = EngineState.SUCCEEDED
                self.detail = "safe destination reached; mission completed"
            return MotionCommand()

        moving_forward = command.linear_x > 0.0
        if moving_forward and scan.front_m < self.emergency_stop_m:
            return self._fail(
                f"emergency stop: obstacle at {scan.front_m:.2f}m"
            )

        return MotionCommand(
            linear_x=clamp(command.linear_x, -0.22, 0.35),
            angular_z=clamp(command.angular_z, -1.20, 1.20),
        )

    def _start_step(self, step: MissionStep, pose: Pose2D, now_s: float) -> None:
        self._step_started_at = now_s
        self._step_start_pose = pose
        self._last_yaw = pose.yaw
        self._turned_rad = 0.0
        self._junction_hits = 0
        self._avoidance_direction = 0.0
        self._avoidance_phase = None
        self._avoidance_start_pose = None
        self._avoidance_start_yaw = None
        self.detail = f"executing step {self.step_index + 1}: {step.description}"

    def _reset_step(self) -> None:
        self._step_started_at = None
        self._step_start_pose = None
        self._last_yaw = None
        self._turned_rad = 0.0
        self._junction_hits = 0

    def _distance_from_step_start(self, pose: Pose2D) -> float:
        assert self._step_start_pose is not None
        return math.hypot(
            pose.x - self._step_start_pose.x,
            pose.y - self._step_start_pose.y,
        )

    def _execute_step(
        self, step: MissionStep, pose: Pose2D, scan: ScanFrame
    ) -> tuple[MotionCommand, bool]:
        if step.type is ActionType.STOP:
            return MotionCommand(), True

        if step.type is ActionType.MOVE_DISTANCE:
            assert step.distance_m is not None and step.speed_mps is not None
            done = self._distance_from_step_start(pose) >= step.distance_m
            return MotionCommand(linear_x=step.speed_mps), done

        if step.type is ActionType.TURN:
            assert step.angle_deg is not None
            assert step.angular_speed_rps is not None
            assert step.direction is not None
            assert self._last_yaw is not None
            delta = normalize_angle(pose.yaw - self._last_yaw)
            self._turned_rad += abs(delta)
            self._last_yaw = pose.yaw
            target = math.radians(step.angle_deg)
            if self._turned_rad >= target:
                return MotionCommand(), True
            sign = 1.0 if step.direction == "left" else -1.0
            remaining = target - self._turned_rad
            speed = step.angular_speed_rps
            if remaining < math.radians(20.0):
                speed = max(0.18, speed * 0.45)
            return MotionCommand(angular_z=sign * speed), False

        if step.type is ActionType.MOVE_UNTIL_WALL:
            assert step.clearance_m is not None and step.speed_mps is not None
            if scan.front_m <= step.clearance_m:
                return MotionCommand(), True
            speed = min(step.speed_mps, max(0.06, (scan.front_m - step.clearance_m) * 0.55))
            steering = clamp((scan.front_right_m - scan.front_left_m) * 0.35, -0.35, 0.35)
            return MotionCommand(linear_x=speed, angular_z=steering), False

        if step.type is ActionType.MOVE_UNTIL_JUNCTION:
            assert step.side is not None and step.speed_mps is not None
            travelled = self._distance_from_step_start(pose)
            opening = {
                "left": scan.left_open_m >= self.junction_open_m,
                "right": scan.right_open_m >= self.junction_open_m,
                "any": (
                    scan.left_open_m >= self.junction_open_m
                    or scan.right_open_m >= self.junction_open_m
                ),
            }[step.side]
            self._junction_hits = self._junction_hits + 1 if opening and travelled > 0.35 else 0
            if self._junction_hits >= self.junction_confirmations:
                return MotionCommand(), True
            steering = clamp((scan.front_right_m - scan.front_left_m) * 0.30, -0.30, 0.30)
            return MotionCommand(linear_x=step.speed_mps, angular_z=steering), False

        if step.type is ActionType.FOLLOW_WALL:
            assert step.side in {"left", "right"}
            assert step.distance_m is not None
            assert step.clearance_m is not None
            assert step.speed_mps is not None
            if self._distance_from_step_start(pose) >= step.distance_m:
                return MotionCommand(), True

            if self._avoidance_phase == "turn":
                assert self._avoidance_start_yaw is not None
                turned = abs(normalize_angle(pose.yaw - self._avoidance_start_yaw))
                if turned < math.radians(30.0):
                    return MotionCommand(
                        angular_z=self._avoidance_direction,
                    ), False
                self._avoidance_phase = "bypass"
                self._avoidance_start_pose = pose

            if self._avoidance_phase == "bypass":
                assert self._avoidance_start_pose is not None
                if scan.front_m < 1.00:
                    self._avoidance_direction = (
                        0.45 if scan.left_open_m >= scan.right_open_m else -0.45
                    )
                    self._avoidance_phase = "turn"
                    self._avoidance_start_pose = None
                    self._avoidance_start_yaw = pose.yaw
                    return MotionCommand(
                        angular_z=self._avoidance_direction,
                    ), False
                bypass_distance = math.hypot(
                    pose.x - self._avoidance_start_pose.x,
                    pose.y - self._avoidance_start_pose.y,
                )
                if bypass_distance < 0.85:
                    return MotionCommand(linear_x=0.12), False
                self._avoidance_phase = None
                self._avoidance_direction = 0.0
                self._avoidance_start_pose = None
                self._avoidance_start_yaw = None

            if scan.front_m < 0.70:
                self._avoidance_direction = (
                    0.45 if scan.left_open_m >= scan.right_open_m else -0.45
                )
                self._avoidance_phase = "turn"
                self._avoidance_start_yaw = pose.yaw
                return MotionCommand(
                    angular_z=self._avoidance_direction,
                ), False

            measured = scan.left_m if step.side == "left" else scan.right_m
            distance_error = measured - step.clearance_m
            side_sign = 1.0 if step.side == "left" else -1.0
            assert self._step_start_pose is not None
            heading_error = normalize_angle(pose.yaw - self._step_start_pose.yaw)

            # Follow the wall with a shallow approach angle while preserving the
            # corridor heading captured at the start of the step.  A distance-only
            # controller can keep turning toward a far wall until the rover loops.
            wall_correction = side_sign * distance_error * 0.35
            heading_correction = -heading_error * 1.20
            steering = clamp(
                wall_correction + heading_correction,
                -0.38,
                0.38,
            )
            speed = step.speed_mps * (0.72 if abs(steering) > 0.28 else 1.0)
            return MotionCommand(linear_x=speed, angular_z=steering), False

        raise AssertionError(f"unhandled action: {step.type}")

    def _fail(self, detail: str) -> MotionCommand:
        self.state = EngineState.FAILED
        self.detail = detail
        return MotionCommand()

