#!/usr/bin/env bash
# One-command launcher: lidar map UI + optional smart camera.
set -eo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MAP_DIR="$ROOT_DIR/lidar_map"
CAM_DIR="$ROOT_DIR/camera"

echo "[stack] starting lidar + kiosk UI"
bash "$MAP_DIR/start_drive_map.sh"

if [ "${START_CAMERA:-1}" = "1" ]; then
  echo "[stack] starting camera"
  nohup bash "$CAM_DIR/start_camera.sh" >/tmp/camera.log 2>&1 &
  sleep 1
  pgrep -af "camera/main.py|python3 main.py" | grep -v grep || echo "[stack] WARN: camera process not found"
fi

echo "[stack] done"
