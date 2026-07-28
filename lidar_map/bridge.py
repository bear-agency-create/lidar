"""ROS bridge: LiDAR + odom → map / pose / teleop / A→B."""

from __future__ import annotations

import math
import threading
import time
from typing import Any

import numpy as np
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import LaserScan

from config import (
    AUTOSAVE_SEC,
    CSM_REFINE_XY_SPAN,
    CSM_REFINE_XY_STEP,
    CSM_REFINE_YAW_SPAN,
    CSM_REFINE_YAW_STEP,
    LOG_PATH,
    MAP_PATH,
    MAP_RES,
    NAV_ROBOT_R,
    ODOM_QOS,
    ODOM_STALE_SEC,
    ROBOT_LENGTH_M,
    ROBOT_RADIUS_M,
    ROBOT_WIDTH_M,
    SCAN_QOS,
    TEMP_CELL_VAL,
    TEMP_INFLATE,
    TEMP_TTL_SEC,
)
from drive import DriveCommander
from geometry import clamp, transform_local, wrap_angle, yaw_from_quat
from lidar import hits_to_world, local_from_scan
from logutil import get_logger
from nav import build_blocked, plan_path, pursuit_cmd
from occupancy import OccupancyMap
from scan_match import correlative_search

log = get_logger("bridge")


class ScanBridge(Node):
    def __init__(self) -> None:
        super().__init__("lidar_map_bridge")
        self._lock = threading.Lock()
        self._points: list[dict[str, float]] = []
        self._stamp = 0.0
        self._ok = False
        self._error = "ожидание /scan"
        self._pose = {"x": 0.0, "y": 0.0, "yaw": 0.0, "ok": False}
        self._odom = {"x": 0.0, "y": 0.0, "yaw": 0.0}
        self._odom_stamp = 0.0
        self._odom_ok = False
        self._prev_world: np.ndarray | None = None
        self._last_score = 0.0
        self._mapping_ok = True
        self._map_frozen = False
        self._temp: dict[int, float] = {}
        self._nav_path: list[tuple[float, float]] = []
        self._nav_goal: tuple[float, float] | None = None
        self._selected_path: list[tuple[float, float]] = []
        self._selected_goal: tuple[float, float] | None = None
        self._nav_i = 0
        self._nav_status = "idle"
        self._last_scan_t = 0.0
        self._map_bootstrap_scans = 120
        self._scan_count = 0
        self.omap = OccupancyMap()

        self._cmd_pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.drive = DriveCommander(publish_twist=self._cmd_pub.publish)

        loaded = self.omap.load(MAP_PATH)
        if loaded:
            self.get_logger().info(f"Загружена память карты: {MAP_PATH}")
            log.info("boot: loaded map %s", MAP_PATH)
        else:
            self.get_logger().info("Новая карта (памяти на диске нет / другой grid)")
            log.info(
                "boot: empty map res=%.3f robot=%.2fx%.2f r=%.2f nav_r=%s log=%s",
                MAP_RES, ROBOT_LENGTH_M, ROBOT_WIDTH_M, ROBOT_RADIUS_M,
                NAV_ROBOT_R, LOG_PATH,
            )
        self.get_logger().info(
            f"DRIVE map: robot {ROBOT_LENGTH_M:.2f}x{ROBOT_WIDTH_M:.2f}m "
            f"r={ROBOT_RADIUS_M:.2f}m grid={MAP_RES}m"
        )
        self.create_subscription(LaserScan, "/scan", self._on_scan, SCAN_QOS)
        self.create_subscription(Odometry, "/odom", self._on_odom, ODOM_QOS)
        self.create_timer(AUTOSAVE_SEC, self._autosave)
        self.create_timer(0.05, self.drive.watchdog_tick)
        self.create_timer(0.10, self._nav_tick)

    def _autosave(self) -> None:
        with self.omap.lock:
            dirty = self.omap.dirty
        if dirty:
            info = self.omap.save(MAP_PATH)
            self.get_logger().info(
                f"Автосохранение: {info.get('hits')} стен → {MAP_PATH}"
            )
            log.info("autosave hits=%s", info.get("hits"))

    def set_cmd(self, vx: float, vy: float, w: float) -> dict[str, Any]:
        out = self.drive.set(vx, vy, w, from_teleop=True)
        if abs(vx) > 0.02 or abs(vy) > 0.02 or abs(w) > 0.05:
            with self._lock:
                if self._nav_goal is not None:
                    self._nav_status = "interrupted"
                self._nav_path = []
                self._nav_goal = None
                self._nav_i = 0
        return out

    def stop_cmd(self) -> dict[str, Any]:
        with self._lock:
            if self._nav_goal is not None:
                self._nav_status = "cancelled"
            self._nav_path = []
            self._nav_goal = None
            self._nav_i = 0
        return self.drive.stop()

    def _on_odom(self, msg: Odometry) -> None:
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        yaw = yaw_from_quat(q.x, q.y, q.z, q.w)
        with self._lock:
            self._odom = {"x": float(p.x), "y": float(p.y), "yaw": float(yaw)}
            self._odom_stamp = time.time()
            self._odom_ok = True

    def _odom_fresh(self) -> bool:
        with self._lock:
            if not self._odom_ok:
                return False
            return (time.time() - self._odom_stamp) <= ODOM_STALE_SEC

    def _on_scan(self, msg: LaserScan) -> None:
        local, map_hits_local = local_from_scan(msg)
        odom_ok = self._odom_fresh()
        with self._lock:
            if odom_ok:
                ox = float(self._odom["x"])
                oy = float(self._odom["y"])
                oyaw = float(self._odom["yaw"])
            else:
                ox = float(self._pose["x"])
                oy = float(self._pose["y"])
                oyaw = float(self._pose["yaw"])
            lx = float(self._pose["x"])
            ly = float(self._pose["y"])
            lyaw = float(self._pose["yaw"])
            pose_ok = bool(self._pose.get("ok"))
            cmd_vx, cmd_vy, cmd_w = self.drive.get()
            prev = None if self._prev_world is None else self._prev_world.copy()
            last_t = float(self._last_scan_t)

        now = time.time()
        dt = 0.1 if last_t <= 0 else clamp(now - last_t, 0.02, 0.35)
        c0, s0 = math.cos(lyaw), math.sin(lyaw)
        pred_x = lx + (c0 * cmd_vx - s0 * cmd_vy) * dt
        pred_y = ly + (s0 * cmd_vx + c0 * cmd_vy) * dt
        pred_yaw = wrap_angle(lyaw + cmd_w * dt)
        if pose_ok:
            x, y, yaw = pred_x, pred_y, pred_yaw
        elif odom_ok:
            x, y, yaw = ox, oy, oyaw
        else:
            x, y, yaw = lx, ly, lyaw

        score = 0.0
        mapping_ok = False
        map_pts = self.omap.occupied_xy()
        with self._lock:
            bootstrap = self._map_bootstrap_scans > 0
            if bootstrap:
                self._map_bootstrap_scans -= 1
        young = bootstrap or map_pts.shape[0] < 120

        if local.shape[0] >= 25:
            ref_parts: list[np.ndarray] = []
            if map_pts.shape[0] >= 40:
                ref_parts.append(map_pts)
            if prev is not None and prev.shape[0] >= 25:
                ref_parts.append(prev)
            if ref_parts:
                ref = np.vstack(ref_parts)
                score_fn = (
                    self.omap.score_world_hits if map_pts.shape[0] >= 40 else None
                )
                if map_pts.shape[0] >= 40 and not young:
                    nx, ny, nyaw, score = correlative_search(
                        local, ref, x, y, yaw, score_fn=score_fn,
                        yaw_span=math.radians(40.0), yaw_step=math.radians(3.0),
                        xy_span=0.40, xy_step=0.10,
                    )
                    if score >= 0.16:
                        x, y, yaw = nx, ny, nyaw
                        mapping_ok = True
                else:
                    nx, ny, nyaw, score = correlative_search(
                        local, ref, x, y, yaw, score_fn=score_fn,
                        yaw_span=CSM_REFINE_YAW_SPAN, yaw_step=CSM_REFINE_YAW_STEP,
                        xy_span=CSM_REFINE_XY_SPAN, xy_step=CSM_REFINE_XY_STEP,
                    )
                    if score >= 0.18:
                        x, y, yaw = nx, ny, nyaw
                    mapping_ok = True
            else:
                mapping_ok = True
                score = 1.0
        else:
            mapping_ok = young or map_pts.shape[0] < 20

        world = (
            transform_local(local, x, y, yaw)
            if local.shape[0]
            else np.zeros((0, 2))
        )
        hits, points = hits_to_world(map_hits_local, x, y, yaw)
        if not points and world.shape[0]:
            for wx, wy in world:
                points.append({"x": float(wx), "y": float(wy), "r": 0.0})

        with self._lock:
            frozen = self._map_frozen
        if hits and mapping_ok:
            if frozen:
                self._update_temp_from_hits(hits)
            else:
                self.omap.integrate(x, y, hits)

        with self._lock:
            self._pose = {"x": x, "y": y, "yaw": yaw, "ok": True}
            self._prev_world = world if world.shape[0] else self._prev_world
            self._points = points
            self._stamp = time.time()
            self._last_scan_t = now
            self._ok = True
            self._error = ""
            self._last_score = float(score)
            self._mapping_ok = bool(mapping_ok)
            self._odom_ok = odom_ok
            self._scan_count += 1
            sc = self._scan_count
        if sc % 50 == 0:
            log.info(
                "scan#%s mapping=%s score=%.2f map_hits=%s frozen=%s pose=(%.2f,%.2f,%.2f)",
                sc, mapping_ok, score, self.omap.hit_count(), frozen, x, y, yaw,
            )

    def _update_temp_from_hits(self, hits: list[tuple[float, float]]) -> None:
        now = time.time()
        fresh: list[int] = []
        for hx, hy in hits:
            ix, iy = self.omap._world_to_cell(hx, hy)
            if self.omap.is_static_occupied(ix, iy, margin=1):
                continue
            i = self.omap._idx(ix, iy)
            if i is None:
                continue
            fresh.append(i)
            for dy in range(-TEMP_INFLATE, TEMP_INFLATE + 1):
                for dx in range(-TEMP_INFLATE, TEMP_INFLATE + 1):
                    if dx * dx + dy * dy > TEMP_INFLATE * TEMP_INFLATE:
                        continue
                    nx, ny = ix + dx, iy + dy
                    if self.omap.is_static_occupied(nx, ny, margin=0):
                        continue
                    j = self.omap._idx(nx, ny)
                    if j is not None:
                        fresh.append(j)
        with self._lock:
            self._temp = {i: t for i, t in self._temp.items() if now - t <= TEMP_TTL_SEC}
            for i in fresh:
                self._temp[i] = now

    def _temp_cells_for_ui(self) -> list[list[int]]:
        now = time.time()
        out: list[list[int]] = []
        with self._lock:
            live = {i: t for i, t in self._temp.items() if now - t <= TEMP_TTL_SEC}
            self._temp = live
            items = list(live.keys())
        for i in items:
            out.append([i % self.omap.w, i // self.omap.w, TEMP_CELL_VAL])
        return out

    def set_frozen(self, frozen: bool) -> dict[str, Any]:
        with self._lock:
            self._map_frozen = bool(frozen)
            if not self._map_frozen:
                self._temp.clear()
            self._nav_path = []
            self._nav_goal = None
            self._nav_i = 0
            self._nav_status = "cancelled"
            was = self._map_frozen
        if was:
            info = self.omap.save(MAP_PATH)
            self.get_logger().info(f"Карта заморожена, сохранено стен={info.get('hits')}")
            log.info("freeze ON hits=%s", info.get("hits"))
        else:
            log.info("freeze OFF — wall writing enabled")
        return {"ok": True, "frozen": was, "hits": self.omap.to_dict().get("hits", 0)}

    def set_goal(self, gx: float, gy: float) -> dict[str, Any]:
        result = self._plan_goal(gx, gy)
        if not result.get("ok"):
            return result
        with self._lock:
            self._nav_path = list(result["path"])
            self._nav_goal = (float(gx), float(gy))
            self._selected_path = list(result["path"])
            self._selected_goal = (float(gx), float(gy))
            self._nav_i = 0
            self._nav_status = "navigating"
        return {
            "ok": True,
            "path_len": result["path_len"],
            "goal": result["goal"],
            "start": result["start"],
            "started": True,
        }

    def set_selected_goal(self, gx: float, gy: float) -> dict[str, Any]:
        result = self._plan_goal(gx, gy)
        if not result.get("ok"):
            return result
        with self._lock:
            self._selected_path = list(result["path"])
            self._selected_goal = (float(gx), float(gy))
            if self._nav_goal is None:
                self._nav_status = "selected"
        return {
            "ok": True,
            "path_len": result["path_len"],
            "goal": result["goal"],
            "start": result["start"],
            "started": False,
        }

    def start_selected_goal(self) -> dict[str, Any]:
        with self._lock:
            goal = self._selected_goal
        if goal is None:
            return {"ok": False, "error": "goal_not_selected"}
        return self.set_goal(float(goal[0]), float(goal[1]))

    def _plan_goal(self, gx: float, gy: float) -> dict[str, Any]:
        with self._lock:
            x = float(self._pose["x"])
            y = float(self._pose["y"])
            temp = dict(self._temp)
        blocked = build_blocked(self.omap, temp, time.time())
        return plan_path(self.omap, blocked, (x, y), (float(gx), float(gy)))

    def _nav_tick(self) -> None:
        with self._lock:
            if time.time() - self.drive.teleop_stamp < 0.35:
                return
            path = list(self._nav_path)
            goal = self._nav_goal
            i = self._nav_i
            x = float(self._pose["x"])
            y = float(self._pose["y"])
            yaw = float(self._pose["yaw"])
            frozen = self._map_frozen
            temp = dict(self._temp)
        if not frozen or not path or goal is None:
            return
        blocked = build_blocked(self.omap, temp, time.time())
        while i < len(path):
            ix, iy = self.omap._world_to_cell(path[i][0], path[i][1])
            if (ix, iy) in blocked and i + 1 < len(path):
                i += 1
                continue
            break
        if i >= len(path):
            self.set_goal(goal[0], goal[1])
            return
        vx, vy, w, i, arrived = pursuit_cmd(path, goal, i, x, y, yaw)
        with self._lock:
            self._nav_i = i
            if arrived:
                self._nav_path = []
                self._nav_goal = None
                self._nav_i = 0
                self._nav_status = "arrived"
        self.drive.set(vx, vy, w, from_teleop=False)

    def snapshot(self) -> dict[str, Any]:
        temp_cells = self._temp_cells_for_ui()
        with self._lock:
            odom_ok = bool(
                self._odom_ok and (time.time() - self._odom_stamp) <= ODOM_STALE_SEC
            )
            frozen = self._map_frozen
            path = [[p[0], p[1]] for p in self._nav_path]
            goal = list(self._nav_goal) if self._nav_goal else None
            selected_path = [[p[0], p[1]] for p in self._selected_path]
            selected_goal = list(self._selected_goal) if self._selected_goal else None
            nav_status = self._nav_status
            robot = {
                "length": ROBOT_LENGTH_M,
                "width": ROBOT_WIDTH_M,
                "radius": ROBOT_RADIUS_M,
            }
            if not self._ok:
                return {
                    "ok": False,
                    "error": self._error,
                    "points": [],
                    "pose": dict(self._pose),
                    "mode": "drive",
                    "odom_ok": odom_ok,
                    "frozen": frozen,
                    "temp_hits": len(temp_cells),
                    "map": self.omap.to_dict(temp_cells),
                    "path": path,
                    "goal": goal,
                    "selected_path": selected_path,
                    "selected_goal": selected_goal,
                    "nav_status": nav_status,
                    "map_align": "",
                    "robot": robot,
                }
            age = time.time() - self._stamp
            saved_ago = (
                int(time.time() - self.omap.last_save) if self.omap.last_save > 0 else None
            )
            base = {
                "ok": True,
                "mode": "drive",
                "points": list(self._points),
                "pose": dict(self._pose),
                "map": self.omap.to_dict(temp_cells),
                "odom_ok": odom_ok,
                "saved_ago": saved_ago,
                "score": self._last_score,
                "mapping": self._mapping_ok,
                "frozen": frozen,
                "temp_hits": len(temp_cells),
                "path": path,
                "goal": goal,
                "selected_path": selected_path,
                "selected_goal": selected_goal,
                "nav_status": nav_status,
                "map_align": "",
                "robot": robot,
                "stale": age > 2.0,
            }
            if age > 2.0:
                base["error"] = "лидар молчит — проверь USB / перезапуск драйвера"
            return base

    def clear_map(self) -> dict[str, Any]:
        with self._lock:
            if self._odom_ok and (time.time() - self._odom_stamp) <= ODOM_STALE_SEC:
                x = float(self._odom["x"])
                y = float(self._odom["y"])
                yaw = float(self._odom["yaw"])
            else:
                x = float(self._pose["x"])
                y = float(self._pose["y"])
                yaw = float(self._pose["yaw"])
            self._pose = {"x": x, "y": y, "yaw": yaw, "ok": True}
            self._prev_world = None
            self._last_score = 0.0
            self._mapping_ok = True
            self._map_frozen = False
            self._temp.clear()
            self._nav_path = []
            self._nav_goal = None
            self._selected_path = []
            self._selected_goal = None
            self._nav_i = 0
            self._nav_status = "cancelled"
            self._map_bootstrap_scans = 120
            self._last_scan_t = 0.0
        self.omap.recentre(x, y)
        self.omap.save(MAP_PATH)
        self.get_logger().info("Карта сброшена — запись стен снова включена")
        log.info("map cleared at pose=(%.2f,%.2f,%.2f)", x, y, yaw)
        return {"ok": True, "frozen": False, "message": "карта сброшена — едь, стены копятся"}

    def save_map(self) -> dict[str, Any]:
        return self.omap.save(MAP_PATH)
