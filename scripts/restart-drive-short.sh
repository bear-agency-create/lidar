#!/bin/bash
set -e
echo raspberry | sudo -S systemctl stop robot-nav-watchdog.timer || true
pkill -f drive_encoders.py || true
sleep 1
echo raspberry | sudo -S systemctl restart robot-nav.service
sleep 5
echo raspberry | sudo -S systemctl start robot-nav-watchdog.timer
# Quick confirm WSCALE/FRF applied
python3 - <<'PY'
from pathlib import Path
t=Path('/home/pi/robot_nav/logs/lidar_map.log').read_text(errors='replace')
for ln in t.splitlines()[-30:]:
    if any(x in ln for x in ('WSCALE_OK','FRF_OK','mega cal','drive_encoders on')):
        print(ln)
PY
curl -s -o /dev/null -w "http=%{http_code}\n" http://127.0.0.1:8765/
echo OK
