#!/usr/bin/env python3
"""After SIGN_RL flip: measure FWD vs BACK RL ticks."""
import re, time, serial
from pathlib import Path

PORT = "/dev/ttyMEGA" if Path("/dev/ttyMEGA").exists() else "/dev/ttyUSB1"
ENC = re.compile(r"ENC FL=(-?\d+) FR=(-?\d+) RL=(-?\d+) RR=(-?\d+)")
ser = serial.Serial(PORT, 115200, timeout=0.2)
time.sleep(2.5)


def enc():
    ser.reset_input_buffer(); ser.write(b"ENC?\n")
    t0 = time.time()
    while time.time() - t0 < 0.8:
        m = ENC.search(ser.readline().decode("ascii", "ignore"))
        if m:
            return [int(m.group(i)) for i in range(1, 5)]
    return None


def burst(label, cmd, sec=1.2):
    ser.write(b"STOP\n"); time.sleep(0.2)
    e0 = enc()
    t0 = time.time()
    while time.time() - t0 < sec:
        ser.write((cmd + "\n").encode()); time.sleep(0.07)
    ser.write(b"STOP\n"); time.sleep(0.35)
    e1 = enc()
    d = [e1[i] - e0[i] for i in range(4)] if e0 and e1 else None
    print(f"{label}: dENC={d} RL={d[2] if d else None}")

for pct in (80, -80):
    burst(f"ONE {pct}", f"ONE_WHEEL 2 {pct}")
ser.write(b"SET_PIDV 0 0\n"); time.sleep(0.1)
ser.write(b"SET_RLB 200\n"); time.sleep(0.1)
ser.write(b"SET_WSCALE 100 100 100 100\n"); time.sleep(0.1)
burst("FWD", "SET_ROBOT_VELOCITY 350 0 0")
burst("BACK", "SET_ROBOT_VELOCITY -350 0 0")
burst("STRL", "SET_ROBOT_VELOCITY 0 350 0")
burst("STRR", "SET_ROBOT_VELOCITY 0 -350 0")
ser.close()
print("DONE")
