#!/usr/bin/env python3
"""Isolate each mecanum wheel at high PWM via WSCALE (others at 40%)."""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else (
    "/dev/ttyMEGA" if Path("/dev/ttyMEGA").exists() else "/dev/ttyUSB1"
)
ENC_RE = re.compile(r"ENC FL=(-?\d+) FR=(-?\d+) RL=(-?\d+) RR=(-?\d+)")
NAMES = ("FL", "FR", "RL", "RR")


def drain(ser, sec=0.3):
    t0 = time.time()
    while time.time() - t0 < sec:
        ser.read(512)
        time.sleep(0.02)


def cmd(ser, line, wait=0.1):
    ser.write((line + "\n").encode())
    time.sleep(wait)
    return ser.read(512).decode("ascii", "ignore")


def enc(ser):
    ser.reset_input_buffer()
    ser.write(b"ENC?\n")
    t0 = time.time()
    while time.time() - t0 < 0.8:
        raw = ser.readline().decode("ascii", "ignore").strip()
        m = ENC_RE.search(raw)
        if m:
            return [int(m.group(i)) for i in range(1, 5)]
    return None


def burst(ser, label, wscale, vx=500, seconds=1.4):
    scales = " ".join(str(v) for v in wscale)
    cmd(ser, f"SET_WSCALE {scales}", 0.12)
    cmd(ser, "STOP", 0.2)
    drain(ser, 0.15)
    e0 = enc(ser)
    t0 = time.time()
    while time.time() - t0 < seconds:
        ser.write(f"SET_ROBOT_VELOCITY {vx} 0 0\n".encode())
        time.sleep(0.06)
    cmd(ser, "STOP", 0.5)
    e1 = enc(ser)
    if not e0 or not e1:
        print(f"{label}: ENC fail")
        return
    d = [e1[i] - e0[i] for i in range(4)]
    print(f"{label}: WSCALE=[{scales}] dENC={d}  (focus should move)")


def main():
    print(f"port={PORT}")
    ser = serial.Serial(PORT, 115200, timeout=0.2)
    time.sleep(2.0)
    drain(ser, 0.4)
    print("PING", cmd(ser, "PING", 0.25).strip().splitlines()[-1:])
    cmd(ser, "SET_PIDV 0 0", 0.1)
    cmd(ser, "SET_FRB 100", 0.1)
    cmd(ser, "SET_FRF 100", 0.1)

    # All wheels together
    burst(ser, "ALL_FWD", [100, 100, 100, 100], 500, 1.5)
    burst(ser, "ALL_BACK", [100, 100, 100, 100], -500, 1.5)

    # Isolate one wheel at a time (others at firmware min 40%)
    for i, name in enumerate(NAMES):
        ws = [40, 40, 40, 40]
        ws[i] = 200
        burst(ser, f"ONLY_{name}_FWD", ws, 500, 1.5)
        burst(ser, f"ONLY_{name}_BACK", ws, -500, 1.5)

    # Strafe with flat scales
    cmd(ser, "SET_WSCALE 100 100 100 100", 0.1)
    for label, vy in (("STRL", 500), ("STRR", -500)):
        cmd(ser, "STOP", 0.2)
        e0 = enc(ser)
        t0 = time.time()
        while time.time() - t0 < 1.5:
            ser.write(f"SET_ROBOT_VELOCITY 0 {vy} 0\n".encode())
            time.sleep(0.06)
        cmd(ser, "STOP", 0.5)
        e1 = enc(ser)
        d = [e1[i] - e0[i] for i in range(4)] if e0 and e1 else None
        print(f"{label}: dENC={d}")

    cmd(ser, "SET_WSCALE 100 100 100 100", 0.1)
    cmd(ser, "STOP", 0.1)
    ser.close()
    print("DONE")


if __name__ == "__main__":
    main()
