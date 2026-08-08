#!/bin/bash
set -e
pkill -9 -f drive_encoders.py || true
pkill -9 -f lidar_map/main.py || true
pkill -9 -f cspc_lidar || true
fuser -k /dev/ttyMEGA /dev/ttyUSB0 2>/dev/null || true
sleep 1
bash /home/pi/robot_nav/lidar_map/flash_smooth.sh
RESTART_DRIVE=0 bash /home/pi/robot_nav/lidar_map/start_drive_map.sh || bash /home/pi/robot_nav/lidar_map/start_drive_map.sh
sleep 5
python3 - <<'PY'
import json, time, urllib.request, subprocess
def post(path, body):
    req = urllib.request.Request(
        "http://127.0.0.1:8765"+path,
        data=json.dumps(body).encode(),
        headers={"Content-Type":"application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=3) as r:
        return json.load(r)

# Hold forward like keyboard (80ms refresh) for 2s
t0 = time.time()
n = 0
while time.time() - t0 < 2.0:
    post("/api/cmd", {"vx": 0.85, "vy": 0.0, "w": 0.0, "teleop": True})
    n += 1
    time.sleep(0.08)
print("sent", n, "cmds")
print("cmdfile", open("/tmp/robot_cmd.json").read().strip())
post("/api/cmd/stop", {})
time.sleep(0.2)
print("procs:")
subprocess.call("pgrep -af 'drive_encoders|lidar_map/main.py' | grep -v grep || true", shell=True)
print("log:")
subprocess.call("tail -15 /tmp/mega_teleop.log", shell=True)
print("DONE")
PY
