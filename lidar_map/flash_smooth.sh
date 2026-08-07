#!/bin/bash
# Flash MecanumTeleopBridge to Mega. By default does NOT restart drive —
# call start_drive_map.sh after so only one drive_encoders owns the serial port.
set -euo pipefail
export PATH="$HOME/bin:$PATH"
RESTART_DRIVE="${RESTART_DRIVE:-0}"

if [ -e /dev/ttyMEGA ]; then
  MEGA="$(readlink -f /dev/ttyMEGA)"
elif [ -e /dev/ttyUSB1 ]; then
  MEGA=/dev/ttyUSB1
else
  echo "ERROR: no Mega serial device" >&2
  exit 1
fi

pkill -f '/lidar_map/drive_encoders.py' || true
sleep 1
arduino-cli compile --fqbn arduino:avr:mega /home/pi/robot_nav/arduino/MecanumTeleopBridge
arduino-cli upload -p "$MEGA" --fqbn arduino:avr:mega /home/pi/robot_nav/arduino/MecanumTeleopBridge
echo FLASH_OK
sleep 2

if [ "$RESTART_DRIVE" = "1" ]; then
  set +u
  source /opt/ros/jazzy/setup.bash
  source /home/pi/ws_ros2/install/setup.bash
  set -u
  MEGA_DEV=/dev/ttyMEGA nohup python3 /home/pi/robot_nav/lidar_map/drive_encoders.py \
    >>/home/pi/robot_nav/logs/lidar_map.log 2>&1 &
  sleep 4
  pgrep -af drive_encoders.py || echo NO_DRIVE
  grep -aE 'READY|WSCALE|PIDV|mega cal|FRF_OK|FRB_OK' /home/pi/robot_nav/logs/lidar_map.log | tail -20
fi
