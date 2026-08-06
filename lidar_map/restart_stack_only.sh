#!/bin/bash
set -e
bash /home/pi/robot_nav/lidar_map/start_drive_map.sh
sleep 4
pgrep -af 'drive_encoders|lidar_map/main.py' | grep -v grep || true
curl -s -o /dev/null -w "http=%{http_code}\n" --max-time 3 http://127.0.0.1:8765/ || true
grep -E 'mega cal|PIDV_OK' /home/pi/robot_nav/logs/lidar_map.log | tail -5
