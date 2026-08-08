#!/usr/bin/env python3
"""Diagnose BL/RL: ONE_WHEEL ± vs BACK / STRR mix. Dump WHEEL_OUT + ENC."""
from __future__ import annotations

import re
import time
from pathlib import Path

import serial

PORT = "/dev/ttyMEGA" if Path("/dev/ttyMEGA").exists() else "/dev/ttyUSB1"
ENC_RE = re.compile(r"ENC FL=(-?\d+) FR=(-?\d+) RL=(-?\d+) RR=(-?\d+)")


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
    while time.time() - t0 < 0.7:
        raw = ser.readline().decode("ascii", "ignore").strip()
        m = ENC_RE.search(raw)
        if m:
            return [int(m.group(i)) for i in range(1, 5)]
    return None


def wheel_out(ser):
    out = cmd(ser, "WHEEL_OUT?", 0.12)
    for line in out.splitlines():
        if "OUT" in line or "t2=" in line:
            return line.strip()
    return out.strip().replace("\n", " | ")


def pulse_velocity(ser, label, vx, vy, sec=1.2):
    cmd(ser, "STOP", 0.2)
    cmd(ser, "SET_PIDV 0 0", 0.1)  # force open-loop for test
    cmd(ser, "SET_WSCALE 100 100 100 100", 0.1)
    e0 = enc(ser)
    t0 = time.time()
    last_out = ""
    while time.time() - t0 < sec:
        ser.write(f"SET_ROBOT_VELOCITY {vx} {vy} 0\n".encode())
        time.sleep(0.08)
        if time.time() - t0 > 0.4 and not last_out:
            last_out = wheel_out(ser)
    cmd(ser, "STOP", 0.25)
    e1 = enc(ser)
    d = None if not e0 or not e1 else [e1[i] - e0[i] for i in range(4)]
    print(f"\n[{label}] vx={vx} vy={vy}")
    print(f"  WHEEL_OUT: {last_out}")
    print(f"  dENC: {d}  (RL delta={d[2] if d else None})")
    return d, last_out


def pulse_one(ser, label, pct, sec=1.0):
    cmd(ser, "STOP", 0.2)
    e0 = enc(ser)
    t0 = time.time()
    while time.time() - t0 < sec:
        ser.write(f"ONE_WHEEL 2 {pct}\n".encode())
        time.sleep(0.08)
    cmd(ser, "STOP", 0.25)
    e1 = enc(ser)
    d = None if not e0 or not e1 else [e1[i] - e0[i] for i in range(4)]
    print(f"\n[{label}] ONE_WHEEL RL {pct}%")
    print(f"  dENC: {d}  (RL delta={d[2] if d else None})")
    return d


def main():
    print("PORT", PORT)
    ser = serial.Serial(PORT, 115200, timeout=0.2)
    time.sleep(2.2)
    drain(ser, 0.5)
    print("PING", cmd(ser, "PING", 0.25).strip().splitlines()[-2:])
    cmd(ser, "SET_FL_ENC_MODE 2", 0.08)

    # Baseline: isolated RL both ways
    pulse_one(ser, "RL_FWD", 70)
    time.sleep(0.4)
    pulse_one(ser, "RL_BACK", -70)
    time.sleep(0.4)

    # Body cmds that user says kill BL
    pulse_velocity(ser, "BACK", -280, 0)
    time.sleep(0.4)
    pulse_velocity(ser, "STRR", 0, -280)
    time.sleep(0.4)
    # Controls that work
    pulse_velocity(ser, "FWD", 280, 0)
    time.sleep(0.4)
    pulse_velocity(ser, "STRL", 0, 280)

    cmd(ser, "STOP", 0.1)
    ser.close()
    print("\nDONE")


if __name__ == "__main__":
    main()
