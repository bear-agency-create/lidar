#!/bin/bash
set -e
export PATH="$HOME/bin:$PATH"
set +u
source /opt/ros/jazzy/setup.bash
source /home/pi/ws_ros2/install/setup.bash
set -u

MEGA=$(readlink -f /dev/ttyMEGA 2>/dev/null || true)
LIDAR=$(readlink -f /dev/ttyLIDAR 2>/dev/null || true)
[ -n "$MEGA" ] || MEGA=/dev/ttyUSB0
[ -n "$LIDAR" ] || LIDAR=/dev/ttyUSB1
echo "MEGA=$MEGA LIDAR=$LIDAR"

pkill -9 -f drive_encoders.py || true
pkill -9 -f 'lidar_map/main.py' || true
pkill -9 -f cspc_lidar || true
fuser -k "$MEGA" "$LIDAR" /dev/ttyUSB0 /dev/ttyUSB1 2>/dev/null || true
sleep 1

arduino-cli compile --fqbn arduino:avr:mega /home/pi/robot_nav/arduino/MecanumTeleopBridge
arduino-cli upload -p "$MEGA" --fqbn arduino:avr:mega /home/pi/robot_nav/arduino/MecanumTeleopBridge
echo FLASH_OK
sleep 2

MEGA_DEV=/dev/ttyMEGA LIDAR_DEV=/dev/ttyLIDAR bash /home/pi/robot_nav/lidar_map/start_drive_map.sh
sleep 4
curl -s -o /dev/null -w "http=%{http_code}\n" http://127.0.0.1:8765/ || true
grep -aE 'WSCALE_OK|drive_encoders on|READY|PIDV' /tmp/mega_teleop.log | tail -6 || true
echo "--- lidar ---"
tail -8 /tmp/lidar_usb0.log || true
timeout 5 ros2 topic hz /scan 2>&1 | head -5 || true
pgrep -af 'cspc_lidar|drive_encoders|lidar_map/main' | grep -v grep || true
echo "MAX_POWER_LIDAR_READY UI=http://$(hostname -I | awk '{print $1}'):8765/"
