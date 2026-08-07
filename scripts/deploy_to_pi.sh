#!/usr/bin/env bash
# From Mac/laptop: pull+flash+restart full stack on the Pi over SSH.
set -euo pipefail

PI_HOST="${PI_HOST:-10.255.210.201}"
PI_USER="${PI_USER:-pi}"
PI_PASS="${PI_PASS:-raspberry}"

if ! command -v expect >/dev/null 2>&1; then
  echo "need expect" >&2
  exit 1
fi

if ! nc -z -G 3 "$PI_HOST" 22 >/dev/null 2>&1; then
  echo "Pi $PI_HOST:22 unreachable — power on robot / join same Wi‑Fi" >&2
  exit 2
fi

# Fetch on Pi FIRST, then run the refreshed deploy_pi.sh (never exec a stale script body).
expect <<EOF
set timeout 420
spawn ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password -o PubkeyAuthentication=no ${PI_USER}@${PI_HOST} bash -s
expect {
  -re {(?i)password:} { send "${PI_PASS}\r"; exp_continue }
  -re {.*} {}
}
send "set -euo pipefail\n"
send "if \[ ! -d \\\$HOME/lidar/.git \]; then git clone https://github.com/bear-agency-create/lidar.git \\\$HOME/lidar; fi\n"
send "git -C \\\$HOME/lidar fetch origin\n"
send "git -C \\\$HOME/lidar reset --hard origin/main\n"
send "chmod +x \\\$HOME/lidar/lidar_map/*.sh \\\$HOME/lidar/scripts/*.sh 2>/dev/null || true\n"
send "bash \\\$HOME/lidar/lidar_map/deploy_pi.sh\n"
send "exit\n"
expect {
  DONE { }
  eof { }
  timeout { puts TIMEOUT; exit 1 }
}
expect eof
catch wait result
exit \[lindex \$result 3\]
EOF

echo "operator: http://${PI_HOST}:8765/"
echo "kiosk:    http://${PI_HOST}:8765/kiosk"
