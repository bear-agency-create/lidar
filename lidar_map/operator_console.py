#!/usr/bin/env python3
"""Operator console — curses TUI (default) + optional Tk GUI.

TUI works over SSH. Set OPERATOR_UI=tk for desktop window when DISPLAY works.
"""

from __future__ import annotations

import json
import math
import os
import threading
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

API = os.environ.get("ROBOT_API", "http://127.0.0.1:8765").rstrip("/")
LOG_PATH = Path(
    os.environ.get("ROBOT_LOG", os.path.expanduser("~/robot_nav/logs/lidar_map.log"))
)


def http_json(method: str, path: str, body: dict | None = None, timeout: float = 3.0) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = Request(
        API + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def read_logs(n: int = 18) -> list[str]:
    """Prefer remote /api/logs (laptop → Pi), fallback to local file."""
    try:
        data = http_json("GET", f"/api/logs?n={int(n)}", timeout=2.5)
        lines = data.get("lines")
        if isinstance(lines, list):
            return [str(x) for x in lines]
        if data.get("error"):
            return [str(data["error"])]
    except Exception as exc:  # noqa: BLE001
        # fall through to local file
        remote_err = str(exc)
    else:
        remote_err = ""
    try:
        if LOG_PATH.is_file():
            return LOG_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()[-n:]
    except OSError as exc:
        return [f"log error: {exc}"]
    return [f"no local log; remote: {remote_err or 'empty'}"]


class TuiApp:
    def __init__(self) -> None:
        self.waypoints: list[dict[str, Any]] = []
        self.snap: dict[str, Any] = {}
        self.msg = "ready"
        self.mode = "main"
        self.add_buf = ""
        self.last_fetch = 0.0

    def fetch(self) -> None:
        try:
            self.snap = http_json("GET", "/api/scan")
        except Exception as exc:  # noqa: BLE001
            self.snap = {"ok": False, "error": str(exc), "pose": {}, "mission": {}}
            self.msg = f"ERR scan: {exc}"

    def add_wp(self, x: float, y: float, prio: int) -> None:
        i = len(self.waypoints)
        self.waypoints.append(
            {
                "x": x,
                "y": y,
                "priority": prio,
                "order": i,
                "id": f"wp{i + 1}",
                "label": f"P{i + 1}",
            }
        )

    def ordered(self) -> list[dict[str, Any]]:
        return sorted(self.waypoints, key=lambda w: (-int(w["priority"]), int(w["order"])))

    def draw_map(self, win, h: int, w: int) -> None:
        import curses

        win.erase()
        win.border()
        win.addstr(0, 2, " MAP ")
        pose = self.snap.get("pose") or {}
        px = float(pose.get("x", 0.0))
        py = float(pose.get("y", 0.0))
        m = self.snap.get("map") or {}
        cells = m.get("cells") or []
        origin = m.get("origin") or [0, 0]
        res = float(m.get("resolution") or 0.05)
        ox, oy = float(origin[0]), float(origin[1])
        scale = 2.0
        cx, cy = max(2, w // 2), max(2, h // 2)
        step = max(1, len(cells) // 900 or 1)
        for cell in cells[::step]:
            if len(cell) < 3 or float(cell[2]) < 1.0:
                continue
            wx = ox + (int(cell[0]) + 0.5) * res
            wy = oy + (int(cell[1]) + 0.5) * res
            col = cx + int((wx - px) * scale)
            row = cy - int((wy - py) * scale)
            if 1 <= row < h - 1 and 1 <= col < w - 1:
                try:
                    win.addch(row, col, ord("#"))
                except curses.error:
                    pass
        path = self.snap.get("path") or self.snap.get("selected_path") or []
        pstep = max(1, len(path) // 200 or 1)
        for p in path[::pstep]:
            col = cx + int((float(p[0]) - px) * scale)
            row = cy - int((float(p[1]) - py) * scale)
            if 1 <= row < h - 1 and 1 <= col < w - 1:
                try:
                    win.addch(row, col, ord("."))
                except curses.error:
                    pass
        for i, wp in enumerate(self.ordered()):
            col = cx + int((float(wp["x"]) - px) * scale)
            row = cy - int((float(wp["y"]) - py) * scale)
            if 1 <= row < h - 1 and 1 <= col < w - 1:
                try:
                    win.addstr(row, col, str((i + 1) % 10), curses.A_BOLD)
                except curses.error:
                    pass
        try:
            win.addstr(cy, cx, "R", curses.A_REVERSE)
        except curses.error:
            pass
        win.noutrefresh()

    def draw(self, stdscr) -> None:
        import curses

        H, W = stdscr.getmaxyx()
        left_w = max(36, min(48, W // 3))
        map_h = max(12, H - 12)
        log_h = max(6, H - map_h - 2)
        pose = self.snap.get("pose") or {}
        mission = self.snap.get("mission") or {}
        stdscr.erase()
        stdscr.addstr(0, 0, f" ROBOT OPERATOR  {API} "[: W - 1], curses.A_REVERSE)
        lines = [
            f"scan={self.snap.get('ok')} odom={self.snap.get('odom_ok')} nav={self.snap.get('nav_status')}",
            f"pose {pose.get('x', 0):+.2f} {pose.get('y', 0):+.2f} yaw={pose.get('yaw', 0):+.2f}",
            f"mission {mission.get('status')} {mission.get('index', 0)}/{mission.get('total', 0)}",
            f"goal {self.snap.get('goal')}",
            f"err {self.snap.get('error') or '-'}",
            "",
            "WAYPOINTS (prio high→low):",
        ]
        for wp in self.ordered():
            lines.append(f" p{wp['priority']:>2} ({wp['x']:+.2f},{wp['y']:+.2f}) {wp['label']}")
        if not self.waypoints:
            lines.append(" (empty — press a)")
        lines += [
            "",
            "a add  p plan  g go  s stop",
            "d del-last  c clear  q quit",
            f"MSG: {self.msg}"[: left_w - 2],
        ]
        if self.mode == "add":
            lines.append(f"> {self.add_buf}_")
        left = curses.newwin(map_h, left_w, 1, 0)
        left.erase()
        left.border()
        left.addstr(0, 2, " STATUS ")
        for i, line in enumerate(lines[: map_h - 2]):
            try:
                left.addstr(1 + i, 1, line[: left_w - 2])
            except curses.error:
                pass
        left.noutrefresh()
        mmap = curses.newwin(map_h, max(10, W - left_w), 1, left_w)
        self.draw_map(mmap, map_h, max(10, W - left_w))
        logw = curses.newwin(log_h, W, 1 + map_h, 0)
        logw.erase()
        logw.border()
        logw.addstr(0, 2, " LOGS ")
        for i, line in enumerate(read_logs(log_h - 2)):
            try:
                logw.addstr(1 + i, 1, line[: max(1, W - 2)])
            except curses.error:
                pass
        logw.noutrefresh()
        curses.doupdate()

    def _http_err(self, prefix: str, exc: Exception) -> None:
        if isinstance(exc, HTTPError):
            try:
                body = json.loads(exc.read().decode())
                self.msg = f"ERR {prefix} {body.get('error')}"
                return
            except Exception:  # noqa: BLE001
                pass
        self.msg = f"ERR {prefix} {exc}"

    def handle(self, key: int) -> bool:
        import curses

        if self.mode == "add":
            if key in (10, 13):
                self.mode = "main"
                parts = [p.strip() for p in self.add_buf.split(",")]
                self.add_buf = ""
                try:
                    x = float(parts[0])
                    y = float(parts[1])
                    prio = int(parts[2]) if len(parts) > 2 and parts[2] else 0
                    self.add_wp(x, y, prio)
                    self.msg = f"OK add ({x:.2f},{y:.2f}) p={prio}"
                except Exception as exc:  # noqa: BLE001
                    self.msg = f"ERR format x,y,prio ({exc})"
                return True
            if key == 27:
                self.mode = "main"
                self.add_buf = ""
                return True
            if key in (curses.KEY_BACKSPACE, 127, 8):
                self.add_buf = self.add_buf[:-1]
                return True
            if 32 <= key < 127:
                self.add_buf += chr(key)
            return True

        if key in (ord("q"), ord("Q")):
            return False
        if key in (ord("a"), ord("A")):
            self.mode = "add"
            self.add_buf = ""
            self.msg = "type x,y,prio then Enter"
            return True
        if key in (ord("d"), ord("D")) and self.waypoints:
            self.waypoints.pop()
            self.msg = "OK deleted last"
            return True
        if key in (ord("c"), ord("C")):
            self.waypoints.clear()
            self.msg = "OK cleared"
            return True
        if key in (ord("s"), ord("S")):
            try:
                http_json("POST", "/api/cmd/stop", {})
                self.msg = "OK stop"
            except Exception as exc:  # noqa: BLE001
                self._http_err("stop", exc)
            return True
        if key in (ord("p"), ord("P")):
            if not self.waypoints:
                self.msg = "ERR no waypoints"
                return True
            try:
                res = http_json("POST", "/api/mission/plan", {"waypoints": self.waypoints})
                if res.get("ok"):
                    self.snap["selected_path"] = res.get("path") or []
                    self.msg = f"OK plan len={res.get('path_len')}"
                else:
                    self.msg = f"ERR plan {res.get('error')}"
            except Exception as exc:  # noqa: BLE001
                self._http_err("plan", exc)
            return True
        if key in (ord("g"), ord("G")):
            if not self.waypoints:
                self.msg = "ERR no waypoints"
                return True
            try:
                res = http_json(
                    "POST", "/api/mission", {"waypoints": self.waypoints, "start": True}
                )
                self.msg = (
                    f"OK go len={res.get('path_len')}"
                    if res.get("ok")
                    else f"ERR go {res.get('error')}"
                )
            except Exception as exc:  # noqa: BLE001
                self._http_err("go", exc)
            return True
        return True


def run_tui() -> None:
    import curses

    app = TuiApp()

    def _main(stdscr) -> None:
        curses.curs_set(0)
        stdscr.nodelay(True)
        stdscr.timeout(200)
        while True:
            now = time.time()
            if now - app.last_fetch > 0.45:
                app.fetch()
                app.last_fetch = now
            app.draw(stdscr)
            key = stdscr.getch()
            if key != -1 and not app.handle(key):
                break

    curses.wrapper(_main)


def run_tk() -> None:
    from operator_gui import run

    run()


def main() -> None:
    ui = os.environ.get("OPERATOR_UI", "auto").lower()
    # On Windows laptop without explicit UI, prefer Tk window
    if ui == "auto" and os.name == "nt":
        ui = "tk"
    if ui == "tk":
        run_tk()
        return
    if ui == "tui":
        run_tui()
        return
    if os.environ.get("DISPLAY") or os.name == "nt":
        try:
            run_tk()
            return
        except Exception:
            pass
    run_tui()


if __name__ == "__main__":
    main()
