#!/usr/bin/env python3
import serial
import time

s = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.15)
time.sleep(2.2)
s.reset_input_buffer()
s.write(b"SET_POSE 0 0 0\n")
time.sleep(0.15)
s.reset_input_buffer()
s.write(b"w\n")
t0 = time.time()
rows = []
while time.time() - t0 < 2.2:
    if time.time() - t0 > 1.0:
        s.write(b"w\n")
    line = s.readline().decode("ascii", "ignore").strip()
    if line.startswith("POS") or line.startswith("ENC"):
        rows.append(line)
s.write(b"STOP\n")
time.sleep(0.2)
s.write(b"ENC?\n")
time.sleep(0.25)
for _ in range(12):
    line = s.readline().decode("ascii", "ignore").strip()
    if line:
        rows.append("AFTER " + line)
s.close()
print("samples", len(rows))
for r in rows[:3]:
    print(r)
print("...")
for r in rows[-8:]:
    print(r)
