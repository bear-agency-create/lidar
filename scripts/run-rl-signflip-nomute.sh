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
arduino-cli upload -p "$MEGA" --fqbn arduino:avr:mega "$ROOT/arduino/MecanumTeleopBridge"
sleep 2.5
# Must NOT contain mute
if grep -E 'wantRlStrong|Opposite polarity|out\[2\] > 0\.03' "$ROOT/arduino/MecanumTeleopBridge/MecanumTeleopBridge.ino"; then
  echo "MUTE_STILL_PRESENT"; exit 1
fi
grep -n 'SIGN_RL' "$ROOT/arduino/MecanumTeleopBridge/MecanumTeleopBridge.ino" | head -4
python3 /tmp/test-rl-both-ways.py | tee /tmp/test-rl-signflip.out
echo raspberry | sudo -S systemctl restart robot-nav.service
sleep 5
echo raspberry | sudo -S systemctl start robot-nav-watchdog.timer || true
systemctl is-active robot-nav
curl -s -o /dev/null -w 'http=%{http_code}\n' http://127.0.0.1:8765/
curl -s -o /dev/null -w 'panel=%{http_code}\n' http://127.0.0.1:8765/operator-panel
grep -E 'ONE_WHEEL|WHEEL_OUT|dENC|RL=' /tmp/test-rl-signflip.out
echo SIGNFLIP_DONE
