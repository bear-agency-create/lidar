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

# Prove source matches GitHub polarity (dir>0 → IN1 HIGH)
echo "=== driveRL polarity on disk ==="
sed -n '261,268p' "$ROOT/arduino/MecanumTeleopBridge/MecanumTeleopBridge.ino"
sha256sum "$ROOT/arduino/MecanumTeleopBridge/MecanumTeleopBridge.ino"

arduino-cli compile --fqbn arduino:avr:mega "$ROOT/arduino/MecanumTeleopBridge"
MEGA="$(readlink -f /dev/ttyMEGA 2>/dev/null || true)"
if [[ -z "$MEGA" || ! -e "$MEGA" ]]; then MEGA=/dev/ttyUSB1; fi
echo "MEGA=$MEGA"
arduino-cli upload -p "$MEGA" --fqbn arduino:avr:mega "$ROOT/arduino/MecanumTeleopBridge"
sleep 2.5

python3 <<'PY'
import re, time, serial
from pathlib import Path
PORT = "/dev/ttyMEGA" if Path("/dev/ttyMEGA").exists() else "/dev/ttyUSB1"
ENC = re.compile(r"ENC FL=(-?\d+) FR=(-?\d+) RL=(-?\d+) RR=(-?\d+)")
ser = serial.Serial(PORT, 115200, timeout=0.35)
time.sleep(2.2)
ser.reset_input_buffer()

def enc():
    ser.reset_input_buffer(); ser.write(b"ENC?\n"); t0=time.time()
    while time.time()-t0<0.8:
        m=ENC.search(ser.readline().decode("ascii","ignore"))
        if m: return [int(m.group(i)) for i in range(1,5)]
    return None

def lines(sec=2.0):
    out=[]; t0=time.time()
    while time.time()-t0<sec:
        line=ser.readline().decode("ascii","ignore").strip()
        if line and not line.startswith("POS "): out.append(line)
    return out

print("PORT", PORT, "GITHUB_PURE_FLASH")
ser.write(b"PING\n"); print("PING", lines(0.6))
for label, cmd in [("RL_+1", b"TEST_WHEEL 2 1 1500\n"), ("RL_-1", b"TEST_WHEEL 2 -1 1500\n")]:
    e0=enc(); print(">>", cmd.decode().strip()); ser.write(cmd); print("<<", lines(2.0))
    ser.write(b"STOP\n"); time.sleep(0.4); e1=enc()
    d=[e1[i]-e0[i] for i in range(4)] if e0 and e1 else None
    print(f"{label} RL={d[2] if d else None} dENC={d}")
ser.close()
print("PURE_GITHUB_TEST_DONE")
PY

echo raspberry | sudo -S systemctl start robot-nav.service
sleep 6
echo raspberry | sudo -S systemctl start robot-nav-watchdog.timer || true
systemctl is-active robot-nav
curl -s -o /dev/null -w 'http=%{http_code}\n' http://127.0.0.1:8765/
echo PURE_GITHUB_DEPLOY_DONE
