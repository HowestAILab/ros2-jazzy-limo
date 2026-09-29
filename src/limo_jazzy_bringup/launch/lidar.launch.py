"""YDLidar -> /<namespace>/scan, with frame <namespace>/laser_frame.

Driver parameters come from the stock limo_bringup ydlidar.yaml (port /dev/ydlidar).
frame_id is message content, not a topic name, so it's overridden explicitly; it's put
in the node's own parameter list (after the yaml) because node parameters win over the
yaml, a scope-wide SetParameter would not. The static base_link -> laser_frame transform
uses the vendor's 2 cm offset from open_ydlidar_launch.py.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, OpaqueFunction
from launch.substitutions import EnvironmentVariable, LaunchConfiguration
from launch_ros.actions import Node, PushRosNamespace, SetRemap


def _setup(context):
    ns = LaunchConfiguration('namespace').perform(context).strip('/')
    params = os.path.join(get_package_share_directory('limo_bringup'), 'param', 'ydlidar.yaml')
    return [GroupAction([
        PushRosNamespace(ns),
        SetRemap('tf', '/tf'),
        SetRemap('tf_static', '/tf_static'),
        Node(
            package='ydlidar_ros2_driver',
            executable='ydlidar_ros2_driver_node',
            name='ydlidar_ros2_driver_node',
            output='screen',
            emulate_tty=True,
            parameters=[params, {'frame_id': f'{ns}/laser_frame'}],
        ),
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='static_tf_pub_laser',
            arguments=['--z', '0.02', '--frame-id', f'{ns}/base_link', '--child-frame-id', f'{ns}/laser_frame'],
        ),
    ])]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('namespace', default_value=EnvironmentVariable('LIMO_NAMESPACE', default_value='limo')),
        OpaqueFunction(function=_setup),
    ])
