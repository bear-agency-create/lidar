#!/usr/bin/env python3
"""Test all 4 motors both directions via TEST_WHEEL / ONE_WHEEL + ENC."""
from __future__ import annotations

import re
import time
from pathlib import Path

import serial

PORT = "/dev/ttyMEGA" if Path("/dev/ttyMEGA").exists() else "/dev/ttyUSB1"
ENC = re.compile(r"ENC FL=(-?\d+) FR=(-?\d+) RL=(-?\d+) RR=(-?\d+)")
NAMES = ("FL", "FR", "RL", "RR")
PULSE_MS = 1200


def enc(ser):
    ser.reset_input_buffer()
    ser.write(b"ENC?\n")
    t0 = time.time()
    while time.time() - t0 < 0.8:
        m = ENC.search(ser.readline().decode("ascii", "ignore"))
        if m:
            return [int(m.group(i)) for i in range(1, 5)]
    return None


def drain(ser, sec=0.25):
    t0 = time.time()
    while time.time() - t0 < sec:
        ser.read(512)
        time.sleep(0.02)


def lines(ser, sec=1.5):
    out = []
    t0 = time.time()
    while time.time() - t0 < sec:
        line = ser.readline().decode("ascii", "ignore").strip()
        if line and not line.startswith("POS "):
            out.append(line)
    return out


def pulse(ser, idx: int, direction: int) -> dict:
    name = NAMES[idx]
    label = "FWD" if direction > 0 else "BACK"
    drain(ser, 0.15)
    ser.write(b"STOP\n")
    time.sleep(0.2)
    e0 = enc(ser)
    cmd = f"TEST_WHEEL {idx} {direction} {PULSE_MS}\n".encode()
    ser.write(cmd)
    resp = lines(ser, PULSE_MS / 1000.0 + 0.8)
    ser.write(b"STOP\n")
    time.sleep(0.35)
    e1 = enc(ser)
    d = [e1[i] - e0[i] for i in range(4)] if e0 and e1 else None
    own = abs(d[idx]) if d else 0
    cross = sum(abs(d[i]) for i in range(4) if i != idx) if d else 0
    if own >= 400:
        status = "OK"
    elif own >= 80:
        status = "WEAK"
    else:
        status = "DEAD"
    return {
        "wheel": name,
        "dir": label,
        "dENC": d,
        "own": own,
        "cross": cross,
        "status": status,
        "resp": resp[-3:],
    }


def main():
    print(f"PORT={PORT}")
    print(f"Pulse={PULSE_MS}ms each direction, all 4 wheels")
    print("=" * 60)
    ser = serial.Serial(PORT, 115200, timeout=0.3)
    time.sleep(2.2)
    drain(ser, 0.4)
    ser.write(b"PING\n")
    print("PING", lines(ser, 0.6))

    results = []
    for idx in range(4):
        for direction in (1, -1):
            r = pulse(ser, idx, direction)
            results.append(r)
            print(
                f"{r['wheel']:2s} {r['dir']:4s}  own={r['own']:5d}  "
                f"cross={r['cross']:5d}  status={r['status']:4s}  dENC={r['dENC']}"
            )
            time.sleep(0.45)

    ser.write(b"STOP\n")
    ser.close()

    print("=" * 60)
    print("SUMMARY")
    ok = weak = dead = 0
    for r in results:
        mark = {"OK": "✓", "WEAK": "~", "DEAD": "✗"}[r["status"]]
        print(f"  {mark} {r['wheel']} {r['dir']:4s}  ticks={r['own']}")
        if r["status"] == "OK":
            ok += 1
        elif r["status"] == "WEAK":
            weak += 1
        else:
            dead += 1
    print(f"OK={ok} WEAK={weak} DEAD={dead} / {len(results)}")
    print("ALL_MOTORS_TEST_DONE")


if __name__ == "__main__":
    main()
