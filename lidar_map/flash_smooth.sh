#!/bin/bash
set -euo pipefail
export PATH="$HOME/bin:$PATH"
MEGA="$(readlink -f /dev/ttyMEGA)"
pkill -f '/lidar_map/drive_encoders.py' || true
sleep 1
arduino-cli compile --fqbn arduino:avr:mega /home/pi/robot_nav/arduino/MecanumTeleopBridge
arduino-cli upload -p "$MEGA" --fqbn arduino:avr:mega /home/pi/robot_nav/arduino/MecanumTeleopBridge
echo FLASH_OK
sleep 2
set +u
source /opt/ros/jazzy/setup.bash
source /home/pi/ws_ros2/install/setup.bash
set -u
MEGA_DEV=/dev/ttyMEGA nohup python3 /home/pi/robot_nav/lidar_map/drive_encoders.py \
  >>/home/pi/robot_nav/logs/lidar_map.log 2>&1 &
sleep 4
pgrep -af drive_encoders.py || echo NO_DRIVE
grep -E 'READY|WSCALE|PIDV|mega cal|FRF_OK|FRB_OK' /home/pi/robot_nav/logs/lidar_map.log | tail -20
