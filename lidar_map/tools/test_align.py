#!/usr/bin/env python3
"""Drive fwd/back/strafe-L/strafe-R with heading hold; report drift per motion."""
import math
import re
import sys
import time

import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
POS_RE = re.compile(
    r"POS X=([-\d.]+) Y=([-\d.]+) Th=([-\d.]+) L=(-?\d+) R=(-?\d+) C=([-\d.]+)"
)


def parse_pos(line):
    m = POS_RE.search(line)
    if not m:
        return None
    return tuple(float(m.group(i)) for i in range(1, 7))


def run_motion(ser, vx, vy, label, seconds=2.0):
    ser.write(b"STOP\n")
    time.sleep(0.25)
    ser.write(b"RESET_ODOM\n")
    time.sleep(0.15)
    ser.reset_input_buffer()

    first = last = None
    max_corr = 0.0
    t0 = time.time()
    while time.time() - t0 < seconds:
        ser.write(f"SET_ROBOT_VELOCITY {vx} {vy} 0\n".encode())
        raw = ser.readline().decode("ascii", "ignore").strip()
        p = parse_pos(raw)
        if p:
            if first is None:
                first = p
            last = p
            max_corr = max(max_corr, abs(p[5]))
        time.sleep(0.07)
    ser.write(b"STOP\n")
    time.sleep(0.4)
    # drain final pose
    t1 = time.time()
    while time.time() - t1 < 0.4:
        raw = ser.readline().decode("ascii", "ignore").strip()
        p = parse_pos(raw)
        if p:
            last = p

    ser.write(b"ENC?\n")
    time.sleep(0.15)
    enc = ""
    t1 = time.time()
    while time.time() - t1 < 0.5:
        raw = ser.readline().decode("ascii", "ignore").strip()
        if raw.startswith("ENC"):
            enc = raw
            break

    if not first or not last:
        print(f"{label}: NO DATA")
        return
    dth = last[2] - first[2]
    while dth > math.pi:
        dth -= 2 * math.pi
    while dth < -math.pi:
        dth += 2 * math.pi
    dx = last[0] - first[0]
    dy = last[1] - first[1]
    print(
        f"{label}: dX={dx:+7.0f}mm dY={dy:+7.0f}mm dTh={math.degrees(dth):+6.1f}deg "
        f"max|C|={max_corr:.2f}"
    )
    print(f"  {enc}")


def main():
    ser = serial.Serial(PORT, 115200, timeout=0.2)
    time.sleep(2.2)
    ser.reset_input_buffer()
    ser.write(b"PING\n")
    time.sleep(0.3)
    print("boot:", ser.read(200))

    run_motion(ser, 500, 0, "FWD     ")
    time.sleep(0.8)
    run_motion(ser, -500, 0, "BACK    ")
    time.sleep(0.8)
    run_motion(ser, 0, 500, "STRAFE_L")
    time.sleep(0.8)
    run_motion(ser, 0, -500, "STRAFE_R")

    ser.write(b"STOP\n")
    ser.close()
    print("DONE")


if __name__ == "__main__":
    main()
