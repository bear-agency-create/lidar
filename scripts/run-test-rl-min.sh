#!/bin/bash
set -e
echo raspberry | sudo -S systemctl stop robot-nav-watchdog.timer || true
pkill -f drive_encoders.py || true
sleep 2
python3 /tmp/test-rl-min.py | tee /tmp/test-rl-min.out
echo raspberry | sudo -S systemctl restart robot-nav.service
sleep 4
echo raspberry | sudo -S systemctl start robot-nav-watchdog.timer
cat /tmp/test-rl-min.out
echo MIN_DONE
