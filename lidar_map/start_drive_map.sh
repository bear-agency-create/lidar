#!/usr/bin/env bash
# Карта + пульт: лидар + drive_encoders + веб :8765
set -eo pipefail
set +u
source /opt/ros/jazzy/setup.bash
source ~/ws_ros2/install/setup.bash
set -u

STACK_DIR="${STACK_DIR:-$HOME/robot_nav/lidar_map}"
if [ ! -d "$STACK_DIR" ]; then
  # fallback: flat copy of main modules next to lidar_map_server.py
  STACK_DIR="$HOME"
fi

# Prefer stable udev symlinks (port 1=LiDAR, port 2=Mega on this robot)
if [ -e /dev/ttyLIDAR ] && [ -e /dev/ttyMEGA ]; then
  LIDAR_DEV="${LIDAR_DEV:-/dev/ttyLIDAR}"
  MEGA_DEV="${MEGA_DEV:-/dev/ttyMEGA}"
elif [ -e /dev/ttyUSB0 ] && [ -e /dev/ttyUSB1 ]; then
  # Fallback if symlinks missing: USB0=LiDAR, USB1=Mega (verified)
  LIDAR_DEV="${LIDAR_DEV:-/dev/ttyUSB0}"
  MEGA_DEV="${MEGA_DEV:-/dev/ttyUSB1}"
else
  LIDAR_DEV="${LIDAR_DEV:-/dev/ttyLIDAR}"
  MEGA_DEV="${MEGA_DEV:-/dev/ttyMEGA}"
fi

pkill -9 -f 'lidar_map/main.py|lidar_map_server.py|server.py' 2>/dev/null || true
pkill -9 -f 'drive_encoders.py|mega_teleop_bridge.py' 2>/dev/null || true
pkill -9 -f cspc_lidar 2>/dev/null || true
pkill -9 -f robot_driver_node 2>/dev/null || true
fuser -k 8765/tcp 2>/dev/null || true
sleep 1

echo "LIDAR=$LIDAR_DEV MEGA=$MEGA_DEV STACK=$STACK_DIR"
mkdir -p ~/robot_nav/logs ~/robot_nav/maps

nohup ros2 run cspc_lidar cspc_lidar --ros-args \
  -r __node:=cspc_lidar \
  -p port:="$LIDAR_DEV" \
  -p frame_id:=laser_frame \
  -p baudrate:=230400 \
  -p frequency:=8.0 \
  -p version:=4 \
  -p reversion:=true \
  -p auto_reconnect:=true \
  > /tmp/lidar_usb0.log 2>&1 &

export MEGA_DEV
if [ -f "$STACK_DIR/drive_encoders.py" ]; then
  DRIVE_PY="$STACK_DIR/drive_encoders.py"
elif [ -f "$HOME/robot_nav/drive_encoders.py" ]; then
  DRIVE_PY="$HOME/robot_nav/drive_encoders.py"
else
  DRIVE_PY="$HOME/robot_nav/mega_teleop_bridge.py"
fi
nohup env MEGA_DEV="$MEGA_DEV" python3 "$DRIVE_PY" \
  > /tmp/mega_teleop.log 2>&1 &

sleep 2

if [ -f "$STACK_DIR/main.py" ]; then
  MAP_PY="$STACK_DIR/main.py"
elif [ -f "$HOME/lidar_map_server.py" ]; then
  MAP_PY="$HOME/lidar_map_server.py"
else
  MAP_PY="$STACK_DIR/server.py"
fi
nohup python3 "$MAP_PY" > /tmp/lidar_map.log 2>&1 &
sleep 2

echo "UI: http://$(hostname -I | awk '{print $1}'):8765/"
curl -s -o /dev/null -w "http=%{http_code}\n" http://127.0.0.1:8765/ || true
pgrep -af 'drive_encoders|mega_teleop' | grep -v grep || echo "WARN: teleop bridge not running"
tail -5 /tmp/lidar_map.log 2>/dev/null || true
tail -3 /tmp/mega_teleop.log 2>/dev/null || true
timeout 3 ros2 topic hz /scan 2>&1 | head -3 || true
