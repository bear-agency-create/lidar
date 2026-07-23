#!/usr/bin/env bash
# Карта лидара на localhost (скан + odom → occupancy при движении)
set -euo pipefail
PI_HOST="${PI_HOST:-172.17.118.159}"
PI_USER="${PI_USER:-pi}"
PI_PASS="${PI_PASS:-raspberry}"
LOCAL_PORT="${LOCAL_PORT:-8765}"

expect <<EOF
set timeout 90
spawn ssh -o StrictHostKeyChecking=accept-new -o PreferredAuthentications=password -o PubkeyAuthentication=no ${PI_USER}@${PI_HOST}
expect "password:"
send "${PI_PASS}\r"
expect -re {\\\$ }
send "source /opt/ros/jazzy/setup.bash; source ~/ws_ros2/install/setup.bash\r"
expect -re {\\\$ }
send "pgrep -f '/cspc_lidar' >/dev/null || nohup ros2 run cspc_lidar cspc_lidar --ros-args -r __node:=cspc_lidar -p port:=/dev/ttyUSB0 -p frame_id:=laser_frame -p baudrate:=230400 -p frequency:=8.0 -p angle_min:=-180.0 -p angle_max:=180.0 -p max_range:=12.0 -p min_range:=0.05 -p version:=4 -p reversion:=true -p auto_reconnect:=true > /tmp/lidar_usb0.log 2>&1 &\r"
expect -re {\\\$ }
send "pgrep -f robot_driver_node >/dev/null || nohup ros2 run robot_driver robot_driver_node --ros-args -p serial_port:=/dev/ttyUSB1 > /tmp/robot_driver.log 2>&1 &\r"
expect -re {\\\$ }
send "pgrep -f lidar_map_server.py >/dev/null || (fuser -k 8765/tcp >/dev/null 2>&1; sleep 1; nohup python3 ~/lidar_map_server.py > /tmp/lidar_map.log 2>&1 &)\r"
expect -re {\\\$ }
send "exit\r"
expect eof
EOF

lsof -ti:"${LOCAL_PORT}" | xargs kill -9 2>/dev/null || true
echo "http://127.0.0.1:${LOCAL_PORT}/  (Ctrl+C = стоп туннеля)"
expect <<EOF
set timeout -1
spawn ssh -o StrictHostKeyChecking=accept-new -o PreferredAuthentications=password -o PubkeyAuthentication=no -N -L ${LOCAL_PORT}:127.0.0.1:8765 ${PI_USER}@${PI_HOST}
expect "password:"
send "${PI_PASS}\r"
expect
EOF
