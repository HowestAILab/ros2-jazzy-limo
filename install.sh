#!/bin/bash
# Installs the ROS 2 Jazzy container stack on an AgileX Limo Pro.
#
#   sudo ./install.sh [--user NAME] [--no-build]
#
#   --user NAME   account the containers run as (default: the user who ran sudo)
#   --no-build    don't build the Docker image (build it later, see README)
#
# Installs Docker if needed, the limo-jazzy command, the systemd units and, only if it
# doesn't exist yet, /etc/limo-jazzy/limo-jazzy.env. Nothing is started; see the output
# for the next steps. Safe to run again after `git pull`.
set -euo pipefail

REPO=$(cd "$(dirname "$0")" && pwd)
RUN_USER=${SUDO_USER:-}
BUILD=1
while [ $# -gt 0 ]; do
  case $1 in
    --user) RUN_USER=$2; shift 2 ;;
    --no-build) BUILD=0; shift ;;
    *) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
  esac
done

[ "$(id -u)" -eq 0 ] || { echo "run with sudo" >&2; exit 1; }
[ -n "$RUN_USER" ] && [ "$RUN_USER" != root ] && id "$RUN_USER" >/dev/null 2>&1 \
  || { echo "pass --user NAME (a normal account that will run the containers)" >&2; exit 1; }
IMAGE=$(grep -oP '^DEFAULT_IMAGE=\K\S+' "$REPO/bin/limo-jazzy-run")

echo "== Docker"
if ! command -v docker >/dev/null; then
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io
fi
systemctl enable -q --now docker
id -nG "$RUN_USER" | grep -qw docker || { usermod -aG docker "$RUN_USER"; echo "added $RUN_USER to the docker group"; }
for g in dialout video plugdev; do
  if getent group $g >/dev/null && ! id -nG "$RUN_USER" | grep -qw $g; then usermod -aG $g "$RUN_USER"; fi
done

echo "== limo-jazzy command and units"
install -D -m 755 "$REPO/bin/limo-jazzy-run" /usr/local/lib/limo-jazzy/limo-jazzy-run
install -D -m 755 "$REPO/bin/limo-jazzy" /usr/local/bin/limo-jazzy
sed "s/@USER@/$RUN_USER/" "$REPO/systemd/limo-jazzy@.service" > /etc/systemd/system/limo-jazzy@.service
install -m 644 "$REPO/systemd/limo-jazzy.target" /etc/systemd/system/limo-jazzy.target
systemctl daemon-reload

echo "== config"
install -d -m 755 /etc/limo-jazzy
if [ -e /etc/limo-jazzy/limo-jazzy.env ]; then
  echo "kept existing /etc/limo-jazzy/limo-jazzy.env"
  cmp -s "$REPO/limo-jazzy.env.example" /etc/limo-jazzy/limo-jazzy.env.example \
    || echo "note: limo-jazzy.env.example changed; compare it with your config for new settings"
else
  install -m 644 "$REPO/limo-jazzy.env.example" /etc/limo-jazzy/limo-jazzy.env
  echo "created /etc/limo-jazzy/limo-jazzy.env"
fi
install -m 644 "$REPO/limo-jazzy.env.example" /etc/limo-jazzy/limo-jazzy.env.example
install -d -m 755 -o "$RUN_USER" -g "$(id -gn "$RUN_USER")" /var/lib/limo-jazzy/maps

if [ $BUILD = 1 ]; then
  if docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "== image $IMAGE already present"
  else
    echo "== building $IMAGE (about 20-40 minutes on an Orin Nano)"
    DOCKER_BUILDKIT=0 docker build -t "$IMAGE" "$REPO"
  fi
fi

echo "== hardware"
for dev in /dev/ttyTHS0 /dev/ydlidar; do
  [ -e $dev ] && echo "ok $dev" || echo "WARNING: $dev missing (motor controller / lidar udev rule)"
done
ls /etc/udev/rules.d/*orbbec* >/dev/null 2>&1 && echo "ok Orbbec udev rule" \
  || echo "WARNING: no Orbbec udev rule in /etc/udev/rules.d (camera)"

cat <<EOF

Installed. Nothing was started. Next:
  sudo nano /etc/limo-jazzy/limo-jazzy.env    # namespace, domain, peers, bridge
  sudo limo-jazzy start                        # start now
  sudo limo-jazzy enable                       # start at every boot
Stop any other ROS stack (e.g. the vendor Foxy launch files) that uses the base, lidar or
camera first; only one program can own the hardware.
EOF
