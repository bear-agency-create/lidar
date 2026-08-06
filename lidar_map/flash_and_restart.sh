#!/bin/bash
set -e
export PATH="$HOME/bin:$PATH"
pkill -9 -f drive_encoders || true
sleep 1
arduino-cli compile --fqbn arduino:avr:mega /home/pi/robot_nav/arduino/MecanumTeleopBridge
arduino-cli upload -p /dev/ttyUSB0 --fqbn arduino:avr:mega /home/pi/robot_nav/arduino/MecanumTeleopBridge
echo FLASH_OK
bash /home/pi/robot_nav/lidar_map/start_drive_map.sh
sleep 5
curl -s -o /dev/null -w "http=%{http_code}\n" --max-time 3 http://127.0.0.1:8765/ || true
pgrep -af 'drive_encoders|lidar_map/main.py' | grep -v grep || true
