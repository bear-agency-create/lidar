#!/bin/bash
set -e
ROOT=/home/pi/robot_nav
export PATH="$HOME/bin:$PATH"
echo raspberry | sudo -S systemctl stop robot-nav-watchdog.timer || true
echo raspberry | sudo -S systemctl stop robot-nav.service || true
pkill -f drive_encoders.py || true
sleep 2
arduino-cli compile --fqbn arduino:avr:mega "$ROOT/arduino/MecanumTeleopBridge"
MEGA="$(readlink -f /dev/ttyMEGA 2>/dev/null || echo /dev/ttyUSB1)"
echo "upload port=$MEGA"
arduino-cli upload -p "$MEGA" --fqbn arduino:avr:mega "$ROOT/arduino/MecanumTeleopBridge"
sleep 2.5
grep -n 'wantRlStrong' "$ROOT/arduino/MecanumTeleopBridge/MecanumTeleopBridge.ino" | head -3
python3 /tmp/test-bl-focus.py | tee /tmp/test-bl-focus.out
echo raspberry | sudo -S systemctl restart robot-nav.service
sleep 4
echo raspberry | sudo -S systemctl start robot-nav-watchdog.timer || true
systemctl is-active robot-nav || true
echo BL_FOCUS_FLASH_DONE
