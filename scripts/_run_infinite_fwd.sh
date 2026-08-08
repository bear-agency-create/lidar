#!/bin/bash
# Flash InfiniteFwd and leave it running (setup() starts FWD forever).
set -euo pipefail
export PATH="$HOME/bin:$PATH"
pkill -9 -f drive_encoders.py || true
pkill -9 -f lidar_map/main.py || true
pkill -9 -f cspc_lidar || true
fuser -k /dev/ttyMEGA /dev/ttyUSB0 2>/dev/null || true
sleep 1
MEGA="$(readlink -f /dev/ttyMEGA 2>/dev/null || echo /dev/ttyUSB0)"
echo "MEGA=$MEGA"
SKETCH="$HOME/robot_nav/arduino/InfiniteFwd"
arduino-cli compile --fqbn arduino:avr:mega "$SKETCH"
arduino-cli upload -p "$MEGA" --fqbn arduino:avr:mega "$SKETCH"
echo "FLASH_OK — robot should be driving FWD forever at PWM 255"
echo "Stop later: flash CleanFwdBack / Mecanum, or open serial and send x"
