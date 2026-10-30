# Local verification record

Verified on an Intel macOS host with Docker Desktop, ROS2 Humble and Ignition Gazebo Fortress.

## Static and unit checks

- `ign sdf -k`: world file reported `Valid`.
- `colcon build --symlink-install`: one ROS2 package built successfully.
- `python -m compileall`: Python nodes and launch files compiled successfully.
- `xmllint`: `package.xml` and the SDF world passed XML validation.
- Python suite: 13 tests passed, including AI gateway selection, mission validation, odometry completion, emergency stop, bounded wall following, heading recovery and chained obstacle selection.

## Runtime data paths

The running graph exposed all expected topics:

```text
/camera/image_raw  sensor_msgs/msg/Image
/clock             rosgraph_msgs/msg/Clock
/cmd_vel           geometry_msgs/msg/Twist
/hazard/mission_plan
/hazard/mission_status
/odom              nav_msgs/msg/Odometry
/scan              sensor_msgs/msg/LaserScan
```

With the Gazebo GUI also open in the VNC desktop, observed rates were approximately 6.8 Hz for the 540-ray LiDAR and 3.2 Hz for the 480×270 camera. The requested SDF update rates are 12 Hz and 6 Hz; the lower wall-clock rates are caused by the simulation running below real time on the Intel Mac, while all controller timeouts use simulation time.

## Closed-loop smoke task

The 0.8 m + 45° smoke mission completed with `succeeded`. Final odometry was approximately:

```text
x = 0.821 m
y = 0.000 m
yaw ≈ 46°
```

This verifies that distance and turn completion come from odometry rather than fixed sleep durations.

## Full hazardous-area mission

The final nine-step mission completed end to end:

```json
{"state":"succeeded","mission_name":"damaged_corridor_to_safe_zone","step_index":9,"step_count":9,"detail":"safe destination reached; mission completed"}
```

Final Gazebo world pose and velocity:

```text
position = (3.97894, 4.63291, 0.12500) m
yaw      = 1.55356 rad
linear   = (0, 0, 0) m/s
angular  = (0, 0, 0) rad/s
```

The green safe-zone marker is centred at `(4.1, 4.75)` with radius `0.78 m`, so the final rover centre is about `0.17 m` from the marker centre and is inside the safe zone.

## API boundary

The container successfully imports `openai 2.54.0`, `pydantic 2.14.1` and `sounddevice 0.5.6`. The gateway accepts `OPENROUTER_API_KEY` for both structured language planning and audio transcription, while retaining native `OPENAI_API_KEY` support.

On 2026-10-30, a live request was tested with the zero-model-cost `openrouter/free` router. The first model response set the stop action timeout to zero; the independent mission validator rejected it before publication. The planner schema was then tightened so every numeric field carries the same minimum and maximum as the deterministic executor, including a 1–120 second action timeout.

The repeated Chinese route command produced a valid nine-action structured plan. That AI-generated plan was published through `/hazard/mission_plan` and completed end to end:

```json
{"state":"succeeded","mission_name":"rescue_route_to_green_safe_zone","step_index":9,"step_count":9,"detail":"safe destination reached; mission completed"}
```

Final live-API mission evidence:

```text
Gazebo position = (3.970260, 4.562130, 0.125000) m
Gazebo yaw      = 1.557190 rad
/cmd_vel linear = (0, 0, 0) m/s
/cmd_vel angular= (0, 0, 0) rad/s
```

The final rover centre was approximately `0.228 m` from the green safe-zone centre, safely inside its `0.78 m` radius. The API key was loaded only from the gitignored local `.env` and was not printed in the test output.
