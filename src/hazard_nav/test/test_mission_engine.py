import math
import unittest

from hazard_nav.mission_engine import (
    EngineState,
    MissionEngine,
    Pose2D,
    ScanFrame,
)
from hazard_nav.mission_models import MissionPlan


CLEAR_SCAN = ScanFrame(
    front_m=3.0,
    left_m=0.5,
    right_m=0.5,
    front_left_m=2.5,
    front_right_m=2.5,
    left_open_m=0.8,
    right_open_m=0.8,
)


def make_plan(actions):
    return MissionPlan.from_dict(
        {
            "mission_name": "test_mission",
            "intent": "test closed-loop execution",
            "actions": actions,
        }
    )


class MissionEngineTest(unittest.TestCase):
    def test_distance_turn_stop_mission(self):
        plan = make_plan(
            [
                {
                    "type": "move_distance",
                    "description": "move one metre",
                    "distance_m": 1.0,
                    "speed_mps": 0.2,
                },
                {
                    "type": "turn",
                    "description": "turn left",
                    "direction": "left",
                    "angle_deg": 90.0,
                    "angular_speed_rps": 0.5,
                },
                {"type": "stop", "description": "stop"},
            ]
        )
        engine = MissionEngine()
        engine.load(plan)

        command = engine.update(Pose2D(0.0, 0.0, 0.0), CLEAR_SCAN, 0.0)
        self.assertGreater(command.linear_x, 0.0)
        command = engine.update(Pose2D(1.01, 0.0, 0.0), CLEAR_SCAN, 5.0)
        self.assertEqual(command.linear_x, 0.0)
        self.assertEqual(engine.status.step_index, 1)

        command = engine.update(Pose2D(1.01, 0.0, 0.0), CLEAR_SCAN, 5.1)
        self.assertGreater(command.angular_z, 0.0)
        command = engine.update(
            Pose2D(1.01, 0.0, math.radians(92.0)), CLEAR_SCAN, 7.0
        )
        self.assertEqual(command.angular_z, 0.0)
        self.assertEqual(engine.status.step_index, 2)

        engine.update(Pose2D(1.01, 0.0, math.radians(92.0)), CLEAR_SCAN, 7.1)
        self.assertEqual(engine.status.state, EngineState.SUCCEEDED)

    def test_move_until_wall_uses_lidar_condition(self):
        plan = make_plan(
            [
                {
                    "type": "move_until_wall",
                    "description": "approach wall",
                    "clearance_m": 0.5,
                    "speed_mps": 0.2,
                }
            ]
        )
        engine = MissionEngine()
        engine.load(plan)
        command = engine.update(Pose2D(0, 0, 0), CLEAR_SCAN, 0.0)
        self.assertGreater(command.linear_x, 0.0)

        near_wall = ScanFrame(
            front_m=0.48,
            left_m=0.5,
            right_m=0.5,
            front_left_m=0.6,
            front_right_m=0.6,
            left_open_m=0.7,
            right_open_m=0.7,
        )
        command = engine.update(Pose2D(0.8, 0, 0), near_wall, 4.0)
        self.assertEqual(command.linear_x, 0.0)
        self.assertEqual(engine.status.state, EngineState.SUCCEEDED)

    def test_emergency_stop_fails_active_motion(self):
        plan = make_plan(
            [
                {
                    "type": "move_distance",
                    "description": "move through corridor",
                    "distance_m": 2.0,
                    "speed_mps": 0.2,
                }
            ]
        )
        engine = MissionEngine(emergency_stop_m=0.18)
        engine.load(plan)
        blocked = ScanFrame(
            front_m=0.12,
            left_m=0.5,
            right_m=0.5,
            front_left_m=0.2,
            front_right_m=0.2,
            left_open_m=0.8,
            right_open_m=0.8,
        )
        command = engine.update(Pose2D(0, 0, 0), blocked, 0.0)
        self.assertEqual(command.linear_x, 0.0)
        self.assertEqual(engine.status.state, EngineState.FAILED)
        self.assertIn("emergency stop", engine.status.detail)

    def test_wall_following_preserves_corridor_heading(self):
        plan = make_plan(
            [
                {
                    "type": "follow_wall",
                    "description": "follow the right wall",
                    "side": "right",
                    "distance_m": 3.0,
                    "clearance_m": 0.7,
                    "speed_mps": 0.16,
                }
            ]
        )
        far_right_wall = ScanFrame(
            front_m=3.0,
            left_m=1.0,
            right_m=1.2,
            front_left_m=2.5,
            front_right_m=2.0,
            left_open_m=1.0,
            right_open_m=1.0,
        )
        engine = MissionEngine()
        engine.load(plan)

        approaching = engine.update(Pose2D(0, 0, 0), far_right_wall, 0.0)
        self.assertLess(approaching.angular_z, 0.0)
        self.assertLessEqual(abs(approaching.angular_z), 0.38)

        recovering = engine.update(Pose2D(0.2, -0.02, -0.2), far_right_wall, 1.0)
        self.assertGreater(recovering.angular_z, approaching.angular_z)
        self.assertLessEqual(abs(recovering.angular_z), 0.38)

    def test_wall_following_turns_toward_the_more_open_side(self):
        plan = make_plan(
            [
                {
                    "type": "follow_wall",
                    "description": "pass debris",
                    "side": "right",
                    "distance_m": 2.0,
                    "clearance_m": 0.7,
                    "speed_mps": 0.16,
                }
            ]
        )
        blocked_with_right_open = ScanFrame(
            front_m=0.6,
            left_m=0.4,
            right_m=0.8,
            front_left_m=0.35,
            front_right_m=0.35,
            left_open_m=0.6,
            right_open_m=1.8,
        )
        engine = MissionEngine()
        engine.load(plan)
        command = engine.update(Pose2D(0, 0, 0), blocked_with_right_open, 0.0)
        self.assertLess(command.angular_z, 0.0)
        self.assertEqual(command.linear_x, 0.0)

        still_avoiding = ScanFrame(
            front_m=1.2,
            left_m=0.8,
            right_m=0.4,
            front_left_m=0.9,
            front_right_m=0.7,
            left_open_m=1.8,
            right_open_m=0.6,
        )
        command = engine.update(Pose2D(0.0, 0.0, -0.1), still_avoiding, 0.5)
        self.assertLess(command.angular_z, 0.0)

        command = engine.update(Pose2D(0.0, 0.0, -0.55), still_avoiding, 1.0)
        self.assertGreater(command.linear_x, 0.0)
        self.assertEqual(command.angular_z, 0.0)

        second_obstacle = ScanFrame(
            front_m=0.9,
            left_m=0.8,
            right_m=0.4,
            front_left_m=0.7,
            front_right_m=0.5,
            left_open_m=1.8,
            right_open_m=0.5,
        )
        command = engine.update(Pose2D(0.2, -0.1, -0.55), second_obstacle, 1.5)
        self.assertGreater(command.angular_z, 0.0)
        self.assertEqual(command.linear_x, 0.0)


if __name__ == "__main__":
    unittest.main()

