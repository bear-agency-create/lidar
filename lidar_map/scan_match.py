"""Scan-to-scan / scan-to-map pose refinement (CSM + ICP)."""

from __future__ import annotations

import math
from typing import Callable

import numpy as np

from config import (
    CSM_XY_SPAN,
    CSM_XY_STEP,
    CSM_YAW_SPAN,
    CSM_YAW_STEP,
    ICP_ITERS,
    ICP_MAX_DIST,
    MIN_MATCHES_ICP,
)
from geometry import transform_local, wrap_angle


def icp_refine_pose(
    local: np.ndarray,
    ref_world: np.ndarray,
    x: float,
    y: float,
    yaw: float,
) -> tuple[float, float, float, int]:
    if local.shape[0] < 25 or ref_world.shape[0] < 25:
        return x, y, yaw, 0
    matches = 0
    for _ in range(ICP_ITERS):
        src = transform_local(local, x, y, yaw)
        d2 = np.sum((src[:, None, :] - ref_world[None, :, :]) ** 2, axis=2)
        idx = np.argmin(d2, axis=1)
        mind = d2[np.arange(len(src)), idx]
        mask = mind < (ICP_MAX_DIST * ICP_MAX_DIST)
        matches = int(mask.sum())
        if matches < 20:
            break
        a = src[mask]
        b = ref_world[idx[mask]]
        ca = a.mean(axis=0)
        cb = b.mean(axis=0)
        aa = a - ca
        bb = b - cb
        h = aa.T @ bb
        u, _, vt = np.linalg.svd(h)
        r = vt.T @ u.T
        if np.linalg.det(r) < 0:
            vt = vt.copy()
            vt[-1, :] *= -1.0
            r = vt.T @ u.T
        t = cb - r @ ca
        c, s = math.cos(yaw), math.sin(yaw)
        r_pose = np.array([[c, -s], [s, c]], dtype=np.float64)
        r_new = r @ r_pose
        yaw = math.atan2(r_new[1, 0], r_new[0, 0])
        xy = r @ np.array([x, y], dtype=np.float64) + t
        x, y = float(xy[0]), float(xy[1])
    return x, y, yaw, matches


def score_against_ref(world: np.ndarray, ref: np.ndarray) -> float:
    if world.shape[0] == 0 or ref.shape[0] == 0:
        return 0.0
    if ref.shape[0] > 220:
        ref = ref[:: max(1, ref.shape[0] // 220)]
    d2 = np.sum((world[:, None, :] - ref[None, :, :]) ** 2, axis=2)
    mind = np.min(d2, axis=1)
    good = mind < (0.35 * 0.35)
    if good.size == 0:
        return 0.0
    return float(np.mean(good))


def correlative_search(
    local: np.ndarray,
    ref: np.ndarray,
    x: float,
    y: float,
    yaw: float,
    score_fn: Callable[[np.ndarray], float] | None = None,
    yaw_span: float = CSM_YAW_SPAN,
    yaw_step: float = CSM_YAW_STEP,
    xy_span: float = CSM_XY_SPAN,
    xy_step: float = CSM_XY_STEP,
) -> tuple[float, float, float, float]:
    best_score = -1.0
    bx, by, byaw = x, y, yaw
    yaw_vals = np.arange(-yaw_span, yaw_span + 1e-9, yaw_step)
    xy_vals = np.arange(-xy_span, xy_span + 1e-9, xy_step)
    step = max(1, local.shape[0] // 50)
    coarse = local[::step]

    def eval_pose(px: float, py: float, pyaw: float) -> float:
        ww = transform_local(coarse, px, py, pyaw)
        if score_fn is not None:
            return float(score_fn(ww))
        return score_against_ref(ww, ref)

    for dyaw in yaw_vals:
        yy = wrap_angle(yaw + float(dyaw))
        for dx in xy_vals:
            for dy in xy_vals:
                sc = eval_pose(x + float(dx), y + float(dy), yy)
                if sc > best_score:
                    best_score = sc
                    bx, by, byaw = x + float(dx), y + float(dy), yy
    nx, ny, nyaw, matches = icp_refine_pose(local, ref, bx, by, byaw)
    world = transform_local(local, nx, ny, nyaw)
    if score_fn is not None:
        score = float(score_fn(world))
    else:
        score = score_against_ref(world, ref)
    if matches < MIN_MATCHES_ICP:
        score *= 0.5
    return nx, ny, nyaw, score
