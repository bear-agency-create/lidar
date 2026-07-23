#!/usr/bin/env bash
# Карта + пульт: лидар + mega_teleop_bridge + веб :8765
set -eo pipefail
set +u
source /opt/ros/jazzy/setup.bash
source ~/ws_ros2/install/setup.bash
set -u

if [ -e /dev/ttyUSB0 ] && [ -e /dev/ttyUSB1 ]; then
  LIDAR_DEV="${LIDAR_DEV:-/dev/ttyUSB1}"
  MEGA_DEV="${MEGA_DEV:-/dev/ttyUSB0}"
else
  LIDAR_DEV="${LIDAR_DEV:-/dev/ttyLIDAR}"
  MEGA_DEV="${MEGA_DEV:-/dev/ttyMEGA}"
fi

pkill -9 -f lidar_map_server.py 2>/dev/null || true
pkill -9 -f mega_teleop_bridge.py 2>/dev/null || true
pkill -9 -f cspc_lidar 2>/dev/null || true
pkill -9 -f robot_driver_node 2>/dev/null || true
fuser -k 8765/tcp 2>/dev/null || true
sleep 1

echo "LIDAR=$LIDAR_DEV MEGA=$MEGA_DEV"

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
nohup env MEGA_DEV="$MEGA_DEV" python3 ~/robot_nav/mega_teleop_bridge.py \
  > /tmp/mega_teleop.log 2>&1 &

sleep 2
nohup python3 ~/lidar_map_server.py > /tmp/lidar_map.log 2>&1 &
sleep 2

echo "UI: http://$(hostname -I | awk '{print $1}'):8765/"
curl -s -o /dev/null -w "http=%{http_code}\n" http://127.0.0.1:8765/ || true
pgrep -af mega_teleop_bridge | grep -v grep || echo "WARN: teleop bridge not running"
tail -3 /tmp/mega_teleop.log 2>/dev/null || true
timeout 3 ros2 topic hz /scan 2>&1 | head -3 || true
