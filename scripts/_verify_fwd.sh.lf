#!/bin/bash
python3 - <<'PY'
import json, time, urllib.request
def post(path, body):
    req = urllib.request.Request(
        "http://127.0.0.1:8765" + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=3) as r:
        return json.load(r)

for _ in range(20):
    post("/api/cmd", {"vx": 0.85, "vy": 0.0, "w": 0.0, "teleop": True})
    time.sleep(0.08)
print("cmd", open("/tmp/robot_cmd.json").read().strip())
post("/api/cmd/stop", {})
print("stopped")
PY
pgrep -af 'drive_encoders|lidar_map/main.py' || true
tail -12 /tmp/mega_teleop.log || true
