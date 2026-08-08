#!/bin/bash
set -euo pipefail
ROOT=/home/pi/robot_nav
export PATH="$HOME/bin:$PATH"

echo raspberry | sudo -S systemctl stop robot-nav-watchdog.timer || true
echo raspberry | sudo -S systemctl stop robot-nav.service || true
pkill -9 -f drive_encoders.py || true
pkill -9 -f 'lidar_map/main.py' || true
fuser -k /dev/ttyMEGA 2>/dev/null || true
fuser -k /dev/ttyUSB1 2>/dev/null || true
sleep 2

SKETCH="$ROOT/arduino/CleanFwdBack"
echo "=== FLASH CLEAN SKETCH ==="
arduino-cli compile --fqbn arduino:avr:mega "$SKETCH"
MEGA="$(readlink -f /dev/ttyMEGA 2>/dev/null || true)"
if [[ -z "$MEGA" || ! -e "$MEGA" ]]; then MEGA=/dev/ttyUSB1; fi
echo "MEGA=$MEGA"
arduino-cli upload -p "$MEGA" --fqbn arduino:avr:mega "$SKETCH"
sleep 2.5

echo "=== IDLE FWD/BACK TRIP ==="
python3 <<'PY'
import time, serial
from pathlib import Path
PORT = "/dev/ttyMEGA" if Path("/dev/ttyMEGA").exists() else "/dev/ttyUSB1"
ser = serial.Serial(PORT, 115200, timeout=0.4)
time.sleep(2.2)
ser.reset_input_buffer()

def read_for(sec):
    lines = []
    t0 = time.time()
    while time.time() - t0 < sec:
        line = ser.readline().decode("ascii", "ignore").strip()
        if line:
            print("<<", line, flush=True)
            lines.append(line)
    return lines

print("PORT", PORT)
ser.write(b"PING\n")
read_for(0.8)
print(">> AUTO (FWD 2s, pause, BACK 2s)")
ser.write(b"AUTO\n")
read_for(8.0)
ser.write(b"STOP\n")
read_for(0.5)
ser.close()
print("CLEAN_TRIP_DONE")
PY

echo "=== RESTORE MecanumTeleopBridge (GitHub) ==="
arduino-cli compile --fqbn arduino:avr:mega "$ROOT/arduino/MecanumTeleopBridge"
arduino-cli upload -p "$MEGA" --fqbn arduino:avr:mega "$ROOT/arduino/MecanumTeleopBridge"
sleep 2
echo raspberry | sudo -S systemctl start robot-nav.service
sleep 5
echo raspberry | sudo -S systemctl start robot-nav-watchdog.timer || true
systemctl is-active robot-nav || true
curl -s -o /dev/null -w 'http=%{http_code}\n' http://127.0.0.1:8765/ || true
echo ALL_DONE
