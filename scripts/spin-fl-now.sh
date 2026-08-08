#!/bin/bash
set -e
echo raspberry | sudo -S systemctl stop robot-nav-watchdog.timer || true
pkill -f 'lidar_map/drive_encoders.py' || true
sleep 1

python3 - <<'PY'
import time, serial
from pathlib import Path
port = "/dev/ttyMEGA" if Path("/dev/ttyMEGA").exists() else "/dev/ttyUSB1"
ser = serial.Serial(port, 115200, timeout=0.2)
time.sleep(2.0)
ser.reset_input_buffer()
print("PORT", port)
print("Spinning FL (idx=0) forward 70% for 3s …")
t0 = time.time()
while time.time() - t0 < 3.0:
    ser.write(b"ONE_WHEEL 0 70\n")
    time.sleep(0.08)
ser.write(b"STOP\n")
time.sleep(0.4)
print("Spinning FL backward -70% for 3s …")
t0 = time.time()
while time.time() - t0 < 3.0:
    ser.write(b"ONE_WHEEL 0 -70\n")
    time.sleep(0.08)
ser.write(b"STOP\n")
time.sleep(0.3)
ser.close()
print("FL done")
PY

echo raspberry | sudo -S systemctl restart robot-nav.service
sleep 4
echo raspberry | sudo -S systemctl start robot-nav-watchdog.timer
echo OK
