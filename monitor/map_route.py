#!/usr/bin/env python3
"""Build a clean visitor map preview with points A/B and an A* route."""

from __future__ import annotations

import heapq
import json
import random
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REMEMBERED_MAP_CANDIDATES = (
    ROOT / "data" / "remembered_occupancy.json",
    Path.home() / "robot_nav" / "maps" / "remembered_occupancy.json",
)
DEMO_MAP = ROOT / "data" / "demo_floor.json"

# Display / planning grid size for the visitor map
GRID_W = 160
GRID_H = 100
OCC_SOLID = 1.0
# Kiosk orientation fix: remembered map was displayed upside down.
ROTATE_180 = True


def _orient_display(x: int, y: int, w: int, h: int) -> tuple[int, int]:
    if not ROTATE_180:
        return x, y
    return (w - 1 - x), (h - 1 - y)


def _empty(w: int, h: int) -> list[list[bool]]:
    return [[False] * w for _ in range(h)]


def _fill_rect(walls: list[list[bool]], x0: int, y0: int, x1: int, y1: int) -> None:
    h = len(walls)
    w = len(walls[0]) if h else 0
    for y in range(max(0, y0), min(h, y1 + 1)):
        row = walls[y]
        for x in range(max(0, x0), min(w, x1 + 1)):
            row[x] = True


def _clear_rect(walls: list[list[bool]], x0: int, y0: int, x1: int, y1: int) -> None:
    h = len(walls)
    w = len(walls[0]) if h else 0
    for y in range(max(0, y0), min(h, y1 + 1)):
        row = walls[y]
        for x in range(max(0, x0), min(w, x1 + 1)):
            row[x] = False


def build_demo_floor() -> list[list[bool]]:
    """Airport-like hall: outer walls, corridors, desks — clean binary walls."""
    w, h = GRID_W, GRID_H
    walls = _empty(w, h)

    # Outer shell
    _fill_rect(walls, 0, 0, w - 1, 2)
    _fill_rect(walls, 0, h - 3, w - 1, h - 1)
    _fill_rect(walls, 0, 0, 2, h - 1)
    _fill_rect(walls, w - 3, 0, w - 1, h - 1)

    # Horizontal partitions with corridor openings
    for y in (28, 55, 78):
        _fill_rect(walls, 3, y, w - 4, y + 1)
        for gap_x in (22, 70, 118):
            _clear_rect(walls, gap_x, y - 1, gap_x + 14, y + 2)

    # Vertical partitions
    for x in (48, 96):
        _fill_rect(walls, x, 3, x + 1, h - 4)
        for gap_y in (12, 40, 66):
            _clear_rect(walls, x - 1, gap_y, x + 2, gap_y + 10)

    # Check-in desk blocks (solid furniture islands)
    for x0 in (12, 58, 104):
        _fill_rect(walls, x0, 8, x0 + 18, 16)

    # Pillars
    for x, y in ((34, 42), (82, 42), (130, 42), (34, 68), (82, 68), (130, 68)):
        _fill_rect(walls, x, y, x + 3, y + 3)

    return walls


def save_demo_floor(path: Path = DEMO_MAP) -> None:
    walls = build_demo_floor()
    cells = [[x, y] for y, row in enumerate(walls) for x, solid in enumerate(row) if solid]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"w": GRID_W, "h": GRID_H, "walls": cells, "format": "demo_floor_v1"}, separators=(",", ":")),
        encoding="utf-8",
    )


def load_demo_floor(path: Path = DEMO_MAP) -> list[list[bool]] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        w = int(data["w"])
        h = int(data["h"])
        walls = _empty(w, h)
        for item in data.get("walls") or []:
            x, y = int(item[0]), int(item[1])
            if 0 <= x < w and 0 <= y < h:
                walls[y][x] = True
        return walls
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def load_remembered_as_display_grid(path: Path | None = None) -> list[list[bool]] | None:
    """Load sparse occupancy and downsample into a clean visitor grid."""
    candidates = (path,) if path is not None else REMEMBERED_MAP_CANDIDATES
    data = None
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
            break
        except (json.JSONDecodeError, OSError):
            continue
    if data is None:
        return None

    src_w = int(data.get("w") or 0)
    src_h = int(data.get("h") or 0)
    if src_w < 8 or src_h < 8:
        return None

    solid = set()
    sparse = data.get("sparse")
    if isinstance(sparse, list):
        for item in sparse:
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            idx, lo = int(item[0]), float(item[1])
            if lo >= OCC_SOLID:
                solid.add((idx % src_w, idx // src_w))
    elif isinstance(data.get("logodds"), list):
        for idx, lo in enumerate(data["logodds"]):
            if float(lo) >= OCC_SOLID:
                solid.add((idx % src_w, idx // src_w))
    if not solid:
        return None

    # Crop to occupied bbox with padding, then scale into display grid.
    # Keep aspect ratio (no axis stretch), otherwise kiosk map shape diverges
    # from operator lidar map.
    xs = [p[0] for p in solid]
    ys = [p[1] for p in solid]
    pad = 8
    min_x, max_x = max(0, min(xs) - pad), min(src_w - 1, max(xs) + pad)
    min_y, max_y = max(0, min(ys) - pad), min(src_h - 1, max(ys) + pad)
    bw = max(1, max_x - min_x + 1)
    bh = max(1, max_y - min_y + 1)

    out_w, out_h = GRID_W, GRID_H
    walls = _empty(out_w, out_h)
    src_w_span = max(1, bw - 1)
    src_h_span = max(1, bh - 1)
    scale = min((out_w - 1) / src_w_span, (out_h - 1) / src_h_span)
    used_w = src_w_span * scale
    used_h = src_h_span * scale
    x_off = (out_w - 1 - used_w) * 0.5
    y_off = (out_h - 1 - used_h) * 0.5
    for sx, sy in solid:
        dx = int(round((sx - min_x) * scale + x_off))
        dy = int(round((sy - min_y) * scale + y_off))
        if 0 <= dx < out_w and 0 <= dy < out_h:
            ox, oy = _orient_display(dx, dy, out_w, out_h)
            walls[oy][ox] = True

    return _clean_walls(walls)


def load_remembered_with_meta(path: Path | None = None) -> tuple[list[list[bool]], dict[str, float]] | None:
    """Return remembered map projected to display grid + projection metadata."""
    candidates = (path,) if path is not None else REMEMBERED_MAP_CANDIDATES
    data = None
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
            break
        except (json.JSONDecodeError, OSError):
            continue
    if data is None:
        return None

    src_w = int(data.get("w") or 0)
    src_h = int(data.get("h") or 0)
    if src_w < 8 or src_h < 8:
        return None
    res = float(data.get("res") or 0.05)
    origin_x = float(data.get("origin_x") or 0.0)
    origin_y = float(data.get("origin_y") or 0.0)

    solid = set()
    sparse = data.get("sparse")
    if isinstance(sparse, list):
        for item in sparse:
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            idx, lo = int(item[0]), float(item[1])
            if lo >= OCC_SOLID:
                solid.add((idx % src_w, idx // src_w))
    elif isinstance(data.get("logodds"), list):
        for idx, lo in enumerate(data["logodds"]):
            if float(lo) >= OCC_SOLID:
                solid.add((idx % src_w, idx // src_w))
    if not solid:
        return None

    xs = [p[0] for p in solid]
    ys = [p[1] for p in solid]
    pad = 8
    min_x, max_x = max(0, min(xs) - pad), min(src_w - 1, max(xs) + pad)
    min_y, max_y = max(0, min(ys) - pad), min(src_h - 1, max(ys) + pad)
    bw = max(1, max_x - min_x + 1)
    bh = max(1, max_y - min_y + 1)

    out_w, out_h = GRID_W, GRID_H
    walls = _empty(out_w, out_h)
    src_w_span = max(1, bw - 1)
    src_h_span = max(1, bh - 1)
    scale = min((out_w - 1) / src_w_span, (out_h - 1) / src_h_span)
    used_w = src_w_span * scale
    used_h = src_h_span * scale
    x_off = (out_w - 1 - used_w) * 0.5
    y_off = (out_h - 1 - used_h) * 0.5
    for sx, sy in solid:
        dx = int(round((sx - min_x) * scale + x_off))
        dy = int(round((sy - min_y) * scale + y_off))
        if 0 <= dx < out_w and 0 <= dy < out_h:
            ox, oy = _orient_display(dx, dy, out_w, out_h)
            walls[oy][ox] = True

    meta = {
        "min_x": float(min_x),
        "min_y": float(min_y),
        "scale": float(scale),
        "x_off": float(x_off),
        "y_off": float(y_off),
        "origin_x": origin_x,
        "origin_y": origin_y,
        "res": res,
        "src_w": float(src_w),
        "src_h": float(src_h),
    }
    return _clean_walls(walls), meta


def _project_solid_to_display(
    solid: set[tuple[int, int]],
    src_w: int,
    src_h: int,
    *,
    origin_x: float,
    origin_y: float,
    res: float,
    pad: int = 8,
) -> tuple[list[list[bool]], dict[str, float]] | None:
    if src_w < 8 or src_h < 8 or not solid:
        return None
    xs = [p[0] for p in solid]
    ys = [p[1] for p in solid]
    min_x, max_x = max(0, min(xs) - pad), min(src_w - 1, max(xs) + pad)
    min_y, max_y = max(0, min(ys) - pad), min(src_h - 1, max(ys) + pad)
    bw = max(1, max_x - min_x + 1)
    bh = max(1, max_y - min_y + 1)

    out_w, out_h = GRID_W, GRID_H
    walls = _empty(out_w, out_h)
    src_w_span = max(1, bw - 1)
    src_h_span = max(1, bh - 1)
    scale = min((out_w - 1) / src_w_span, (out_h - 1) / src_h_span)
    used_w = src_w_span * scale
    used_h = src_h_span * scale
    x_off = (out_w - 1 - used_w) * 0.5
    y_off = (out_h - 1 - used_h) * 0.5
    for sx, sy in solid:
        dx = int(round((sx - min_x) * scale + x_off))
        dy = int(round((sy - min_y) * scale + y_off))
        if 0 <= dx < out_w and 0 <= dy < out_h:
            ox, oy = _orient_display(dx, dy, out_w, out_h)
            walls[oy][ox] = True
    meta = {
        "min_x": float(min_x),
        "min_y": float(min_y),
        "scale": float(scale),
        "x_off": float(x_off),
        "y_off": float(y_off),
        "origin_x": origin_x,
        "origin_y": origin_y,
        "res": res,
        "src_w": float(src_w),
        "src_h": float(src_h),
    }
    return _clean_walls(walls), meta


def build_live_map_with_meta(live_map: dict[str, Any] | None) -> tuple[list[list[bool]], dict[str, float]] | None:
    if not isinstance(live_map, dict):
        return None
    try:
        src_w = int(live_map.get("w") or live_map.get("width") or 0)
        src_h = int(live_map.get("h") or live_map.get("height") or 0)
        res = float(live_map.get("resolution") or 0.05)
        origin = live_map.get("origin") or [0.0, 0.0]
        origin_x = float(origin[0])
        origin_y = float(origin[1])
    except (TypeError, ValueError, IndexError):
        return None
    cells = live_map.get("cells")
    if not isinstance(cells, list):
        return None
    solid: set[tuple[int, int]] = set()
    for item in cells:
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            continue
        try:
            ix = int(item[0])
            iy = int(item[1])
            val = int(item[2])
        except (TypeError, ValueError):
            continue
        if 0 <= ix < src_w and 0 <= iy < src_h and val >= 90:
            solid.add((ix, iy))
    if not solid:
        return None
    # For live lidar map keep projection frame fixed to full map extents.
    # This prevents A/B jitter caused by changing occupied bounding boxes.
    out_w, out_h = GRID_W, GRID_H
    walls = _empty(out_w, out_h)
    src_w_span = max(1, src_w - 1)
    src_h_span = max(1, src_h - 1)
    scale = min((out_w - 1) / src_w_span, (out_h - 1) / src_h_span)
    used_w = src_w_span * scale
    used_h = src_h_span * scale
    x_off = (out_w - 1 - used_w) * 0.5
    y_off = (out_h - 1 - used_h) * 0.5
    for sx, sy in solid:
        dx = int(round(sx * scale + x_off))
        dy = int(round(sy * scale + y_off))
        if 0 <= dx < out_w and 0 <= dy < out_h:
            ox, oy = _orient_display(dx, dy, out_w, out_h)
            walls[oy][ox] = True
    meta = {
        "min_x": 0.0,
        "min_y": 0.0,
        "scale": float(scale),
        "x_off": float(x_off),
        "y_off": float(y_off),
        "origin_x": origin_x,
        "origin_y": origin_y,
        "res": res,
        "src_w": float(src_w),
        "src_h": float(src_h),
    }
    return _clean_walls(walls), meta


def _clean_walls(walls: list[list[bool]]) -> list[list[bool]]:
    """Light morphological close: fill tiny holes so walls look solid."""
    h = len(walls)
    w = len(walls[0]) if h else 0
    out = [row[:] for row in walls]
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if out[y][x]:
                continue
            neigh = 0
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    if walls[y + dy][x + dx]:
                        neigh += 1
            if neigh >= 5:
                out[y][x] = True
    return out


def inflate(walls: list[list[bool]], radius: int = 1) -> set[tuple[int, int]]:
    h = len(walls)
    w = len(walls[0]) if h else 0
    blocked: set[tuple[int, int]] = set()
    r2 = radius * radius
    for y in range(h):
        for x in range(w):
            if not walls[y][x]:
                continue
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if dx * dx + dy * dy > r2:
                        continue
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h:
                        blocked.add((nx, ny))
    return blocked


def free_cells(blocked: set[tuple[int, int]], w: int, h: int) -> list[tuple[int, int]]:
    return [(x, y) for y in range(h) for x in range(w) if (x, y) not in blocked]


def pick_random_pair(
    free: list[tuple[int, int]],
    min_dist: float = 45.0,
    rng: random.Random | None = None,
) -> tuple[tuple[int, int], tuple[int, int]] | None:
    rng = rng or random.Random()
    if len(free) < 2:
        return None
    for _ in range(80):
        a = rng.choice(free)
        far = [p for p in free if abs(p[0] - a[0]) + abs(p[1] - a[1]) >= min_dist]
        if not far:
            continue
        b = rng.choice(far)
        return a, b
    a, b = rng.sample(free, 2)
    return a, b


def astar(
    blocked: set[tuple[int, int]],
    start: tuple[int, int],
    goal: tuple[int, int],
    w: int,
    h: int,
) -> list[tuple[int, int]] | None:
    if start == goal:
        return [start]

    def inb(p: tuple[int, int]) -> bool:
        return 0 <= p[0] < w and 0 <= p[1] < h

    def heur(a: tuple[int, int], b: tuple[int, int]) -> float:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    open_h: list[tuple[float, int, tuple[int, int]]] = []
    heapq.heappush(open_h, (heur(start, goal), 0, start))
    came: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    gscore = {start: 0.0}
    closed: set[tuple[int, int]] = set()
    dirs = (
        (1, 0), (-1, 0), (0, 1), (0, -1),
        (1, 1), (1, -1), (-1, 1), (-1, -1),
    )
    while open_h:
        _, _, cur = heapq.heappop(open_h)
        if cur in closed:
            continue
        if cur == goal:
            path = [cur]
            while came[cur] is not None:
                cur = came[cur]  # type: ignore[assignment]
                path.append(cur)
            path.reverse()
            return path
        closed.add(cur)
        for dx, dy in dirs:
            nxt = (cur[0] + dx, cur[1] + dy)
            if not inb(nxt) or nxt in blocked or nxt in closed:
                continue
            step = 1.414 if dx and dy else 1.0
            ng = gscore[cur] + step
            if ng < gscore.get(nxt, 1e18):
                gscore[nxt] = ng
                came[nxt] = cur
                heapq.heappush(open_h, (ng + heur(nxt, goal), id(nxt), nxt))
    return None


def sparsen_path(path: list[tuple[int, int]], step: int = 2) -> list[list[int]]:
    if not path:
        return []
    out = [list(path[0])]
    for point in path[1:]:
        if abs(point[0] - out[-1][0]) + abs(point[1] - out[-1][1]) >= step:
            out.append(list(point))
    if out[-1] != list(path[-1]):
        out.append(list(path[-1]))
    return out


def _line_clear(a: tuple[int, int], b: tuple[int, int], blocked: set[tuple[int, int]]) -> bool:
    """Bresenham line-of-sight check against blocked cells."""
    x0, y0 = a
    x1, y1 = b
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    x, y = x0, y0
    while True:
        if (x, y) in blocked:
            return False
        if x == x1 and y == y1:
            return True
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy


def simplify_path(path: list[tuple[int, int]], blocked: set[tuple[int, int]]) -> list[tuple[int, int]]:
    """Keep only turning points while preserving collision-free route."""
    if len(path) <= 2:
        return path
    out = [path[0]]
    i = 0
    while i < len(path) - 1:
        j = len(path) - 1
        while j > i + 1 and not _line_clear(path[i], path[j], blocked):
            j -= 1
        out.append(path[j])
        i = j
    return out


def get_display_walls(live_map: dict[str, Any] | None = None) -> tuple[list[list[bool]], str, dict[str, float] | None]:
    live = build_live_map_with_meta(live_map)
    if live is not None:
        walls, meta = live
        return walls, "live", meta
    remembered = load_remembered_with_meta()
    if remembered is not None:
        walls, meta = remembered
        return walls, "remembered", meta
    demo = load_demo_floor()
    if demo is None:
        demo = build_demo_floor()
        save_demo_floor()
    return demo, "demo", None


def _robot_to_display(
    robot_pose: dict[str, Any] | None,
    meta: dict[str, float] | None,
) -> tuple[int, int] | None:
    if not robot_pose or not meta:
        return None
    try:
        rx = float(robot_pose.get("x"))
        ry = float(robot_pose.get("y"))
    except (TypeError, ValueError):
        return None
    res = float(meta["res"])
    if res <= 0.0:
        return None
    sx = (rx - float(meta["origin_x"])) / res
    sy = (ry - float(meta["origin_y"])) / res
    dx = int(round((sx - float(meta["min_x"])) * float(meta["scale"]) + float(meta["x_off"])))
    dy = int(round((sy - float(meta["min_y"])) * float(meta["scale"]) + float(meta["y_off"])))
    if not (0 <= dx < GRID_W and 0 <= dy < GRID_H):
        return None
    return _orient_display(dx, dy, GRID_W, GRID_H)


def _goal_to_display(
    goal_xy: list[float] | tuple[float, float] | None,
    meta: dict[str, float] | None,
) -> tuple[int, int] | None:
    if not goal_xy or not meta or len(goal_xy) < 2:
        return None
    try:
        gx = float(goal_xy[0])
        gy = float(goal_xy[1])
    except (TypeError, ValueError):
        return None
    res = float(meta["res"])
    if res <= 0.0:
        return None
    sx = (gx - float(meta["origin_x"])) / res
    sy = (gy - float(meta["origin_y"])) / res
    dx = int(round((sx - float(meta["min_x"])) * float(meta["scale"]) + float(meta["x_off"])))
    dy = int(round((sy - float(meta["min_y"])) * float(meta["scale"]) + float(meta["y_off"])))
    if not (0 <= dx < GRID_W and 0 <= dy < GRID_H):
        return None
    return _orient_display(dx, dy, GRID_W, GRID_H)


def _inflate_radius_cells(source: str, meta: dict[str, float] | None, robot_radius_m: float) -> int:
    if source not in {"remembered", "live"} or not meta:
        return 1
    scale = float(meta.get("scale") or 1.0)
    res = float(meta.get("res") or 0.05)
    meter_per_cell = res / max(scale, 1e-6)
    radius_cells = int(round(robot_radius_m / max(meter_per_cell, 1e-4)))
    return max(1, min(radius_cells, 14))


def _nearest_free(
    start: tuple[int, int] | None,
    blocked: set[tuple[int, int]],
    w: int,
    h: int,
    max_radius: int = 24,
) -> tuple[int, int] | None:
    if start is None:
        return None
    sx, sy = start
    if 0 <= sx < w and 0 <= sy < h and (sx, sy) not in blocked:
        return sx, sy
    for r in range(1, max_radius + 1):
        for dy in range(-r, r + 1):
            for dx in (-r, r):
                x, y = sx + dx, sy + dy
                if 0 <= x < w and 0 <= y < h and (x, y) not in blocked:
                    return x, y
        for dx in range(-r + 1, r):
            for dy in (-r, r):
                x, y = sx + dx, sy + dy
                if 0 <= x < w and 0 <= y < h and (x, y) not in blocked:
                    return x, y
    return None


def build_route_preview(
    seed: int | None = None,
    robot_pose: dict[str, Any] | None = None,
    goal_xy: list[float] | tuple[float, float] | None = None,
    robot_radius_m: float = 0.48,
    live_map: dict[str, Any] | None = None,
) -> dict[str, Any]:
    walls, source, meta = get_display_walls(live_map=live_map)
    h = len(walls)
    w = len(walls[0]) if h else 0
    blocked = inflate(walls, radius=_inflate_radius_cells(source, meta, robot_radius_m))
    free = free_cells(blocked, w, h)
    rng = random.Random(seed)
    robot_anchor = _nearest_free(_robot_to_display(robot_pose, meta), blocked, w, h)
    goal_anchor = _nearest_free(_goal_to_display(goal_xy, meta), blocked, w, h)
    pair = None
    if robot_anchor is not None and goal_anchor is not None and robot_anchor != goal_anchor:
        pair = (robot_anchor, goal_anchor)
    elif robot_anchor is not None and free:
        far = [p for p in free if abs(p[0] - robot_anchor[0]) + abs(p[1] - robot_anchor[1]) >= 30]
        if far:
            pair = (robot_anchor, rng.choice(far))
    if pair is None:
        pair = pick_random_pair(free, min_dist=40.0, rng=rng)
    if pair is None:
        return {"ok": False, "error": "no_free_space"}
    point_a, point_b = pair
    path = astar(blocked, point_a, point_b, w, h)
    if not path:
        # retry a few times with new points
        for _ in range(12):
            pair = pick_random_pair(free, min_dist=30.0, rng=rng)
            if not pair:
                break
            point_a, point_b = pair
            path = astar(blocked, point_a, point_b, w, h)
            if path:
                break
    if not path:
        return {"ok": False, "error": "path_not_found", "source": source}

    wall_cells = [[x, y] for y in range(h) for x in range(w) if walls[y][x]]
    smooth_path = simplify_path(path, blocked)
    return {
        "ok": True,
        "source": source,
        "width": w,
        "height": h,
        "walls": wall_cells,
        "pointA": {"x": point_a[0], "y": point_a[1], "label": "A"},
        "pointB": {"x": point_b[0], "y": point_b[1], "label": "B"},
        "path": sparsen_path(smooth_path, step=2),
        "pathLength": len(path),
        "inflationRadiusCells": _inflate_radius_cells(source, meta, robot_radius_m),
    }


if __name__ == "__main__":
    save_demo_floor()
    preview = build_route_preview(seed=7)
    print(json.dumps({k: preview[k] for k in preview if k != "walls"}, ensure_ascii=False, indent=2))
    print("walls", len(preview.get("walls") or []), "path", preview.get("pathLength"))
