# HazardNav

## 日本語

自然言語で危険区域を走行する遠隔ナビゲーションロボットです。オペレーターがテキストまたは音声で複数ステップの任務を与え、AI が命令を制限付きの動作計画に変換します。Gazebo 内の自作差動二輪ロボットは、LiDAR とオドメトリを使って各動作を確認しながら実行します。

プロジェクトの概念、デモ手順、評価指標は [`docs/project-concept.md`](docs/project-concept.md)、システム接続は [`docs/architecture.md`](docs/architecture.md)、実機環境での検証結果は [`docs/verification.md`](docs/verification.md) を参照してください。

### 単なる「音声リモコン」ではありません

システムは一定時間だけモーターを動かすのではなく、各動作の完了条件をセンサーで確認します。

- 移動距離は `/odom` で判定します。
- 回転角度は向きの変化で判定します。
- 壁の手前で止まる条件は `/scan` で判定します。
- 分岐は左右の開放空間を連続的に検査します。
- 壁沿い走行では LiDAR の距離を使って向きを調整します。
- 前方の障害物が近すぎる場合は任務を緊急停止します。

AI は Python コードを生成して実行するのではなく、次の流れで制限されたデータのみを出力します。

```text
自然言語 -> Structured Output -> 厳格な検証 -> 固定の動作実行器
```

言語計画には OpenAI SDK の Pydantic [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=chat) と OpenRouter の [OpenAI-compatible API](https://openrouter.ai/docs/community/open-ai-sdk) を使用します。JSON Schema に対応する接続先だけが選ばれ、形式に合わない回答はロボットへ送られません。音声転写は同じ OpenRouter key で [`/audio/transcriptions`](https://openrouter.ai/blog/tutorials/transcription-on-openrouter/) を使用します。

### ディレクトリ構成

```text
hazard_nav_ws/
├── Dockerfile
├── compose.yaml
├── requirements-api.txt
├── docs/
└── src/hazard_nav/
    ├── hazard_nav/
    │   ├── mission_models.py
    │   ├── ai_gateway.py
    │   ├── mission_engine.py
    │   ├── scan_geometry.py
    │   ├── language_planner_node.py
    │   ├── mission_executor_node.py
    │   ├── operator_console_node.py
    │   └── voice_operator_node.py
    ├── launch/
    ├── worlds/
    └── test/
```

### ローカルテスト

制御の中心部分は ROS2 なしでもテストできます。

```bash
cd hazard_nav_ws
PYTHONPATH=src/hazard_nav python3 -m unittest discover -s src/hazard_nav/test -v
```

### ROS2 / Gazebo 環境

プロジェクトは `tiryoh/ros2-desktop-vnc` の ROS2 Humble 環境を使用します。Docker のインストール後に次を実行します。

```bash
cp .env.example .env
# OPENROUTER_API_KEY はローカルの .env にだけ記入し、チャットや Git には送らないでください。
docker compose build
docker compose up -d
```

ブラウザーで `http://localhost:6080/` を開きます。VNC パスワードは `ubuntu` です。コンテナーのターミナルで次を実行します。

```bash
source /opt/ros/humble/setup.bash
source /opt/hazard_nav_ws/install/setup.bash
ros2 launch hazard_nav hazard_world.launch.py
```

この起動で、危険な建物環境、自作救援ロボット、任務実行器が開始します。画面なしでテストする場合は次を使います。

```bash
ros2 launch hazard_nav hazard_world.launch.py gui:=false
```

### 手作業の計画でロボットを検証

別のターミナルで付属の安全ルートを送信します。

```bash
source /opt/ros/humble/setup.bash
source /opt/hazard_nav_ws/install/setup.bash
ros2 run hazard_nav mission_file
```

これにより、AI を使う前に、直進、左右回転、壁沿い走行、安全エリアへの到達を確認できます。

### テキストによる自然言語操作

既定値は `OPENROUTER_API_KEY` と、低コストで構造化出力に対応する `google/gemini-2.5-flash-lite` です。プランナーはモデルが提案した速度とタイムアウトを実行前に正規化し、直進には加減速の余裕、壁沿い走行には安定性の上限を与えます。`.env` を変更した場合は、`docker compose up -d --force-recreate` でコンテナーに再読み込みさせます。

```bash
ros2 run hazard_nav language_planner
```

別のターミナルで次を実行します。

```bash
ros2 run hazard_nav operator_console
```

入力例：

```text
壁から 0.5 メートルの位置まで前進し、左に 90 度回転し、右側の壁に沿って 3 メートル進んで停止してください。
```

### 音声操作

マイクと PortAudio を利用できる環境で次を実行します。

```bash
ros2 run hazard_nav voice_operator
```

Enter キーの後に 7 秒間録音し、`openai/whisper-large-v3-turbo` でテキストに変換します。言語計画と音声転写は同じ OpenRouter key を使用します。macOS の Docker Desktop ではマイク接続の追加設定が必要です。

### システムの観察

```bash
ros2 topic echo /hazard/mission_plan
ros2 topic echo /hazard/mission_status
ros2 topic echo /scan
ros2 topic echo /odom
ros2 topic echo /cmd_vel
rqt_image_view /camera/image_raw
```

実験を記録する場合：

```bash
ros2 bag record -o hazard_run \
  /hazard/command_text \
  /hazard/mission_plan \
  /hazard/mission_status \
  /scan /odom /cmd_vel
```

### 現在の範囲

- ロボットはオペレーターの経路指示に従い、建物全体の経路を自律的に選びません。
- 前方カメラは遠隔監視に使用し、LiDAR とオドメトリが走行制御を担当します。
- 火炎・煙の自動認識、動的障害物、Nav2 による大域経路計画は将来の拡張です。

---

## English

HazardNav is a natural-language remote navigation robot for hazardous areas. An operator gives a multi-step mission by text or voice, and AI converts it into a constrained action plan. A custom differential-drive rescue robot in Gazebo then executes each action using LiDAR and odometry feedback.

See [`docs/project-concept.md`](docs/project-concept.md) for the project concept, demo flow, and evaluation metrics; [`docs/architecture.md`](docs/architecture.md) for system interfaces; and [`docs/verification.md`](docs/verification.md) for local end-to-end evidence.

### More than voice remote control

The system does not simply run each motor command for a fixed number of seconds. Every action has a measurable completion condition:

- `/odom` determines travelled distance.
- Heading change determines turn completion.
- `/scan` determines when the robot reaches a wall clearance.
- Repeated left and right opening measurements detect junctions.
- LiDAR distance feedback corrects wall-following motion.
- The mission stops immediately when the front clearance becomes unsafe.

The AI never generates and executes Python source code. It can only produce constrained data through this pipeline:

```text
Natural language -> Structured Output -> strict validation -> fixed action executor
```

Language planning uses the OpenAI SDK Pydantic [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=chat) through OpenRouter's [OpenAI-compatible API](https://openrouter.ai/docs/community/open-ai-sdk). Requests require an endpoint that supports JSON Schema, and a response that fails the schema never reaches the robot executor. Audio transcription uses [`/audio/transcriptions`](https://openrouter.ai/blog/tutorials/transcription-on-openrouter/) with the same OpenRouter key.

### Directory layout

```text
hazard_nav_ws/
├── Dockerfile
├── compose.yaml
├── requirements-api.txt
├── docs/
└── src/hazard_nav/
    ├── hazard_nav/
    │   ├── mission_models.py
    │   ├── ai_gateway.py
    │   ├── mission_engine.py
    │   ├── scan_geometry.py
    │   ├── language_planner_node.py
    │   ├── mission_executor_node.py
    │   ├── operator_console_node.py
    │   └── voice_operator_node.py
    ├── launch/
    ├── worlds/
    └── test/
```

### Local tests

The pure Python control core can be tested without ROS2:

```bash
cd hazard_nav_ws
PYTHONPATH=src/hazard_nav python3 -m unittest discover -s src/hazard_nav/test -v
```

### ROS2 / Gazebo environment

The project uses the ROS2 Humble environment from `tiryoh/ros2-desktop-vnc`. After installing Docker, run:

```bash
cp .env.example .env
# Put OPENROUTER_API_KEY only in the local .env file. Never paste it into chat or commit it.
docker compose build
docker compose up -d
```

Open `http://localhost:6080/` in a browser. The VNC password is `ubuntu`. In the container desktop terminal, run:

```bash
source /opt/ros/humble/setup.bash
source /opt/hazard_nav_ws/install/setup.bash
ros2 launch hazard_nav hazard_world.launch.py
```

This starts the hazardous building, the custom rescue robot, and the mission executor. For headless testing, use:

```bash
ros2 launch hazard_nav hazard_world.launch.py gui:=false
```

### Verify the robot with a hand-authored plan

In another container terminal, publish the included safe route:

```bash
source /opt/ros/humble/setup.bash
source /opt/hazard_nav_ws/install/setup.bash
ros2 run hazard_nav mission_file
```

This verifies straight motion, left and right turns, wall following, and entry into the green safe zone before the language model is introduced.

### Text-based natural-language control

The default configuration uses `OPENROUTER_API_KEY` and the low-cost `google/gemini-2.5-flash-lite` model with structured-output support. Before execution, the planner normalizes model-proposed speeds and timeouts, leaving acceleration margin for straight motion and applying a stability cap to wall following. After changing `.env`, run `docker compose up -d --force-recreate` so that the container reloads it.

```bash
ros2 run hazard_nav language_planner
```

In another terminal:

```bash
ros2 run hazard_nav operator_console
```

Example command:

```text
Move forward until the wall is half a metre away, turn left 90 degrees, follow the right wall for three metres, and stop.
```

### Voice control

With microphone and PortAudio access available, run:

```bash
ros2 run hazard_nav voice_operator
```

Press Enter to record a seven-second command. `openai/whisper-large-v3-turbo` converts it to text before it enters the same planning pipeline. Planning and transcription share one OpenRouter key. Docker Desktop on macOS requires separate microphone-device setup.

### Observe the system

```bash
ros2 topic echo /hazard/mission_plan
ros2 topic echo /hazard/mission_status
ros2 topic echo /scan
ros2 topic echo /odom
ros2 topic echo /cmd_vel
rqt_image_view /camera/image_raw
```

Record a complete experiment with:

```bash
ros2 bag record -o hazard_run \
  /hazard/command_text \
  /hazard/mission_plan \
  /hazard/mission_status \
  /scan /odom /cmd_vel
```

### Current scope

- The operator supplies route instructions; the robot does not independently solve a full building map.
- The front camera supports remote observation, while LiDAR and odometry control motion.
- Automatic fire or smoke recognition, dynamic obstacles, and Nav2 global planning remain future extensions.

---

## 中文

HazardNav 是一个由自然语言驱动的危险区域远程导航机器人。操作员通过文字或语音下达多步任务，AI 将命令转换为受限的动作计划，Gazebo 中的自建差动轮救援车再结合 LiDAR 和里程计反馈执行每一步。

项目概念、演示流程和评价指标见 [`docs/project-concept.md`](docs/project-concept.md)，系统接口见 [`docs/architecture.md`](docs/architecture.md)，本机端到端实测证据见 [`docs/verification.md`](docs/verification.md)。

### 不只是“语音遥控”

系统不会按固定时间播放一串电机命令，每个动作都有可测量的完成条件：

- 移动距离由 `/odom` 判断。
- 转向角由朝向变化判断。
- 到墙前停止由 `/scan` 判断。
- 岔路口由左右开放空间的连续测量判断。
- 沿墙行驶使用 LiDAR 距离反馈修正方向。
- 前方距离过小时立即停止任务。

AI 不会生成并执行 Python 源码，只能按下列流程输出受限数据：

```text
自然语言 -> Structured Output -> 严格校验 -> 固定动作执行器
```

语言规划通过 OpenRouter 的 [OpenAI-compatible API](https://openrouter.ai/docs/community/open-ai-sdk) 使用 OpenAI SDK 的 Pydantic [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=chat)。请求只会选择支持 JSON Schema 的接口，不符合规格的回答不会进入机器人执行器。语音转录使用同一个 OpenRouter key 的 [`/audio/transcriptions`](https://openrouter.ai/blog/tutorials/transcription-on-openrouter/)。

### 目录结构

```text
hazard_nav_ws/
├── Dockerfile
├── compose.yaml
├── requirements-api.txt
├── docs/
└── src/hazard_nav/
    ├── hazard_nav/
    │   ├── mission_models.py
    │   ├── ai_gateway.py
    │   ├── mission_engine.py
    │   ├── scan_geometry.py
    │   ├── language_planner_node.py
    │   ├── mission_executor_node.py
    │   ├── operator_console_node.py
    │   └── voice_operator_node.py
    ├── launch/
    ├── worlds/
    └── test/
```

### 本机测试

纯 Python 控制核心可以在不启动 ROS2 的情况下测试：

```bash
cd hazard_nav_ws
PYTHONPATH=src/hazard_nav python3 -m unittest discover -s src/hazard_nav/test -v
```

### ROS2 / Gazebo 环境

项目使用 `tiryoh/ros2-desktop-vnc` 的 ROS2 Humble 环境。安装 Docker 后执行：

```bash
cp .env.example .env
# OPENROUTER_API_KEY 只填入本机 .env，不要发到聊天或提交到 Git。
docker compose build
docker compose up -d
```

浏览器打开 `http://localhost:6080/`，VNC 密码为 `ubuntu`。在容器桌面的终端中执行：

```bash
source /opt/ros/humble/setup.bash
source /opt/hazard_nav_ws/install/setup.bash
ros2 launch hazard_nav hazard_world.launch.py
```

这会启动危险建筑场景、自建救援车和任务执行器。如果只需无界面测试，使用：

```bash
ros2 launch hazard_nav hazard_world.launch.py gui:=false
```

### 先用手写计划验证机器人

在另一个容器终端中发布项目自带的安全路线：

```bash
source /opt/ros/humble/setup.bash
source /opt/hazard_nav_ws/install/setup.bash
ros2 run hazard_nav mission_file
```

该路线会在接入语言模型前，先验证直行、左右转向、沿墙行驶和进入绿色安全区。

### 文字自然语言控制

默认配置使用 `OPENROUTER_API_KEY` 和支持结构化输出的低成本模型 `google/gemini-2.5-flash-lite`。执行前，规划器会自动调整模型给出的速度和超时时间，为直线行驶保留加减速余量，并限制沿墙速度以保持稳定。修改 `.env` 后，执行 `docker compose up -d --force-recreate` 让容器重新读取配置。

```bash
ros2 run hazard_nav language_planner
```

在另一个终端中执行：

```bash
ros2 run hazard_nav operator_console
```

示例命令：

```text
向前走到距离墙壁半米的位置，然后左转九十度，沿右侧墙壁前进三米，最后停止。
```

### 语音控制

在可以访问麦克风和 PortAudio 的环境中执行：

```bash
ros2 run hazard_nav voice_operator
```

按 Enter 后录制 7 秒指令，`openai/whisper-large-v3-turbo` 会先将语音转成文字，再进入同一规划流程。语言规划和语音转录共用一个 OpenRouter key。macOS 的 Docker Desktop 需要额外设置麦克风设备。

### 观察系统

```bash
ros2 topic echo /hazard/mission_plan
ros2 topic echo /hazard/mission_status
ros2 topic echo /scan
ros2 topic echo /odom
ros2 topic echo /cmd_vel
rqt_image_view /camera/image_raw
```

记录一次完整实验：

```bash
ros2 bag record -o hazard_run \
  /hazard/command_text \
  /hazard/mission_plan \
  /hazard/mission_status \
  /scan /odom /cmd_vel
```

### 当前范围

- 机器人按照操作员提供的路线指令行驶，不会独立解决整张建筑地图。
- 前视相机用于远程观察，LiDAR 和里程计负责运动控制。
- 自动火焰或烟雾识别、动态障碍物和 Nav2 全局规划属于后续扩展。
