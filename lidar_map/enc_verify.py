#!/usr/bin/env python3
import serial
import time

s = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.2)
time.sleep(2)
s.reset_input_buffer()
s.write(b"w\n")
time.sleep(2.0)
enc = []
pos = []
t0 = time.time()
while time.time() - t0 < 2.5:
    line = s.readline().decode("ascii", "ignore").strip()
    if not line:
        continue
    if line.startswith("ENC"):
        enc.append(line)
    if line.startswith("POS"):
        pos.append(line)
s.write(b"STOP\n")
time.sleep(0.3)
s.write(b"ENC?\n")
time.sleep(0.2)
print("after STOP:")
for _ in range(8):
    line = s.readline().decode("ascii", "ignore").strip()
    if line:
        print(line)
print("ENC samples", len(enc))
for e in enc[-4:]:
    print(e)
print("POS first", pos[0] if pos else None)
print("POS last", pos[-1] if pos else None)
s.close()
