#!/bin/bash
set -euo pipefail
export PATH="$HOME/bin:$PATH"
pkill -9 -f drive_encoders.py || true
pkill -9 -f lidar_map/main.py || true
pkill -9 -f cspc_lidar || true
fuser -k /dev/ttyMEGA /dev/ttyUSB0 2>/dev/null || true
sleep 1
MEGA="$(readlink -f /dev/ttyMEGA 2>/dev/null || echo /dev/ttyUSB0)"
echo "MEGA=$MEGA"
SKETCH="$HOME/robot_nav/arduino/WheelSweepMax"
arduino-cli compile --fqbn arduino:avr:mega "$SKETCH"
arduino-cli upload -p "$MEGA" --fqbn arduino:avr:mega "$SKETCH"
echo FLASH_OK
sleep 2
python3 - <<PY
import serial, time
s = serial.Serial("$MEGA", 115200, timeout=0.5)
time.sleep(2.0)
t0 = time.time()
while time.time() - t0 < 14:
    line = s.readline()
    if line:
        print(line.decode("ascii", "ignore").rstrip())
    if b"DONE" in line:
        break
s.write(b"x\n")
s.close()
print("SWEEP_DONE")
PY
