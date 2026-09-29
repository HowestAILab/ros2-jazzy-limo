"""limo_base (motor controller, odometry, IMU) under /<namespace>.

limo_driver.cpp creates its topics with a leading slash (/odom, /imu, /limo_status,
/cmd_vel), so PushRosNamespace can't move them; they're remapped explicitly instead.
Odometry drives <namespace>/base_footprint (REP-105, ground level); description.launch.py
publishes base_footprint -> base_link from the URDF. tf/tf_static stay global so several
robots can share one TF tree, with every frame prefixed by the namespace.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import EnvironmentVariable, LaunchConfiguration
from launch_ros.actions import PushRosNamespace, SetParameter, SetRemap

ABSOLUTE_TOPICS = ['odom', 'imu', 'limo_status', 'cmd_vel']


def _setup(context):
    ns = LaunchConfiguration('namespace').perform(context).strip('/')
    port = LaunchConfiguration('port_name').perform(context)
    vendor_launch = os.path.join(
        get_package_share_directory('limo_base'), 'launch', 'limo_base.launch.py')
    return [GroupAction([
        PushRosNamespace(ns),
        SetRemap('tf', '/tf'),
        SetRemap('tf_static', '/tf_static'),
        SetParameter(name='imu_frame', value=f'{ns}/imu_link'),
        *[SetRemap(f'/{t}', f'/{ns}/{t}') for t in ABSOLUTE_TOPICS],
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(vendor_launch),
            launch_arguments={
                'port_name': port,
                'odom_frame': f'{ns}/odom',
                'base_frame': f'{ns}/base_footprint',
            }.items(),
        ),
    ])]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('namespace', default_value=EnvironmentVariable('LIMO_NAMESPACE', default_value='limo')),
        DeclareLaunchArgument('port_name', default_value=EnvironmentVariable('LIMO_BASE_PORT', default_value='ttyTHS0'),
                              description='serial port of the motor controller, without /dev/'),
        OpaqueFunction(function=_setup),
    ])
