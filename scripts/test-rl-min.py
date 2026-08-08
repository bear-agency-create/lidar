#!/usr/bin/env python3
"""Minimal RL reverse: try both SIGN polarities via inverted command mapping."""
from __future__ import annotations

import re
import time
from pathlib import Path

import serial

PORT = "/dev/ttyMEGA" if Path("/dev/ttyMEGA").exists() else "/dev/ttyUSB1"
ENC = re.compile(r"ENC FL=(-?\d+) FR=(-?\d+) RL=(-?\d+) RR=(-?\d+)")


def enc(ser):
    ser.reset_input_buffer()
    ser.write(b"ENC?\n")
    t0 = time.time()
    while time.time() - t0 < 0.8:
        m = ENC.search(ser.readline().decode("ascii", "ignore"))
        if m:
            return [int(m.group(i)) for i in range(1, 5)]
    return None


def one(ser, pct, sec=1.5):
    e0 = enc(ser)
    t0 = time.time()
    while time.time() - t0 < sec:
        ser.write(f"ONE_WHEEL 2 {pct}\n".encode())
        time.sleep(0.06)
    ser.write(b"STOP\n")
    time.sleep(0.35)
    e1 = enc(ser)
    d = [e1[i] - e0[i] for i in range(4)] if e0 and e1 else None
    print(f"ONE_WHEEL {pct:+4d}%  {sec}s  dENC={d}  RL={d[2] if d else None}")
    return d


def main():
    ser = serial.Serial(PORT, 115200, timeout=0.2)
    time.sleep(2.5)
    ser.reset_input_buffer()
    ser.write(b"PING\n")
    time.sleep(0.3)
    print(ser.read(200))
    for pct in (70, -70, 100, -100, 70, -70):
        one(ser, pct)
        time.sleep(0.5)
    ser.close()
    print("DONE")


if __name__ == "__main__":
    main()
