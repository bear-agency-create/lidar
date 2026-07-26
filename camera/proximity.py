"""Оценка близости / приближения по размеру лица в кадре."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from face_detect import FaceBox


@dataclass
class ProximityState:
    area_frac: float
    close: bool
    approaching: bool
    in_zone: bool


class ProximityEstimator:
    """area_frac = (face_w * face_h) / (frame_w * frame_h) — прокси дистанции."""

    def __init__(
        self,
        min_area_frac: float,
        close_area_frac: float,
        approach_delta: float,
        history: int = 8,
    ) -> None:
        self.min_area_frac = min_area_frac
        self.close_area_frac = close_area_frac
        self.approach_delta = approach_delta
        self._hist: deque[float] = deque(maxlen=history)

    def reset(self) -> None:
        self._hist.clear()

    def evaluate(self, face: FaceBox | None, frame_w: int, frame_h: int) -> ProximityState:
        frame_area = max(1, frame_w * frame_h)
        if face is None:
            self._hist.clear()
            return ProximityState(0.0, False, False, False)

        area_frac = float(face.area) / float(frame_area)
        approaching = False
        if self._hist:
            # сравниваем с медианой недавнего прошлого
            prev = sorted(self._hist)[len(self._hist) // 2]
            approaching = (area_frac - prev) >= self.approach_delta
        self._hist.append(area_frac)

        in_zone = area_frac >= self.min_area_frac
        close = area_frac >= self.close_area_frac
        return ProximityState(area_frac, close, approaching, in_zone)
