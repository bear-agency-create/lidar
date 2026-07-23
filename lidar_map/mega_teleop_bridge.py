#!/usr/bin/env python3
"""Web teleop → Mega serial + publish /odom from POS lines."""

from __future__ import annotations

import json
import math
import os
import re
import time
from pathlib import Path

import serial

CMD_FILE = Path("/tmp/robot_cmd.json")
PORT = os.environ.get("MEGA_DEV", "/dev/ttyUSB0")
BAUD = 115200
STALE_SEC = 0.35
POS_RE = re.compile(r"POS X=([-\d.]+) Y=([-\d.]+) Th=([-\d.]+)")


def main() -> None:
    try:
        import rclpy
        from geometry_msgs.msg import TransformStamped
        from nav_msgs.msg import Odometry
        import tf2_ros
        from transforms3d.euler import euler2quat
    except ImportError as e:
        raise SystemExit(f"ROS2 python deps missing: {e}") from e

    rclpy.init()
    node = rclpy.create_node("mega_teleop_bridge")
    odom_pub = node.create_publisher(Odometry, "odom", 10)
    tf_br = tf2_ros.TransformBroadcaster(node)

    ser = serial.Serial(PORT, BAUD, timeout=0.05)
    time.sleep(2.0)
    ser.reset_input_buffer()
    node.get_logger().info(f"mega_teleop_bridge on {PORT}")
    last_stop = False

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
                    if line.startswith("ENC ") or line.startswith("READY"):
                        node.get_logger().info(line)
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

        vx = vy = w = 0.0
        fresh = False
        try:
            if CMD_FILE.is_file():
                data = json.loads(CMD_FILE.read_text(encoding="utf-8"))
                age = time.time() - float(data.get("t", 0.0))
                if age <= STALE_SEC:
                    fresh = True
                    vx = float(data.get("vx", 0.0))
                    vy = float(data.get("vy", 0.0))
                    w = float(data.get("w", 0.0))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            fresh = False

        moving = fresh and (abs(vx) > 0.02 or abs(vy) > 0.02 or abs(w) > 0.05)
        try:
            if moving:
                vx_mm = int(max(-700, min(700, vx * 1000.0 * 1.8)))
                vy_mm = int(max(-700, min(700, vy * 1000.0 * 1.8)))
                w_mrad = int(max(-2500, min(2500, w * 1000.0)))
                ser.write(f"SET_ROBOT_VELOCITY {vx_mm} {vy_mm} {w_mrad}\n".encode())
                last_stop = False
            elif not last_stop:
                ser.write(b"STOP\n")
                last_stop = True
        except serial.SerialException as e:
            node.get_logger().error(f"serial error: {e}")
            time.sleep(1.0)
            try:
                ser.close()
            except Exception:
                pass
            try:
                ser = serial.Serial(PORT, BAUD, timeout=0.05)
                time.sleep(2.0)
                last_stop = False
            except serial.SerialException:
                time.sleep(2.0)
            continue

        time.sleep(0.02)

    ser.close()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
