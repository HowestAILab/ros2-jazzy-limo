# ROS 2 Jazzy image for the AgileX Limo Pro. Runs on the robot's own JetPack 5 kernel;
# the Limo stack needs no CUDA.
#   docker build -t ros2-jazzy-limo:<YYYYMMDD> .
# The tag is the build date; bump DEFAULT_IMAGE in bin/limo-jazzy-run to match.
FROM ros:jazzy-ros-base

ARG DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends \
      ros-jazzy-rmw-cyclonedds-cpp \
      ros-jazzy-robot-state-publisher ros-jazzy-joint-state-publisher ros-jazzy-xacro \
      ros-jazzy-tf2-ros ros-jazzy-tf2-sensor-msgs ros-jazzy-tf2-msgs \
      ros-jazzy-image-transport ros-jazzy-image-transport-plugins ros-jazzy-compressed-image-transport \
      ros-jazzy-cv-bridge ros-jazzy-image-publisher ros-jazzy-camera-info-manager \
      ros-jazzy-backward-ros ros-jazzy-diagnostic-updater ros-jazzy-statistics-msgs \
      ros-jazzy-slam-toolbox ros-jazzy-nav2-map-server ros-jazzy-foxglove-bridge \
      libgflags-dev nlohmann-json3-dev libgoogle-glog-dev libusb-1.0-0-dev libudev-dev libeigen3-dev \
      libdw-dev \
    && rm -rf /var/lib/apt/lists/*

# YDLidar SDK (static library + CMake config); its tests and samples don't build on 24.04.
COPY src/YDLidar-SDK /tmp/YDLidar-SDK
RUN cmake -S /tmp/YDLidar-SDK -B /tmp/ydsdk-build -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF \
      -DBUILD_TEST=OFF -DBUILD_EXAMPLES=OFF -DBUILD_CSHARP=OFF \
    && cmake --build /tmp/ydsdk-build -j"$(nproc)" && cmake --install /tmp/ydsdk-build \
    && rm -rf /tmp/YDLidar-SDK /tmp/ydsdk-build

COPY src /opt/limo_ws/src
RUN rm -rf /opt/limo_ws/src/YDLidar-SDK \
    && source /opt/ros/jazzy/setup.bash \
    && cd /opt/limo_ws \
    && MAKEFLAGS="-j2" colcon build --merge-install --install-base /opt/limo_ws/install \
         --cmake-args -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF \
    && rm -rf build log

COPY entrypoint.sh /usr/local/bin/limo-entrypoint
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
ENTRYPOINT ["/usr/local/bin/limo-entrypoint"]
CMD ["bash"]
