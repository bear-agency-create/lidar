#!/bin/bash
set -e
export PATH="$HOME/bin:$PATH"
set +u
source /opt/ros/jazzy/setup.bash
source "$HOME/ws_ros2/install/setup.bash"
set -u

pkill -9 -f cspc_lidar || true
pkill -9 -f drive_encoders.py || true
pkill -9 -f lidar_map/main.py || true
fuser -k 8765/tcp 2>/dev/null || true
fuser -k /dev/ttyUSB0 /dev/ttyMEGA 2>/dev/null || true
sleep 2

MEGA=/dev/ttyUSB0
if [ -e /dev/ttyMEGA ]; then MEGA=$(readlink -f /dev/ttyMEGA); fi
echo "MEGA=$MEGA"
ls -l /dev/ttyUSB* /dev/ttyMEGA 2>&1 || true

arduino-cli compile --fqbn arduino:avr:mega "$HOME/robot_nav/arduino/MecanumTeleopBridge"
arduino-cli upload -p "$MEGA" --fqbn arduino:avr:mega "$HOME/robot_nav/arduino/MecanumTeleopBridge"
echo FLASH_OK
sleep 2

STACK="$HOME/robot_nav/lidar_map"
nohup env MEGA_DEV="$MEGA" python3 "$STACK/drive_encoders.py" > /tmp/mega_teleop.log 2>&1 &
sleep 2
nohup python3 "$STACK/main.py" > /tmp/lidar_map.log 2>&1 &
sleep 3

echo "procs:"; pgrep -a python3 | grep -E 'drive_encoders|main.py' || true
echo "holders:"; fuser -v "$MEGA" 2>&1 || true
curl -s -o /dev/null -w "http=%{http_code}\n" http://127.0.0.1:8765/ || true
tail -6 /tmp/mega_teleop.log || true
echo "UI=http://$(hostname -I | awk '{print $1}'):8765/"
