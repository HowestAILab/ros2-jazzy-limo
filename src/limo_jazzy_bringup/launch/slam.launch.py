"""slam_toolbox for the Limo, in mapping or localization mode.

  mode:=mapping        build a new map while you drive; save it with the slam_toolbox
                       serialize_map service (see the README)
  mode:=localization   localize against a saved map: map_file:=<path without extension>

Frames are <namespace>/map -> <namespace>/odom -> <namespace>/base_footprint. The map topic
is /<namespace>/map. Settings live in config/slam_toolbox.yaml.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import EnvironmentVariable, LaunchConfiguration
from launch_ros.actions import Node


def _setup(context):
    ns = LaunchConfiguration('namespace').perform(context).strip('/')
    mode = LaunchConfiguration('mode').perform(context)
    map_file = LaunchConfiguration('map_file').perform(context)
    if mode not in ('mapping', 'localization'):
        raise RuntimeError(f"mode must be 'mapping' or 'localization', not {mode!r}")
    if mode == 'localization' and not map_file:
        raise RuntimeError('mode:=localization needs map_file:=<saved map, without extension>')

    params = {
        'mode': mode,
        'odom_frame': f'{ns}/odom',
        'map_frame': f'{ns}/map',
        'base_frame': f'{ns}/base_footprint',
        'scan_topic': f'/{ns}/scan',
    }
    if mode == 'localization':
        params['map_file_name'] = map_file

    return [Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node' if mode == 'mapping' else 'localization_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[os.path.join(get_package_share_directory('limo_jazzy_bringup'), 'config', 'slam_toolbox.yaml'), params],
        remappings=[('map', f'/{ns}/map'), ('map_metadata', f'/{ns}/map_metadata')],
    )]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('namespace', default_value=EnvironmentVariable('LIMO_NAMESPACE', default_value='limo')),
        DeclareLaunchArgument('mode', default_value='mapping'),
        DeclareLaunchArgument('map_file', default_value=EnvironmentVariable('LIMO_SLAM_MAP', default_value='')),
        OpaqueFunction(function=_setup),
    ])
