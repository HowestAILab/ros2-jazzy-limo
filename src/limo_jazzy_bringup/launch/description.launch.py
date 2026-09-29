"""robot_state_publisher + joint_state_publisher for the Limo, frames prefixed with <namespace>/.

Built from the vendor limo_four_diff.xacro with three adjustments:
- The decorative sensor links laser_link and depth_camera_link/depth_link are dropped. The
  real frames are <namespace>/laser_frame (lidar.launch.py) and limo_camera_link (the
  camera driver); the xacro's offsets for them don't match the Limo Pro hardware.
- base_footprint -> base_link z is the `ground_clearance` argument (vendor value 0.15).
  Odometry drives base_footprint, so the chain is odom -> base_footprint -> base_link.
- Mesh URIs become package:// so remote viewers (Foxglove, RViz) can resolve them, and with
  mesh_detail=low the decimated meshes in meshes/visual_lowpoly/ are used.
"""

import os
import subprocess
import sys
import xml.etree.ElementTree as ET

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import EnvironmentVariable, LaunchConfiguration
from launch_ros.actions import Node

DROP_LINKS = {'laser_link', 'depth_camera_link', 'depth_link'}
DROP_JOINTS = {'laser_joint', 'depth_camera_joint', 'depth_camera_to_camera_joint'}


def _robot_description(mesh_detail, ground_clearance):
    share = get_package_share_directory('limo_description')
    urdf = subprocess.check_output(['xacro', os.path.join(share, 'urdf', 'limo_four_diff.xacro')], text=True)
    root = ET.fromstring(urdf)

    for tag, drop in (('link', DROP_LINKS), ('joint', DROP_JOINTS)):
        for el in list(root.findall(tag)):
            if el.get('name') in drop:
                root.remove(el)
    for gazebo in list(root.findall('gazebo')):
        if gazebo.get('reference') in DROP_LINKS:
            root.remove(gazebo)

    for joint in root.findall('joint'):
        if joint.get('name') == 'base_joint':
            origin = joint.find('origin')
            x, y, _ = origin.get('xyz').split()
            origin.set('xyz', f'{x} {y} {ground_clearance}')

    prefix = f'file://{share}/meshes/'
    lowpoly = os.path.join(share, 'meshes', 'visual_lowpoly')
    for mesh in root.findall('.//mesh'):
        name = mesh.get('filename', '')
        if name.startswith(prefix):
            name = 'package://limo_description/meshes/' + name[len(prefix):]
            mesh.set('filename', name)
    if mesh_detail == 'low':
        for mesh in root.findall('./link/visual/geometry/mesh'):
            base = os.path.basename(mesh.get('filename', ''))
            if os.path.isfile(os.path.join(lowpoly, base)):
                mesh.set('filename', f'package://limo_description/meshes/visual_lowpoly/{base}')
            else:
                print(f'[description] no low-poly {base}, keeping the full mesh', file=sys.stderr)

    return ET.tostring(root, encoding='unicode')


def _setup(context):
    ns = LaunchConfiguration('namespace').perform(context).strip('/')
    description = _robot_description(
        LaunchConfiguration('mesh_detail').perform(context),
        float(LaunchConfiguration('ground_clearance').perform(context)))
    return [
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            namespace=ns,
            name='robot_state_publisher',
            parameters=[{'robot_description': description, 'frame_prefix': f'{ns}/'}],
            remappings=[('tf', '/tf'), ('tf_static', '/tf_static')],
        ),
        Node(
            package='joint_state_publisher',
            executable='joint_state_publisher',
            namespace=ns,
            name='joint_state_publisher',
            parameters=[{'robot_description': description}],
        ),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('namespace', default_value=EnvironmentVariable('LIMO_NAMESPACE', default_value='limo')),
        DeclareLaunchArgument('mesh_detail', default_value=EnvironmentVariable('LIMO_MESH_DETAIL', default_value='low'),
                              description="'low' (decimated) or 'high' (original CAD meshes)"),
        DeclareLaunchArgument('ground_clearance', default_value=EnvironmentVariable('LIMO_GROUND_CLEARANCE', default_value='0.15'),
                              description='base_footprint -> base_link z offset in metres (vendor value 0.15)'),
        OpaqueFunction(function=_setup),
    ])
