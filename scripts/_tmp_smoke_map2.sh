#!/usr/bin/env bash
set -eo pipefail
echo "=== service status ==="
systemctl --no-pager --full status robot-nav.service | head -40 || true
echo "=== import check ==="
cd /home/pi/robot_nav/lidar_map
python3 - <<'PY'
import bridge, config, occupancy, lidar, geometry
print('MIN_MATCH', config.MIN_MATCH_SCORE, 'MIN_REFINE', config.MIN_REFINE_SCORE)
print('PAD', config.FRAME_BODY_PAD, 'ANG', config.FRAME_POST_HALF_ANGLE, 'MRG', config.FRAME_POST_RANGE_MARGIN)
print('has clear_robot_footprint', hasattr(occupancy.OccupancyMap, 'clear_robot_footprint'))
print('LIDAR offset', config.LIDAR_DX_M, config.LIDAR_DY_M, config.LIDAR_DYAW_RAD)
# quick footprint clear smoke
m = occupancy.OccupancyMap()
m.integrate(0.0, 0.0, [(0.9, 0.0), (0.05, 0.0)])
n = m.clear_robot_footprint(0.0, 0.0, 0.0)
d = m.to_dict()
free = sum(1 for c in d['cells'] if c[2] == 0)
print('wipe_cells', n, 'to_dict_free', free, 'hits', d['hits'], 'cells', len(d['cells']))
print('IMPORT_OK')
PY

echo "=== try start again ==="
echo raspberry | sudo -S systemctl restart robot-nav.service
sleep 18
systemctl is-active robot-nav.service || true
journalctl -u robot-nav -n 50 --no-pager || true
pgrep -af 'main.py|drive_encoders|cspc_lidar' | grep -v grep || true
curl -fsS --max-time 3 http://127.0.0.1:8765/api/scan/health || echo NO_HTTP
echo
python3 - <<'PY'
import json, urllib.request
try:
    raw = urllib.request.urlopen('http://127.0.0.1:8765/api/scan', timeout=5).read()
    j = json.loads(raw)
    cells = (j.get('map') or {}).get('cells') or []
    print('bytes', len(raw), 'ok', j.get('ok'), 'odom', j.get('odom_ok'), 'err', j.get('error'),
          'hits', (j.get('map') or {}).get('hits'), 'cells', len(cells),
          'free', sum(1 for c in cells if len(c)>=3 and c[2]==0))
except Exception as e:
    print('api_err', e)
PY
