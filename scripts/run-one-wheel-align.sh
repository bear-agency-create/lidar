#!/bin/bash
set -e
ROOT=/home/pi/robot_nav
echo raspberry | sudo -S systemctl stop robot-nav-watchdog.timer || true
echo raspberry | sudo -S systemctl stop robot-nav.service || true
pkill -9 -f 'lidar_map/drive_encoders.py' || true
pkill -9 -f 'lidar_map/main.py' || true
fuser -k /dev/ttyMEGA 2>/dev/null || true
fuser -k /dev/ttyUSB1 2>/dev/null || true
sleep 2

export PATH="$HOME/bin:$PATH"
echo "=== flash ONE_WHEEL firmware ==="
arduino-cli compile --fqbn arduino:avr:mega "$ROOT/arduino/MecanumTeleopBridge"
MEGA="$(readlink -f /dev/ttyMEGA 2>/dev/null || echo /dev/ttyUSB1)"
arduino-cli upload -p "$MEGA" --fqbn arduino:avr:mega "$ROOT/arduino/MecanumTeleopBridge"
sleep 2

echo "=== sequential one-wheel encoder align ==="
python3 "$ROOT/lidar_map/tools/one_wheel_align.py" /dev/ttyMEGA | tee /tmp/one_wheel_align.out

echo "=== restart stack ==="
echo raspberry | sudo -S systemctl start robot-nav.service
sleep 5
echo raspberry | sudo -S systemctl start robot-nav-watchdog.timer
pgrep -af 'main.py|drive_encoders' | grep -v grep || true
echo "=== cal ==="
cat "$ROOT/lidar_map/drive_cal.json"
echo ONE_WHEEL_DONE
