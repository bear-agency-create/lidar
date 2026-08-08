#!/bin/bash
set -e
pkill -f 'lidar_map/drive_encoders.py' || true
sleep 2
python3 /tmp/wheel_isolate_test.py /dev/ttyMEGA | tee /tmp/wheel_isolate.out
echo raspberry | sudo -S systemctl restart robot-nav.service
sleep 6
pgrep -af 'main.py|drive_encoders' | grep -v grep || true
grep -E 'WSCALE|drive_encoders on|mega cal' /home/pi/robot_nav/logs/lidar_map.log | tail -n 6 || true
echo ISOLATE_DONE
