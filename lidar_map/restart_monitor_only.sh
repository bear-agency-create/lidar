#!/bin/bash
set -e
set +u
source /opt/ros/jazzy/setup.bash
source ~/ws_ros2/install/setup.bash
set -u

# Restart web/map only — do not touch Mega / drive_encoders
pkill -9 -f 'lidar_map/main.py' || true
fuser -k 8765/tcp 2>/dev/null || true
sleep 1

# Keep lidar if already up; start if missing
if ! pgrep -f 'cspc_lidar' >/dev/null 2>&1; then
  LIDAR_DEV=/dev/ttyLIDAR
  [ -e /dev/ttyLIDAR ] || LIDAR_DEV=/dev/ttyUSB0
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
  sleep 2
fi

nohup python3 /home/pi/robot_nav/lidar_map/main.py > /tmp/lidar_map.log 2>&1 &
sleep 4
curl -s -o /dev/null -w "http=%{http_code}\n" --max-time 3 http://127.0.0.1:8765/ || true
curl -s -o /dev/null -w "kiosk=%{http_code}\n" --max-time 3 http://127.0.0.1:8765/kiosk || true
grep -n "modePanel\|escortWait\|modeEscort" /home/pi/robot_nav/monitor/airport_ui.html | head -5
pgrep -af 'lidar_map/main.py|cspc_lidar' | grep -v grep || true
pgrep -af drive_encoders | grep -v grep || echo "Mega/drive skipped (as requested)"
