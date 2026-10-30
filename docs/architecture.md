# Architecture notes

## Trust boundary

The language model never produces executable Python. It produces a typed mission
containing only six action primitives. The mission is parsed a second time by
`MissionPlan.from_dict` before it reaches the motor controller.

```text
voice -> transcription -> LLM structured output -> strict validator
      -> deterministic mission engine -> /cmd_vel -> custom rescue rover
                                      <- /scan, /odom
```

This deliberately differs from the Quri natural-language sample, which writes
the model response to `generated_script.py` and executes it. The sample proves
that natural language can drive a ROS2 robot; this project turns the idea into a
closed-loop system with an explicit command vocabulary.

## Runtime topics

| Topic | Type | Producer | Consumer |
|---|---|---|---|
| `/hazard/command_text` | `std_msgs/String` | operator | language planner |
| `/hazard/mission_plan` | `std_msgs/String` (JSON) | language planner | executor |
| `/hazard/planner_status` | `std_msgs/String` | language planner | operator/log |
| `/hazard/mission_status` | `std_msgs/String` (JSON) | executor | operator/log |
| `/scan` | `sensor_msgs/LaserScan` | Gazebo rescue rover | executor |
| `/odom` | `nav_msgs/Odometry` | Gazebo rescue rover | executor |
| `/cmd_vel` | `geometry_msgs/Twist` | executor | Gazebo rescue rover |
| `/camera/image_raw` | `sensor_msgs/Image` | front camera | remote operator |

## Action semantics

- `move_distance`: terminate from odometry displacement.
- `turn`: integrate wrapped yaw increments from odometry.
- `move_until_wall`: terminate from the forward LiDAR sector.
- `move_until_junction`: require several consecutive side-opening detections.
- `follow_wall`: LiDAR wall-distance correction plus corridor-heading hold, with front-obstacle turning.
- `stop`: explicit zero velocity and mission completion.

Each moving action has a timeout. The executor stops immediately when forward
clearance falls below the emergency threshold.

## Development boundary

The pure modules `mission_models.py`, `mission_engine.py`, and
`scan_geometry.py` do not import ROS. They can be unit tested on macOS before
the Docker/ROS2 environment is installed. ROS nodes are thin adapters around
those modules.

