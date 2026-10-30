import json
import unittest

from hazard_nav.mission_models import MissionPlan, MissionValidationError


class MissionModelsTest(unittest.TestCase):
    def test_valid_multistep_plan_round_trips(self):
        raw = {
            "mission_name": "reach_safe_zone",
            "intent": "穿过受损走廊抵达安全地点",
            "actions": [
                {
                    "type": "move_distance",
                    "description": "沿走廊前进",
                    "distance_m": 2.0,
                    "speed_mps": 0.2,
                    "max_duration_s": 20.0,
                },
                {
                    "type": "turn",
                    "description": "向左转弯",
                    "direction": "left",
                    "angle_deg": 90.0,
                    "angular_speed_rps": 0.5,
                    "max_duration_s": 10.0,
                },
                {
                    "type": "stop",
                    "description": "抵达后停止",
                    "max_duration_s": 2.0,
                },
            ],
        }
        plan = MissionPlan.from_dict(raw)
        restored = MissionPlan.from_json(plan.to_json())
        self.assertEqual(restored, plan)
        self.assertEqual(json.loads(plan.to_json())["actions"][0]["distance_m"], 2.0)

    def test_rejects_unknown_action_field(self):
        raw = {
            "mission_name": "unsafe",
            "intent": "attempt arbitrary code",
            "actions": [
                {
                    "type": "stop",
                    "description": "stop",
                    "python_code": "import os",
                }
            ],
        }
        with self.assertRaisesRegex(MissionValidationError, "unsupported action fields"):
            MissionPlan.from_dict(raw)

    def test_rejects_out_of_range_speed(self):
        raw = {
            "mission_name": "too_fast",
            "intent": "unsafe speed",
            "actions": [
                {
                    "type": "move_distance",
                    "description": "move",
                    "distance_m": 1.0,
                    "speed_mps": 4.0,
                }
            ],
        }
        with self.assertRaisesRegex(MissionValidationError, "speed_mps"):
            MissionPlan.from_dict(raw)


if __name__ == "__main__":
    unittest.main()

