#!/usr/bin/env bash
set -eo pipefail
sed -i 's/\r$//' /home/pi/robot_nav/lidar_map/geometry.py
grep -n filter_self_hits_world /home/pi/robot_nav/lidar_map/geometry.py | head -3
echo raspberry | sudo -S systemctl restart robot-nav.service
sleep 15
systemctl is-active robot-nav.service || true
pgrep -af 'main.py|drive_encoders|cspc_lidar' | grep -v grep || true
curl -fsS --max-time 3 http://127.0.0.1:8765/api/scan/health || echo NO_HTTP
echo
python3 - <<'PY'
import json, urllib.request
try:
    raw = urllib.request.urlopen('http://127.0.0.1:8765/api/scan', timeout=5).read()
    j = json.loads(raw)
    c = (j.get('map') or {}).get('cells') or []
    print(
        'bytes', len(raw),
        'ok', j.get('ok'),
        'odom', j.get('odom_ok'),
        'err', j.get('error'),
        'hits', (j.get('map') or {}).get('hits'),
        'cells', len(c),
        'free', sum(1 for x in c if len(x) >= 3 and x[2] == 0),
        'pose', j.get('pose'),
    )
except Exception as e:
    print('api_err', e)
PY
journalctl -u robot-nav -n 25 --no-pager || true
