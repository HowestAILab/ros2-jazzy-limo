# Foxy -> Jazzy porting notes

`src/` holds the Limo's vendor packages, built for Jazzy inside the image:
- AgileX `limo_ros2`
- Orbbec `OrbbecSDK_ROS2`
- YDLIDAR `ydlidar_ros2_driver` and `YDLidar-SDK`

They're based on the versions on a Limo Pro (JetPack 5.1.2, Foxy). These changes were needed for Jazzy:

| Package | Change | Why |
|---|---|---|
| `limo_base` | `tf2_geometry_msgs/tf2_geometry_msgs.h` -> `.hpp` | header renamed since Humble |
| `limo_base` | `tf2_geometry_msgs` added to `CMakeLists.txt` (`find_package`, `ament_target_dependencies`) and `package.xml` | Foxy got it transitively through tf2 |
| `limo_base` | `declare_parameter()` calls given typed defaults | declaring without a default is no longer allowed |
| `ydlidar_ros2_driver` | `declare_parameter()` calls given the existing variable as default | same |
| `YDLidar-SDK` | built with `-DBUILD_TEST=OFF -DBUILD_EXAMPLES=OFF` | its tests don't compile against gtest on Ubuntu 24.04 |

Details:
- **`limo_base` defaults** keep the behaviour: `port_name` string, frames as strings, `pub_odom_tf=true`,
  `use_mcnamu=false`, `control_rate=50`. The launch files set every parameter explicitly anyway.
- **Types have to match in Jazzy.** A yaml integer given to a float parameter throws at startup. The
  lidar's `ydlidar.yaml` was checked parameter by parameter.

`orbbec_camera` 1.5.11, `limo_description`, `limo_msgs` and `limo_bringup` build unchanged.

`limo_jazzy_bringup` is new. It holds the namespaced launch files the containers run:
- `base`, `lidar`, `camera`, `description`
- `slam`, in mapping or localization mode

Each takes a `namespace` argument, which defaults to `$LIMO_NAMESPACE`.

## Known gaps

- **Camera TF:** the Orbbec driver computes `limo_camera_link` in C++ without a parameter, so that
  frame isn't prefixed with the namespace and isn't attached to `base_link`. Add a measured static
  transform if you need the camera in the robot's TF tree.
- **Low-poly meshes:** `limo_description` has decimated meshes in `meshes/visual_lowpoly/`
  (`LIMO_MESH_DETAIL=low`). They were made from the vendor CAD meshes, which are about 1.3M
  triangles; see the README in that directory.
