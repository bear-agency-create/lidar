#!/usr/bin/env python3
"""Ground-truth alignment check: lidar scans before/after each motion.

Estimates real robot yaw change via circular correlation of range
profiles, and rough translation via masked centroid shift.
Usage: lidar_verify.py [mega_port]
"""
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


def centroid(msg, r):
    ang = msg.angle_min + np.arange(len(r)) * msg.angle_increment
    m = (r > 0.1) & (r < 4.0)
    if m.sum() < 30:
        return None
    x = r[m] * np.cos(ang[m])
    y = r[m] * np.sin(ang[m])
    return float(np.mean(x)), float(np.mean(y))


def drive(ser, vx, vy, seconds=1.5):
    t0 = time.time()
    while time.time() - t0 < seconds:
        ser.write(f"SET_ROBOT_VELOCITY {vx} {vy} 0\n".encode())
        time.sleep(0.08)
    ser.write(b"STOP\n")
    time.sleep(0.8)


def main():
    rclpy.init()
    node = rclpy.create_node("lidar_verify")
    grab = ScanGrab(node)
    spin = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    spin.start()

    ser = serial.Serial(MEGA, 115200, timeout=0.2)
    time.sleep(2.2)
    ser.reset_input_buffer()

    first = grab.fresh(timeout=10.0)
    if first is None:
        print("NO /scan DATA")
        return
    print(f"scan ok: {len(first.ranges)} pts, inc={first.angle_increment:.4f} rad")

    motions = [
        ("FWD     ", 500, 0),
        ("BACK    ", -500, 0),
        ("STRAFE_L", 0, 500),
        ("STRAFE_R", 0, -500),
    ]
    for label, vx, vy in motions:
        m_a = grab.fresh()
        if m_a is None:
            print(f"{label}: no scan before")
            continue
        a = clean(m_a)
        drive(ser, vx, vy)
        m_b = grab.fresh()
        if m_b is None:
            print(f"{label}: no scan after")
            continue
        b = clean(m_b)
        dyaw = yaw_by_correlation(a, b, m_a.angle_increment)
        ca, cb = centroid(m_a, a), centroid(m_b, b)
        move = ""
        if ca and cb:
            # rotate B centroid back by dyaw, translation ~ -(cb' - ca)
            c, s = math.cos(dyaw), math.sin(dyaw)
            cbx = c * cb[0] - s * cb[1]
            cby = s * cb[0] + c * cb[1]
            move = f" moveX~{-(cbx - ca[0]):+.2f}m moveY~{-(cby - ca[1]):+.2f}m"
        print(f"{label}: dYaw={math.degrees(dyaw):+6.1f}deg{move}")
        time.sleep(0.6)

    ser.write(b"STOP\n")
    ser.close()
    print("DONE")


if __name__ == "__main__":
    main()
