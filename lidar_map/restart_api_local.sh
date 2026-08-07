#!/usr/bin/env bash
set -eo pipefail
set +u
source /opt/ros/jazzy/setup.bash 2>/dev/null || true
source "$HOME/ws_ros2/install/setup.bash" 2>/dev/null || true
set -u

echo "--- kill old ---"
pkill -9 -f '/home/pi/robot_nav/lidar_map/main.py' || true
pkill -9 -f '/home/pi/robot_nav/lidar_map/drive_encoders.py' || true
pkill -9 -f 'lidar_map_server.py' || true
# Kill whatever holds :8765
if command -v fuser >/dev/null; then
  fuser -k 8765/tcp 2>/dev/null || true
fi
ss -ltnp 2>/dev/null | grep 8765 || netstat -ltnp 2>/dev/null | grep 8765 || true
sleep 2

echo "--- start ---"
bash /home/pi/robot_nav/lidar_map/start_drive_map.sh
sleep 5

echo "--- check ---"
curl -s -m 3 -X POST http://127.0.0.1:8765/api/cmd \
  -H 'Content-Type: application/json' \
  -d '{"vx":0.1,"vy":0,"w":0}' || echo CMD_FAIL
echo
curl -s -m 2 -X POST http://127.0.0.1:8765/api/cmd/stop >/dev/null || true
pgrep -af '/home/pi/robot_nav/lidar_map/(main|drive_encoders)' | grep -v grep || echo NO_PROCS
curl -s -m 2 -o /dev/null -w "http=%{http_code}\n" http://127.0.0.1:8765/ || true
echo ALL_DONE
