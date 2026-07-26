#!/usr/bin/env python3
"""Recalibrate Mega wheel scales + direction yaw trims for the current floor.

Stops are expected externally (kill drive_encoders before running).
Writes lidar_map/drive_cal.json used by drive_encoders.py on startup.

Usage on Pi:
  pkill -f drive_encoders.py
  python3 tools/recalibrate_drive.py [/dev/ttyUSB0]
"""
from __future__ import annotations

import json
import math
import re
import sys
import time
from pathlib import Path

import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
OUT = Path(__file__).resolve().parents[1] / "drive_cal.json"
ENC_RE = re.compile(r"ENC FL=(-?\d+) FR=(-?\d+) RL=(-?\d+) RR=(-?\d+)")
POS_RE = re.compile(
    r"POS X=([-\d.]+) Y=([-\d.]+) Th=([-\d.]+) L=(-?\d+) R=(-?\d+) C=([-\d.]+)"
)
RUN_SEC = 1.6
SETTLE = 0.7


def drain(ser: serial.Serial, sec: float = 0.3) -> None:
    t0 = time.time()
    while time.time() - t0 < sec:
        ser.read(256)
        time.sleep(0.02)


def cmd(ser: serial.Serial, line: str, wait: float = 0.12) -> str:
    ser.write((line + "\n").encode())
    time.sleep(wait)
    return ser.read(256).decode("ascii", "ignore")


def read_enc(ser: serial.Serial) -> list[int] | None:
    ser.reset_input_buffer()
    ser.write(b"ENC?\n")
    t0 = time.time()
    while time.time() - t0 < 0.8:
        raw = ser.readline().decode("ascii", "ignore").strip()
        m = ENC_RE.search(raw)
        if m:
            return [int(m.group(i)) for i in range(1, 5)]
    return None


def drive_burst(ser: serial.Serial, vx: int, vy: int, seconds: float) -> tuple[list[int] | None, float]:
    """Open-loop burst; return delta encoders and odom yaw change (rad)."""
    cmd(ser, "STOP", 0.25)
    cmd(ser, "RESET_ODOM", 0.15)
    drain(ser, 0.2)
    e0 = read_enc(ser)
    if e0 is None:
        return None, 0.0

    first_th = last_th = None
    t0 = time.time()
    while time.time() - t0 < seconds:
        ser.write(f"SET_ROBOT_VELOCITY {vx} {vy} 0\n".encode())
        raw = ser.readline().decode("ascii", "ignore").strip()
        m = POS_RE.search(raw)
        if m:
            th = float(m.group(3))
            if first_th is None:
                first_th = th
            last_th = th
        time.sleep(0.07)
    cmd(ser, "STOP", SETTLE)
    drain(ser, 0.2)
    e1 = read_enc(ser)
    if e0 is None or e1 is None:
        return None, 0.0
    delta = [e1[i] - e0[i] for i in range(4)]
    dth = 0.0
    if first_th is not None and last_th is not None:
        dth = last_th - first_th
        while dth > math.pi:
            dth -= 2 * math.pi
        while dth < -math.pi:
            dth += 2 * math.pi
    return delta, dth


def mean_abs(samples: list[list[int]]) -> list[float]:
    out = [0.0] * 4
    n = 0
    for s in samples:
        if not s:
            continue
        n += 1
        for i in range(4):
            out[i] += abs(s[i])
    if n == 0:
        return out
    return [v / n for v in out]


def main() -> None:
    print(f"Opening {PORT} …")
    ser = serial.Serial(PORT, 115200, timeout=0.2)
    time.sleep(2.2)
    drain(ser, 0.4)
    print("PING:", cmd(ser, "PING", 0.3).strip())

    # Open-loop for scale measurement
    print("Disable PI for open-loop scale measure")
    print(cmd(ser, "SET_PIDV 0 0", 0.2).strip())

    scale_samples: list[list[int]] = []
    for label, vx, vy in (("FWD", 500, 0), ("BACK", -500, 0), ("FWD2", 500, 0), ("BACK2", -500, 0)):
        print(f"\n=== scale run {label} {RUN_SEC}s ===")
        delta, dth = drive_burst(ser, vx, vy, RUN_SEC)
        if delta is None:
            print("  FAILED (no encoders)")
            continue
        tps = [abs(d) / RUN_SEC for d in delta]
        print(
            f"  dENC FL={delta[0]:+6d} FR={delta[1]:+6d} RL={delta[2]:+6d} RR={delta[3]:+6d} "
            f"dTh={math.degrees(dth):+.1f}deg"
        )
        print(f"  tps  FL={tps[0]:6.0f} FR={tps[1]:6.0f} RL={tps[2]:6.0f} RR={tps[3]:6.0f}")
        scale_samples.append(delta)
        time.sleep(0.5)

    abs_mean = mean_abs(scale_samples)
    if sum(abs_mean) < 10:
        raise SystemExit("No encoder motion — aborting calibration")

    # ticks over RUN_SEC → ticks/s at mix≈1.0
    cal = [max(80, int(round(v / RUN_SEC))) for v in abs_mean]
    # Keep FR from collapsing if encoder is flaky: floor at 40% of mean of others
    others = (cal[0] + cal[2] + cal[3]) / 3.0
    if cal[1] < 0.35 * others:
        cal[1] = max(80, int(round(0.55 * others)))
        print(f"FR encoder weak — floored cal FR to {cal[1]}")

    print(f"\nSET_CAL {' '.join(str(c) for c in cal)}")
    print(cmd(ser, f"SET_CAL {cal[0]} {cal[1]} {cal[2]} {cal[3]}", 0.2).strip())

    # Mild PI on new surface (less twist than old 500/2500)
    print(cmd(ser, "SET_PIDV 350 1800", 0.2).strip())

    # Measure yaw drift per direction with PI on; derive feedforward w trim
    trim_w = {"fwd": 0.0, "back": 0.0, "strl": 0.0, "strr": 0.0}
    motions = (
        ("fwd", 500, 0),
        ("back", -500, 0),
        ("strl", 0, 500),
        ("strr", 0, -500),
    )
    # Also collect BACK yaw vs FRB candidates
    frb_best = 108
    frb_best_abs = 1e9
    for pct in (100, 90, 110, 80, 120, 105, 115):
        print(cmd(ser, f"SET_FRB {pct}", 0.15).strip())
        delta, dth = drive_burst(ser, -500, 0, 1.4)
        if delta is None:
            continue
        ad = abs(dth)
        print(f"FRB {pct}: dTh={math.degrees(dth):+.1f}deg")
        if ad < frb_best_abs:
            frb_best_abs = ad
            frb_best = pct
        time.sleep(0.4)
    print(cmd(ser, f"SET_FRB {frb_best}", 0.15).strip())
    print(f"Chosen FRB={frb_best}% (|dTh|={math.degrees(frb_best_abs):.1f}deg)")

    for name, vx, vy in motions:
        ys = []
        for rep in range(2):
            print(f"\n=== trim run {name}#{rep} ===")
            delta, dth = drive_burst(ser, vx, vy, 1.5)
            if delta is None:
                continue
            print(
                f"  dENC={delta} dTh={math.degrees(dth):+.1f}deg"
            )
            ys.append(dth)
            time.sleep(0.45)
        if not ys:
            continue
        mean_th = sum(ys) / len(ys)
        # Convert observed yaw change over ~1.5s into opposing w (rad/s)
        # Gain 0.85 leaves room for lidar yaw-hold fine correction.
        trim = -0.85 * (mean_th / 1.5)
        trim = max(-0.55, min(0.55, trim))
        trim_w[name] = round(trim, 3)
        print(f"  trim_w[{name}] = {trim_w[name]:+.3f} rad/s")

    cal_doc = {
        "cal_tps": cal,
        "pidv_kp_x1000": 350,
        "pidv_ki_x1000": 1800,
        "frb_pct": frb_best,
        "yaw_kp": 1.2,
        "yaw_deadband_deg": 3.0,
        "trim_w": trim_w,
        "notes": f"Recalibrated on-device {time.strftime('%Y-%m-%d %H:%M:%S')}",
    }
    OUT.write_text(json.dumps(cal_doc, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {OUT}")
    print(json.dumps(cal_doc, indent=2))

    # Final verify burst forward
    print("\n=== verify FWD with new cal ===")
    delta, dth = drive_burst(ser, 500, 0, 1.5)
    if delta:
        print(f"  dENC={delta} dTh={math.degrees(dth):+.1f}deg")
    cmd(ser, "STOP", 0.2)
    ser.close()
    print("DONE")


if __name__ == "__main__":
    main()
