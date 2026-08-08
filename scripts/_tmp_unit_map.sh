#!/usr/bin/env bash
set -eo pipefail
cd /home/pi/robot_nav/lidar_map
python3 - <<'PY'
from occupancy import OccupancyMap
from config import MIN_MATCH_SCORE, MIN_REFINE_SCORE, FRAME_BODY_PAD, FRAME_POST_HALF_ANGLE, FRAME_POST_RANGE_MARGIN
import math

m = OccupancyMap()
# seed wall outside body + fake self-hit inside
m.integrate(0.0, 0.0, [(1.2, 0.0), (0.02, 0.0), (-1.0, 0.5)])
before = m.to_dict()
wiped = m.clear_robot_footprint(0.0, 0.0, 0.0)
after = m.to_dict()
free_before = sum(1 for c in before['cells'] if c[2] == 0)
free_after = sum(1 for c in after['cells'] if c[2] == 0)
print('scores', MIN_MATCH_SCORE, MIN_REFINE_SCORE)
print('filter', FRAME_BODY_PAD, round(math.degrees(FRAME_POST_HALF_ANGLE),1), FRAME_POST_RANGE_MARGIN)
print('before_hits', before['hits'], 'cells', len(before['cells']), 'free', free_before)
print('wiped', wiped, 'after_hits', after['hits'], 'cells', len(after['cells']), 'free', free_after)
assert free_before == 0 and free_after == 0, 'to_dict must omit free cells'
assert wiped >= 1, 'footprint wipe should clear near-body hit'
assert after['hits'] >= 1, 'far wall must survive footprint wipe'
print('SMOKE_OK')
PY

# Confirm bridge source has odom-prior path
grep -n 'Prefer Mega\|MIN_MATCH_SCORE\|clear_robot_footprint\|pose_ok = bool' bridge.py | head -20
