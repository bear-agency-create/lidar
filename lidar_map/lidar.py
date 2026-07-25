"""LiDAR scan processing: chassis filter, hit extraction, pose prior."""

from __future__ import annotations

import math

import numpy as np
from sensor_msgs.msg import LaserScan

from config import (
    ICP_MAX_POINTS,
    ICP_STRIDE,
    MAP_HIT_STRIDE,
    MAX_RANGE,
    MIN_RANGE_MAP,
    MIN_RANGE_SHOW,
)
from geometry import is_frame_rack_hit


def local_from_scan(
    msg: LaserScan,
) -> tuple[np.ndarray, list[tuple[float, float]]]:
    """Return (ICP sample points, every-beam map hits) in robot frame."""
    angle = float(msg.angle_min)
    rmin = max(float(msg.range_min), MIN_RANGE_SHOW)
    rmax = min(float(msg.range_max), MAX_RANGE)
    locals_xy: list[list[float]] = []
    map_hits_local: list[tuple[float, float]] = []
    for i, r in enumerate(msg.ranges):
        dist = float(r)
        if math.isfinite(dist) and rmin <= dist <= rmax:
            if is_frame_rack_hit(angle, dist):
                angle += float(msg.angle_increment)
                continue
            lx = dist * math.cos(angle)
            ly = dist * math.sin(angle)
            if i % ICP_STRIDE == 0:
                locals_xy.append([lx, ly])
            if dist >= MIN_RANGE_MAP and (i % MAP_HIT_STRIDE == 0):
                map_hits_local.append((lx, ly))
        angle += float(msg.angle_increment)
    if len(locals_xy) > ICP_MAX_POINTS:
        step = max(1, len(locals_xy) // ICP_MAX_POINTS)
        locals_xy = locals_xy[::step][:ICP_MAX_POINTS]
    return np.asarray(locals_xy, dtype=np.float64), map_hits_local


def hits_to_world(
    map_hits_local: list[tuple[float, float]],
    x: float,
    y: float,
    yaw: float,
) -> tuple[list[tuple[float, float]], list[dict[str, float]]]:
    c, s = math.cos(yaw), math.sin(yaw)
    hits: list[tuple[float, float]] = []
    points: list[dict[str, float]] = []
    for hlx, hly in map_hits_local:
        wx = x + c * hlx - s * hly
        wy = y + s * hlx + c * hly
        hits.append((wx, wy))
        points.append({"x": wx, "y": wy, "r": math.hypot(hlx, hly)})
    return hits, points
