#!/bin/bash
set -e
ROOT=/home/pi/robot_nav
echo raspberry | sudo -S systemctl stop robot-nav-watchdog.timer || true
echo raspberry | sudo -S systemctl stop robot-nav.service || true
pkill -9 -f 'lidar_map/drive_encoders.py' || true
pkill -9 -f 'lidar_map/main.py' || true
fuser -k /dev/ttyMEGA 2>/dev/null || true
fuser -k /dev/ttyUSB1 2>/dev/null || true
sleep 2

echo "=== ONE_WHEEL sequential (robot lifted) ==="
python3 "$ROOT/lidar_map/tools/one_wheel_align.py" /dev/ttyMEGA | tee /tmp/one_wheel_align_lifted.out

echo "=== restart stack ==="
echo raspberry | sudo -S systemctl start robot-nav.service
sleep 5
echo raspberry | sudo -S systemctl start robot-nav-watchdog.timer
pgrep -af 'main.py|drive_encoders' | grep -v grep || true
echo "=== applied cal ==="
python3 - <<'PY'
from pathlib import Path
t=Path('/home/pi/robot_nav/logs/lidar_map.log').read_text(errors='replace')
for ln in t.splitlines()[-25:]:
    if any(x in ln for x in ('WSCALE_OK','FRF_OK','mega cal','drive_encoders on')):
        print(ln)
print('---')
print(Path('/home/pi/robot_nav/lidar_map/drive_cal.json').read_text())
PY
echo LIFTED_DONE
