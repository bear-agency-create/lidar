#!/bin/bash
set -e
echo raspberry | sudo -S systemctl stop robot-nav-watchdog.timer || true
pkill -f 'lidar_map/drive_encoders.py' || true
sleep 1

python3 - <<'PY'
import re, time, serial
from pathlib import Path

port = "/dev/ttyMEGA" if Path("/dev/ttyMEGA").exists() else "/dev/ttyUSB1"
ENC_RE = re.compile(r"ENC FL=(-?\d+) FR=(-?\d+) RL=(-?\d+) RR=(-?\d+)")

ser = serial.Serial(port, 115200, timeout=0.15)
time.sleep(2.0)
ser.reset_input_buffer()

def enc():
    ser.reset_input_buffer()
    ser.write(b"ENC?\n")
    t0 = time.time()
    while time.time() - t0 < 0.8:
        line = ser.readline().decode("ascii", "ignore").strip()
        m = ENC_RE.search(line)
        if m:
            return [int(m.group(i)) for i in range(1, 5)]
    return None

def pulse(pct, sec=2.5):
    e0 = enc()
    t0 = time.time()
    samples = []
    while time.time() - t0 < sec:
        ser.write(f"ONE_WHEEL 0 {pct}\n".encode())
        # poll mid-run
        if int((time.time() - t0) * 10) % 5 == 0:
            e = enc()
            if e:
                samples.append(e)
        time.sleep(0.08)
    ser.write(b"STOP\n")
    time.sleep(0.25)
    e1 = enc()
    return e0, e1, samples

print("PORT", port)
print("baseline", enc())

for label, pct in (("FL_FWD", 80), ("FL_BACK", -80)):
    print(f"\n=== {label} {pct}% 2.5s ===")
    e0, e1, mid = pulse(pct, 2.5)
    d = None if e0 is None or e1 is None else [e1[i] - e0[i] for i in range(4)]
    print("  start", e0)
    print("  end  ", e1)
    print("  delta", d)
    if mid:
        print("  mid  ", mid[0], "…", mid[-1] if len(mid) > 1 else "")

# Also read raw a few times while stopped
print("\n=== idle ENC spam ===")
for i in range(5):
    print(" ", enc())
    time.sleep(0.15)

ser.write(b"STOP\n")
ser.close()
print("\nDONE")
PY

echo raspberry | sudo -S systemctl restart robot-nav.service
sleep 4
echo raspberry | sudo -S systemctl start robot-nav-watchdog.timer
echo OK
