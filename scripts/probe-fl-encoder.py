#!/usr/bin/env python3
"""Software-revive probe for FL encoder: modes, pin swaps, pullup, levels."""
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


def levels(ser):
    out = cmd(ser, "ENC_LEVELS", 0.12)
    for line in out.splitlines():
        if "LVL" in line or "FL_A" in line:
            return line.strip()
    return out.strip().splitlines()[-1] if out.strip() else "?"


def trial(ser, label, sec=2.0, pct=80):
    cmd(ser, "FL_ENC_RESET_EDGES", 0.08)
    cmd(ser, "RESET_ODOM", 0.1)
    e0 = enc(ser)
    lv0 = levels(ser)
    t0 = time.time()
    while time.time() - t0 < sec:
        ser.write(f"ONE_WHEEL 0 {pct}\n".encode())
        time.sleep(0.05)
    ser.write(b"STOP\n")
    time.sleep(0.2)
    e1 = enc(ser)
    lv1 = levels(ser)
    d = None if not e0 or not e1 else [e1[i] - e0[i] for i in range(4)]
    print(f"\n[{label}]")
    print(f"  delta ENC={d}")
    print(f"  levels before: {lv0}")
    print(f"  levels after : {lv1}")
    fl = 0 if not d else abs(d[0])
    return fl


def main():
    print("PORT", PORT)
    ser = serial.Serial(PORT, 115200, timeout=0.2)
    time.sleep(2.2)
    drain(ser, 0.5)
    print("boot:", cmd(ser, "PING", 0.25).strip().splitlines()[-2:])

    candidates = []

    # 1) Default pins, all decode modes × pullup on/off
    for pup in (1, 0):
        cmd(ser, f"FL_ENC_PULLUP {pup}", 0.1)
        cmd(ser, "SET_FL_ENC 50 51", 0.1)
        for mode in (1, 2, 0):
            cmd(ser, f"SET_FL_ENC_MODE {mode}", 0.1)
            fl = trial(ser, f"pins=50/51 mode={mode} pup={pup}")
            candidates.append((fl, 50, 51, mode, pup))

    # 2) Swap A/B
    cmd(ser, "FL_ENC_PULLUP 1", 0.1)
    cmd(ser, "SET_FL_ENC 51 50", 0.1)
    for mode in (1, 2):
        cmd(ser, f"SET_FL_ENC_MODE {mode}", 0.1)
        fl = trial(ser, f"pins=51/50 mode={mode} pup=1")
        candidates.append((fl, 51, 50, mode, 1))

    # 3) Try neighboring encoder headers (in case FL cable on wrong socket)
    for a, b, name in (
        (48, 49, "FR_header"),
        (52, 53, "RL_header"),
        (46, 47, "RR_header"),
    ):
        cmd(ser, f"SET_FL_ENC {a} {b}", 0.1)
        cmd(ser, "SET_FL_ENC_MODE 2", 0.1)
        fl = trial(ser, f"try_{name} pins={a}/{b} mode=2", sec=1.5)
        candidates.append((fl, a, b, 2, 1))

    candidates.sort(key=lambda x: -x[0])
    best = candidates[0]
    print("\n=== BEST ===")
    print(f"ticks={best[0]} pins={best[1]}/{best[2]} mode={best[3]} pup={best[4]}")

    # Apply best if any ticks seen
    if best[0] > 5:
        cmd(ser, f"SET_FL_ENC {best[1]} {best[2]}", 0.1)
        cmd(ser, f"SET_FL_ENC_MODE {best[3]}", 0.1)
        cmd(ser, f"FL_ENC_PULLUP {best[4]}", 0.1)
        print("APPLIED best FL encoder config")
        trial(ser, "verify_best", sec=2.5, pct=80)
    else:
        print("NO SIGNAL on any pin/mode — hardware open / dead sensor (software cannot revive)")
        # leave improved default: mode1 dual-edge on 50/51
        cmd(ser, "SET_FL_ENC 50 51", 0.1)
        cmd(ser, "SET_FL_ENC_MODE 1", 0.1)
        cmd(ser, "FL_ENC_PULLUP 1", 0.1)

    cmd(ser, "STOP", 0.1)
    ser.close()
    print("DONE")


if __name__ == "__main__":
    main()
