"""Orbbec Dabai depth camera -> /<namespace>/limo_camera/...

The vendor dabai.launch.py already pushes a `camera_name` namespace (limo_camera), so
pushing <namespace> on top gives /<namespace>/limo_camera/<stream>/image_raw.

The color/depth frame ids are derived from camera_name in ob_camera_node.cpp and can't be
prefixed through camera_name without doubling the topic prefix, so they are overridden
through their own parameters. Known gap: the camera's link frame (limo_camera_link) is
computed in C++ without a parameter, so it stays unprefixed and is not attached to
base_link. Add a measured static transform if you need the camera in the robot's TF tree.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import EnvironmentVariable, LaunchConfiguration
from launch_ros.actions import PushRosNamespace, SetParameter, SetRemap

CAMERA_NAME = 'limo_camera'


def _setup(context):
    ns = LaunchConfiguration('namespace').perform(context).strip('/')
    fps = LaunchConfiguration('fps').perform(context)
    dabai_launch = os.path.join(get_package_share_directory('orbbec_camera'), 'launch', 'dabai.launch.py')

    frame_params = []
    for stream in ('color', 'depth'):
        frame_params += [
            SetParameter(name=f'{stream}_optical_frame_id', value=f'{ns}/{CAMERA_NAME}_{stream}_optical_frame'),
            SetParameter(name=f'{CAMERA_NAME}_{stream}_frame_id', value=f'{ns}/{CAMERA_NAME}_{stream}_frame'),
        ]

    return [GroupAction([
        PushRosNamespace(ns),
        SetRemap('tf', '/tf'),
        SetRemap('tf_static', '/tf_static'),
        *frame_params,
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(dabai_launch),
            launch_arguments={
                'camera_name': CAMERA_NAME,
                'depth_registration': 'false',
                'enable_color': 'true',
                'enable_depth': 'true',
                'enable_ir': 'false',
                'enable_point_cloud': 'false',
                'color_fps': fps,
                'depth_fps': fps,
            }.items(),
        ),
    ])]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('namespace', default_value=EnvironmentVariable('LIMO_NAMESPACE', default_value='limo')),
        DeclareLaunchArgument('fps', default_value=EnvironmentVariable('LIMO_CAMERA_FPS', default_value='15')),
        OpaqueFunction(function=_setup),
    ])
