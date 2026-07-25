#!/usr/bin/env python3
import serial
import time
from collections import Counter

PORT = "/dev/ttyUSB0"
ser = serial.Serial(PORT, 115200, timeout=0.2)
time.sleep(0.5)
ser.reset_input_buffer()
lines = []
t0 = time.time()
while time.time() - t0 < 3.0:
    raw = ser.readline()
    if not raw:
        continue
    line = raw.decode("ascii", "ignore").strip()
    if line:
        lines.append(line)
ser.close()
print("N", len(lines))
for line in lines[:50]:
    print(line)
print("--- prefixes ---")
print(Counter((line.split() or ["?"])[0] for line in lines).most_common(20))
pos = [line for line in lines if "POS" in line]
print("POS samples", len(pos))
for line in pos[:10]:
    print(line)
