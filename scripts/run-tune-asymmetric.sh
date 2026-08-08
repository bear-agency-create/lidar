#!/bin/bash
set -e
pkill -f 'lidar_map/drive_encoders.py' || true
sleep 2
python3 /tmp/tune_asymmetric_drive.py | tee /tmp/tune_asymmetric.out
echo raspberry | sudo -S systemctl restart robot-nav.service
sleep 6
pgrep -af 'main.py|drive_encoders' | grep -v grep || true
python3 - <<'PY'
from pathlib import Path
print(Path('/home/pi/robot_nav/logs/lidar_map.log').read_text(errors='ignore').splitlines()[-15:])
PY
curl -s -o /dev/null -w "http=%{http_code}\n" http://127.0.0.1:8765/
echo TUNE_DONE
