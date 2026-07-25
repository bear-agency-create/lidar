#!/usr/bin/env python3
"""Per-wheel encoder scale calibration: drive with yaw hold OFF, log raw ticks."""
import re
import sys
import time

import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
ENC_RE = re.compile(r"ENC FL=(-?\d+) FR=(-?\d+) RL=(-?\d+) RR=(-?\d+)")


def read_enc(ser):
    ser.write(b"ENC?\n")
    t0 = time.time()
    while time.time() - t0 < 0.6:
        raw = ser.readline().decode("ascii", "ignore").strip()
        m = ENC_RE.search(raw)
        if m:
            return [int(m.group(i)) for i in range(1, 5)]
    return None


def run(ser, vx, vy, label, seconds=1.8):
    ser.write(b"STOP\n")
    time.sleep(0.3)
    ser.write(b"RESET_ODOM\n")
    time.sleep(0.15)
    ser.reset_input_buffer()
    t0 = time.time()
    while time.time() - t0 < seconds:
        ser.write(f"SET_ROBOT_VELOCITY {vx} {vy} 0\n".encode())
        ser.readline()
        time.sleep(0.07)
    ser.write(b"STOP\n")
    time.sleep(0.5)
    ser.reset_input_buffer()
    e = read_enc(ser)
    if e:
        print(f"{label}: FL={e[0]:6d} FR={e[1]:6d} RL={e[2]:6d} RR={e[3]:6d}")
    else:
        print(f"{label}: no ENC reply")
    return e


def main():
    ser = serial.Serial(PORT, 115200, timeout=0.2)
    time.sleep(2.2)
    ser.reset_input_buffer()
    ser.write(b"SET_YAW 0 0\n")
    time.sleep(0.2)
    print("yaw-hold off:", ser.read(120))

    runs = {}
    for rep in range(2):
        runs.setdefault("FWD", []).append(run(ser, 500, 0, f"FWD{rep}"))
        time.sleep(0.6)
        runs.setdefault("BACK", []).append(run(ser, -500, 0, f"BACK{rep}"))
        time.sleep(0.6)
    runs.setdefault("STRL", []).append(run(ser, 0, 500, "STRL"))
    time.sleep(0.6)
    runs.setdefault("STRR", []).append(run(ser, 0, -500, "STRR"))

    ser.write(b"STOP\n")
    ser.close()

    # Scale estimate from straight runs: same physical distance per wheel.
    samples = [e for e in runs["FWD"] + runs["BACK"] if e]
    if samples:
        sums = [0.0] * 4
        for e in samples:
            for i in range(4):
                sums[i] += abs(e[i])
        mean = sum(sums) / 4.0
        scales = [s / mean if mean else 0.0 for s in sums]
        print("relative scales (FL FR RL RR):",
              " ".join(f"{s:.3f}" for s in scales))
    print("DONE")


if __name__ == "__main__":
    main()
