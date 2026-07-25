#!/usr/bin/env python3
"""Verify equal open-loop forward then reverse."""
import time
import serial

s = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.2)
time.sleep(2.0)
s.reset_input_buffer()
s.write(b"PING\n")
time.sleep(0.2)
print("boot", s.read(200))

def burst(vx, label, sec=1.5):
    s.write(b"RESET_ODOM\n")
    time.sleep(0.1)
    s.reset_input_buffer()
    t0 = time.time()
    last = None
    while time.time() - t0 < sec:
        s.write(f"SET_ROBOT_VELOCITY {vx} 0 0\n".encode())
        raw = s.readline().decode("ascii", "ignore").strip()
        if raw.startswith("POS"):
            last = raw
        time.sleep(0.08)
    s.write(b"STOP\n")
    time.sleep(0.2)
    s.write(b"ENC?\n")
    time.sleep(0.15)
    enc = s.readline().decode("ascii", "ignore").strip()
    print(label, last)
    print(" ", enc)

burst(500, "FWD")
time.sleep(0.8)
burst(-500, "REV")
s.close()
print("DONE")
