# DDS discovery

The stack uses CycloneDDS (`rmw_cyclonedds_cpp`). Every container gets its DDS configuration from
`/etc/limo-jazzy/limo-jazzy.env`: `limo-jazzy-run` turns the settings into CycloneDDS XML and passes
it as `CYCLONEDDS_URI`. There's no separate XML file to maintain, unless you choose to use one.

## Where to set the peer list

**Only in `/etc/limo-jazzy/limo-jazzy.env`:**

```bash
LIMO_DDS_PEERS="192.168.1.10 192.168.1.20 my-laptop.local"
LIMO_DDS_INTERFACE=wlan0
LIMO_DDS_MULTICAST=spdp
```

Then apply and check it:

```bash
sudo limo-jazzy restart     # DDS reads its config only at startup
limo-jazzy dds              # the XML the containers actually get
```

- **Peers:** IP addresses or hostnames, separated by spaces.
  - List every machine the robot should talk to, on every network it may join. Unreachable
    peers are harmless: CycloneDDS keeps retrying them quietly.
  - Static peers are needed wherever multicast is blocked, which is common on Wi-Fi.
- **Interface:** bind by **name** (e.g. `wlan0`), not by IP. The same config then works on any
  Wi-Fi network the robot joins. Leave it empty to let CycloneDDS choose.
- **Multicast:** `spdp` (the default) uses multicast for discovery wherever it works, next to the
  static peers. `false` turns it off; `true` also uses it for data.

**Full control:** set `LIMO_CYCLONEDDS_URI` to your own XML.
- Point it at a file under `/etc/limo-jazzy/` (that directory is mounted read-only in every container):
  `LIMO_CYCLONEDDS_URI=file:///etc/limo-jazzy/cyclonedds.xml`.
- Or put inline XML in it.
- The three settings above are then ignored.

The other machines need this Limo's address in **their** peer lists too.

## ROS 2 distributions don't mix

Discovery information (`ros_discovery_info`) changed format in ROS 2 Iron: GIDs went from 24 to
16 bytes. The practical consequence:

| Talking to Jazzy from | Result |
|---|---|
| Jazzy | works |
| Humble | graph/discovery errors |
| Foxy | Foxy nodes crash as soon as they discover the Jazzy participant (`invalid data size`, `UnicodeDecodeError`, or a segfault) |

So:
- Run every machine on the same ROS domain with the same distribution.
- **Don't run the vendor Foxy stack and this Jazzy stack at the same time on one domain.** That
  includes a Foxy `ros2` CLI on the robot's host: use `limo-jazzy ros2 …` instead.
- If you still need Foxy machines, put them on a different `ROS_DOMAIN_ID`.

## Gotcha on Foxy: comments in the peer list

This matters only if you also maintain a CycloneDDS config for Foxy machines. CycloneDDS 0.7 (Foxy)
segfaults on XML comments inside `<Peers>`. The generated Jazzy config has no comments.
