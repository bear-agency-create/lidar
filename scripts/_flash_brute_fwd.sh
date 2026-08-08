#!/bin/bash
set -euo pipefail
export PATH="$HOME/bin:$PATH"
pkill -9 -f drive_encoders.py || true
pkill -9 -f lidar_map/main.py || true
pkill -9 -f cspc_lidar || true
fuser -k /dev/ttyMEGA /dev/ttyUSB0 2>/dev/null || true
sleep 1
MEGA="$(readlink -f /dev/ttyMEGA 2>/dev/null || echo /dev/ttyUSB0)"
echo "MEGA=$MEGA"
arduino-cli compile --fqbn arduino:avr:mega /home/pi/robot_nav/arduino/BruteFwd
arduino-cli upload -p "$MEGA" --fqbn arduino:avr:mega /home/pi/robot_nav/arduino/BruteFwd
echo "FLASH_OK — Mega drives FWD pins NOW"
echo "If motors silent: NO motor supply / E-stop / L298 power (USB logic alone is not enough)"
