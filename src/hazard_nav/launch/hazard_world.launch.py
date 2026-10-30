#!/usr/bin/env python3

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    package_share = get_package_share_directory("hazard_nav")
    world_path = os.path.join(package_share, "worlds", "hazard_facility.sdf")
    ros_gz_share = get_package_share_directory("ros_gz_sim")

    gz_server = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(ros_gz_share, "launch", "gz_sim.launch.py")
        ),
        launch_arguments={
            "gz_args": ["-r -s -v2 ", world_path],
            "on_exit_shutdown": "true",
        }.items(),
    )
    gz_client = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(ros_gz_share, "launch", "gz_sim.launch.py")
        ),
        launch_arguments={
            "gz_args": "-g -v2",
            "on_exit_shutdown": "true",
        }.items(),
        condition=IfCondition(LaunchConfiguration("gui")),
    )
    bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="hazard_gazebo_bridge",
        output="screen",
        arguments=[
            "/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock",
            "/cmd_vel@geometry_msgs/msg/Twist]ignition.msgs.Twist",
            "/odom@nav_msgs/msg/Odometry[ignition.msgs.Odometry",
            "/scan@sensor_msgs/msg/LaserScan[ignition.msgs.LaserScan",
            "/camera/image_raw@sensor_msgs/msg/Image[ignition.msgs.Image",
        ],
    )
    executor = Node(
        package="hazard_nav",
        executable="mission_executor",
        name="mission_executor",
        output="screen",
        parameters=[{"use_sim_time": True}],
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "gui",
                default_value="true",
                description="Start the Gazebo graphical client",
            ),
            gz_server,
            gz_client,
            bridge,
            executor,
        ]
    )

