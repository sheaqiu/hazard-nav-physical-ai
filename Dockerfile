FROM tiryoh/ros2-desktop-vnc:humble-20261025T0907

USER root
SHELL ["/bin/bash", "-c"]

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    libportaudio2 \
    python3-pip \
    ros-humble-ros-gz \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-api.txt /tmp/hazard-nav-requirements.txt
RUN python3 -m pip install --no-cache-dir -r /tmp/hazard-nav-requirements.txt

WORKDIR /opt/hazard_nav_ws
COPY src ./src
COPY docs ./docs
COPY README.md ./README.md

RUN source /opt/ros/humble/setup.bash \
    && colcon build --symlink-install --event-handlers console_direct+

