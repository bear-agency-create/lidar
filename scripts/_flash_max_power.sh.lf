#!/bin/bash
set -e
export PATH="$HOME/bin:$PATH"
MEGA=$(readlink -f /dev/ttyMEGA 2>/dev/null || echo /dev/ttyUSB0)
echo "MEGA=$MEGA"
pkill -9 -f drive_encoders.py || true
pkill -9 -f lidar_map/main.py || true
pkill -9 -f cspc_lidar || true
fuser -k "$MEGA" /dev/ttyUSB0 /dev/ttyUSB1 2>/dev/null || true
sleep 2
arduino-cli compile --fqbn arduino:avr:mega /home/pi/robot_nav/arduino/MecanumTeleopBridge
arduino-cli upload -p "$MEGA" --fqbn arduino:avr:mega /home/pi/robot_nav/arduino/MecanumTeleopBridge
echo FLASH_OK
sleep 2
MEGA_DEV=/dev/ttyMEGA LIDAR_DEV=/dev/ttyLIDAR bash /home/pi/robot_nav/lidar_map/start_drive_map.sh
sleep 4
grep -aE 'WSCALE_OK|drive_encoders on|HARD_STOP' /tmp/mega_teleop.log | tail -10
curl -s -o /dev/null -w "http=%{http_code}\n" http://127.0.0.1:8765/
echo "MAX: STRAIGHT_PWM=255 CRAB=255 WSCALE=255"
echo "UI=http://$(hostname -I | awk '{print $1}'):8765/"
