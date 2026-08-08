#!/usr/bin/env bash
set -eo pipefail
echo raspberry | sudo -S systemctl restart robot-nav.service
sleep 12
python3 - <<'PY'
import json, urllib.request, serial, time
j=json.load(urllib.request.urlopen('http://127.0.0.1:8765/api/scan', timeout=3))
print('ok', j.get('ok'), 'odom', j.get('odom_ok'), 'err', j.get('error'))
# quick mega check without stealing from drive long
import subprocess
print(subprocess.getoutput("pgrep -af 'drive_encoders|cspc_lidar|main.py' | grep -v grep"))
print('links', subprocess.getoutput('ls -l /dev/ttyMEGA /dev/ttyLIDAR'))
PY
curl -fsS --max-time 2 http://127.0.0.1:8765/ >/dev/null && echo UI_OK
