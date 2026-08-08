#!/bin/bash
set -e
echo raspberry | sudo -S systemctl stop robot-nav-watchdog.timer || true
pkill -f drive_encoders.py || true
sleep 1
echo raspberry | sudo -S systemctl restart robot-nav.service
sleep 6
echo raspberry | sudo -S systemctl start robot-nav-watchdog.timer
pgrep -af 'main.py|drive_encoders' | grep -v grep || true
tail -c 8000 /home/pi/robot_nav/logs/lidar_map.log | tr -cd '\11\12\15\40-\176' | grep -E 'WSCALE_OK|mega cal applied|drive_encoders on' | tail -n 5
curl -s -o /dev/null -w "http=%{http_code}\n" http://127.0.0.1:8765/
cat /home/pi/robot_nav/lidar_map/drive_cal.json
echo RESTART_DONE
