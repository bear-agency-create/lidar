#!/usr/bin/env bash
# On the Pi: pull EVERYTHING from GitHub, flash Mega, restart, verify teleop.
set -eo pipefail

REPO="${REPO:-https://github.com/bear-agency-create/lidar.git}"
CLONE="${CLONE:-$HOME/lidar}"
NAV="${NAV:-$HOME/robot_nav}"

mkdir -p "$CLONE" "$NAV/logs" "$NAV/maps"

if [ -d "$CLONE/.git" ]; then
  git -C "$CLONE" fetch origin
  git -C "$CLONE" reset --hard origin/main
else
  git clone "$REPO" "$CLONE"
fi

echo "GitHub: $(git -C "$CLONE" log -1 --oneline)"

# Install ALL packages
rm -rf "$NAV/lidar_map"
cp -a "$CLONE/lidar_map" "$NAV/lidar_map"
rm -rf "$NAV/arduino" "$NAV/monitor" "$NAV/camera" "$NAV/scripts"
[ -d "$CLONE/arduino" ] && cp -a "$CLONE/arduino" "$NAV/arduino"
[ -d "$CLONE/monitor" ] && cp -a "$CLONE/monitor" "$NAV/monitor"
[ -d "$CLONE/camera" ] && cp -a "$CLONE/camera" "$NAV/camera"
[ -d "$CLONE/scripts" ] && cp -a "$CLONE/scripts" "$NAV/scripts"
[ -f "$CLONE/README.md" ] && cp -a "$CLONE/README.md" "$NAV/README.md"

find "$NAV" -type f \( -name '*.sh' -o -name 'start' \) -exec chmod +x {} + 2>/dev/null || true

echo "Installed packages:"
for d in lidar_map monitor arduino camera scripts; do
  if [ -d "$NAV/$d" ]; then
    echo "  OK $d ($(find "$NAV/$d" -type f | wc -l | tr -d ' ') files)"
  else
    echo "  MISSING $d"
  fi
done

TARGET="$NAV/lidar_map"

if [ -e /dev/ttyMEGA ] || [ -e /dev/ttyUSB1 ]; then
  echo '--- flash Mega (MecanumTeleopBridge) ---'
  if [ -x "$TARGET/flash_smooth.sh" ]; then
    bash "$TARGET/flash_smooth.sh" || echo "WARN: Mega flash failed — check arduino-cli / USB"
  else
    echo "WARN: flash_smooth.sh missing"
  fi
else
  echo "WARN: no Mega serial device — skip flash"
fi

echo '--- restart full stack ---'
export LIDAR_DEV="${LIDAR_DEV:-/dev/ttyLIDAR}" MEGA_DEV="${MEGA_DEV:-/dev/ttyMEGA}"
bash "$TARGET/start_drive_map.sh"
sleep 4

echo '--- footprint ---'
grep -E 'ROBOT_LENGTH|ROBOT_WIDTH|ROBOT_RADIUS' "$TARGET/config.py" || true

echo '--- teleop smoke test ---'
CMD_JSON=$(curl -s -X POST http://127.0.0.1:8765/api/cmd \
  -H 'Content-Type: application/json' \
  -d '{"vx":0.20,"vy":0,"w":0}' || true)
echo "cmd=$CMD_JSON"
sleep 0.5
echo -n "robot_cmd="; cat /tmp/robot_cmd.json 2>/dev/null || echo "MISSING"
echo
sleep 1
echo '--- mega log ---'
tail -15 /tmp/mega_teleop.log 2>/dev/null || tail -15 "$NAV/logs/lidar_map.log" 2>/dev/null || true
curl -s -X POST http://127.0.0.1:8765/api/cmd/stop >/dev/null || true
echo

echo '--- health ---'
curl -s http://127.0.0.1:8765/api/health || true
echo
curl -s -o /dev/null -w 'root=%{http_code} ' http://127.0.0.1:8765/ || true
curl -s -o /dev/null -w 'kiosk=%{http_code}\n' http://127.0.0.1:8765/kiosk || true
pgrep -af 'main.py|drive_encoders|cspc_lidar' | grep -v grep || true
echo DONE
