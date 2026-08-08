#!/usr/bin/env python3
"""RL-only mix vs full BACK — isolate multi-wheel effect."""
from __future__ import annotations

import re
import time
from pathlib import Path

import serial

PORT = "/dev/ttyMEGA" if Path("/dev/ttyMEGA").exists() else "/dev/ttyUSB1"
ENC_RE = re.compile(r"ENC FL=(-?\d+) FR=(-?\d+) RL=(-?\d+) RR=(-?\d+)")


def drain(ser, sec=0.25):
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
    while time.time() - t0 < 0.7:
        m = ENC_RE.search(ser.readline().decode("ascii", "ignore"))
        if m:
            return [int(m.group(i)) for i in range(1, 5)]
    return None


def burst_vel(ser, label, wscale, vx, vy, sec=1.3):
    cmd(ser, f"SET_WSCALE {wscale}", 0.1)
    cmd(ser, "SET_PIDV 0 0", 0.08)
    cmd(ser, "SET_RLB 185", 0.08)
    cmd(ser, "STOP", 0.15)
    e0 = enc(ser)
    t0 = time.time()
    while time.time() - t0 < sec:
        ser.write(f"SET_ROBOT_VELOCITY {vx} {vy} 0\n".encode())
        time.sleep(0.07)
    # sample out mid-run already done; stop
    ser.write(b"WHEEL_OUT?\n")
    time.sleep(0.1)
    out = ser.read(512).decode("ascii", "ignore").strip().splitlines()
    out_line = next((l for l in out if "OUT" in l), "?")
    cmd(ser, "STOP", 0.3)
    e1 = enc(ser)
    d = None if not e0 or not e1 else [e1[i] - e0[i] for i in range(4)]
    print(f"{label}: {out_line}")
    print(f"  dENC={d} RL={d[2] if d else None}")


def burst_one(ser, pct, sec=1.0):
    cmd(ser, "STOP", 0.15)
    e0 = enc(ser)
    t0 = time.time()
    while time.time() - t0 < sec:
        ser.write(f"ONE_WHEEL 2 {pct}\n".encode())
        time.sleep(0.07)
    cmd(ser, "STOP", 0.3)
    e1 = enc(ser)
    d = [e1[i] - e0[i] for i in range(4)]
    print(f"ONE_WHEEL {pct}%: dENC={d} RL={d[2]}")


def main():
    ser = serial.Serial(PORT, 115200, timeout=0.2)
    time.sleep(2.0)
    drain(ser, 0.4)
    print("PING", cmd(ser, "PING", 0.2).strip().splitlines()[-1:])

    burst_one(ser, -55)
    burst_one(ser, -90)
    burst_vel(ser, "onlyRL_BACK_-280", "0 0 100 0", -280, 0)
    burst_vel(ser, "onlyRL_BACK_-500", "0 0 100 0", -500, 0)
    burst_vel(ser, "onlyRL_STRR", "0 0 100 0", 0, -280)
    burst_vel(ser, "all_BACK_-500", "100 100 100 100", -500, 0)
    burst_vel(ser, "all_BACK_RLB250", "100 100 100 100", -500, 0)
    # max RLB
    cmd(ser, "SET_RLB 250", 0.1)
    burst_vel(ser, "all_BACK_rlb250_cmd", "100 100 100 100", -400, 0)

    cmd(ser, "SET_WSCALE 100 100 100 100", 0.1)
    cmd(ser, "SET_RLB 185", 0.1)
    ser.close()
    print("DONE")


if __name__ == "__main__":
    main()
