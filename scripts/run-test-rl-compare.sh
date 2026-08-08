#!/bin/bash
echo raspberry | sudo -S systemctl stop robot-nav-watchdog.timer || true
pkill -f drive_encoders.py || true
sleep 2
python3 /tmp/test-rl-compare.py | tee /tmp/test-rl-compare.out
echo raspberry | sudo -S systemctl restart robot-nav.service
sleep 5
echo raspberry | sudo -S systemctl start robot-nav-watchdog.timer
echo COMPARE_DONE
