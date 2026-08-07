#!/usr/bin/env bash
# Run ON the Pi: clean restart, reinstall ALL packages from ~/lidar, flash Mega, verify teleop.
set -eo pipefail

echo '=== kill duplicates ==='
pkill -9 -f 'lidar_map/main.py' 2>/dev/null || true
pkill -9 -f 'drive_encoders.py' 2>/dev/null || true
pkill -9 -f 'mega_teleop_bridge.py' 2>/dev/null || true
pkill -9 -f cspc_lidar 2>/dev/null || true
fuser -k 8765/tcp 2>/dev/null || true
sleep 2

echo '=== ensure latest from GitHub ==='
REPO="${REPO:-https://github.com/bear-agency-create/lidar.git}"
CLONE="${CLONE:-$HOME/lidar}"
NAV="${NAV:-$HOME/robot_nav}"

if [ -d "$CLONE/.git" ]; then
  git -C "$CLONE" fetch origin
  git -C "$CLONE" reset --hard origin/main
else
  git clone "$REPO" "$CLONE"
fi

echo "GitHub: $(git -C "$CLONE" log -1 --oneline)"

rm -rf "$NAV/lidar_map" "$NAV/arduino" "$NAV/monitor" "$NAV/camera" "$NAV/scripts"
cp -a "$CLONE/lidar_map" "$NAV/lidar_map"
cp -a "$CLONE/arduino" "$NAV/arduino"
cp -a "$CLONE/monitor" "$NAV/monitor"
cp -a "$CLONE/camera" "$NAV/camera"
[ -d "$CLONE/scripts" ] && cp -a "$CLONE/scripts" "$NAV/scripts"
find "$NAV" -type f \( -name '*.sh' -o -name 'start' \) -exec chmod +x {} + 2>/dev/null || true

echo "files: lidar_map=$(find "$NAV/lidar_map" -type f | wc -l | tr -d ' ') monitor=$(find "$NAV/monitor" -type f | wc -l | tr -d ' ') arduino=$(find "$NAV/arduino" -type f | wc -l | tr -d ' ')"

echo '=== flash Mega ==='
if [ -e /dev/ttyMEGA ] || [ -e /dev/ttyUSB1 ]; then
  bash "$NAV/lidar_map/flash_smooth.sh"
else
  echo 'ERROR: no Mega serial device'
  exit 1
fi

echo '=== start stack ==='
export LIDAR_DEV="${LIDAR_DEV:-/dev/ttyLIDAR}" MEGA_DEV="${MEGA_DEV:-/dev/ttyMEGA}"
bash "$NAV/lidar_map/start_drive_map.sh"
sleep 4

echo '=== verify ==='
pgrep -af 'main.py|drive_encoders|cspc_lidar' | grep -v grep || true
curl -s -o /dev/null -w 'root=%{http_code}\n' http://127.0.0.1:8765/ || true
curl -s http://127.0.0.1:8765/api/health || true
echo

echo '=== teleop smoke ==='
CMD_JSON=$(curl -s -X POST http://127.0.0.1:8765/api/cmd \
  -H 'Content-Type: application/json' \
  -d '{"vx":0.25,"vy":0,"w":0}' || true)
echo "cmd=$CMD_JSON"
sleep 0.6
echo -n 'robot_cmd='; cat /tmp/robot_cmd.json 2>/dev/null || echo MISSING
echo
sleep 1
echo '--- mega log ---'
tail -20 /tmp/mega_teleop.log 2>/dev/null || true
curl -s -X POST http://127.0.0.1:8765/api/cmd/stop >/dev/null || true
sleep 0.3
tail -5 /tmp/mega_teleop.log 2>/dev/null || true
grep -E 'ROBOT_LENGTH|ROBOT_WIDTH|ROBOT_RADIUS' "$NAV/lidar_map/config.py" || true
echo DONE
