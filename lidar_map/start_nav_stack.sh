#!/usr/bin/env bash
# Полный стек: SLAM mapping + Guide UI на localhost:8080
# Режимы: map (картирование) | guide (A→B по сохранённой карте) | mission (авто map→A→B)
set -euo pipefail
PI_HOST="${PI_HOST:-172.17.118.159}"
PI_USER="${PI_USER:-pi}"
PI_PASS="${PI_PASS:-raspberry}"
MODE="${1:-map}"   # map | guide | mission
LOCAL_PORT="${LOCAL_PORT:-8080}"

remote_cmd() {
  local cmd="$1"
  expect <<EOF
set timeout 180
spawn ssh -o StrictHostKeyChecking=accept-new -o PreferredAuthentications=password -o PubkeyAuthentication=no ${PI_USER}@${PI_HOST}
expect "password:"
send "${PI_PASS}\r"
expect -re {\\\$ }
send "${cmd}\r"
expect -re {\\\$ }
send "exit\r"
expect eof
EOF
}

case "$MODE" in
  map)
    echo "Starting mapping teleop + SLAM + UI..."
    remote_cmd "bash ~/robot_nav/fix_serial_aliases.sh; pkill -f lidar_map_server.py 2>/dev/null || true; nohup bash ~/robot_nav/start_mapping_teleop.sh > ~/robot_nav/logs/boot_teleop.log 2>&1 & sleep 2; echo STARTED"
    ;;
  guide)
    echo "Starting guide (AMCL+Nav2 A→B)..."
    remote_cmd "bash ~/robot_nav/fix_serial_aliases.sh; nohup bash ~/robot_nav/start_guide.sh > ~/robot_nav/logs/boot_guide.log 2>&1 & sleep 2; echo STARTED"
    ;;
  mission)
    echo "Starting auto mission MAP→A→B (blocks on Pi)..."
    remote_cmd "bash ~/robot_nav/fix_serial_aliases.sh; MAP_DURATION=\${MAP_DURATION:-45} nohup bash ~/robot_nav/start_mission.sh > ~/robot_nav/logs/boot_mission.log 2>&1 & sleep 2; echo STARTED"
    ;;
  *)
    echo "Usage: $0 [map|guide|mission]"; exit 1
    ;;
esac

lsof -ti:"${LOCAL_PORT}" | xargs kill -9 2>/dev/null || true
echo "UI: http://127.0.0.1:${LOCAL_PORT}/  (Ctrl+C stops tunnel)"
expect <<EOF
set timeout -1
spawn ssh -o ServerAliveInterval=30 -o StrictHostKeyChecking=accept-new -o PreferredAuthentications=password -o PubkeyAuthentication=no -N -L ${LOCAL_PORT}:127.0.0.1:8080 ${PI_USER}@${PI_HOST}
expect "password:"
send "${PI_PASS}\r"
expect
EOF
