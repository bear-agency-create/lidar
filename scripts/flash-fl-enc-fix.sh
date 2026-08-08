#!/bin/bash
set -e
ROOT=/home/pi/robot_nav
echo raspberry | sudo -S systemctl stop robot-nav-watchdog.timer || true
echo raspberry | sudo -S systemctl stop robot-nav.service || true
pkill -9 -f drive_encoders || true
sleep 2
export PATH="$HOME/bin:$PATH"
arduino-cli compile --fqbn arduino:avr:mega "$ROOT/arduino/MecanumTeleopBridge"
MEGA="$(readlink -f /dev/ttyMEGA 2>/dev/null || echo /dev/ttyUSB1)"
arduino-cli upload -p "$MEGA" --fqbn arduino:avr:mega "$ROOT/arduino/MecanumTeleopBridge"
sleep 2

python3 - <<'PY'
import re, time, serial
from pathlib import Path
port="/dev/ttyMEGA" if Path("/dev/ttyMEGA").exists() else "/dev/ttyUSB1"
ser=serial.Serial(port,115200,timeout=0.2)
time.sleep(2.0)
ENC=re.compile(r"ENC FL=(-?\d+) FR=(-?\d+) RL=(-?\d+) RR=(-?\d+)")

def enc():
    ser.reset_input_buffer(); ser.write(b"ENC?\n")
    t0=time.time()
    while time.time()-t0<0.7:
        m=ENC.search(ser.readline().decode("ascii","ignore"))
        if m: return [int(m.group(i)) for i in range(1,5)]
    return None

ser.write(b"RESET_ODOM\n"); time.sleep(0.1)
e0=enc()
print("start", e0)
t0=time.time()
while time.time()-t0<2.5:
    ser.write(b"ONE_WHEEL 0 80\n"); time.sleep(0.05)
ser.write(b"STOP\n"); time.sleep(0.2)
e1=enc()
print("end", e1)
print("delta", None if not e0 or not e1 else [e1[i]-e0[i] for i in range(4)])
ser.write(b"ENC_LEVELS\n"); time.sleep(0.1)
print(ser.read(512).decode("ascii","ignore"))
ser.close()
PY

echo raspberry | sudo -S systemctl start robot-nav.service
sleep 5
echo raspberry | sudo -S systemctl start robot-nav-watchdog.timer
echo FIXED_DONE
