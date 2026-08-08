#!/bin/bash
python3 <<'PY'
import json, urllib.request
d=json.load(urllib.request.urlopen('http://127.0.0.1:8765/api/analyze'))
q=d.get('quality') or {}
s=d.get('sensors') or {}
p=d.get('pose') or {}
print('ok', d.get('ok'))
print('quality', json.dumps(q, ensure_ascii=False)[:800])
print('sensors', json.dumps(s, ensure_ascii=False)[:800])
print('pose', json.dumps(p, ensure_ascii=False)[:400])
print('recs', d.get('recommendations'))
PY
