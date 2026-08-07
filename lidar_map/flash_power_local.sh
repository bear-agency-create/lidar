#!/usr/bin/env bash
# LOCAL ONLY — flash power-boost firmware to Pi. Do not push to GitHub.
set -eo pipefail
export PATH="$HOME/bin:$PATH"
pkill -9 -f drive_encoders.py || true
pkill -9 -f 'lidar_map/main.py' || true
fuser -k /dev/ttyUSB1 2>/dev/null || true
fuser -k /dev/ttyMEGA 2>/dev/null || true
sleep 2
MEGA="$(readlink -f /dev/ttyMEGA 2>/dev/null || true)"
if [[ -z "$MEGA" || ! -e "$MEGA" ]]; then MEGA=/dev/ttyUSB1; fi
echo "MEGA=$MEGA"
arduino-cli compile --fqbn arduino:avr:mega /home/pi/robot_nav/arduino/MecanumTeleopBridge
arduino-cli upload -p "$MEGA" --fqbn arduino:avr:mega /home/pi/robot_nav/arduino/MecanumTeleopBridge
echo FLASH_OK
sleep 1
bash /home/pi/robot_nav/lidar_map/start_drive_map.sh
sleep 3
grep -aE 'WSCALE_OK|RAMP|mega cal' /tmp/mega_teleop.log | tail -5 || true
echo ALL_DONE
