#!/usr/bin/env python3
"""Sequential ONE_WHEEL motor test + encoder alignment (NO chassis drive).

Each wheel is pulsed alone for ~0.55s at low then mid power.
Does not command vx/vy — robot should mostly pivot in place on one contact patch.
Keep a hand on E-stop / power. Clear ~30 cm if on the floor.

Writes lidar_map/drive_cal.json with WSCALE from encoder TPS of live wheels.
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
NAMES = ("FL", "FR", "RL", "RR")
PULSE_SEC = 0.60
PAUSE_SEC = 0.8
# Mid power — enough for clear encoder ticks when lifted.
PCT_FWD = int(__import__("os").environ.get("ONE_WHEEL_PCT", "70"))
PCT_BACK = -PCT_FWD


def drain(ser: serial.Serial, sec: float = 0.25) -> None:
    t0 = time.time()
    while time.time() - t0 < sec:
        ser.read(512)
        time.sleep(0.02)


def cmd(ser: serial.Serial, line: str, wait: float = 0.08) -> str:
    ser.write((line + "\n").encode())
    time.sleep(wait)
    return ser.read(512).decode("ascii", "ignore")


def read_enc(ser: serial.Serial) -> list[int] | None:
    ser.reset_input_buffer()
    ser.write(b"ENC?\n")
    t0 = time.time()
    while time.time() - t0 < 0.7:
        raw = ser.readline().decode("ascii", "ignore").strip()
        m = ENC_RE.search(raw)
        if m:
            return [int(m.group(i)) for i in range(1, 5)]
    return None


def pulse_one(ser: serial.Serial, idx: int, pct: int) -> list[int] | None:
    cmd(ser, "STOP", 0.15)
    drain(ser, 0.1)
    e0 = read_enc(ser)
    if e0 is None:
        return None
    t0 = time.time()
    while time.time() - t0 < PULSE_SEC:
        # Keep alive (Mega CMD timeout 1.5s) — refresh ONE_WHEEL.
        ser.write(f"ONE_WHEEL {idx} {pct}\n".encode())
        time.sleep(0.08)
    cmd(ser, "STOP", 0.25)
    time.sleep(0.15)
    e1 = read_enc(ser)
    if e0 is None or e1 is None:
        return None
    return [e1[i] - e0[i] for i in range(4)]


def main() -> None:
    print(f"PORT={PORT}")
    print("=== SEQUENTIAL ONE-WHEEL TEST (encoder align, no vx/vy) ===")
    print(f"Each wheel: {PULSE_SEC}s @ ±{PCT_FWD}% then pause {PAUSE_SEC}s")
    print("Hand near power cut. Tiny pivot only.\n")

    ser = serial.Serial(PORT, 115200, timeout=0.2)
    time.sleep(2.2)
    drain(ser, 0.5)
    print("PING:", cmd(ser, "PING", 0.25).strip().splitlines()[-3:])
    cmd(ser, "SET_PIDV 0 0", 0.1)
    cmd(ser, "SET_WSCALE 100 100 100 100", 0.1)
    cmd(ser, "SET_FRB 100", 0.08)
    cmd(ser, "SET_FRF 100", 0.08)
    cmd(ser, "STOP", 0.1)

    results: dict[str, dict] = {}
    abs_tps = [0.0, 0.0, 0.0, 0.0]
    alive = [False, False, False, False]

    for idx, name in enumerate(NAMES):
        print(f"\n--- {name} (idx={idx}) FORWARD {PCT_FWD}% ---")
        d_fwd = pulse_one(ser, idx, PCT_FWD)
        print(f"  dENC={d_fwd}")
        time.sleep(PAUSE_SEC)

        print(f"--- {name} BACKWARD {PCT_BACK}% ---")
        d_back = pulse_one(ser, idx, PCT_BACK)
        print(f"  dENC={d_back}")
        time.sleep(PAUSE_SEC)

        own_fwd = abs(d_fwd[idx]) if d_fwd else 0
        own_back = abs(d_back[idx]) if d_back else 0
        # Crosstalk: other encoders shouldn't move much if truly isolated.
        cross_fwd = sum(abs(d_fwd[i]) for i in range(4) if i != idx) if d_fwd else 0
        cross_back = sum(abs(d_back[i]) for i in range(4) if i != idx) if d_back else 0
        tps = (own_fwd + own_back) / (2.0 * PULSE_SEC)
        # Threshold: live motor+encoder should produce decent ticks in 0.55s.
        ok = tps >= 40.0
        alive[idx] = ok
        abs_tps[idx] = tps
        status = "OK" if ok else ("DEAD_ENC_OR_MOTOR" if tps < 8 else "WEAK")
        results[name] = {
            "tps": round(tps, 1),
            "d_fwd": d_fwd,
            "d_back": d_back,
            "cross_fwd": cross_fwd,
            "cross_back": cross_back,
            "status": status,
        }
        print(f"  => {name}: tps≈{tps:.0f}  status={status}  cross={cross_fwd}/{cross_back}")

    cmd(ser, "STOP", 0.2)

    # cal_tps: use measured rate scaled to "full" (~100% / 55% * measured)
    full_factor = 100.0 / float(PCT_FWD)
    cal = [max(80, int(round(abs_tps[i] * full_factor))) for i in range(4)]
    for i in range(4):
        if not alive[i]:
            # Placeholder so Mega SET_CAL accepts; PI stays off anyway.
            live_vals = [cal[j] for j in range(4) if alive[j]]
            cal[i] = max(80, int(round(0.5 * (sum(live_vals) / max(1, len(live_vals))))))

    # WSCALE: equalize live wheels by inverse TPS (faster → lower scale).
    live_idx = [i for i in range(4) if alive[i] and abs_tps[i] > 1]
    wscale = [100, 100, 100, 100]
    if len(live_idx) >= 2:
        target = math.exp(sum(math.log(abs_tps[i]) for i in live_idx) / len(live_idx))
        for i in live_idx:
            raw = 100.0 * target / abs_tps[i]
            wscale[i] = int(round(max(70, min(200, raw))))
        # Dead wheels: leave 100 (or 0 if confirmed dead motor — keep 100 for try).
        mean_live = sum(wscale[i] for i in live_idx) / len(live_idx)
        if mean_live > 1:
            fac = 100.0 / mean_live
            for i in live_idx:
                wscale[i] = int(round(max(70, min(200, wscale[i] * fac))))
    # Mirror FL←FR if FL encoder dead but we still command FL motor.
    if not alive[0] and alive[1]:
        wscale[0] = wscale[1]

    print("\n=== SUMMARY ===")
    for name in NAMES:
        r = results[name]
        print(f"  {name}: {r['status']:18s} tps≈{r['tps']}")
    print(f"SET_CAL {' '.join(map(str, cal))}")
    print(f"SET_WSCALE {' '.join(map(str, wscale))}")

    doc = {
        "cal_tps": cal,
        "pidv_kp_x1000": 0,
        "pidv_ki_x1000": 0,
        "frb_pct": 100,
        "frf_pct": 100,
        "wheel_scale_pct": wscale,
        "yaw_kp": 1.6,
        "yaw_deadband_deg": 2.5,
        "trim_w": {"fwd": 0.0, "back": 0.0, "strl": 0.0, "strr": 0.0},
        "motor_health": {NAMES[i]: results[NAMES[i]]["status"] for i in range(4)},
        "one_wheel_results": {
            NAMES[i]: {
                "tps": results[NAMES[i]]["tps"],
                "status": results[NAMES[i]]["status"],
                "d_fwd": results[NAMES[i]]["d_fwd"],
                "d_back": results[NAMES[i]]["d_back"],
            }
            for i in range(4)
        },
        "notes": (
            f"ONE_WHEEL encoder align {time.strftime('%Y-%m-%d %H:%M:%S')} "
            f"pulse={PULSE_SEC}s @{PCT_FWD}% — no chassis vx/vy calibration"
        ),
    }
    OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")

    # Push scales into Mega for immediate use after restart.
    cmd(ser, f"SET_CAL {cal[0]} {cal[1]} {cal[2]} {cal[3]}", 0.12)
    cmd(ser, f"SET_WSCALE {wscale[0]} {wscale[1]} {wscale[2]} {wscale[3]}", 0.12)
    cmd(ser, "STOP", 0.1)
    ser.close()
    print("DONE")


if __name__ == "__main__":
    main()
