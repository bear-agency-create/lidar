#!/usr/bin/env bash
# Keep :8765 alive after Pi reboot / process crash.
set -eo pipefail

STACK_DIR="${STACK_DIR:-$HOME/robot_nav/lidar_map}"
LOG="$HOME/robot_nav/logs/watchdog.log"
mkdir -p "$(dirname "$LOG")"

ok_http() {
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 http://127.0.0.1:8765/ || true)
  [ "$code" = "200" ]
}

main_alive() {
  pgrep -f 'lidar_map/main.py' >/dev/null 2>&1
}

if ok_http && main_alive; then
  exit 0
fi

{
  echo "$(date -Is) watchdog: stack down (http/main) — restarting"
  bash "$STACK_DIR/start_drive_map.sh"
  sleep 3
  if ok_http; then
    echo "$(date -Is) watchdog: recovered"
  else
    echo "$(date -Is) watchdog: FAILED to recover"
  fi
} >>"$LOG" 2>&1
