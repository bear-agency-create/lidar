#!/usr/bin/env python3
"""Single FWD burst with lidar yaw + translation measurement."""
import math
import sys
import threading
import time

import numpy as np
import serial

import rclpy
from sensor_msgs.msg import LaserScan

MEGA = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
MAX_SHIFT_DEG = 90.0


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


def yaw_corr(a, b, inc):
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    max_s = int(MAX_SHIFT_DEG * math.pi / 180.0 / inc)
    best_s, best = 0, -1e9
    am = a > 0
    for s in range(-max_s, max_s + 1):
        br = np.roll(b, s)
        m = am & (br > 0)
        if m.sum() < 40:
            continue
        sc = -np.mean(np.minimum(np.abs(a[m] - br[m]), 0.5))
        if sc > best:
            best, best_s = sc, s
    return best_s * inc


def centroid(msg, r):
    ang = msg.angle_min + np.arange(len(r)) * msg.angle_increment
    m = (r > 0.1) & (r < 4.0)
    if m.sum() < 30:
        return None
    return (float(np.mean(r[m] * np.cos(ang[m]))),
            float(np.mean(r[m] * np.sin(ang[m]))))


def main():
    rclpy.init()
    node = rclpy.create_node("quick_fwd")
    grab = ScanGrab(node)
    threading.Thread(target=rclpy.spin, args=(node,), daemon=True).start()

    ser = serial.Serial(MEGA, 115200, timeout=0.2)
    time.sleep(2.2)
    ser.reset_input_buffer()
    ser.write(b"PING\n")
    time.sleep(0.4)
    print("boot:", ser.read(120))

    m_a = grab.fresh(timeout=10.0)
    if m_a is None:
        print("NO /scan DATA")
        return
    t0 = time.time()
    while time.time() - t0 < 1.2:
        ser.write(b"SET_ROBOT_VELOCITY 500 0 0\n")
        time.sleep(0.08)
    ser.write(b"STOP\n")
    time.sleep(0.9)
    m_b = grab.fresh()
    a, b = clean(m_a), clean(m_b)
    dyaw = math.degrees(yaw_corr(a, b, m_a.angle_increment))
    ca, cb = centroid(m_a, a), centroid(m_b, b)
    move = ""
    if ca and cb:
        r = math.radians(dyaw)
        cbx = math.cos(r) * cb[0] - math.sin(r) * cb[1]
        cby = math.sin(r) * cb[0] + math.cos(r) * cb[1]
        move = f" moveX~{-(cbx - ca[0]):+.2f}m moveY~{-(cby - ca[1]):+.2f}m"
    print(f"FWD_CMD result: dYaw={dyaw:+6.1f}deg{move}")
    ser.write(b"STOP\n")
    ser.close()
    print("DONE")


if __name__ == "__main__":
    main()
