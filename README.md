# ros2-jazzy-limo

Run the **AgileX Limo Pro** on **ROS 2 Jazzy**, in Docker, without reinstalling the robot.

The Limo Pro ships with Ubuntu 20.04, JetPack 5 and ROS 2 Foxy. Jazzy needs Ubuntu 24.04, and
Foxy and Jazzy machines can't share a ROS network: Foxy nodes crash on Jazzy discovery traffic
([docs/dds.md](docs/dds.md#ros-2-distributions-dont-mix)). This repo builds the Limo's drivers for
Jazzy in a container image and runs each part of the robot as its own container. The vendor
Foxy install stays untouched, and removing this stack puts the robot back as it was.

## What runs

| Component | What | Topics (namespace `limo`) |
|---|---|---|
| `base` | motor controller, odometry, IMU (`limo_base`) | `/limo/odom`, `/limo/imu`, `/limo/cmd_vel`, `/limo/limo_status` |
| `lidar` | YDLidar (`ydlidar_ros2_driver`) | `/limo/scan` |
| `camera` | Orbbec depth camera (`orbbec_camera`) | `/limo/limo_camera/color/image_raw`, `.../depth/image_raw` |
| `compressor` | compressed color image | `/limo/limo_camera/color/image/compressed` |
| `description` | URDF, `robot_state_publisher`, `joint_state_publisher` | `/limo/robot_description`, TF |
| `mapping` | slam_toolbox, build a map (optional) | `/limo/map` |
| `localization` | slam_toolbox, localize in a saved map (optional) | `/limo/map` |
| `bridge` | `foxglove_bridge` WebSocket for Foxglove Studio (optional, port 8765) | - |

Topics:
- **Namespace:** every topic is under `/<namespace>`.
- **TF:** every frame is prefixed `<namespace>/`. `tf`/`tf_static` stay global, so several
  robots can share one TF tree: `<ns>/odom -> <ns>/base_footprint -> <ns>/base_link -> ...`

Containers:
- **Names:** `ros2-jazzy-<domain>-limo-<component>-node`. The bridge is `ros2-jazzy-<domain>-limo-bridge`.
- **Image:** `ros2-jazzy-limo:<build date>`.
- **Units:** each container is a systemd unit `limo-jazzy@<component>`. It restarts when it
  stops and writes its log to the journal.

## Install

On the Limo, as the normal user (`agilex` on a stock Limo Pro):

```bash
git clone <this repository> ~/ros2-jazzy-limo
cd ~/ros2-jazzy-limo
sudo ./install.sh                       # Docker, units, config; builds the image (20-40 min)
sudo nano /etc/limo-jazzy/limo-jazzy.env
sudo limo-jazzy start                   # start now
sudo limo-jazzy enable                  # and at every boot
```

- **Requirements:** a Limo Pro with the vendor image (JetPack 5, `/dev/ttyTHS0`, the `/dev/ydlidar`
  and Orbbec udev rules), internet for the build, and about 10 GB free disk space.
- **Hardware:** only one program can use the base, lidar and camera. **Stop any vendor Foxy launch
  (e.g. `limo_start.launch.py`) first.**
- **Updating:** after `git pull`, run `sudo ./install.sh` again. It keeps your config, and builds a
  new image if the pinned tag changed.

## Use

```bash
sudo limo-jazzy start                   # components from LIMO_COMPONENTS (+ bridge if enabled)
sudo limo-jazzy start --no-bridge       # same, without foxglove_bridge
sudo limo-jazzy start --bridge          # same, with foxglove_bridge
sudo limo-jazzy start lidar description # only these (+ bridge if enabled)
sudo limo-jazzy stop                    # everything
sudo limo-jazzy restart                 # after editing the config
sudo limo-jazzy enable [--no-bridge]    # what starts at boot
sudo limo-jazzy disable
limo-jazzy status
limo-jazzy logs lidar -f
limo-jazzy ros2 topic list              # the Jazzy ros2 CLI, in a container
limo-jazzy shell                        # interactive Jazzy shell
limo-jazzy dds                          # effective DDS config
```

Don't use the host's Foxy `ros2` command while the stack runs; see [docs/dds.md](docs/dds.md).

### foxglove_bridge on or off

- **Default:** set `LIMO_FOXGLOVE_BRIDGE=true|false` in the config. It applies to `start`, `restart` and `enable`.
- **One-off:** `--bridge` / `--no-bridge` override it for a single run.
- **Stopping only the bridge:** `start --no-bridge` also stops a bridge that's already running.
  To stop just the bridge and leave the rest running: `sudo limo-jazzy stop bridge`.
- **Connecting:** in Foxglove Studio, open `ws://<robot-ip>:8765` (`LIMO_FOXGLOVE_PORT`).

### SLAM

Build a map with the `mapping` component while you drive the robot, e.g. with the remote control:

```bash
sudo limo-jazzy start base lidar description mapping
```

Save the map from any shell. Maps go to `/var/lib/limo-jazzy/maps`, which every container has mounted:

```bash
limo-jazzy ros2 service call /slam_toolbox/serialize_map slam_toolbox/srv/SerializePoseGraph \
  "{filename: '/var/lib/limo-jazzy/maps/my-map'}"
```

Localize in that map later:
1. Set `LIMO_SLAM_MAP=/var/lib/limo-jazzy/maps/my-map` in the config.
2. Put `localization` in `LIMO_COMPONENTS`.
3. Run `sudo limo-jazzy restart`.

## Configuration

**Everything is in one file, `/etc/limo-jazzy/limo-jazzy.env`.** It's created from
[limo-jazzy.env.example](limo-jazzy.env.example) on the first install and never overwritten after
that. Every setting is described in the file.

| Setting | Default | What |
|---|---|---|
| `LIMO_NAMESPACE` | `limo` | topic namespace and TF prefix |
| `ROS_DOMAIN_ID` | `0` | ROS domain (also part of the container names) |
| `LIMO_COMPONENTS` | `base lidar camera compressor description` | what `start` and `enable` run |
| `LIMO_FOXGLOVE_BRIDGE`, `LIMO_FOXGLOVE_PORT` | `true`, `8765` | foxglove_bridge |
| `LIMO_DDS_PEERS` | empty | **static DDS peer list**, see below |
| `LIMO_DDS_INTERFACE` | `wlan0` | interface DDS binds to |
| `LIMO_DDS_MULTICAST` | `spdp` | multicast discovery on/off |
| `LIMO_CYCLONEDDS_URI` | empty | your own CycloneDDS XML, overrides the three above |
| `LIMO_BASE_PORT`, `LIMO_CAMERA_FPS` | `ttyTHS0`, `15` | hardware |
| `LIMO_GROUND_CLEARANCE`, `LIMO_MESH_DETAIL` | `0.15`, `low` | URDF |
| `LIMO_SLAM_MAP` | empty | map for `localization` |

After a change: `sudo limo-jazzy restart`.

### Peer list

When multicast doesn't work, which is common on Wi-Fi, list the other ROS 2 machines here:

```bash
LIMO_DDS_PEERS="192.168.1.10 192.168.1.20 my-laptop.local"
```

- **Format:** addresses or hostnames, separated by spaces.
- **Several networks:** include the addresses from every network the robot joins. Unreachable
  peers are harmless.
- **Checking it:** `limo-jazzy dds` shows the resulting CycloneDDS XML.
- **Your own XML:** set `LIMO_CYCLONEDDS_URI=file:///etc/limo-jazzy/cyclonedds.xml` to use your own file.
- More in [docs/dds.md](docs/dds.md).

## Repository layout

| Path | What |
|---|---|
| `Dockerfile`, `entrypoint.sh` | the `ros2-jazzy-limo` image |
| `src/` | vendor packages ported to Jazzy ([docs/porting.md](docs/porting.md)), plus `limo_jazzy_bringup` (launch files) |
| `bin/limo-jazzy` | the command above (installed in `/usr/local/bin`) |
| `bin/limo-jazzy-run` | runs one component's container, used by the units (installed in `/usr/local/lib/limo-jazzy`) |
| `systemd/` | `limo-jazzy@.service` (one instance per component) and `limo-jazzy.target` |
| `limo-jazzy.env.example` | the configuration template |
| `install.sh`, `uninstall.sh` | install / remove (`--purge` also removes config, maps and image) |

## Rebuilding the image

The image tag is the build date and is pinned as `DEFAULT_IMAGE` in `bin/limo-jazzy-run`. After
changing `src/` or the `Dockerfile`:

1. Set a new date in `DEFAULT_IMAGE`.
2. Run `sudo ./install.sh`, which builds the new tag.
3. Run `sudo limo-jazzy restart`.

## Licenses

`src/` contains third-party packages under their own licenses, some with the changes listed in
[docs/porting.md](docs/porting.md):

| Package | License |
|---|---|
| AgileX `limo_ros2` | per `package.xml`; some packages declare none |
| Orbbec `OrbbecSDK_ROS2` | Apache-2.0 (`package.xml`); includes the prebuilt Orbbec SDK libraries |
| YDLIDAR `ydlidar_ros2_driver`, `YDLidar-SDK` | see their `LICENSE.txt` |

Check these before making a fork public.
