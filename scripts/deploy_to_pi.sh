#!/usr/bin/env bash
# From Mac/laptop: push full GitHub install+flash+restart onto the Pi over SSH.
set -euo pipefail

PI_HOST="${PI_HOST:-10.255.210.201}"
PI_USER="${PI_USER:-pi}"
PI_PASS="${PI_PASS:-raspberry}"

if ! command -v expect >/dev/null 2>&1; then
  echo "need expect" >&2
  exit 1
fi

# Fail fast if host is down
if ! nc -z -G 3 "$PI_HOST" 22 >/dev/null 2>&1; then
  echo "Pi $PI_HOST:22 unreachable — power on robot / join same Wi‑Fi" >&2
  exit 2
fi

expect <<EOF
set timeout 300
spawn ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password -o PubkeyAuthentication=no ${PI_USER}@${PI_HOST} {bash -lc 'set -euo pipefail
if [ ! -d \$HOME/lidar/.git ]; then
  git clone https://github.com/bear-agency-create/lidar.git \$HOME/lidar
fi
chmod +x \$HOME/lidar/lidar_map/*.sh
bash \$HOME/lidar/lidar_map/deploy_pi.sh
'}
expect {
  -re {(?i)password:} { send "${PI_PASS}\r"; exp_continue }
  eof
}
catch wait result
exit [lindex \$result 3]
EOF

echo "operator: http://${PI_HOST}:8765/"
echo "kiosk:    http://${PI_HOST}:8765/kiosk"
