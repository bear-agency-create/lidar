#!/usr/bin/env python3
"""Tune FR reverse scale (SET_FRB) by lidar-measured yaw during BACK runs."""
import math
import sys
import threading
import time

import numpy as np
import serial

import rclpy
from sensor_msgs.msg import LaserScan

MEGA = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
MAX_SHIFT_DEG = 60.0
CANDIDATES = [100, 85, 115, 70, 130]


class ScanGrab:
    def __init__(self, node):
        self.lock = threading.Lock()
        self.msg = None
        node.create_subscription(LaserScan, "/scan", self._cb, 5)

    def _cb(self, msg):
        with self.lock:
            self.msg = msg

    def fresh(self, timeout=5.0):
        with self.lock:
            self.msg = None
        t0 = time.time()
        while time.time() - t0 < timeout:
            with self.lock:
                if self.msg is not None:
                    return self.msg
            time.sleep(0.05)
        return None


def clean(msg):
    r = np.asarray(msg.ranges, dtype=np.float64)
    r = np.nan_to_num(r, nan=0.0, posinf=0.0, neginf=0.0)
    r[(r < 0.08) | (r > 8.0)] = 0.0
    return r


def yaw_by_correlation(a, b, inc):
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    max_s = int(MAX_SHIFT_DEG * math.pi / 180.0 / inc)
    best_s, best_score = 0, -1.0
    am = a > 0
    for s in range(-max_s, max_s + 1):
        br = np.roll(b, s)
        m = am & (br > 0)
        if m.sum() < 40:
            continue
        d = np.abs(a[m] - br[m])
        score = -np.mean(np.minimum(d, 0.5))
        if score > best_score:
            best_score, best_s = score, s
    return best_s * inc


def drive(ser, vx, vy, seconds=1.5):
    t0 = time.time()
    while time.time() - t0 < seconds:
        ser.write(f"SET_ROBOT_VELOCITY {vx} {vy} 0\n".encode())
        time.sleep(0.08)
    ser.write(b"STOP\n")
    time.sleep(0.8)


def cmd(ser, line):
    ser.write((line + "\n").encode())
    time.sleep(0.15)
    ser.reset_input_buffer()


def main():
    rclpy.init()
    node = rclpy.create_node("sweep_frb")
    grab = ScanGrab(node)
    threading.Thread(target=rclpy.spin, args=(node,), daemon=True).start()

    ser = serial.Serial(MEGA, 115200, timeout=0.2)
    time.sleep(2.2)
    ser.reset_input_buffer()

    if grab.fresh(timeout=10.0) is None:
        print("NO /scan DATA")
        return

    results = []
    for pct in CANDIDATES:
        cmd(ser, f"SET_FRB {pct}")
        m_a = grab.fresh()
        drive(ser, -500, 0)          # BACK, measured
        m_b = grab.fresh()
        if m_a is None or m_b is None:
            print(f"FRB {pct}: no scan")
            continue
        dyaw = math.degrees(yaw_by_correlation(clean(m_a), clean(m_b),
                                               m_a.angle_increment))
        print(f"FRB {pct}: BACK dYaw={dyaw:+6.1f}deg")
        results.append((abs(dyaw), pct, dyaw))
        drive(ser, 500, 0, seconds=1.4)   # return forward
        time.sleep(0.5)

    if results:
        results.sort()
        best = results[0][1]
        cmd(ser, f"SET_FRB {best}")
        print(f"BEST FRB={best} (dYaw={results[0][2]:+.1f}deg)")
    ser.write(b"STOP\n")
    ser.close()
    print("DONE")


if __name__ == "__main__":
    main()
