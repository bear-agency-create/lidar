#!/bin/bash
curl -s http://127.0.0.1:8765/api/analyze > /tmp/analyze.json
python3 <<'PY'
import json
from pathlib import Path
d=json.loads(Path('/tmp/analyze.json').read_text())
keys=sorted(d.keys())
print('keys', keys)
for k in ('grade','odom_ok','lidar_ok','scan_age_sec','nearest_m','issues','hints','summary'):
    if k in d:
        print(k, ':', d[k])
# print nested useful bits
for k,v in d.items():
    if isinstance(v,(bool,int,float,str)) and any(x in k.lower() for x in ('odom','lidar','scan','near','grade','age','ok')):
        print(f'{k}={v}')
PY
