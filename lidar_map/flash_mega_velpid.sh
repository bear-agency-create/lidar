#!/bin/bash
set -euo pipefail
export PATH="$HOME/bin:$PATH"
MEGA="$(readlink -f /dev/ttyMEGA 2>/dev/null || true)"
if [[ -z "$MEGA" || ! -e "$MEGA" ]]; then
  echo "ERROR: /dev/ttyMEGA missing"
  ls -l /dev/ttyUSB* /dev/ttyMEGA 2>&1 || true
  exit 1
fi
echo "Flashing MecanumTeleopBridge to $MEGA (symlink /dev/ttyMEGA)"
pkill -f drive_encoders.py || true
sleep 1
arduino-cli compile --fqbn arduino:avr:mega /home/pi/robot_nav/arduino/MecanumTeleopBridge
arduino-cli upload -p "$MEGA" --fqbn arduino:avr:mega /home/pi/robot_nav/arduino/MecanumTeleopBridge
echo FLASH_OK
sleep 2
python3 /tmp/_mega_ping.py
