#!/bin/bash
# Removes the ROS 2 Jazzy container stack from this Limo.
#
#   sudo ./uninstall.sh            stop and remove the command and units; keep the config,
#                                  the maps and the Docker image
#   sudo ./uninstall.sh --purge    also remove /etc/limo-jazzy, /var/lib/limo-jazzy and the image
set -euo pipefail

REPO=$(cd "$(dirname "$0")" && pwd)
PURGE=0
[ "${1:-}" = --purge ] && PURGE=1
[ "$(id -u)" -eq 0 ] || { echo "run with sudo" >&2; exit 1; }

if [ -x /usr/local/bin/limo-jazzy ]; then
  /usr/local/bin/limo-jazzy disable >/dev/null 2>&1 || true
  /usr/local/bin/limo-jazzy stop >/dev/null 2>&1 || true
fi
rm -f /usr/local/bin/limo-jazzy /etc/systemd/system/limo-jazzy@.service /etc/systemd/system/limo-jazzy.target
rm -rf /usr/local/lib/limo-jazzy
systemctl daemon-reload
echo "removed the limo-jazzy command and units"

if [ $PURGE = 1 ]; then
  IMAGE=$(grep -oP '^DEFAULT_IMAGE=\K\S+' "$REPO/bin/limo-jazzy-run")
  rm -rf /etc/limo-jazzy /var/lib/limo-jazzy
  docker image rm "$IMAGE" 2>/dev/null || true
  echo "removed the config, maps and image $IMAGE"
else
  echo "kept /etc/limo-jazzy, /var/lib/limo-jazzy/maps and the Docker image"
fi
