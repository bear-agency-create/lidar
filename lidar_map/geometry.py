"""Math helpers and chassis-frame LiDAR filtering."""

from __future__ import annotations

import math

import numpy as np

from config import (
    FRAME_BODY_PAD,
    FRAME_POST_HALF_ANGLE,
    FRAME_POST_RANGE_MARGIN,
    FRAME_POSTS_XY,
    ROBOT_LENGTH_M,
    ROBOT_WIDTH_M,
)

_HL = ROBOT_LENGTH_M * 0.5
_HW = ROBOT_WIDTH_M * 0.5


def wrap_angle(a: float) -> float:
    return math.atan2(math.sin(a), math.cos(a))


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def yaw_from_quat(qx: float, qy: float, qz: float, qw: float) -> float:
    siny_cosp = 2.0 * (qw * qz + qx * qy)
    cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
    return math.atan2(siny_cosp, cosy_cosp)


def transform_local(pts: np.ndarray, x: float, y: float, yaw: float) -> np.ndarray:
    c, s = math.cos(yaw), math.sin(yaw)
    out = np.empty_like(pts)
    out[:, 0] = x + c * pts[:, 0] - s * pts[:, 1]
    out[:, 1] = y + s * pts[:, 0] + c * pts[:, 1]
    return out


def is_frame_rack_hit(angle: float, dist: float) -> bool:
    """True if this LiDAR return is a chassis rack / body (must not map)."""
    if not math.isfinite(dist) or dist <= 0.0:
        return True
    lx = dist * math.cos(angle)
    ly = dist * math.sin(angle)
    if abs(lx) <= _HL + FRAME_BODY_PAD and abs(ly) <= _HW + FRAME_BODY_PAD:
        return True
    for px, py in FRAME_POSTS_XY:
        post_r = math.hypot(px, py)
        if dist > post_r + FRAME_POST_RANGE_MARGIN:
            continue
        post_a = math.atan2(py, px)
        if abs(wrap_angle(angle - post_a)) <= FRAME_POST_HALF_ANGLE:
            return True
    return False
