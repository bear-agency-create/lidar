"""PTZ-управление Tapo C200 через pytapo."""

from __future__ import annotations

import logging
import time
from typing import Any

log = logging.getLogger("camera.ptz")


class PtzController:
    """Удержание цели в центре: offset → moveMotor(dx, dy)."""

    def __init__(
        self,
        host: str,
        user: str,
        password: str,
        *,
        deadzone: float,
        gain_x: float,
        gain_y: float,
        sign_x: float,
        sign_y: float,
        max_step: float,
        min_step: float,
        cmd_interval_sec: float,
        dry_run: bool = False,
    ) -> None:
        self.deadzone = deadzone
        self.gain_x = gain_x
        self.gain_y = gain_y
        self.sign_x = sign_x
        self.sign_y = sign_y
        self.max_step = max_step
        self.min_step = min_step
        self.cmd_interval_sec = cmd_interval_sec
        self.dry_run = dry_run
        self._last_cmd_t = 0.0
        self._tapo: Any = None

        if dry_run:
            log.warning("PTZ dry-run — мотор не двигаем")
            return

        from pytapo import Tapo  # lazy: чтобы stream/detect работали без камеры

        self._tapo = Tapo(host, user, password)
        info = self._tapo.getBasicInfo()
        log.info("Tapo connected: %s", info.get("device_info") or info)

    def center_on_offset(self, offset_x: float, offset_y: float) -> dict[str, Any]:
        """offset >0: лицо правее / ниже центра кадра."""
        now = time.time()
        if now - self._last_cmd_t < self.cmd_interval_sec:
            return {"ok": True, "skipped": "rate_limit"}

        ax, ay = abs(offset_x), abs(offset_y)
        if ax < self.deadzone and ay < self.deadzone:
            return {"ok": True, "skipped": "deadzone", "ox": offset_x, "oy": offset_y}

        dx = 0.0
        dy = 0.0
        if ax >= self.deadzone:
            dx = self.sign_x * offset_x * self.gain_x
            dx = self._clamp_step(dx)
        if ay >= self.deadzone:
            dy = self.sign_y * offset_y * self.gain_y
            dy = self._clamp_step(dy)

        # Tapo часто не любит одновременный pan+tilt
        if abs(dx) >= abs(dy) and abs(dx) >= self.min_step:
            dy = 0.0
        elif abs(dy) >= self.min_step:
            dx = 0.0
        else:
            return {"ok": True, "skipped": "too_small", "dx": dx, "dy": dy}

        self._last_cmd_t = now
        return self._move(int(round(dx)), int(round(dy)))

    def _clamp_step(self, v: float) -> float:
        if abs(v) < self.min_step:
            return 0.0
        mag = min(self.max_step, abs(v))
        return mag if v > 0 else -mag

    def _move(self, dx: int, dy: int) -> dict[str, Any]:
        if dx == 0 and dy == 0:
            return {"ok": True, "skipped": "zero"}
        log.info("PTZ moveMotor dx=%s dy=%s", dx, dy)
        if self.dry_run or self._tapo is None:
            return {"ok": True, "dry_run": True, "dx": dx, "dy": dy}
        try:
            self._tapo.moveMotor(dx, dy)
            return {"ok": True, "dx": dx, "dy": dy}
        except Exception as exc:  # noqa: BLE001
            log.warning("moveMotor failed: %s", exc)
            return {"ok": False, "error": str(exc), "dx": dx, "dy": dy}
