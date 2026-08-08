#!/bin/bash
bash /home/pi/robot_nav/lidar_map/start_drive_map.sh
sleep 5
pgrep -af 'cspc_lidar|drive_encoders|lidar_map/main.py' || true
echo ---
python3 - <<'PY'
import urllib.request, json
j = json.load(urllib.request.urlopen("http://127.0.0.1:8765/api/scan", timeout=4))
print(j.get("ok"), j.get("error"), "odom", j.get("odom_ok"), "pts", len(j.get("points") or []))
PY
echo ---
tail -12 /tmp/lidar_usb0.log || true
echo DONE
