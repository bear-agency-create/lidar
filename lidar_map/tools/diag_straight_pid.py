#!/usr/bin/env python3
"""Straight-drive encoder PID diagnostic on Mega."""
import math
import re
import time
import serial

s = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.2)
time.sleep(2.0)
s.reset_input_buffer()
s.write(b"PING\n")
time.sleep(0.3)
print("boot", repr(s.read(300)))
s.write(b"ENC?\n")
time.sleep(0.2)
print("enc0", repr(s.read(200)))

s.write(b"SET_ROBOT_VELOCITY 500 0 0\n")
lines = []
enc_rows = []
t0 = time.time()
while time.time() - t0 < 2.5:
    s.write(b"SET_ROBOT_VELOCITY 500 0 0\n")
    raw = s.readline().decode("ascii", "ignore").strip()
    if raw.startswith("POS"):
        lines.append(raw)
        s.write(b"ENC?\n")
    elif raw.startswith("ENC"):
        enc_rows.append(raw)
    time.sleep(0.08)
s.write(b"STOP\n")
time.sleep(0.2)
print("n_pos", len(lines))

def parse_pos(ln):
    m = re.search(
        r"X=([-\d.]+) Y=([-\d.]+) Th=([-\d.]+) L=(-?\d+) R=(-?\d+) C=([-\d.]+)",
        ln,
    )
    if not m:
        return None
    return tuple(float(m.group(i)) for i in range(1, 7))

first = parse_pos(lines[0]) if lines else None
last = parse_pos(lines[-1]) if lines else None
if first and last:
    dx = last[0] - first[0]
    dy = last[1] - first[1]
    dth = last[2] - first[2]
    while dth > math.pi:
        dth -= 2 * math.pi
    while dth < -math.pi:
        dth += 2 * math.pi
    dist = math.hypot(dx, dy)
    print(
        f"SUMMARY dist={dist:.0f}mm dTh={math.degrees(dth):.1f}deg "
        f"L={int(last[3])} R={int(last[4])} C={last[5]:.1f}"
    )
    print(f"  path_efficiency={dist / max(1.0, abs(last[3])+abs(last[4])):.2f} mm/tickpair")

step = max(1, len(lines) // 8)
for ln in lines[::step]:
    print(ln)
if enc_rows:
    print("enc_last", enc_rows[-1])

prev = None
imb = []
for ln in lines:
    p = parse_pos(ln)
    if not p:
        continue
    L, R, C = int(p[3]), int(p[4]), p[5]
    if prev is not None:
        dL, dR = L - prev[0], R - prev[1]
        if abs(dL) + abs(dR) > 0:
            imbalance = dL - dR
            imb.append(imbalance)
            print(f"dL={dL:4d} dR={dR:4d} C={C:6.1f} imbalance={imbalance}")
    prev = (L, R)
if imb:
    avg = sum(imb) / len(imb)
    print(f"avg_imbalance={avg:.1f} (0=ideal)")
s.close()
print("DONE")
