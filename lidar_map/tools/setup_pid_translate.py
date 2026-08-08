#!/usr/bin/env python3
"""Measure per-wheel cal_tps (ONE_WHEEL), enable velocity PI, verify translate.

Short motions only (~0.5s). Prefer robot lifted for ONE_WHEEL; verify bursts
are gentle (Mega 280/500) so on-floor is safer in tight spaces.

Writes lidar_map/drive_cal.json
"""
from __future__ import annotations

import json
import math
import re
import sys
import time
from pathlib import Path

import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else (
    "/dev/ttyMEGA" if Path("/dev/ttyMEGA").exists() else "/dev/ttyUSB1"
)
OUT = Path(__file__).resolve().parents[1] / "drive_cal.json"
ENC_RE = re.compile(r"ENC FL=(-?\d+) FR=(-?\d+) RL=(-?\d+) RR=(-?\d+)")
POS_RE = re.compile(
    r"POS X=([-\d.]+) Y=([-\d.]+) Th=([-\d.]+) L=(-?\d+) R=(-?\d+) C=([-\d.]+)"
)
NAMES = ("FL", "FR", "RL", "RR")
PULSE = 0.55
PCT = 70
# Verify body motions — short / mid power.
VERIFY_SEC = 0.55
VERIFY_VX = 280  # of 500
VERIFY_VY = 280


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
        raw = ser.readline().decode("ascii", "ignore").strip()
        m = ENC_RE.search(raw)
        if m:
            return [int(m.group(i)) for i in range(1, 5)]
    return None


def one_wheel(ser, idx, pct, sec=PULSE):
    cmd(ser, "STOP", 0.15)
    e0 = enc(ser)
    t0 = time.time()
    while time.time() - t0 < sec:
        ser.write(f"ONE_WHEEL {idx} {pct}\n".encode())
        time.sleep(0.06)
    cmd(ser, "STOP", 0.25)
    e1 = enc(ser)
    if not e0 or not e1:
        return None
    return [e1[i] - e0[i] for i in range(4)]


def body_burst(ser, vx, vy, sec=VERIFY_SEC):
    cmd(ser, "STOP", 0.15)
    cmd(ser, "RESET_ODOM", 0.12)
    drain(ser, 0.12)
    first = last = None
    t0 = time.time()
    while time.time() - t0 < sec:
        ser.write(f"SET_ROBOT_VELOCITY {vx} {vy} 0\n".encode())
        raw = ser.readline().decode("ascii", "ignore").strip()
        m = POS_RE.search(raw)
        if m:
            pose = (float(m.group(1)), float(m.group(2)), float(m.group(3)))
            if first is None:
                first = pose
            last = pose
        time.sleep(0.05)
    cmd(ser, "STOP", 0.35)
    if not first or not last:
        return None
    dx, dy = last[0] - first[0], last[1] - first[1]
    dth = last[2] - first[2]
    while dth > math.pi:
        dth -= 2 * math.pi
    while dth < -math.pi:
        dth += 2 * math.pi
    return dx, dy, dth


def main():
    print(f"PORT={PORT}")
    ser = serial.Serial(PORT, 115200, timeout=0.2)
    time.sleep(2.2)
    drain(ser, 0.4)
    print("PING", cmd(ser, "PING", 0.2).strip().splitlines()[-1:])

    # FL B-channel decode + open-loop while measuring cal_tps
    cmd(ser, "SET_FL_ENC_MODE 2", 0.08)
    cmd(ser, "FL_ENC_PULLUP 1", 0.08)
    cmd(ser, "SET_PIDV 0 0", 0.1)
    cmd(ser, "SET_WSCALE 100 100 100 100", 0.1)

    print("\n=== ONE_WHEEL cal_tps @%d%% ===" % PCT)
    abs_peak = [0.0, 0.0, 0.0, 0.0]
    n_ok = [0, 0, 0, 0]
    for idx, name in enumerate(NAMES):
        for pct in (PCT, -PCT):
            d = one_wheel(ser, idx, pct)
            print(f"  {name} {pct:+d}% dENC={d}")
            if not d:
                continue
            abs_peak[idx] = max(abs_peak[idx], abs(d[idx]))
            n_ok[idx] += 1
            time.sleep(0.35)

    cal = []
    for i in range(4):
        if n_ok[i] <= 0 or abs_peak[i] < 1:
            cal.append(800)
            continue
        tps = abs_peak[i] / PULSE
        full = tps * (100.0 / float(PCT))
        cal.append(max(120, int(round(full))))
    # FL mode2 denser edges — don't inflate vs peers.
    peer = sorted([cal[1], cal[2], cal[3]])[1]
    if cal[0] > int(1.25 * peer):
        print(f"FL cal_tps {cal[0]} → peer median {peer} (mode2 density)")
        cal[0] = peer
    print("SET_CAL", cal)
    cmd(ser, f"SET_CAL {cal[0]} {cal[1]} {cal[2]} {cal[3]}", 0.15)

    kp, ki = 140, 350
    print(f"SET_PIDV {kp} {ki}")
    cmd(ser, f"SET_PIDV {kp} {ki}", 0.15)
    cmd(ser, "SET_WSCALE 100 100 100 100", 0.1)
    cmd(ser, "SET_FRB 100", 0.08)
    cmd(ser, "SET_FRF 100", 0.08)

    print("\n=== verify body translate (short) ===")
    results = {}
    for name, vx, vy in (
        ("FWD", VERIFY_VX, 0),
        ("BACK", -VERIFY_VX, 0),
        ("STRL", 0, VERIFY_VY),
        ("STRR", 0, -VERIFY_VY),
    ):
        r = body_burst(ser, vx, vy)
        results[name] = r
        if r:
            dx, dy, dth = r
            print(
                f"  {name}: dX={dx:+.0f}mm dY={dy:+.0f}mm "
                f"dTh={math.degrees(dth):+.1f}deg"
            )
        else:
            print(f"  {name}: no pose")
        time.sleep(0.5)

    doc = {
        "cal_tps": cal,
        "pidv_kp_x1000": kp,
        "pidv_ki_x1000": ki,
        "frb_pct": 100,
        "frf_pct": 100,
        "wheel_scale_pct": [100, 100, 100, 100],
        "yaw_kp": 2.2,
        "yaw_deadband_deg": 1.5,
        "trim_w": {"fwd": 0.0, "back": 0.0, "strl": 0.0, "strr": 0.0},
        "verify": {
            k: None
            if v is None
            else {
                "dX_mm": round(v[0], 1),
                "dY_mm": round(v[1], 1),
                "dTh_deg": round(math.degrees(v[2]), 2),
            }
            for k, v in results.items()
        },
        "notes": (
            f"PID translate setup {time.strftime('%Y-%m-%d %H:%M:%S')}: "
            "per-wheel velocity PI + flat WSCALE; lidar yaw-hold on teleop "
            "for FWD/BACK/STRAFE without spin"
        ),
    }
    OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {OUT}")
    print(json.dumps(doc, indent=2))
    cmd(ser, "STOP", 0.1)
    ser.close()
    print("DONE")


if __name__ == "__main__":
    main()
