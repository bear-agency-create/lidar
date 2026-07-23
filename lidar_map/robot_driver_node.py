#!/usr/bin/env python3

import json
import time
from pathlib import Path

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from geometry_msgs.msg import Pose2D
from nav_msgs.msg import Odometry
from geometry_msgs.msg import TransformStamped

import tf2_ros
import serial
import re
from transforms3d.euler import euler2quat

CMD_FILE = Path("/tmp/robot_cmd.json")


class RobotDriverNode(Node):
    def __init__(self):
        super().__init__('robot_driver_node')

        self.declare_parameter('serial_port', '/dev/ttyMEGA')
        self.declare_parameter('baudrate', 115200)
        self.declare_parameter('mecanum', True)
        self.mecanum = bool(self.get_parameter('mecanum').value)

        self.cmd_vel_sub = self.create_subscription(
            Twist, '/cmd_vel', self.cmd_vel_callback, 10
        )

        self.odom_pub = self.create_publisher(Odometry, 'odom', 10)
        self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)

        serial_port_path = self.get_parameter('serial_port').get_parameter_value().string_value
        baudrate = self.get_parameter('baudrate').get_parameter_value().integer_value

        self.ser = serial.Serial(serial_port_path, baudrate=baudrate, timeout=0.05)
        self.get_logger().info(
            f'Opened Arduino Mega: {serial_port_path} @ {baudrate} '
            f'(mecanum={self.mecanum}, file={CMD_FILE})'
        )

        self.pos_pattern = re.compile(r'POS X=([\-\d\.]+) Y=([\-\d\.]+) Th=([\-\d\.]+)')

        self._last_cmd_t = time.time()
        self._stopped = True
        self._last_sent = (0.0, 0.0, 0.0)

        self.create_timer(0.05, self.read_serial_timer_callback)
        self.create_timer(0.05, self._poll_cmd_file)
        self.create_timer(0.2, self._cmd_watchdog)

        self.set_pose_sub = self.create_subscription(
            Pose2D, '/set_pose', self.set_pose_callback, 10
        )

    def _apply_velocity(self, vx_mps: float, vy_mps: float, w: float) -> None:
        # Integers only — Mega parses with atoi (AVR float scanf is unreliable)
        boost = 1.8
        vx_mm = int(max(-700, min(700, vx_mps * 1000.0 * boost)))
        vy_mm = int(max(-700, min(700, vy_mps * 1000.0 * boost)))
        w_mrad = int(max(-2500, min(2500, w * 1000.0)))
        if self.mecanum:
            command = f'SET_ROBOT_VELOCITY {vx_mm} {vy_mm} {w_mrad}\n'
        else:
            command = f'SET_ROBOT_VELOCITY {vx_mm} {w_mrad}\n'
        try:
            self.ser.write(command.encode())
            self._last_cmd_t = time.time()
            self._stopped = False
            self._last_sent = (vx_mps, vy_mps, w)
        except serial.SerialException as e:
            self.get_logger().error(f'Failed to write to serial: {e}')

    def _poll_cmd_file(self) -> None:
        """Надёжный канал от веб-пульта: /tmp/robot_cmd.json"""
        try:
            if not CMD_FILE.is_file():
                return
            payload = json.loads(CMD_FILE.read_text(encoding='utf-8'))
            t = float(payload.get('t', 0.0))
            if time.time() - t > 1.4:
                return
            vx = float(payload.get('vx', 0.0))
            vy = float(payload.get('vy', 0.0))
            w = float(payload.get('w', 0.0))
            self._apply_velocity(vx, vy, w)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return

    def _cmd_watchdog(self) -> None:
        age = time.time() - self._last_cmd_t
        if age > 0.65 and not self._stopped:
            try:
                self.ser.write(b'STOP\n')
                self._stopped = True
                self._last_sent = (0.0, 0.0, 0.0)
            except serial.SerialException:
                pass

    def cmd_vel_callback(self, msg: Twist):
        self._apply_velocity(msg.linear.x, msg.linear.y, msg.angular.z)

    def read_serial_timer_callback(self):
        try:
            # drain a few lines per tick
            for _ in range(8):
                raw = self.ser.readline()
                if not raw:
                    break
                line = raw.decode('ascii', errors='ignore').strip()
                if not line:
                    continue
                match = self.pos_pattern.search(line)
                if not match:
                    continue
                x_mm = float(match.group(1))
                y_mm = float(match.group(2))
                th = float(match.group(3))
                x = x_mm / 1000.0
                y = y_mm / 1000.0

                odom_msg = Odometry()
                odom_msg.header.stamp = self.get_clock().now().to_msg()
                odom_msg.header.frame_id = 'odom'
                odom_msg.child_frame_id = 'base_link'
                odom_msg.pose.pose.position.x = x
                odom_msg.pose.pose.position.y = y
                odom_msg.pose.pose.position.z = 0.0
                q = euler2quat(0.0, 0.0, th)
                odom_msg.pose.pose.orientation.w = q[0]
                odom_msg.pose.pose.orientation.x = q[1]
                odom_msg.pose.pose.orientation.y = q[2]
                odom_msg.pose.pose.orientation.z = q[3]
                self.odom_pub.publish(odom_msg)

                t = TransformStamped()
                t.header.stamp = odom_msg.header.stamp
                t.header.frame_id = 'odom'
                t.child_frame_id = 'base_link'
                t.transform.translation.x = x
                t.transform.translation.y = y
                t.transform.translation.z = 0.0
                t.transform.rotation.w = q[0]
                t.transform.rotation.x = q[1]
                t.transform.rotation.y = q[2]
                t.transform.rotation.z = q[3]
                self.tf_broadcaster.sendTransform(t)
        except serial.SerialException as e:
            self.get_logger().error(f'Failed to read from serial: {e}')

    def set_pose_callback(self, msg: Pose2D):
        x = msg.x * 1000
        y = msg.y * 1000
        command = f'SET_POSE {x:.2f} {y:.2f} {msg.theta:.2f}\n'
        try:
            self.ser.write(command.encode())
            self.get_logger().info(f'Sent command: {command.strip()}')
        except serial.SerialException as e:
            self.get_logger().error(f'Failed to write to serial: {e}')


def main(args=None):
    rclpy.init(args=args)
    node = RobotDriverNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
