#!/usr/bin/env python3
from pathlib import Path
import json
import subprocess
import urllib.request

print("USB0", Path("/dev/ttyUSB0").exists())
print("USB1", Path("/dev/ttyUSB1").exists())
for name in ("ttyLIDAR", "ttyMEGA"):
    p = Path("/dev") / name
    print(name, p.exists(), p.resolve() if p.exists() else None)
print("robot-nav", subprocess.getoutput("systemctl is-active robot-nav.service"))
print("procs:")
print(subprocess.getoutput("pgrep -af 'cspc_lidar|drive_encoders|lidar_map/main' || true"))
try:
    with urllib.request.urlopen("http://127.0.0.1:8765/api/scan", timeout=4) as r:
        j = json.load(r)
    print("scan_ok", j.get("ok"), "stale", j.get("stale"), "error", j.get("error"))
    print("points", len(j.get("points") or []))
    print("odom_ok", j.get("odom_ok"), "mapping", j.get("mapping"))
except Exception as e:
    print("scan_err", e)
