#!/usr/bin/env bash
set -eo pipefail
echo raspberry | sudo -S systemctl restart robot-nav.service
sleep 12
source /opt/ros/jazzy/setup.bash
source /home/pi/ws_ros2/install/setup.bash

echo "=== ports ==="
ls -l /dev/ttyMEGA /dev/ttyLIDAR 2>&1 || true

echo "=== /scan hz ==="
timeout 6 ros2 topic hz /scan 2>&1 | head -12 || true

echo "=== api ==="
python3 - <<'PY'
import json, urllib.request, time
time.sleep(2)
health = json.load(urllib.request.urlopen('http://127.0.0.1:8765/api/scan/health', timeout=3))
print('health', health)
raw = urllib.request.urlopen('http://127.0.0.1:8765/api/scan', timeout=5).read()
print('api_scan_bytes', len(raw))
j = json.loads(raw)
cells = (j.get('map') or {}).get('cells') or []
free = sum(1 for c in cells if len(c) >= 3 and c[2] == 0)
occ = sum(1 for c in cells if len(c) >= 3 and c[2] >= 90)
print({
  'ok': j.get('ok'),
  'error': j.get('error'),
  'odom_ok': j.get('odom_ok'),
  'pose': j.get('pose'),
  'points': len(j.get('points') or []),
  'map_hits': (j.get('map') or {}).get('hits'),
  'cells_total': len(cells),
  'cells_free': free,
  'cells_occ': occ,
})
PY
tail -15 /home/pi/robot_nav/logs/lidar_map.log 2>/dev/null || true
echo DONE
