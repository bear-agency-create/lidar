#!/usr/bin/env bash
# Keep :8765 + drive_encoders + lidar alive after Pi reboot / process crash.
set -eo pipefail

STACK_DIR="${STACK_DIR:-$HOME/robot_nav/lidar_map}"
LOG="$HOME/robot_nav/logs/watchdog.log"
SCAN_FAILURES_FILE="/run/robot-nav-scan-failures"
mkdir -p "$(dirname "$LOG")"

ok_http() {
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 http://127.0.0.1:8765/ || true)
  [ "$code" = "200" ]
}

main_alive() {
  pgrep -f 'lidar_map/main.py' >/dev/null 2>&1
}

drive_alive() {
  pgrep -f 'drive_encoders.py' >/dev/null 2>&1
}

lidar_alive() {
  pgrep -f 'cspc_lidar' >/dev/null 2>&1
}

scan_alive() {
  for _attempt in 1 2 3; do
    if curl -fsS --max-time 3 http://127.0.0.1:8765/api/scan/health |
      python3 -c 'import json,sys; j=json.load(sys.stdin); raise SystemExit(0 if j.get("ok") and not j.get("stale", True) else 1)'
    then
      return 0
    fi
    sleep 1
  done
  return 1
}

if ok_http && main_alive && drive_alive && lidar_alive; then
  if scan_alive; then
    rm -f "$SCAN_FAILURES_FILE"
    exit 0
  fi

  failures=0
  if [ -r "$SCAN_FAILURES_FILE" ]; then
    failures=$(cat "$SCAN_FAILURES_FILE" 2>/dev/null || echo 0)
  fi
  failures=$((failures + 1))
  echo "$failures" >"$SCAN_FAILURES_FILE"
  if [ "$failures" -lt 2 ]; then
    echo "$(date -Is) watchdog: transient scan miss ($failures/2), keeping healthy processes" >>"$LOG"
    exit 0
  fi
fi
rm -f "$SCAN_FAILURES_FILE"

{
  echo "$(date -Is) watchdog: stack incomplete (http=$(ok_http && echo ok || echo bad) main=$(main_alive && echo ok || echo bad) drive=$(drive_alive && echo ok || echo bad) lidar=$(lidar_alive && echo ok || echo bad) scan=$(scan_alive && echo ok || echo bad)) — restarting via systemd"
  # Prefer systemd unit so processes are owned by robot-nav.service, not this oneshot.
  if systemctl restart robot-nav.service; then
    sleep 4
  else
    bash "$STACK_DIR/start_drive_map.sh"
    sleep 3
  fi
  if ok_http && main_alive && scan_alive; then
    echo "$(date -Is) watchdog: recovered (drive=$(drive_alive && echo ok || echo bad) lidar=$(lidar_alive && echo ok || echo bad) scan=ok)"
  else
    echo "$(date -Is) watchdog: FAILED to recover"
  fi
} >>"$LOG" 2>&1
