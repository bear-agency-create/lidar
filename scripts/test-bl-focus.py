#!/usr/bin/env python3
"""BL/RL focus: WHEEL_OUT + ENC for ONE_WHEEL, BACK±w, STRR, only-RL mix."""
from __future__ import annotations

import re
import time
from pathlib import Path

import serial

PORT = "/dev/ttyMEGA" if Path("/dev/ttyMEGA").exists() else "/dev/ttyUSB1"
ENC_RE = re.compile(r"ENC FL=(-?\d+) FR=(-?\d+) RL=(-?\d+) RR=(-?\d+)")
OUT_RE = re.compile(
    r"t2=([-\d.]+)\s+o2=([-\d.]+).*cmd=([-\d]+),([-\d]+),([-\d]+)"
)


def drain(ser, sec=0.25):
    t0 = time.time()
    while time.time() - t0 < sec:
        ser.read(512)
        time.sleep(0.02)


def cmd(ser, line, wait=0.1):
    ser.write((line + "\n").encode())
    time.sleep(wait)
    return ser.read(2048).decode("ascii", "ignore")


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


def wheel_out(ser):
    ser.reset_input_buffer()
    ser.write(b"WHEEL_OUT?\n")
    t0 = time.time()
    while time.time() - t0 < 0.8:
        raw = ser.readline().decode("ascii", "ignore").strip()
        if raw.startswith("OUT") or "t2=" in raw:
            return raw
    return ""


def burst(ser, label, lines, drive_line, sec=1.15):
    for ln in lines:
        cmd(ser, ln, 0.08)
    cmd(ser, "STOP", 0.2)
    e0 = enc(ser)
    t0 = time.time()
    outs = []
    while time.time() - t0 < sec:
        ser.write((drive_line + "\n").encode())
        time.sleep(0.1)
        if time.time() - t0 > 0.45 and len(outs) < 3:
            outs.append(wheel_out(ser))
    cmd(ser, "STOP", 0.25)
    e1 = enc(ser)
    d = None if not e0 or not e1 else [e1[i] - e0[i] for i in range(4)]
    print(f"\n=== {label} ===")
    print(f"  drive: {drive_line}")
    for o in outs:
        m = OUT_RE.search(o)
        if m:
            print(
                f"  OUT t2={m.group(1)} o2={m.group(2)} "
                f"cmd={m.group(3)},{m.group(4)},{m.group(5)}"
            )
        else:
            print(f"  OUT raw: {o}")
    print(f"  dENC={d}  RL={d[2] if d else None}")
    return d


def main():
    print("PORT", PORT)
    ser = serial.Serial(PORT, 115200, timeout=0.2)
    time.sleep(2.0)
    drain(ser)
    print("PING", cmd(ser, "PING", 0.2).strip())
    cmd(ser, "SET_PIDV 0 0", 0.08)
    cmd(ser, "SET_RLB 200", 0.08)
    cmd(ser, "SET_WSCALE 100 100 100 100", 0.08)

    # Isolated BL
    burst(ser, "ONE_RL_+80", [], "ONE_WHEEL 2 80", 1.0)
    time.sleep(0.35)
    burst(ser, "ONE_RL_-80", [], "ONE_WHEEL 2 -80", 1.0)
    time.sleep(0.35)

    # only RL motor in mix (others WSCALE 0)
    burst(
        ser,
        "onlyRL_BACK",
        ["SET_WSCALE 0 0 100 0"],
        "SET_ROBOT_VELOCITY -400 0 0",
    )
    time.sleep(0.35)
    burst(
        ser,
        "onlyRL_BACK_w_neg",
        ["SET_WSCALE 0 0 100 0"],
        "SET_ROBOT_VELOCITY -400 0 -900",
    )
    time.sleep(0.35)
    burst(
        ser,
        "onlyRL_BACK_w_pos",
        ["SET_WSCALE 0 0 100 0"],
        "SET_ROBOT_VELOCITY -400 0 900",
    )
    time.sleep(0.35)

    # full chassis
    cmd(ser, "SET_WSCALE 100 100 100 100", 0.08)
    burst(ser, "FULL_BACK", [], "SET_ROBOT_VELOCITY -400 0 0")
    time.sleep(0.35)
    burst(ser, "FULL_BACK_w_neg", [], "SET_ROBOT_VELOCITY -400 0 -900")
    time.sleep(0.35)
    burst(ser, "FULL_STRR", [], "SET_ROBOT_VELOCITY 0 -400 0")
    time.sleep(0.35)
    burst(ser, "FULL_FWD", [], "SET_ROBOT_VELOCITY 400 0 0")

    cmd(ser, "STOP", 0.1)
    ser.close()
    print("\nBL_FOCUS_DONE")


if __name__ == "__main__":
    main()
