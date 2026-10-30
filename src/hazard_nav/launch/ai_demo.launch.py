#!/usr/bin/env python3

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    package_share = get_package_share_directory("hazard_nav")
    world_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(package_share, "launch", "hazard_world.launch.py")
        )
    )
    planner = Node(
        package="hazard_nav",
        executable="language_planner",
        name="language_planner",
        output="screen",
    )
    return LaunchDescription([world_launch, planner])

