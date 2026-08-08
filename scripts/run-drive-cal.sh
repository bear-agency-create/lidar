#!/bin/bash
set -e
ROOT=/home/pi/robot_nav
cd "$ROOT"

echo "=== stop stack (keep main/lidar if possible; free Mega) ==="
echo raspberry | sudo -S systemctl stop robot-nav-watchdog.timer || true
# Only kill drive bridge so Mega is free; map UI can stay up
pkill -f 'lidar_map/drive_encoders.py' || true
sleep 1
# Make sure nothing holds ttyMEGA
if fuser /dev/ttyMEGA >/dev/null 2>&1; then
  echo "ttyMEGA still busy — stopping full stack"
  echo raspberry | sudo -S systemctl stop robot-nav.service || true
  pkill -9 -f 'lidar_map/main.py' || true
  pkill -9 -f drive_encoders || true
  sleep 1
fi

export PATH="$HOME/bin:$PATH"
echo "=== flash Mega (flat default WSCALE) ==="
arduino-cli compile --fqbn arduino:avr:mega "$ROOT/arduino/MecanumTeleopBridge"
MEGA="$(readlink -f /dev/ttyMEGA 2>/dev/null || echo /dev/ttyUSB1)"
echo "FLASH_PORT=$MEGA"
arduino-cli upload -p "$MEGA" --fqbn arduino:avr:mega "$ROOT/arduino/MecanumTeleopBridge"
sleep 2

echo "=== motor_diag (quick) ==="
python3 "$ROOT/lidar_map/motor_diag.py" /dev/ttyMEGA | tee /tmp/motor_diag.out

echo "=== recalibrate_drive (moves robot) ==="
python3 "$ROOT/lidar_map/tools/recalibrate_drive.py" /dev/ttyMEGA | tee /tmp/recalibrate.out

echo "=== restart stack ==="
echo raspberry | sudo -S systemctl start robot-nav.service
sleep 5
echo raspberry | sudo -S systemctl start robot-nav-watchdog.timer
sleep 2
pgrep -af 'lidar_map/main.py|drive_encoders|cspc_lidar' | grep -v grep || true
echo "=== cal on disk ==="
cat "$ROOT/lidar_map/drive_cal.json"
echo
curl -s -o /dev/null -w "http=%{http_code}\n" http://127.0.0.1:8765/ || true
tail -n 30 /home/pi/robot_nav/logs/lidar_map.log | grep -E 'WSCALE|drive_encoders on|mega cal' || true
echo DONE_CAL
