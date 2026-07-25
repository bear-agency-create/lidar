"""Occupancy grid map (numpy-backed) + A* planner helpers."""

from __future__ import annotations

import heapq
import json
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np

from config import (
    HIT_BLOB,
    MAP_CELLS,
    MAP_RES,
    MAP_SIZE_M,
    OCC_DISPLAY,
    OCC_SOLID,
)
from logutil import get_logger

log = get_logger("occupancy")


class OccupancyMap:
    """Sparse-friendly occupancy grid using a contiguous float32 buffer."""

    def __init__(self) -> None:
        self.res = MAP_RES
        self.w = MAP_CELLS
        self.h = MAP_CELLS
        self.origin_x = -MAP_SIZE_M / 2.0
        self.origin_y = -MAP_SIZE_M / 2.0
        self.logodds = np.zeros(self.w * self.h, dtype=np.float32)
        self.lock = threading.Lock()
        self.dirty = False
        self.last_save = 0.0

    def clear(self) -> None:
        with self.lock:
            self.logodds.fill(0.0)
            self.dirty = True

    def recentre(self, x: float, y: float) -> None:
        with self.lock:
            self.origin_x = x - MAP_SIZE_M / 2.0
            self.origin_y = y - MAP_SIZE_M / 2.0
            self.logodds.fill(0.0)
            self.dirty = True

    def _idx(self, ix: int, iy: int) -> int | None:
        if 0 <= ix < self.w and 0 <= iy < self.h:
            return iy * self.w + ix
        return None

    def _world_to_cell(self, x: float, y: float) -> tuple[int, int]:
        ix = int((x - self.origin_x) / self.res)
        iy = int((y - self.origin_y) / self.res)
        return ix, iy

    def integrate(self, ox: float, oy: float, hits: list[tuple[float, float]]) -> None:
        with self.lock:
            sx, sy = self._world_to_cell(ox, oy)
            touched: list[tuple[int, int]] = []
            lo = self.logodds
            for hx, hy in hits:
                ex, ey = self._world_to_cell(hx, hy)
                for cx, cy in self._bresenham(sx, sy, ex, ey):
                    if cx == ex and cy == ey:
                        break
                    i = self._idx(cx, cy)
                    if i is None or lo[i] > 2.5:
                        continue
                    lo[i] = max(-5.0, lo[i] - 0.18)
                for dy in range(-HIT_BLOB, HIT_BLOB + 1):
                    for dx in range(-HIT_BLOB, HIT_BLOB + 1):
                        if abs(dx) + abs(dy) > HIT_BLOB:
                            continue
                        tx, ty = ex + dx, ey + dy
                        i = self._idx(tx, ty)
                        if i is None:
                            continue
                        boost = 1.15 if (dx == 0 and dy == 0) else 0.55
                        if lo[i] < 4.0:
                            lo[i] = min(6.0, lo[i] + boost)
                        touched.append((tx, ty))
            self.dirty = True
            if len(touched) >= 8:
                self._polish_edges_unlocked(touched)

    def _polish_edges_unlocked(self, seeds: list[tuple[int, int]]) -> None:
        seen: set[tuple[int, int]] = set()
        lo = self.logodds
        for sx, sy in seeds:
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    ix, iy = sx + dx, sy + dy
                    if (ix, iy) in seen:
                        continue
                    seen.add((ix, iy))
                    i = self._idx(ix, iy)
                    if i is None or lo[i] > OCC_DISPLAY:
                        continue
                    neigh = 0
                    for oy in range(-1, 2):
                        for ox in range(-1, 2):
                            if ox == 0 and oy == 0:
                                continue
                            j = self._idx(ix + ox, iy + oy)
                            if j is not None and lo[j] > OCC_SOLID:
                                neigh += 1
                    if neigh >= 5:
                        lo[i] = max(lo[i], 1.4)

    def occupied_xy(self, max_points: int = 450) -> np.ndarray:
        with self.lock:
            idx = np.flatnonzero(self.logodds > OCC_DISPLAY)
            if idx.size == 0:
                return np.zeros((0, 2), dtype=np.float64)
            if idx.size > max_points:
                step = max(1, idx.size // max_points)
                idx = idx[::step][:max_points]
            iy = idx // self.w
            ix = idx % self.w
            xs = self.origin_x + (ix + 0.5) * self.res
            ys = self.origin_y + (iy + 0.5) * self.res
            return np.column_stack((xs, ys)).astype(np.float64)

    def score_world_hits(self, world: np.ndarray) -> float:
        if world.shape[0] == 0:
            return 0.0
        good = 0
        total = 0
        with self.lock:
            ox, oy, res, w, h = self.origin_x, self.origin_y, self.res, self.w, self.h
            lo = self.logodds
            for wx, wy in world:
                ix = int((wx - ox) / res)
                iy = int((wy - oy) / res)
                if not (0 <= ix < w and 0 <= iy < h):
                    continue
                total += 1
                if lo[iy * w + ix] > OCC_DISPLAY:
                    good += 1
        if total == 0:
            return 0.0
        return float(good) / float(total)

    @staticmethod
    def _bresenham(x0: int, y0: int, x1: int, y1: int):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        x, y = x0, y0
        while True:
            yield x, y
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy

    def to_dict(self, temp_cells: list[list[int]] | None = None) -> dict[str, Any]:
        with self.lock:
            solid = np.flatnonzero(self.logodds > OCC_SOLID)
            weak = np.flatnonzero(
                (self.logodds > OCC_DISPLAY) & (self.logodds <= OCC_SOLID)
            )
            free = np.flatnonzero(self.logodds < -0.7)
            cells: list[list[int]] = []
            for i in solid:
                cells.append([int(i % self.w), int(i // self.w), 100])
            for i in weak:
                cells.append([int(i % self.w), int(i // self.w), 90])
            for i in free:
                cells.append([int(i % self.w), int(i // self.w), 0])
            occupied = int(solid.size + weak.size)
            if temp_cells:
                cells.extend(temp_cells)
            return {
                "width": self.w,
                "height": self.h,
                "resolution": self.res,
                "origin": [self.origin_x, self.origin_y],
                "cells": cells,
                "hits": occupied,
            }

    def is_static_occupied(self, ix: int, iy: int, margin: int = 1) -> bool:
        with self.lock:
            for dy in range(-margin, margin + 1):
                for dx in range(-margin, margin + 1):
                    i = self._idx(ix + dx, iy + dy)
                    if i is not None and self.logodds[i] > OCC_DISPLAY:
                        return True
        return False

    def cell_to_world(self, ix: int, iy: int) -> tuple[float, float]:
        return (
            self.origin_x + (ix + 0.5) * self.res,
            self.origin_y + (iy + 0.5) * self.res,
        )

    def hit_count(self) -> int:
        with self.lock:
            return int(np.count_nonzero(self.logodds > OCC_DISPLAY))

    def save(self, path: Path) -> dict[str, Any]:
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock:
            idx = np.flatnonzero(np.abs(self.logodds) >= 0.35)
            sparse = [[int(i), round(float(self.logodds[i]), 3)] for i in idx]
            payload = {
                "res": self.res,
                "w": self.w,
                "h": self.h,
                "origin_x": self.origin_x,
                "origin_y": self.origin_y,
                "sparse": sparse,
                "saved_at": time.time(),
                "format": "sparse_v1",
            }
            hits = int(np.count_nonzero(self.logodds > OCC_SOLID))
            dirty = self.dirty
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(path)
        with self.lock:
            self.dirty = False
            self.last_save = time.time()
        log.info("map saved hits=%s sparse=%s → %s", hits, len(sparse), path)
        return {"ok": True, "path": str(path), "hits": hits, "was_dirty": dirty}

    def load(self, path: Path) -> bool:
        if not path.is_file():
            return False
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("map load failed: %s", exc)
            return False
        if (
            int(payload.get("w", 0)) != self.w
            or int(payload.get("h", 0)) != self.h
            or abs(float(payload.get("res", 0)) - self.res) > 1e-6
        ):
            log.warning(
                "map grid mismatch (need res=%.3f %dx%d) — empty map",
                self.res,
                self.w,
                self.h,
            )
            return False
        with self.lock:
            self.origin_x = float(payload.get("origin_x", self.origin_x))
            self.origin_y = float(payload.get("origin_y", self.origin_y))
            self.logodds.fill(0.0)
            sparse = payload.get("sparse")
            odds = payload.get("logodds")
            if isinstance(sparse, list):
                for item in sparse:
                    if not isinstance(item, (list, tuple)) or len(item) < 2:
                        continue
                    i = int(item[0])
                    if 0 <= i < self.logodds.size:
                        self.logodds[i] = float(item[1])
            elif isinstance(odds, list) and len(odds) == self.logodds.size:
                self.logodds = np.asarray(odds, dtype=np.float32)
            else:
                return False
            self.dirty = False
            self.last_save = float(payload.get("saved_at", time.time()))
        log.info("map loaded from %s hits=%s", path, self.hit_count())
        return True


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
