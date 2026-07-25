"""Teleop / velocity command layer (cmd file + /cmd_vel).

Encoder closed-loop driving lives in drive_encoders.py (Mega serial bridge).
This module only publishes the user's / planner's velocity intent.
"""

from __future__ import annotations

import json
import time
from typing import Any, Callable

from geometry_msgs.msg import Twist

from config import CMD_FILE, CMD_VX_MAX, CMD_VY_MAX, CMD_W_MAX, CMD_WATCHDOG_SEC
from geometry import clamp
from logutil import get_logger

log = get_logger("drive")


class DriveCommander:
    """Thread-safe velocity command buffer + watchdog."""

    def __init__(self, publish_twist: Callable[[Twist], None] | None = None) -> None:
        self._vx = 0.0
        self._vy = 0.0
        self._w = 0.0
        self._stamp = 0.0
        self._teleop_stamp = 0.0
        self._publish_twist = publish_twist
        self._writes = 0

    @property
    def stamp(self) -> float:
        return self._stamp

    @property
    def teleop_stamp(self) -> float:
        return self._teleop_stamp

    def get(self) -> tuple[float, float, float]:
        return self._vx, self._vy, self._w

    def set(self, vx: float, vy: float, w: float, *, from_teleop: bool = True) -> dict[str, Any]:
        vx = clamp(float(vx), -CMD_VX_MAX, CMD_VX_MAX)
        vy = clamp(float(vy), -CMD_VY_MAX, CMD_VY_MAX)
        w = clamp(float(w), -CMD_W_MAX, CMD_W_MAX)
        self._vx, self._vy, self._w = vx, vy, w
        self._stamp = time.time()
        if from_teleop and (abs(vx) > 0.02 or abs(vy) > 0.02 or abs(w) > 0.05):
            self._teleop_stamp = time.time()
        self._emit(vx, vy, w)
        return {"ok": True, "vx": vx, "vy": vy, "w": w}

    def stop(self) -> dict[str, Any]:
        return self.set(0.0, 0.0, 0.0, from_teleop=False)

    def watchdog_tick(self) -> None:
        now = time.time()
        age = now - self._stamp if self._stamp > 0 else 1e9
        if age > CMD_WATCHDOG_SEC:
            self._vx = self._vy = self._w = 0.0
        self._emit(self._vx, self._vy, self._w)

    def _emit(self, vx: float, vy: float, w: float) -> None:
        try:
            CMD_FILE.write_text(
                json.dumps({"vx": vx, "vy": vy, "w": w, "t": time.time()}),
                encoding="utf-8",
            )
        except OSError as exc:
            log.warning("cmd file write failed: %s", exc)
        if self._publish_twist is not None:
            msg = Twist()
            msg.linear.x = float(vx)
            msg.linear.y = float(vy)
            msg.angular.z = float(w)
            self._publish_twist(msg)
        self._writes += 1
        if self._writes % 200 == 0 and (abs(vx) + abs(vy) + abs(w)) > 0.01:
            log.info("cmd stream alive vx=%.2f vy=%.2f w=%.2f", vx, vy, w)
