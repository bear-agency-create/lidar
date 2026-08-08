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

def drain(sec=0.3):
    t0 = time.time()
    while time.time() - t0 < sec:
        ser.read(512); time.sleep(0.02)

def enc():
    ser.reset_input_buffer(); ser.write(b"ENC?\n"); t0 = time.time()
    while time.time() - t0 < 0.8:
        m = ENC.search(ser.readline().decode("ascii", "ignore"))
        if m: return [int(m.group(i)) for i in range(1, 5)]
    return None

def lines_for(sec=2.5):
    out = []
    t0 = time.time()
    while time.time() - t0 < sec:
        line = ser.readline().decode("ascii", "ignore").strip()
        if line and not line.startswith("POS "):
            out.append(line)
    return out

print("PORT", PORT)
ser.write(b"PING\n"); print("PING", lines_for(0.8))

for label, cmd in [
    ("RL_FWD", b"TEST_WHEEL 2 1 1500\n"),
    ("RL_BACK", b"TEST_WHEEL 2 -1 1500\n"),
]:
    drain(0.2)
    e0 = enc()
    print(">>", cmd.decode().strip())
    ser.write(cmd)
    print("<<", lines_for(2.0))
    ser.write(b"STOP\n"); time.sleep(0.4)
    e1 = enc()
    d = [e1[i]-e0[i] for i in range(4)] if e0 and e1 else None
    print(f"{label} dENC={d} RL={d[2] if d else None}")

for label, vx in [("FWD", 400), ("BACK", -400)]:
    ser.write(b"SET_PIDV 0 0\n"); time.sleep(0.05)
    ser.write(b"SET_WSCALE 200 200 200 200\n"); time.sleep(0.05)
    e0 = enc(); t0 = time.time()
    while time.time()-t0 < 1.2:
        ser.write(f"SET_ROBOT_VELOCITY {vx} 0 0\n".encode()); time.sleep(0.07)
    ser.write(b"WHEEL_OUT?\n"); time.sleep(0.12)
    wo = [l for l in ser.read(512).decode("ascii","ignore").splitlines() if "OUT" in l]
    ser.write(b"STOP\n"); time.sleep(0.35)
    e1 = enc()
    d = [e1[i]-e0[i] for i in range(4)] if e0 and e1 else None
    print(f"{label}: {wo[-1] if wo else '?'} RL={d[2] if d else None} dENC={d}")

ser.close()
print("GITHUB_FIX_TEST_DONE")
PY
echo raspberry | sudo -S systemctl start robot-nav.service
sleep 6
echo raspberry | sudo -S systemctl start robot-nav-watchdog.timer || true
systemctl is-active robot-nav
curl -s -o /dev/null -w 'http=%{http_code}\n' http://127.0.0.1:8765/
echo DEPLOY_DONE
