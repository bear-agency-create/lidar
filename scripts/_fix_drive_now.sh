#!/bin/bash
set -e
pkill -9 -f drive_encoders.py || true
pkill -9 -f lidar_map/main.py || true
pkill -9 -f cspc_lidar || true
fuser -k /dev/ttyMEGA /dev/ttyUSB0 2>/dev/null || true
sleep 1
bash /home/pi/robot_nav/lidar_map/flash_smooth.sh
sleep 2
bash /home/pi/robot_nav/lidar_map/start_drive_map.sh
sleep 5
python3 - <<'PY'
import serial, time, os, subprocess, json, urllib.request
# quick motor proof while drive is up: use API burst
def post(path, body):
    req = urllib.request.Request(
        "http://127.0.0.1:8765" + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=3) as r:
        return json.load(r)

print("api_fwd", post("/api/cmd", {"vx": 0.85, "vy": 0, "w": 0, "teleop": True}))
time.sleep(1.2)
print("cmdfile", open("/tmp/robot_cmd.json").read().strip())
print("api_stop", post("/api/cmd/stop", {}))
time.sleep(0.3)
# direct serial check
subprocess.call("pkill -9 -f drive_encoders.py", shell=True)
time.sleep(1.0)
s = serial.Serial("/dev/ttyMEGA", 115200, timeout=0.25)
time.sleep(2.0)
s.reset_input_buffer()
s.write(b"ENC?\n"); time.sleep(0.2); print("enc0", s.read(120))
t0 = time.time()
while time.time() - t0 < 1.2:
    s.write(b"SET_ROBOT_VELOCITY 500 0 0\n")
    time.sleep(0.05)
s.write(b"ENC?\n"); time.sleep(0.25); print("enc1", s.read(120))
s.write(b"HARD_STOP\n"); time.sleep(0.2)
s.close()
# bring drive back
os.system("MEGA_DEV=/dev/ttyMEGA nohup python3 /home/pi/robot_nav/lidar_map/drive_encoders.py >>/tmp/mega_teleop.log 2>&1 &")
time.sleep(3)
print("procs:")
os.system("pgrep -af 'drive_encoders|lidar_map/main' | grep -v grep || true")
print("DONE")
PY
