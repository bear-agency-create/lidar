#!/usr/bin/env python3
"""Tune FRF + RR boost given known hardware asymmetry; rewrite drive_cal.json."""
from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path

import serial

PORT = "/dev/ttyMEGA" if Path("/dev/ttyMEGA").exists() else "/dev/ttyUSB1"
OUT = Path("/home/pi/robot_nav/lidar_map/drive_cal.json")
ENC_RE = re.compile(r"ENC FL=(-?\d+) FR=(-?\d+) RL=(-?\d+) RR=(-?\d+)")
POS_RE = re.compile(
    r"POS X=([-\d.]+) Y=([-\d.]+) Th=([-\d.]+) L=(-?\d+) R=(-?\d+) C=([-\d.]+)"
)


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


def burst(ser, vx, vy, sec=1.4, w=0):
    cmd(ser, "STOP", 0.2)
    cmd(ser, "RESET_ODOM", 0.12)
    drain(ser, 0.15)
    e0 = enc(ser)
    first_th = last_th = None
    t0 = time.time()
    while time.time() - t0 < sec:
        ser.write(f"SET_ROBOT_VELOCITY {vx} {vy} {w}\n".encode())
        raw = ser.readline().decode("ascii", "ignore").strip()
        m = POS_RE.search(raw)
        if m:
            th = float(m.group(3))
            if first_th is None:
                first_th = th
            last_th = th
        time.sleep(0.06)
    cmd(ser, "STOP", 0.55)
    e1 = enc(ser)
    d = [e1[i] - e0[i] for i in range(4)] if e0 and e1 else None
    dth = 0.0
    if first_th is not None and last_th is not None:
        dth = last_th - first_th
        while dth > math.pi:
            dth -= 2 * math.pi
        while dth < -math.pi:
            dth += 2 * math.pi
    return d, dth


def main():
    ser = serial.Serial(PORT, 115200, timeout=0.2)
    time.sleep(2.0)
    drain(ser, 0.4)
    cmd(ser, "SET_PIDV 0 0", 0.1)

    # Aggressive software compensation for weak FR-fwd / deadish RR.
    # RL is the strong wheel — keep it down so chassis does not spin.
    wscale = [110, 120, 72, 200]
    cmd(ser, f"SET_WSCALE {' '.join(map(str, wscale))}", 0.12)
    cmd(ser, "SET_FRB 110", 0.1)

    best_frf, best_abs = 100, 1e9
    for frf in (100, 130, 150, 170, 190, 200):
        cmd(ser, f"SET_FRF {frf}", 0.1)
        d, dth = burst(ser, 500, 0, 1.35)
        ad = abs(dth)
        print(f"FRF {frf}: dENC={d} dTh={math.degrees(dth):+.1f}deg")
        if d is not None and ad < best_abs:
            best_abs, best_frf = ad, frf
        time.sleep(0.35)
    cmd(ser, f"SET_FRF {best_frf}", 0.1)
    print(f"Chosen FRF={best_frf} (|dTh|={math.degrees(best_abs):.1f})")

    # Measure trims with this balance (clamp generous — yaw-hold finishes the job).
    trim = {}
    for name, vx, vy in (("fwd", 500, 0), ("back", -500, 0), ("strl", 0, 450), ("strr", 0, -450)):
        ys = []
        for rep in range(2):
            d, dth = burst(ser, vx, vy, 1.4)
            print(f"trim {name}#{rep}: dENC={d} dTh={math.degrees(dth):+.1f}deg")
            ys.append(dth)
            time.sleep(0.35)
        mean_th = sum(ys) / len(ys)
        t = max(-0.75, min(0.75, -0.95 * (mean_th / 1.4)))
        trim[name] = round(t, 3)
        print(f"  -> trim_w[{name}]={trim[name]:+.3f}")

    # Keep previous cal_tps if file exists, else safe defaults from last run.
    prev = {}
    if OUT.is_file():
        try:
            prev = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            prev = {}
    cal_tps = prev.get("cal_tps") or [208, 241, 924, 225]

    doc = {
        "cal_tps": cal_tps,
        "pidv_kp_x1000": 0,
        "pidv_ki_x1000": 0,
        "frb_pct": 110,
        "frf_pct": best_frf,
        "wheel_scale_pct": wscale,
        "yaw_kp": 1.8,
        "yaw_deadband_deg": 2.0,
        "trim_w": trim,
        "motor_health": {
            "FL_encoder": "dead",
            "FR_forward": "weak",
            "RL": "ok_strong",
            "RR": "dead_or_barely_turning",
            "note": "Mecanum strafe needs 4 live motors. RR must be repaired for real sideways motion.",
        },
        "notes": (
            f"Hardware-aware tune {time.strftime('%Y-%m-%d %H:%M:%S')}: "
            "RR nearly dead, FR fwd weak; RL reduced, RR/FRF maxed; teleop trim+yaw-hold on"
        ),
    }
    OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print("Wrote", OUT)
    print(json.dumps(doc, indent=2))

    print("\n=== verify FWD ===")
    d, dth = burst(ser, 500, 0, 1.5)
    print(f"dENC={d} dTh={math.degrees(dth):+.1f}deg")
    print("=== verify BACK ===")
    d, dth = burst(ser, -500, 0, 1.5)
    print(f"dENC={d} dTh={math.degrees(dth):+.1f}deg")
    cmd(ser, "STOP", 0.1)
    ser.close()
    print("DONE")


if __name__ == "__main__":
    main()
