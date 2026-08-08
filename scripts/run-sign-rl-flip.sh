#!/bin/bash
set -e
ROOT=/home/pi/robot_nav
echo raspberry | sudo -S systemctl stop robot-nav-watchdog.timer || true
pkill -f drive_encoders.py || true
sleep 2
export PATH="$HOME/bin:$PATH"
arduino-cli compile --fqbn arduino:avr:mega "$ROOT/arduino/MecanumTeleopBridge"
MEGA="$(readlink -f /dev/ttyMEGA 2>/dev/null || echo /dev/ttyUSB1)"
arduino-cli upload -p "$MEGA" --fqbn arduino:avr:mega "$ROOT/arduino/MecanumTeleopBridge"
sleep 2
python3 /tmp/test-sign-rl-flip.py | tee /tmp/test-sign-rl-flip.out
echo raspberry | sudo -S systemctl restart robot-nav.service
sleep 5
echo raspberry | sudo -S systemctl start robot-nav-watchdog.timer
cat /tmp/test-sign-rl-flip.out
echo FLIP_DONE
