"""Deep system / map analysis for operator console."""

from __future__ import annotations

import math
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from config import LOG_PATH, MAP_PATH, MAP_RES, MAP_SIZE_M, OCC_SOLID


def _run(cmd: list[str], timeout: float = 2.0) -> str:
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=timeout)
        return out.decode("utf-8", "ignore").strip()
    except Exception as exc:  # noqa: BLE001
        return f"ошибка: {exc}"


def system_health() -> dict[str, Any]:
    """Local Pi health: processes, serial devices, disk logs."""
    listing = _run(["bash", "-lc", "pgrep -af 'lidar_map/main.py|drive_encoders|cspc_lidar' || true"])
    procs = {
        "main": "lidar_map/main.py" in listing,
        "drive_encoders": "drive_encoders" in listing,
        "lidar": "cspc_lidar" in listing,
    }
    devices = {
        "ttyUSB0": Path("/dev/ttyUSB0").exists(),
        "ttyUSB1": Path("/dev/ttyUSB1").exists(),
        "ttyLIDAR": Path("/dev/ttyLIDAR").exists(),
        "ttyMEGA": Path("/dev/ttyMEGA").exists(),
        "ttyLIDAR_target": os.path.realpath("/dev/ttyLIDAR") if Path("/dev/ttyLIDAR").exists() else None,
        "ttyMEGA_target": os.path.realpath("/dev/ttyMEGA") if Path("/dev/ttyMEGA").exists() else None,
    }
    holders = _run(["bash", "-lc", "fuser -v /dev/ttyUSB0 /dev/ttyUSB1 2>&1 || true"])
    log_size = LOG_PATH.stat().st_size if LOG_PATH.is_file() else 0
    map_size = MAP_PATH.stat().st_size if MAP_PATH.is_file() else 0
    map_mtime = MAP_PATH.stat().st_mtime if MAP_PATH.is_file() else 0
    return {
        "ok": True,
        "ts": time.time(),
        "processes": procs,
        "process_listing": listing.splitlines()[-8:],
        "devices": devices,
        "port_holders": holders.splitlines()[-12:],
        "logs": {"path": str(LOG_PATH), "bytes": log_size},
        "map_file": {
            "path": str(MAP_PATH),
            "bytes": map_size,
            "age_sec": (time.time() - map_mtime) if map_mtime else None,
        },
        "hints": _health_hints(procs, devices),
    }


def _health_hints(procs: dict[str, bool], devices: dict[str, Any]) -> list[str]:
    hints: list[str] = []
    if not procs.get("main"):
        hints.append("main.py не запущен — веб/API недоступны")
    if not procs.get("drive_encoders"):
        hints.append("drive_encoders не запущен — моторы не слушаются")
    if not procs.get("lidar"):
        hints.append("cspc_lidar не запущен — нет данных скана лидара")
    if not devices.get("ttyMEGA"):
        hints.append("нет /dev/ttyMEGA — проверь USB Mega (обычно ttyUSB1)")
    if not devices.get("ttyLIDAR"):
        hints.append("нет /dev/ttyLIDAR — проверь USB лидара (обычно ttyUSB0)")
    mega = devices.get("ttyMEGA_target")
    lidar = devices.get("ttyLIDAR_target")
    if mega and lidar and mega == lidar:
        hints.append("ttyMEGA и ttyLIDAR указывают на один порт — udev/перепутаны кабели")
    if not hints:
        hints.append("критичных проблем не видно")
    return hints


def analyze_snapshot(snap: dict[str, Any]) -> dict[str, Any]:
    """Deep map + navigation analysis from /api/scan snapshot."""
    pose = snap.get("pose") or {}
    m = snap.get("map") if isinstance(snap.get("map"), dict) else {}
    cells = m.get("cells") or []
    origin = m.get("origin") or [0.0, 0.0]
    res = float(m.get("resolution") or MAP_RES)
    w = int(m.get("width") or (MAP_SIZE_M / res))
    h = int(m.get("height") or (MAP_SIZE_M / res))
    ox, oy = float(origin[0]), float(origin[1])

    solid = 0
    weak = 0
    xs: list[float] = []
    ys: list[float] = []
    for cell in cells:
        if len(cell) < 3:
            continue
        val = float(cell[2])
        if val >= OCC_SOLID:
            solid += 1
            wx = ox + (int(cell[0]) + 0.5) * res
            wy = oy + (int(cell[1]) + 0.5) * res
            xs.append(wx)
            ys.append(wy)
        elif val > 0.2:
            weak += 1

    total = max(1, w * h)
    coverage = 100.0 * solid / total
    bbox = None
    span = None
    if xs and ys:
        bbox = {
            "xmin": min(xs),
            "xmax": max(xs),
            "ymin": min(ys),
            "ymax": max(ys),
        }
        span = {
            "x_m": bbox["xmax"] - bbox["xmin"],
            "y_m": bbox["ymax"] - bbox["ymin"],
            "area_m2": max(0.0, (bbox["xmax"] - bbox["xmin"]) * (bbox["ymax"] - bbox["ymin"])),
        }

    px = float(pose.get("x", 0.0))
    py = float(pose.get("y", 0.0))
    # nearest solid wall distance (coarse)
    nearest = None
    if xs:
        nearest = min(math.hypot(x - px, y - py) for x, y in zip(xs, ys))

    path = snap.get("path") or []
    path_len_m = 0.0
    for i in range(1, len(path)):
        try:
            path_len_m += math.hypot(
                float(path[i][0]) - float(path[i - 1][0]),
                float(path[i][1]) - float(path[i - 1][1]),
            )
        except (TypeError, ValueError, IndexError):
            pass

    quality = _map_quality(solid, weak, coverage, nearest, snap)
    return {
        "ok": True,
        "ts": time.time(),
        "pose": {
            "x": px,
            "y": py,
            "yaw": float(pose.get("yaw", 0.0)),
            "ok": bool(pose.get("ok")),
        },
        "sensors": {
            "scan_ok": bool(snap.get("ok")),
            "odom_ok": bool(snap.get("odom_ok")),
            "mapping": bool(snap.get("mapping")),
            "score": float(snap.get("score") or 0.0),
            "stale": bool(snap.get("stale")),
            "error": snap.get("error") or "",
        },
        "nav": {
            "status": snap.get("nav_status"),
            "goal": snap.get("goal"),
            "path_points": len(path),
            "path_length_m": round(path_len_m, 3),
            "frozen": bool(snap.get("frozen")),
            "mission": snap.get("mission") or {},
        },
        "map": {
            "resolution_m": res,
            "size_cells": [w, h],
            "size_m": [w * res, h * res],
            "origin": [ox, oy],
            "solid_cells": solid,
            "weak_cells": weak,
            "reported_hits": m.get("hits"),
            "coverage_pct": round(coverage, 4),
            "bbox": bbox,
            "span": span,
            "nearest_wall_m": round(nearest, 3) if nearest is not None else None,
            "temp_hits": snap.get("temp_hits"),
            "saved_ago_sec": snap.get("saved_ago"),
        },
        "quality": quality,
        "recommendations": _map_recommendations(quality, snap, solid, nearest),
    }


def _map_quality(
    solid: int,
    weak: int,
    coverage: float,
    nearest: float | None,
    snap: dict[str, Any],
) -> dict[str, Any]:
    score = 50
    notes: list[str] = []
    if solid < 80:
        score -= 25
        notes.append("мало стен — карта ещё пустая / мало проехали")
    elif solid < 400:
        score -= 10
        notes.append("карта частичная")
    else:
        score += 15
        notes.append("достаточно плотных клеток стен для навигации")
    if weak > solid * 2 and solid > 0:
        score -= 5
        notes.append("много слабых отметок — шум или динамика")
    if nearest is not None and nearest < 0.25:
        score -= 15
        notes.append("робот почти вплотную к стене (<0.25 м)")
    elif nearest is not None and nearest > 8:
        score -= 5
        notes.append("ближайшая стена далеко — возможно, карта не вокруг робота")
    if not snap.get("ok"):
        score -= 30
        notes.append("лидар не в порядке")
    if not snap.get("odom_ok"):
        score -= 10
        notes.append("одометрия устарела или отсутствует")
    if snap.get("frozen"):
        notes.append("карта заморожена (только временные препятствия)")
    score = max(0, min(100, score))
    grade = "A" if score >= 80 else "B" if score >= 60 else "C" if score >= 40 else "D"
    return {"score": score, "grade": grade, "notes": notes, "coverage_pct": coverage}


def _map_recommendations(
    quality: dict[str, Any],
    snap: dict[str, Any],
    solid: int,
    nearest: float | None,
) -> list[str]:
    rec: list[str] = []
    if solid < 150:
        rec.append("Проедь медленно по периметру зоны, чтобы набрать стены")
    if not snap.get("odom_ok"):
        rec.append("Проверь Mega, drive_encoders и порт /dev/ttyMEGA")
    if not snap.get("ok"):
        rec.append("Перезапусти драйвер лидара (cspc_lidar) на /dev/ttyLIDAR")
    if nearest is not None and nearest < 0.3:
        rec.append("Отойди от препятствия перед стартом миссии")
    if snap.get("frozen"):
        rec.append("Если нужно копить стены — сними заморозку карты")
    if quality.get("score", 0) >= 70:
        rec.append("Можно ставить несколько точек и запускать миссию")
    return rec or ["Система выглядит рабочей"]

