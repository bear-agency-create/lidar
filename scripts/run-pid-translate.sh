#!/bin/bash
set -e
ROOT=/home/pi/robot_nav
echo raspberry | sudo -S systemctl stop robot-nav-watchdog.timer || true
echo raspberry | sudo -S systemctl stop robot-nav.service || true
pkill -9 -f drive_encoders || true
pkill -9 -f 'lidar_map/main.py' || true
fuser -k /dev/ttyMEGA 2>/dev/null || true
sleep 2

export PATH="$HOME/bin:$PATH"
echo "=== flash PID+FL firmware ==="
arduino-cli compile --fqbn arduino:avr:mega "$ROOT/arduino/MecanumTeleopBridge"
MEGA="$(readlink -f /dev/ttyMEGA 2>/dev/null || echo /dev/ttyUSB1)"
arduino-cli upload -p "$MEGA" --fqbn arduino:avr:mega "$ROOT/arduino/MecanumTeleopBridge"
sleep 2

echo "=== setup_pid_translate (ONE_WHEEL cal + short FWD/BACK/STRL/STRR) ==="
python3 "$ROOT/lidar_map/tools/setup_pid_translate.py" /dev/ttyMEGA | tee /tmp/setup_pid_translate.out

echo "=== restart stack ==="
echo raspberry | sudo -S systemctl start robot-nav.service
sleep 6
echo raspberry | sudo -S systemctl start robot-nav-watchdog.timer
pgrep -af 'main.py|drive_encoders' | grep -v grep || true
python3 - <<'PY'
from pathlib import Path
t=Path('/home/pi/robot_nav/logs/lidar_map.log').read_text(errors='replace')
for ln in t.splitlines()[-40:]:
    if any(x in ln for x in ('mega cal','PIDV_OK','WSCALE_OK','drive_encoders on','FL_ENC')):
        print(ln)
print('--- cal ---')
print(Path('/home/pi/robot_nav/lidar_map/drive_cal.json').read_text())
PY
curl -s -o /dev/null -w "http=%{http_code}\n" http://127.0.0.1:8765/
echo PID_TRANSLATE_DONE
