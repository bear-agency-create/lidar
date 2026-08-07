#!/usr/bin/env bash
# Push LOCAL repo to Pi, flash Mega, restart stack, smoke-test teleop.
set -euo pipefail

PI_HOST="${PI_HOST:-10.255.210.201}"
PI_USER="${PI_USER:-pi}"
PI_PASS="${PI_PASS:-raspberry}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PI_NAV="/home/pi/robot_nav"

if ! command -v expect >/dev/null 2>&1; then
  echo "need expect" >&2
  exit 1
fi

if ! nc -z -G 3 "$PI_HOST" 22 >/dev/null 2>&1; then
  echo "Pi $PI_HOST:22 unreachable" >&2
  exit 2
fi

run_ssh() {
  local body="$1"
  expect <<EOF
set timeout 600
log_user 1
spawn ssh -tt -o StrictHostKeyChecking=no -o PreferredAuthentications=password -o PubkeyAuthentication=no ${PI_USER}@${PI_HOST} "bash -lc $(printf '%q' "$body")"
expect {
  -re {(?i)password:} { send "${PI_PASS}\r"; exp_continue }
  eof { }
  timeout { puts "SSH TIMEOUT"; exit 1 }
}
catch wait result
exit [lindex \$result 3]
EOF
}

echo "== sync arduino =="
expect <<EOF
set timeout 120
spawn rsync -az --delete -e "ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password -o PubkeyAuthentication=no" "$ROOT/arduino/" ${PI_USER}@${PI_HOST}:${PI_NAV}/arduino/
expect {
  -re {(?i)password:} { send "${PI_PASS}\r"; exp_continue }
  eof { }
  timeout { exit 1 }
}
catch wait result
exit [lindex \$result 3]
EOF

echo "== sync lidar_map =="
expect <<EOF
set timeout 120
spawn rsync -az --delete -e "ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password -o PubkeyAuthentication=no" "$ROOT/lidar_map/" ${PI_USER}@${PI_HOST}:${PI_NAV}/lidar_map/
expect {
  -re {(?i)password:} { send "${PI_PASS}\r"; exp_continue }
  eof { }
  timeout { exit 1 }
}
catch wait result
exit [lindex \$result 3]
EOF

echo "== flash Mega =="
run_ssh "chmod +x ${PI_NAV}/lidar_map/*.sh 2>/dev/null || true; bash ${PI_NAV}/lidar_map/flash_smooth.sh"

echo "== restart stack =="
run_ssh "bash ${PI_NAV}/lidar_map/start_drive_map.sh; sleep 5; echo TELEOP_SMOKE; curl -s -X POST http://127.0.0.1:8765/api/cmd -H 'Content-Type: application/json' -d '{\"vx\":0.25,\"vy\":0,\"w\":0}'; echo; sleep 1; cat /tmp/robot_cmd.json; echo; tail -12 /tmp/mega_teleop.log; curl -s -X POST http://127.0.0.1:8765/api/cmd/stop >/dev/null; pgrep -af 'drive_encoders|main.py' | grep -v grep; echo DONE"

echo "operator: http://${PI_HOST}:8765/"
