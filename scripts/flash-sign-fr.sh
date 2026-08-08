#!/bin/bash
set -e
ROOT=/home/pi/robot_nav
echo raspberry | sudo -S systemctl stop robot-nav-watchdog.timer || true
echo raspberry | sudo -S systemctl stop robot-nav.service || true
pkill -9 -f drive_encoders || true
sleep 2
export PATH="$HOME/bin:$PATH"
arduino-cli compile --fqbn arduino:avr:mega "$ROOT/arduino/MecanumTeleopBridge"
MEGA="$(readlink -f /dev/ttyMEGA 2>/dev/null || echo /dev/ttyUSB1)"
arduino-cli upload -p "$MEGA" --fqbn arduino:avr:mega "$ROOT/arduino/MecanumTeleopBridge"
sleep 2
echo raspberry | sudo -S systemctl start robot-nav.service
sleep 5
echo raspberry | sudo -S systemctl start robot-nav-watchdog.timer
pgrep -af 'drive_encoders|main.py' | grep -v grep || true
echo SIGN_FR_FLIPPED
