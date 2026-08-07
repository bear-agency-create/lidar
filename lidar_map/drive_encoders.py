#!/usr/bin/env python3
"""Encoder mecanum drive: web cmd → Mega serial + /odom + lidar yaw hold.

This file owns ONLY chassis motion (forward/back/strafe/rotate). Mapping
and the web UI live in other modules; main.py / start_drive_map.sh run
this process alongside the map server.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import sys
import threading
import time
from pathlib import Path

import numpy as np
import serial

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from logutil import get_logger, setup_logging
except ImportError:
    setup_logging = None  # type: ignore[assignment]
    get_logger = None  # type: ignore[assignment]

CMD_FILE = Path("/tmp/robot_cmd.json")
CAL_FILE = Path(os.environ.get("DRIVE_CAL_FILE", str(Path(__file__).resolve().parent / "drive_cal.json")))
PORT = os.environ.get("MEGA_DEV", "/dev/ttyMEGA" if os.path.exists("/dev/ttyMEGA") else "/dev/ttyUSB1")
BAUD = 115200
STALE_SEC = 1.5   # tolerate WiFi/SSH hiccups from the web remote
POS_RE = re.compile(r"POS X=([-\d.]+) Y=([-\d.]+) Th=([-\d.]+)")

# Lidar yaw hold (overridden by drive_cal.json when present)
YAW_KP = float(os.environ.get("YAW_KP", "1.2"))      # rad/s per rad of drift
YAW_W_MAX = 0.65                                     # rad/s correction clamp
YAW_DEADBAND = math.radians(3.0)                     # ignore parallax noise
YAW_MAX_SHIFT_DEG = 25.0
SCAN_STALE_SEC = 0.6

DEFAULT_CAL = {
    "cal_tps": [510, 734, 2103, 1389],
    "pidv_kp_x1000": 0,
    "pidv_ki_x1000": 0,
    "frb_pct": 100,
    "frf_pct": 100,
    "wheel_scale_pct": [200, 200, 200, 200],
    "yaw_kp": 2.0,
    "yaw_deadband_deg": 2.0,
    "trim_w": {"fwd": 0.0, "back": 0.0, "strl": 0.0, "strr": 0.0},
}


def load_cal() -> dict:
    cal = dict(DEFAULT_CAL)
    cal["trim_w"] = dict(DEFAULT_CAL["trim_w"])
    try:
        if CAL_FILE.is_file():
            data = json.loads(CAL_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cal.update({k: data[k] for k in data if k != "trim_w"})
                tw = data.get("trim_w") or {}
                if isinstance(tw, dict):
                    for k in ("fwd", "back", "strl", "strr"):
                        if k in tw:
                            cal["trim_w"][k] = float(tw[k])
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass
    return cal


def apply_mega_cal(ser: serial.Serial, cal: dict, log: logging.Logger) -> None:
    """Push floor calibration into Mega firmware (runtime, survives until reboot)."""
    tps = cal.get("cal_tps") or DEFAULT_CAL["cal_tps"]
    if len(tps) == 4:
        line = f"SET_CAL {int(tps[0])} {int(tps[1])} {int(tps[2])} {int(tps[3])}\n"
        ser.write(line.encode())
        time.sleep(0.08)
    kp = int(cal.get("pidv_kp_x1000", 0))
    ki = int(cal.get("pidv_ki_x1000", 0))
    ser.write(f"SET_PIDV {kp} {ki}\n".encode())
    time.sleep(0.08)
    frb = int(cal.get("frb_pct", 100))
    ser.write(f"SET_FRB {frb}\n".encode())
    time.sleep(0.08)
    frf = int(cal.get("frf_pct", 100))
    ser.write(f"SET_FRF {frf}\n".encode())
    time.sleep(0.08)
    ws = cal.get("wheel_scale_pct") or [100, 85, 100, 122]
    if len(ws) == 4:
        ser.write(
            f"SET_WSCALE {int(ws[0])} {int(ws[1])} {int(ws[2])} {int(ws[3])}\n".encode()
        )
        time.sleep(0.08)
    log.info(
        "mega cal applied SET_CAL=%s SET_PIDV=%s %s SET_FRB=%s SET_FRF=%s SET_WSCALE=%s",
        tps, kp, ki, frb, frf, ws,
    )


def direction_trim_w(vx: float, vy: float, trim: dict) -> float:
    """Feedforward yaw trim for pure translation on the current floor."""
    if abs(vx) < 0.02 and abs(vy) < 0.02:
        return 0.0
    if abs(vx) >= abs(vy):
        key = "fwd" if vx > 0 else "back"
        scale = min(1.0, abs(vx) / 0.25)
    else:
        key = "strl" if vy > 0 else "strr"
        scale = min(1.0, abs(vy) / 0.25)
    return float(trim.get(key, 0.0)) * scale


def _clean(ranges) -> np.ndarray:
    r = np.asarray(ranges, dtype=np.float64)
    r = np.nan_to_num(r, nan=0.0, posinf=0.0, neginf=0.0)
    r[(r < 0.08) | (r > 8.0)] = 0.0
    return r


def _yaw_by_correlation(a: np.ndarray, b: np.ndarray, inc: float) -> float | None:
    """Yaw of scan b relative to a, with parabolic sub-bin refinement."""
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    max_s = int(YAW_MAX_SHIFT_DEG * math.pi / 180.0 / max(1e-6, inc))
    am = a > 0
    scores: dict[int, float] = {}
    best_s, best_score = None, -1e9
    for s in range(-max_s, max_s + 1):
        br = np.roll(b, s)
        m = am & (br > 0)
        if m.sum() < 40:
            continue
        score = -float(np.mean(np.minimum(np.abs(a[m] - br[m]), 0.5)))
        scores[s] = score
        if score > best_score:
            best_score, best_s = score, s
    if best_s is None:
        return None
    frac = 0.0
    s0 = scores.get(best_s - 1)
    s2 = scores.get(best_s + 1)
    if s0 is not None and s2 is not None:
        denom = s0 - 2.0 * best_score + s2
        if abs(denom) > 1e-12:
            frac = max(-0.5, min(0.5, 0.5 * (s0 - s2) / denom))
    return (best_s + frac) * inc


class YawHold:
    """Accumulates yaw incrementally between consecutive scans.

    Consecutive scans are ~100 ms apart, so translation between them is
    a few cm and correlation is unbiased by parallax (unlike matching
    against the motion-start reference over a metre of travel).
    """

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.latest = None          # (ranges, inc, t)
        self.active = False
        self.prev = None            # (ranges, inc, t) last accumulated scan
        self.err = 0.0

    def on_scan(self, msg) -> None:
        with self.lock:
            self.latest = (_clean(msg.ranges), float(msg.angle_increment), time.time())

    def start(self) -> None:
        with self.lock:
            self.active = True
            self.prev = self.latest
            self.err = 0.0

    def stop(self) -> None:
        with self.lock:
            self.active = False
            self.prev = None
            self.err = 0.0

    def correction(self) -> float:
        with self.lock:
            if not self.active or self.latest is None:
                return 0.0
            ranges, inc, t = self.latest
            if time.time() - t > SCAN_STALE_SEC:
                return 0.0
            if self.prev is None:
                self.prev = self.latest
                return 0.0
            if t > self.prev[2]:
                dyaw = _yaw_by_correlation(self.prev[0], ranges, inc)
                if dyaw is not None:
                    self.err += dyaw
                self.prev = self.latest
            if abs(self.err) <= YAW_DEADBAND:
                return 0.0
            err = self.err - math.copysign(YAW_DEADBAND, self.err)
            w = -YAW_KP * err
            return max(-YAW_W_MAX, min(YAW_W_MAX, w))


def main() -> None:
    if setup_logging is not None:
        setup_logging("drive_encoders")
        log = get_logger("drive_encoders")
    else:
        logging.basicConfig(level=logging.INFO)
        log = logging.getLogger("drive_encoders")

    try:
        import rclpy
        from geometry_msgs.msg import TransformStamped
        from nav_msgs.msg import Odometry
        from sensor_msgs.msg import LaserScan
        import tf2_ros
        from transforms3d.euler import euler2quat
    except ImportError as e:
        raise SystemExit(f"ROS2 python deps missing: {e}") from e

    global YAW_KP, YAW_DEADBAND

    cal = load_cal()
    YAW_KP = float(os.environ.get("YAW_KP", cal.get("yaw_kp", YAW_KP)))
    YAW_DEADBAND = math.radians(float(cal.get("yaw_deadband_deg", 3.0)))
    trim_w = dict(cal.get("trim_w") or {})

    rclpy.init()
    node = rclpy.create_node("mega_teleop_bridge")
    odom_pub = node.create_publisher(Odometry, "odom", 10)
    tf_br = tf2_ros.TransformBroadcaster(node)

    hold = YawHold()
    node.create_subscription(LaserScan, "/scan", hold.on_scan, 5)

    def open_serial() -> serial.Serial:
        s = serial.Serial(PORT, BAUD, timeout=0.05)
        time.sleep(2.0)
        s.reset_input_buffer()
        apply_mega_cal(s, cal, log)
        return s

    ser = open_serial()
    msg = (
        f"drive_encoders on {PORT} (yaw_kp={YAW_KP} cal={cal.get('cal_tps')} "
        f"frb={cal.get('frb_pct')} trim={trim_w})"
    )
    node.get_logger().info(msg)
    log.info(msg)
    last_stop = False
    holding = False
    cmd_ticks = 0
    last_vx = last_vy = last_w = 0.0
    last_teleop = False
    last_fresh_mono = 0.0

    while rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0.0)
        try:
            while ser.in_waiting:
                raw = ser.readline()
                if not raw:
                    break
                line = raw.decode("ascii", errors="ignore").strip()
                m = POS_RE.search(line)
                if not m:
                    if line.startswith(
                        ("ENC ", "READY", "CAL_OK", "PIDV_OK", "FRB_OK", "FRF_OK", "WSCALE_OK")
                    ):
                        node.get_logger().info(line)
                        log.info(line)
                    continue
                x_mm = float(m.group(1))
                y_mm = float(m.group(2))
                th = float(m.group(3))
                x = x_mm / 1000.0
                y = y_mm / 1000.0
                q = euler2quat(0.0, 0.0, th)
                now = node.get_clock().now().to_msg()

                odom = Odometry()
                odom.header.stamp = now
                odom.header.frame_id = "odom"
                odom.child_frame_id = "base_link"
                odom.pose.pose.position.x = x
                odom.pose.pose.position.y = y
                odom.pose.pose.orientation.w = float(q[0])
                odom.pose.pose.orientation.x = float(q[1])
                odom.pose.pose.orientation.y = float(q[2])
                odom.pose.pose.orientation.z = float(q[3])
                odom_pub.publish(odom)

                t = TransformStamped()
                t.header.stamp = now
                t.header.frame_id = "odom"
                t.child_frame_id = "base_link"
                t.transform.translation.x = x
                t.transform.translation.y = y
                t.transform.rotation.w = float(q[0])
                t.transform.rotation.x = float(q[1])
                t.transform.rotation.y = float(q[2])
                t.transform.rotation.z = float(q[3])
                tf_br.sendTransform(t)
        except serial.SerialException:
            time.sleep(0.5)
            continue

        vx = vy = w_cmd = 0.0
        fresh = False
        teleop = False
        now_m = time.time()
        try:
            if CMD_FILE.is_file():
                raw = CMD_FILE.read_text(encoding="utf-8").strip()
                if raw:
                    data = json.loads(raw)
                    age = now_m - float(data.get("t", 0.0))
                    if age <= STALE_SEC:
                        fresh = True
                        vx = float(data.get("vx", 0.0))
                        vy = float(data.get("vy", 0.0))
                        w_cmd = float(data.get("w", 0.0))
                        teleop = bool(data.get("teleop", False))
                        last_vx, last_vy, last_w = vx, vy, w_cmd
                        last_teleop = teleop
                        last_fresh_mono = now_m
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            # Mid-write glitch: reuse last good cmd briefly.
            if now_m - last_fresh_mono <= STALE_SEC:
                fresh = True
                vx, vy, w_cmd = last_vx, last_vy, last_w
                teleop = last_teleop

        moving = fresh and (abs(vx) > 0.02 or abs(vy) > 0.02 or abs(w_cmd) > 0.05)
        # Pure translation: yaw-hold only for planner/nav — not web teleop buttons.
        translating = moving and abs(w_cmd) <= 0.05 and not teleop

        if translating and not holding:
            hold.start()
            holding = True
        elif not translating and holding:
            hold.stop()
            holding = False

        try:
            if moving:
                w = w_cmd
                if holding:
                    w = direction_trim_w(vx, vy, trim_w) + hold.correction()
                # Strong yaw for in-place turn under load (Arduino full mix ~1500).
                vx_mm = int(max(-1000, min(1000, vx * 1000.0 * 3.8)))
                vy_mm = int(max(-1000, min(1000, vy * 1000.0 * 3.8)))
                w_mrad = int(max(-4000, min(4000, w * 1000.0 * 2.5)))
                ser.write(f"SET_ROBOT_VELOCITY {vx_mm} {vy_mm} {w_mrad}\n".encode())
                last_stop = False
                cmd_ticks += 1
                if cmd_ticks % 100 == 0:
                    log.info(
                        "drive vx=%.2f vy=%.2f w=%.2f hold=%s",
                        vx, vy, w, holding,
                    )
            elif not last_stop:
                ser.write(b"HARD_STOP\n")
                last_stop = True
                log.info("STOP")
        except serial.SerialException as e:
            node.get_logger().error(f"serial error: {e}")
            log.error("serial error: %s", e)
            time.sleep(1.0)
            try:
                ser.close()
            except Exception:
                pass
            try:
                ser = open_serial()
                last_stop = False
            except serial.SerialException:
                time.sleep(2.0)
            continue

        time.sleep(0.02)

    try:
        ser.write(b"HARD_STOP\n")
        time.sleep(0.05)
    except Exception:
        pass
    try:
        ser.close()
    except Exception:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
