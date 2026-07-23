#!/usr/bin/env python3
import json
import time
import urllib.request

print("HOLD forward 2s via API")
for _ in range(25):
    req = urllib.request.Request(
        "http://127.0.0.1:8765/api/cmd",
        data=json.dumps({"vx": 0.35, "vy": 0, "w": 0}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(req, timeout=2).read()
    time.sleep(0.08)
urllib.request.urlopen(
    urllib.request.Request("http://127.0.0.1:8765/api/cmd/stop", method="POST"),
    timeout=2,
).read()
print("STOP")
print("cmdfile:", open("/tmp/robot_cmd.json").read().strip())
print("bridge:", open("/tmp/mega_teleop.log").read()[-200:])
