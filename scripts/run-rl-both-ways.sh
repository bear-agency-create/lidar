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
# Prove mute is gone
if grep -n 'wantRlStrong\|Opposite polarity\|one effective H-bridge' \
    "$ROOT/arduino/MecanumTeleopBridge/MecanumTeleopBridge.ino"; then
  echo "ERROR: polarity mute still in source"
  exit 1
fi
grep -n 'SIGN_RL' "$ROOT/arduino/MecanumTeleopBridge/MecanumTeleopBridge.ino" | head -3
python3 /tmp/test-rl-both-ways.py | tee /tmp/test-rl-both-ways.out
echo raspberry | sudo -S systemctl restart robot-nav.service
sleep 5
echo raspberry | sudo -S systemctl start robot-nav-watchdog.timer || true
systemctl is-active robot-nav || true
curl -s -o /dev/null -w 'http=%{http_code}\n' http://127.0.0.1:8765/
grep -E 'ONE_WHEEL|WHEEL_OUT|dENC|RL=' /tmp/test-rl-both-ways.out || true
echo RL_BOTH_WAYS_DONE
