#!/usr/bin/env python3
"""Quick bidirectional check: ONE_WHEEL RL ± and FWD/BACK mix (open-loop)."""
from __future__ import annotations

import re
import time
from pathlib import Path

import serial

PORT = "/dev/ttyMEGA" if Path("/dev/ttyMEGA").exists() else "/dev/ttyUSB1"
ENC = re.compile(r"ENC FL=(-?\d+) FR=(-?\d+) RL=(-?\d+) RR=(-?\d+)")


def drain(ser, sec=0.3):
    t0 = time.time()
    while time.time() - t0 < sec:
        ser.read(512)
        time.sleep(0.02)


def cmd(ser, line, wait=0.1):
    ser.write((line + "\n").encode())
    time.sleep(wait)
    return ser.read(1024).decode("ascii", "ignore")


def enc(ser):
    ser.reset_input_buffer()
    ser.write(b"ENC?\n")
    t0 = time.time()
    while time.time() - t0 < 0.8:
        m = ENC.search(ser.readline().decode("ascii", "ignore"))
        if m:
            return [int(m.group(i)) for i in range(1, 5)]
    return None


def pulse_one(ser, pct, sec=0.9):
    cmd(ser, "STOP", 0.15)
    e0 = enc(ser)
    t0 = time.time()
    while time.time() - t0 < sec:
        ser.write(f"ONE_WHEEL 2 {pct}\n".encode())
        time.sleep(0.07)
    cmd(ser, "STOP", 0.25)
    e1 = enc(ser)
    d = [e1[i] - e0[i] for i in range(4)] if e0 and e1 else None
    print(f"ONE_WHEEL RL {pct:+4d}%  dENC={d}  RL={d[2] if d else None}")
    return d


def pulse_vel(ser, label, vx, vy, sec=1.0):
    cmd(ser, "STOP", 0.15)
    cmd(ser, "SET_PIDV 0 0", 0.08)
    cmd(ser, "SET_WSCALE 100 100 100 100", 0.08)
    cmd(ser, "SET_RLB 100", 0.05)
    e0 = enc(ser)
    t0 = time.time()
    out_line = ""
    while time.time() - t0 < sec:
        ser.write(f"SET_ROBOT_VELOCITY {vx} {vy} 0\n".encode())
        time.sleep(0.07)
        if not out_line and time.time() - t0 > 0.35:
            ser.write(b"WHEEL_OUT?\n")
            time.sleep(0.1)
            raw = ser.read(512).decode("ascii", "ignore")
            out_line = next((l for l in raw.splitlines() if "OUT" in l), raw.strip()[:120])
    cmd(ser, "STOP", 0.3)
    e1 = enc(ser)
    d = [e1[i] - e0[i] for i in range(4)] if e0 and e1 else None
    print(f"[{label}] vx={vx} vy={vy}")
    print(f"  WHEEL_OUT: {out_line}")
    print(f"  dENC={d}  RL={d[2] if d else None}")
    return d


def main():
    print("PORT", PORT)
    ser = serial.Serial(PORT, 115200, timeout=0.2)
    time.sleep(2.2)
    drain(ser, 0.4)
    print("PING", cmd(ser, "PING", 0.25).strip().splitlines()[-2:])
    cmd(ser, "SET_PIDV 0 0", 0.08)
    cmd(ser, "SET_RLB 100", 0.05)
    cmd(ser, "SET_WSCALE 100 100 100 100", 0.08)

    pulse_one(ser, 70)
    time.sleep(0.35)
    pulse_one(ser, -70)
    time.sleep(0.35)
    pulse_vel(ser, "FWD", 320, 0)
    time.sleep(0.35)
    pulse_vel(ser, "BACK", -320, 0)
    time.sleep(0.35)
    pulse_vel(ser, "STRL", 0, 320)
    time.sleep(0.35)
    pulse_vel(ser, "STRR", 0, -320)

    cmd(ser, "STOP", 0.1)
    ser.close()
    print("DONE")


if __name__ == "__main__":
    main()
