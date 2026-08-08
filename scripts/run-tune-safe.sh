#!/bin/bash
set -e
echo raspberry | sudo -S systemctl stop robot-nav-watchdog.timer || true
echo raspberry | sudo -S systemctl stop robot-nav.service || true
pkill -9 -f 'lidar_map/drive_encoders.py' || true
pkill -9 -f 'lidar_map/main.py' || true
sleep 2

python3 /tmp/tune_asymmetric_drive.py | tee /tmp/tune_asymmetric.out

echo raspberry | sudo -S systemctl start robot-nav.service
sleep 6
echo raspberry | sudo -S systemctl start robot-nav-watchdog.timer
pgrep -af 'main.py|drive_encoders' | grep -v grep || true
python3 - <<'PY'
from pathlib import Path
lines=Path('/home/pi/robot_nav/logs/lidar_map.log').read_text(errors='replace').splitlines()
for ln in lines[-20:]:
    if any(x in ln for x in ('WSCALE','mega cal','drive_encoders on','FRF','FRB')):
        print(ln)
print('--- cal ---')
print(Path('/home/pi/robot_nav/lidar_map/drive_cal.json').read_text())
PY
curl -s -o /dev/null -w "http=%{http_code}\n" http://127.0.0.1:8765/
echo TUNE2_DONE
