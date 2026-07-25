#!/usr/bin/env python3
"""End-to-end alignment test through the teleop bridge (cmd file + lidar)."""
import json
import math
import threading
import time
import urllib.request
from pathlib import Path

import numpy as np

import rclpy
from sensor_msgs.msg import LaserScan

CMD_FILE = Path("/tmp/robot_cmd.json")
MAX_SHIFT_DEG = 60.0
API = "http://127.0.0.1:8765/api/scan"


def map_yaw():
    try:
        with urllib.request.urlopen(API, timeout=2) as resp:
            d = json.load(resp)
        p = d.get("pose") or {}
        if p.get("ok"):
            return float(p.get("yaw", 0.0))
    except Exception:
        pass
    return None


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
    best_s, best_score = 0, -1e9
    am = a > 0
    for s in range(-max_s, max_s + 1):
        br = np.roll(b, s)
        m = am & (br > 0)
        if m.sum() < 40:
            continue
        score = -np.mean(np.minimum(np.abs(a[m] - br[m]), 0.5))
        if score > best_score:
            best_score, best_s = score, s
    return best_s * inc


def drive(vx, vy, seconds=1.5):
    t0 = time.time()
    while time.time() - t0 < seconds:
        CMD_FILE.write_text(json.dumps(
            {"vx": vx, "vy": vy, "w": 0.0, "t": time.time()}))
        time.sleep(0.05)
    CMD_FILE.write_text(json.dumps(
        {"vx": 0.0, "vy": 0.0, "w": 0.0, "t": time.time()}))
    time.sleep(1.0)


def main():
    rclpy.init()
    node = rclpy.create_node("test_align_web")
    grab = ScanGrab(node)
    threading.Thread(target=rclpy.spin, args=(node,), daemon=True).start()

    if grab.fresh(timeout=10.0) is None:
        print("NO /scan DATA")
        return

    motions = [
        ("FWD     ", 0.30, 0.0),
        ("BACK    ", -0.30, 0.0),
        ("STRAFE_L", 0.0, 0.30),
        ("STRAFE_R", 0.0, -0.30),
    ]
    for label, vx, vy in motions:
        m_a = grab.fresh()
        y_a = map_yaw()
        drive(vx, vy)
        m_b = grab.fresh()
        y_b = map_yaw()
        if m_a is None or m_b is None:
            print(f"{label}: no scan")
            continue
        dyaw = math.degrees(yaw_by_correlation(clean(m_a), clean(m_b),
                                               m_a.angle_increment))
        map_s = ""
        if y_a is not None and y_b is not None:
            d = y_b - y_a
            while d > math.pi:
                d -= 2 * math.pi
            while d < -math.pi:
                d += 2 * math.pi
            map_s = f" mapYaw={math.degrees(d):+6.1f}deg"
        print(f"{label}: corrYaw={dyaw:+6.1f}deg{map_s}")
        time.sleep(0.6)
    print("DONE")


if __name__ == "__main__":
    main()
