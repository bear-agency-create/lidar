#!/bin/bash
set -e
cd /home/pi/robot_nav/lidar_map
sed -i 's/\r$//' robot-nav-watchdog.sh start_drive_map.sh flash_and_restart.sh || true
chmod +x robot-nav-watchdog.sh start_drive_map.sh

echo raspberry | sudo -S cp robot-nav.service robot-nav-watchdog.service robot-nav-watchdog.timer /etc/systemd/system/
echo raspberry | sudo -S systemctl daemon-reload
echo raspberry | sudo -S systemctl enable robot-nav.service robot-nav-watchdog.timer
echo raspberry | sudo -S systemctl stop robot-nav-watchdog.timer || true
echo raspberry | sudo -S systemctl stop robot-nav.service || true
pkill -9 -f 'lidar_map/main.py' || true
pkill -9 -f drive_encoders || true
pkill -9 -f cspc_lidar || true
fuser -k 8765/tcp || true
sleep 1

export PATH="$HOME/bin:$PATH"
echo "arduino-cli=$(command -v arduino-cli)"
arduino-cli compile --fqbn arduino:avr:mega /home/pi/robot_nav/arduino/MecanumTeleopBridge
if [ -e /dev/ttyMEGA ]; then
  MEGA="$(readlink -f /dev/ttyMEGA)"
else
  MEGA="/dev/ttyUSB1"
fi
echo "FLASH_PORT=$MEGA"
arduino-cli upload -p "$MEGA" --fqbn arduino:avr:mega /home/pi/robot_nav/arduino/MecanumTeleopBridge
echo FLASH_OK

echo raspberry | sudo -S systemctl start robot-nav.service
sleep 6
echo raspberry | sudo -S systemctl start robot-nav-watchdog.timer
sleep 2
curl -s -o /dev/null -w "http=%{http_code}\n" http://127.0.0.1:8765/ || true
pgrep -af 'lidar_map/main.py|drive_encoders|cspc_lidar' | grep -v grep || true
systemctl is-active robot-nav.service robot-nav-watchdog.timer || true
python3 - <<'PY'
import json
from pathlib import Path
cal=json.loads(Path('/home/pi/robot_nav/lidar_map/drive_cal.json').read_text())
print('cal_wscale', cal.get('wheel_scale_pct'), 'trim', cal.get('trim_w'))
PY
