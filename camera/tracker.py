"""Выбор целевого лица и ошибка относительно центра кадра."""

from __future__ import annotations

from dataclasses import dataclass

from face_detect import FaceBox


@dataclass
class TrackState:
    face: FaceBox | None
    offset_x: float  # -1..1, >0 = лицо правее центра
    offset_y: float  # -1..1, >0 = лицо ниже центра
    locked: bool
    lost_frames: int


class FaceTracker:
    """Sticky lock на одно лицо + нормализованный offset от центра."""

    def __init__(self, iou_sticky: float = 0.25, lost_frames_max: int = 12) -> None:
        self.iou_sticky = iou_sticky
        self.lost_frames_max = lost_frames_max
        self._locked: FaceBox | None = None
        self._lost = 0

    def reset(self) -> None:
        self._locked = None
        self._lost = 0

    def update(
        self,
        faces: list[FaceBox],
        frame_w: int,
        frame_h: int,
        *,
        require_in_zone: bool,
        area_ok: dict[int, bool] | None = None,
    ) -> TrackState:
        """
        area_ok: optional map id(face)->in_zone; если None — все лица кандидаты.
        """
        candidates = faces
        if area_ok is not None:
            candidates = [f for f in faces if area_ok.get(id(f), True)]

        chosen: FaceBox | None = None
        if self._locked is not None and candidates:
            best_iou = 0.0
            best: FaceBox | None = None
            for f in candidates:
                iou = self._locked.iou(f)
                if iou > best_iou:
                    best_iou = iou
                    best = f
            if best is not None and best_iou >= self.iou_sticky:
                chosen = best

        if chosen is None and candidates:
            # ближайший ≈ самый крупный bbox
            chosen = max(candidates, key=lambda f: f.area)
        elif chosen is None and faces and not require_in_zone:
            chosen = max(faces, key=lambda f: f.area)

        if chosen is None:
            self._lost += 1
            if self._lost > self.lost_frames_max:
                self._locked = None
            return TrackState(None, 0.0, 0.0, False, self._lost)

        self._locked = chosen
        self._lost = 0
        cx = frame_w * 0.5
        cy = frame_h * 0.5
        # нормализация к половине кадра → примерно [-1, 1]
        ox = (chosen.cx - cx) / max(1.0, cx)
        oy = (chosen.cy - cy) / max(1.0, cy)
        return TrackState(chosen, float(ox), float(oy), True, 0)
