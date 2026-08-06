"""A→B navigation on the occupancy grid (mecanum pure-pursuit)."""

from __future__ import annotations

import math
from typing import Any

from config import (
    CMD_VX_MAX,
    NAV_CTE_GAIN,
    NAV_GOAL_TOL,
    NAV_ROBOT_R,
    NAV_V,
    NAV_VY_MAX,
    NAV_W_MAX,
    NAV_YAW_DEAD,
    NAV_YAW_KP,
    OCC_SOLID,
    TEMP_TTL_SEC,
)
from geometry import clamp, wrap_angle
from logutil import get_logger
from occupancy import OccupancyMap, astar

log = get_logger("nav")


def build_blocked(
    omap: OccupancyMap,
    temp: dict[int, float],
    now: float,
) -> set[tuple[int, int]]:
    temp_idx = [i for i, t in temp.items() if now - t <= TEMP_TTL_SEC]
    blocked: set[tuple[int, int]] = set()
    with omap.lock:
        solid = (omap.logodds > OCC_SOLID).nonzero()[0]
        for i in solid:
            iy = int(i // omap.w)
            ix = int(i % omap.w)
            for dy in range(-NAV_ROBOT_R, NAV_ROBOT_R + 1):
                for dx in range(-NAV_ROBOT_R, NAV_ROBOT_R + 1):
                    if dx * dx + dy * dy > NAV_ROBOT_R * NAV_ROBOT_R:
                        continue
                    blocked.add((ix + dx, iy + dy))
    for i in temp_idx:
        iy = i // omap.w
        ix = i % omap.w
        for dy in range(-NAV_ROBOT_R, NAV_ROBOT_R + 1):
            for dx in range(-NAV_ROBOT_R, NAV_ROBOT_R + 1):
                if dx * dx + dy * dy > NAV_ROBOT_R * NAV_ROBOT_R:
                    continue
                blocked.add((ix + dx, iy + dy))
    return blocked


def nearest_free(
    blocked: set[tuple[int, int]],
    ix: int,
    iy: int,
    w: int,
    h: int,
    max_rad: int = 28,
) -> tuple[int, int] | None:
    for rad in range(0, max_rad):
        for dy in range(-rad, rad + 1):
            for dx in range(-rad, rad + 1):
                if max(abs(dx), abs(dy)) != rad and rad > 0:
                    continue
                p = (ix + dx, iy + dy)
                if 0 <= p[0] < w and 0 <= p[1] < h and p not in blocked:
                    return p
    return None


def plan_path(
    omap: OccupancyMap,
    blocked: set[tuple[int, int]],
    start_xy: tuple[float, float],
    goal_xy: tuple[float, float],
) -> dict[str, Any]:
    x, y = start_xy
    gx, gy = goal_xy
    sx, sy = omap._world_to_cell(x, y)
    ex, ey = omap._world_to_cell(gx, gy)
    start = nearest_free(blocked, sx, sy, omap.w, omap.h)
    goal = nearest_free(blocked, ex, ey, omap.w, omap.h)
    if start is None or goal is None:
        return {"ok": False, "error": "старт/цель в препятствии"}
    path_cells = astar(blocked, start, goal, omap.w, omap.h)
    if not path_cells:
        return {"ok": False, "error": "путь не найден — попробуй другую точку B"}
    world_path = [omap.cell_to_world(ix, iy) for ix, iy in path_cells]
    sparse: list[tuple[float, float]] = [(x, y)]
    for p in world_path:
        if math.hypot(p[0] - sparse[-1][0], p[1] - sparse[-1][1]) >= 0.22:
            sparse.append(p)
    if math.hypot(sparse[-1][0] - gx, sparse[-1][1] - gy) > 0.05:
        sparse.append((float(gx), float(gy)))
    log.info(
        "goal A→B (%.2f,%.2f)→(%.2f,%.2f) path_len=%s",
        x, y, gx, gy, len(sparse),
    )
    return {
        "ok": True,
        "path": sparse,
        "path_len": len(sparse),
        "goal": [gx, gy],
        "start": [x, y],
    }


def pursuit_cmd(
    path: list[tuple[float, float]],
    goal: tuple[float, float],
    i: int,
    x: float,
    y: float,
    yaw: float,
) -> tuple[float, float, float, int, bool]:
    """Return (vx, vy, w, new_i, arrived)."""
    if math.hypot(goal[0] - x, goal[1] - y) < NAV_GOAL_TOL:
        return 0.0, 0.0, 0.0, i, True
    if i >= len(path):
        return 0.0, 0.0, 0.0, i, False
    tx, ty = path[i]
    dist = math.hypot(tx - x, ty - y)
    if dist < 0.22 and i + 1 < len(path):
        i += 1
        tx, ty = path[i]
        dist = math.hypot(tx - x, ty - y)
    if dist < 1e-3:
        return 0.0, 0.0, 0.0, i, False
    look = path[min(i + 1, len(path) - 1)]
    lx, ly = look[0], look[1]
    speed = NAV_V
    if dist < 0.45:
        speed *= max(0.55, dist / 0.45)
    ux = (lx - x) / max(1e-3, math.hypot(lx - x, ly - y))
    uy = (ly - y) / max(1e-3, math.hypot(lx - x, ly - y))
    if i > 0:
        ax, ay = path[i - 1]
    else:
        ax, ay = x, y
    bx, by = tx, ty
    segx, segy = bx - ax, by - ay
    seglen = math.hypot(segx, segy)
    cte = ((x - ax) * segy - (y - ay) * segx) / seglen if seglen > 1e-3 else 0.0
    c, s = math.cos(yaw), math.sin(yaw)
    vx_w = speed * ux
    vy_w = speed * uy
    vx = clamp(c * vx_w + s * vy_w, -CMD_VX_MAX, CMD_VX_MAX)
    vy = clamp(-s * vx_w + c * vy_w, -NAV_VY_MAX, NAV_VY_MAX)
    if seglen > 1e-3:
        nx, ny = -segy / seglen, segx / seglen
        cte_vx_w = -NAV_CTE_GAIN * cte * nx
        cte_vy_w = -NAV_CTE_GAIN * cte * ny
        vy += clamp(-s * cte_vx_w + c * cte_vy_w, -0.18, 0.18)
        vy = clamp(vy, -NAV_VY_MAX, NAV_VY_MAX)
    want = math.atan2(uy, ux)
    err = wrap_angle(want - yaw)
    w = 0.0 if abs(err) < NAV_YAW_DEAD else clamp(NAV_YAW_KP * err, -NAV_W_MAX, NAV_W_MAX)
    if abs(err) > 1.2:
        vx *= 0.80
        vy *= 0.90
    return vx, vy, w, i, False
