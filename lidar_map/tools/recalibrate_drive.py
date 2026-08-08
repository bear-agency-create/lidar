#!/usr/bin/env python3
"""Recalibrate Mega wheel scales + direction yaw trims for the current floor.

Stops are expected externally (kill drive_encoders before running).
Writes lidar_map/drive_cal.json used by drive_encoders.py on startup.

Key fix vs older versions:
  WSCALE is computed from *normalized* encoder rates (ticks/s ÷ cal_tps),
  not raw tick counts. Raw TPS across wheels with different CPR made
  RR look "slow" → WSCALE RR=122 / FR=85, which balanced forward by luck
  and destroyed mecanum strafe diagonals.

Usage on Pi:
  pkill -f drive_encoders.py
  python3 tools/recalibrate_drive.py [/dev/ttyMEGA]
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
RUN_SEC = 1.6
SETTLE = 0.8
# Keep scales close enough that strafe diagonals still cancel yaw.
WSCALE_MIN = 78
WSCALE_MAX = 128


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


def drive_burst(
    ser: serial.Serial, vx: int, vy: int, seconds: float, w: int = 0
) -> tuple[list[int] | None, float, float, float]:
    """Open-loop burst → (dENC, dTh_rad, dX_mm, dY_mm)."""
    cmd(ser, "STOP", 0.25)
    cmd(ser, "RESET_ODOM", 0.15)
    drain(ser, 0.2)
    e0 = read_enc(ser)
    if e0 is None:
        return None, 0.0, 0.0, 0.0

    first_th = last_th = None
    first_x = last_x = first_y = last_y = None
    t0 = time.time()
    while time.time() - t0 < seconds:
        ser.write(f"SET_ROBOT_VELOCITY {vx} {vy} {w}\n".encode())
        raw = ser.readline().decode("ascii", "ignore").strip()
        m = POS_RE.search(raw)
        if m:
            x, y, th = float(m.group(1)), float(m.group(2)), float(m.group(3))
            if first_th is None:
                first_th, first_x, first_y = th, x, y
            last_th, last_x, last_y = th, x, y
        time.sleep(0.07)
    cmd(ser, "STOP", SETTLE)
    drain(ser, 0.2)
    e1 = read_enc(ser)
    if e0 is None or e1 is None:
        return None, 0.0, 0.0, 0.0
    delta = [e1[i] - e0[i] for i in range(4)]
    dth = 0.0
    if first_th is not None and last_th is not None:
        dth = last_th - first_th
        while dth > math.pi:
            dth -= 2 * math.pi
        while dth < -math.pi:
            dth += 2 * math.pi
    dx = (last_x - first_x) if first_x is not None and last_x is not None else 0.0
    dy = (last_y - first_y) if first_y is not None and last_y is not None else 0.0
    return delta, dth, dx, dy


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


def compute_wscale(abs_mean: list[float], cal: list[int]) -> list[int]:
    """Equalize *physical* wheel speed using ticks/s normalized by cal_tps."""
    # Live wheels used for balance (FL encoder is dead → leave near 100).
    live = [1, 2, 3]  # FR RL RR
    norms: dict[int, float] = {}
    for i in live:
        tps = abs_mean[i] / RUN_SEC
        norms[i] = tps / max(80.0, float(cal[i]))
        print(f"  norm[{i}] tps={tps:.0f} / cal={cal[i]} → {norms[i]:.3f}")

    usable = {i: v for i, v in norms.items() if v > 0.08}
    if len(usable) < 2:
        print("  WARN: not enough live encoders — WSCALE stays flat 100")
        return [100, 100, 100, 100]

    # Geometric mean of usable normalized rates.
    log_sum = sum(math.log(v) for v in usable.values())
    target = math.exp(log_sum / len(usable))
    print(f"  target norm rate = {target:.3f}")

    ws = [100, 100, 100, 100]
    for i in usable:
        # Faster wheel → lower PWM scale.
        raw = 100.0 * target / usable[i]
        ws[i] = int(round(max(WSCALE_MIN, min(WSCALE_MAX, raw))))
    # FL has no encoder: mirror FR (symmetric front axle) or keep 100.
    ws[0] = ws[1]
    # Renormalize so mean of live scales ≈ 100 (preserve overall speed).
    mean_live = sum(ws[i] for i in live) / 3.0
    if mean_live > 1:
        factor = 100.0 / mean_live
        ws = [int(round(max(WSCALE_MIN, min(WSCALE_MAX, v * factor)))) for v in ws]
        ws[0] = ws[1]
    return ws


def expected_strafe_signs(vy: int) -> list[int]:
    # target: FL=-Y FR=+Y RL=+Y RR=-Y  (for vy>0)
    s = 1 if vy > 0 else -1
    return [-s, +s, +s, -s]


def main() -> None:
    print(f"Opening {PORT} …")
    print("CLEAR SPACE ~1.5 m around robot. Calibration drives FWD/BACK/STRAFE.")
    ser = serial.Serial(PORT, 115200, timeout=0.2)
    time.sleep(2.2)
    drain(ser, 0.4)
    print("PING:", cmd(ser, "PING", 0.3).strip())

    print("Open-loop: SET_PIDV 0 0, flat WSCALE 100 100 100 100")
    print(cmd(ser, "SET_PIDV 0 0", 0.2).strip())
    print(cmd(ser, "SET_WSCALE 100 100 100 100", 0.2).strip())
    print(cmd(ser, "SET_FRB 100", 0.15).strip())
    print(cmd(ser, "SET_FRF 100", 0.15).strip())

    # --- 1) Measure per-wheel cal_tps at full mix ---
    scale_samples: list[list[int]] = []
    for label, vx, vy in (
        ("FWD", 500, 0),
        ("BACK", -500, 0),
        ("FWD2", 500, 0),
        ("BACK2", -500, 0),
    ):
        print(f"\n=== cal_tps run {label} {RUN_SEC}s ===")
        delta, dth, dx, dy = drive_burst(ser, vx, vy, RUN_SEC)
        if delta is None:
            print("  FAILED (no encoders)")
            continue
        tps = [abs(d) / RUN_SEC for d in delta]
        print(
            f"  dENC FL={delta[0]:+6d} FR={delta[1]:+6d} RL={delta[2]:+6d} RR={delta[3]:+6d} "
            f"dTh={math.degrees(dth):+.1f}deg dX={dx:+.0f}mm dY={dy:+.0f}mm"
        )
        print(f"  tps  FL={tps[0]:6.0f} FR={tps[1]:6.0f} RL={tps[2]:6.0f} RR={tps[3]:6.0f}")
        scale_samples.append(delta)
        time.sleep(0.45)

    abs_mean = mean_abs(scale_samples)
    if sum(abs_mean) < 10:
        raise SystemExit("No encoder motion — aborting calibration")

    cal = [max(80, int(round(v / RUN_SEC))) for v in abs_mean]
    # FL encoder often dead — don't let it collapse SET_CAL.
    live_mean = (cal[1] + cal[2] + cal[3]) / 3.0
    if cal[0] < 0.25 * live_mean:
        cal[0] = max(80, int(round(0.45 * live_mean)))
        print(f"FL encoder dead/weak — floored cal FL to {cal[0]}")
    others = (cal[0] + cal[2] + cal[3]) / 3.0
    if cal[1] < 0.35 * others:
        cal[1] = max(80, int(round(0.55 * others)))
        print(f"FR encoder weak — floored cal FR to {cal[1]}")

    print(f"\nSET_CAL {' '.join(str(c) for c in cal)}")
    print(cmd(ser, f"SET_CAL {cal[0]} {cal[1]} {cal[2]} {cal[3]}", 0.2).strip())
    print(cmd(ser, "SET_PIDV 0 0", 0.2).strip())

    # --- 2) WSCALE from normalized FWD rates (flat scales) ---
    print("\n=== WSCALE from normalized FWD ===")
    print(cmd(ser, "SET_WSCALE 100 100 100 100", 0.2).strip())
    fwd_samples: list[list[int]] = []
    for rep in range(3):
        print(f"  FWD measure #{rep}")
        delta, dth, dx, dy = drive_burst(ser, 500, 0, RUN_SEC)
        if delta is None:
            continue
        print(
            f"    dENC={delta} dTh={math.degrees(dth):+.1f}deg "
            f"dX={dx:+.0f}mm dY={dy:+.0f}mm"
        )
        fwd_samples.append(delta)
        time.sleep(0.4)
    fwd_mean = mean_abs(fwd_samples)
    wscale = compute_wscale(fwd_mean, cal)
    print(f"SET_WSCALE {' '.join(str(v) for v in wscale)}")
    print(cmd(ser, f"SET_WSCALE {wscale[0]} {wscale[1]} {wscale[2]} {wscale[3]}", 0.2).strip())

    # --- 3) FRB sweep for BACK yaw ---
    frb_best = 100
    frb_best_abs = 1e9
    for pct in (100, 90, 110, 85, 115, 95, 105):
        print(cmd(ser, f"SET_FRB {pct}", 0.15).strip())
        delta, dth, dx, dy = drive_burst(ser, -500, 0, 1.4)
        if delta is None:
            continue
        ad = abs(dth)
        print(f"FRB {pct}: dTh={math.degrees(dth):+.1f}deg dX={dx:+.0f}mm")
        if ad < frb_best_abs:
            frb_best_abs = ad
            frb_best = pct
        time.sleep(0.35)
    print(cmd(ser, f"SET_FRB {frb_best}", 0.15).strip())
    print(f"Chosen FRB={frb_best}% (|dTh|={math.degrees(frb_best_abs):.1f}deg)")

    # --- 4) Strafe sanity: encoder sign pattern ---
    print("\n=== strafe encoder pattern check ===")
    for name, vy in (("STRL", 500), ("STRR", -500)):
        delta, dth, dx, dy = drive_burst(ser, 0, vy, 1.4)
        if delta is None:
            print(f"  {name}: ENC fail")
            continue
        expect = expected_strafe_signs(vy)
        # Compare signs on live wheels only (skip FL if ~0)
        ok = True
        for i in (1, 2, 3):
            if abs(delta[i]) < 30:
                ok = False
                continue
            if (1 if delta[i] > 0 else -1) != expect[i]:
                ok = False
        print(
            f"  {name}: dENC={delta} dTh={math.degrees(dth):+.1f}deg "
            f"dX={dx:+.0f}mm dY={dy:+.0f}mm pattern_ok={ok}"
        )
        if not ok:
            print("  WARN: strafe wheel signs unexpected — check rollers / wiring")
        time.sleep(0.4)

    # --- 5) Direction yaw trims (applied by drive_encoders on teleop too) ---
    trim_w = {"fwd": 0.0, "back": 0.0, "strl": 0.0, "strr": 0.0}
    motions = (
        ("fwd", 500, 0),
        ("back", -500, 0),
        ("strl", 0, 500),
        ("strr", 0, -500),
    )
    for name, vx, vy in motions:
        ys = []
        for rep in range(2):
            print(f"\n=== trim run {name}#{rep} ===")
            delta, dth, dx, dy = drive_burst(ser, vx, vy, 1.5)
            if delta is None:
                continue
            print(
                f"  dENC={delta} dTh={math.degrees(dth):+.1f}deg "
                f"dX={dx:+.0f}mm dY={dy:+.0f}mm"
            )
            ys.append(dth)
            time.sleep(0.4)
        if not ys:
            continue
        mean_th = sum(ys) / len(ys)
        # Opposing yaw feedforward; leave headroom for lidar yaw-hold.
        trim = -0.90 * (mean_th / 1.5)
        trim = max(-0.60, min(0.60, trim))
        trim_w[name] = round(trim, 3)
        print(f"  trim_w[{name}] = {trim_w[name]:+.3f} rad/s")

    # --- 6) Verify FWD / STRL with new cal ---
    print("\n=== verify FWD ===")
    delta, dth, dx, dy = drive_burst(ser, 500, 0, 1.5)
    if delta:
        print(f"  dENC={delta} dTh={math.degrees(dth):+.1f}deg dX={dx:+.0f}mm dY={dy:+.0f}mm")
    print("\n=== verify STRL ===")
    delta, dth, dx, dy = drive_burst(ser, 0, 500, 1.5)
    if delta:
        print(f"  dENC={delta} dTh={math.degrees(dth):+.1f}deg dX={dx:+.0f}mm dY={dy:+.0f}mm")

    cal_doc = {
        "cal_tps": cal,
        "pidv_kp_x1000": 0,
        "pidv_ki_x1000": 0,
        "frb_pct": frb_best,
        "frf_pct": 100,
        "wheel_scale_pct": wscale,
        "yaw_kp": 1.2,
        "yaw_deadband_deg": 3.0,
        "trim_w": trim_w,
        "notes": (
            f"Recalibrated {time.strftime('%Y-%m-%d %H:%M:%S')} "
            "PI off; WSCALE from normalized TPS; trim applies on teleop"
        ),
    }
    OUT.write_text(json.dumps(cal_doc, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {OUT}")
    print(json.dumps(cal_doc, indent=2))
    cmd(ser, "STOP", 0.2)
    ser.close()
    print("DONE")


if __name__ == "__main__":
    main()
