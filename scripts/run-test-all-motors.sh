#!/bin/bash
set -euo pipefail
export PATH="$HOME/bin:$PATH"
echo raspberry | sudo -S systemctl stop robot-nav-watchdog.timer || true
echo raspberry | sudo -S systemctl stop robot-nav.service || true
pkill -9 -f drive_encoders.py || true
fuser -k /dev/ttyMEGA 2>/dev/null || true
fuser -k /dev/ttyUSB1 2>/dev/null || true
sleep 2
python3 /tmp/test-all-motors.py | tee /tmp/test-all-motors.out
echo raspberry | sudo -S systemctl start robot-nav.service
sleep 5
echo raspberry | sudo -S systemctl start robot-nav-watchdog.timer || true
systemctl is-active robot-nav || true
echo ALL_MOTORS_STACK_DONE
