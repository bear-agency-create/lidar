#!/bin/bash
set -e
echo raspberry | sudo -S systemctl stop robot-nav-watchdog.timer || true
pkill -f drive_encoders.py || true
sleep 2
python3 /tmp/test-bl-rl2.py | tee /tmp/test-bl-rl2.out
echo raspberry | sudo -S systemctl restart robot-nav.service
sleep 5
echo raspberry | sudo -S systemctl start robot-nav-watchdog.timer
echo RL2_DONE
