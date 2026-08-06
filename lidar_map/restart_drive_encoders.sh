#!/bin/bash
set -e
source /opt/ros/jazzy/setup.bash
source /home/pi/ws_ros2/install/setup.bash
pkill -f '/lidar_map/drive_encoders.py' || true
sleep 1
MEGA_DEV=/dev/ttyMEGA nohup python3 /home/pi/robot_nav/lidar_map/drive_encoders.py \
  >>/home/pi/robot_nav/logs/lidar_map.log 2>&1 &
sleep 3
pgrep -af drive_encoders.py || echo 'drive_encoders NOT running'
tail -12 /home/pi/robot_nav/logs/lidar_map.log
