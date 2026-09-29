#!/bin/bash
# Sources ROS 2 Jazzy + the Limo workspace, then runs the given command.
set -e
source /opt/ros/jazzy/setup.bash
source /opt/limo_ws/install/setup.bash
exec "$@"
