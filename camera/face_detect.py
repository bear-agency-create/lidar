"""Детекция лиц: OpenCV YuNet (DNN) + fallback Haar."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

_MODELS = Path(__file__).resolve().parent / "models"
_YUNET = _MODELS / "face_detection_yunet_2023mar.onnx"


@dataclass(frozen=True)
class FaceBox:
    x: int
    y: int
    w: int
    h: int
    score: float = 1.0
    # 5 точек YuNet: правый глаз, левый глаз, нос, правый рот, левый рот
    landmarks: tuple[tuple[float, float], ...] = field(default_factory=tuple)

    @property
    def cx(self) -> float:
        return self.x + self.w * 0.5

    @property
    def cy(self) -> float:
        return self.y + self.h * 0.5

    @property
    def area(self) -> int:
        return max(0, self.w) * max(0, self.h)

    def as_xyxy(self) -> tuple[int, int, int, int]:
        return self.x, self.y, self.x + self.w, self.y + self.h

    def iou(self, other: "FaceBox") -> float:
        ax1, ay1, ax2, ay2 = self.as_xyxy()
        bx1, by1, bx2, by2 = other.as_xyxy()
        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
        inter = iw * ih
        if inter <= 0:
            return 0.0
        union = self.area + other.area - inter
        return float(inter) / float(union) if union > 0 else 0.0


class FaceDetector:
    """YuNet — устойчивее к углу/освещению, чем Haar."""

    def __init__(
        self,
        score_threshold: float = 0.55,
        nms_threshold: float = 0.3,
        top_k: int = 20,
        min_size: int = 24,
        model_path: str | None = None,
        # legacy Haar args (fallback)
        scale_factor: float = 1.1,
        min_neighbors: int = 4,
    ) -> None:
        self.score_threshold = score_threshold
        self.nms_threshold = nms_threshold
        self.top_k = top_k
        self.min_size = min_size
        self._input_size: tuple[int, int] | None = None
        self._yunet: cv2.FaceDetectorYN | None = None
        self._haar: cv2.CascadeClassifier | None = None
        self.backend = "none"

        path = Path(model_path) if model_path else _YUNET
        if path.is_file() and hasattr(cv2, "FaceDetectorYN"):
            self._yunet = cv2.FaceDetectorYN.create(
                str(path),
                "",
                (320, 320),
                score_threshold,
                nms_threshold,
                top_k,
            )
            self.backend = "yunet"
        else:
            cascade = str(
                Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
            )
            self._haar = cv2.CascadeClassifier(cascade)
            if self._haar.empty():
                raise RuntimeError("Нет YuNet-модели и не загрузился Haar cascade")
            self.backend = "haar"
            self._scale_factor = scale_factor
            self._min_neighbors = min_neighbors

    def _ensure_yunet_size(self, w: int, h: int) -> None:
        assert self._yunet is not None
        size = (w, h)
        if self._input_size != size:
            self._yunet.setInputSize(size)
            self._input_size = size

    def detect(self, frame_bgr: np.ndarray) -> list[FaceBox]:
        if self._yunet is not None:
            return self._detect_yunet(frame_bgr)
        return self._detect_haar(frame_bgr)

    def _detect_yunet(self, frame_bgr: np.ndarray) -> list[FaceBox]:
        h, w = frame_bgr.shape[:2]
        self._ensure_yunet_size(w, h)
        # лёгкое улучшение контраста в тенях (копия, оригинал для оверлея не трогаем)
        work = frame_bgr
        try:
            lab = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l2 = clahe.apply(l)
            work = cv2.cvtColor(cv2.merge([l2, a, b]), cv2.COLOR_LAB2BGR)
        except cv2.error:
            work = frame_bgr

        _, faces = self._yunet.detect(work)  # type: ignore[union-attr]
        out: list[FaceBox] = []
        if faces is None:
            return out
        for row in faces:
            x, y, bw, bh = row[:4]
            score = float(row[14]) if len(row) > 14 else float(row[-1])
            if score < self.score_threshold:
                continue
            if bw < self.min_size or bh < self.min_size:
                continue
            # landmarks: x1,y1 ... x5,y5 at indices 4..13
            lms: list[tuple[float, float]] = []
            if len(row) >= 14:
                for i in range(4, 14, 2):
                    lms.append((float(row[i]), float(row[i + 1])))
            xi, yi = int(round(x)), int(round(y))
            wi, hi = int(round(bw)), int(round(bh))
            # clamp в кадр
            xi = max(0, min(xi, w - 1))
            yi = max(0, min(yi, h - 1))
            wi = max(1, min(wi, w - xi))
            hi = max(1, min(hi, h - yi))
            out.append(
                FaceBox(xi, yi, wi, hi, score=score, landmarks=tuple(lms))
            )
        out.sort(key=lambda f: f.score * f.area, reverse=True)
        return out

    def _detect_haar(self, frame_bgr: np.ndarray) -> list[FaceBox]:
        assert self._haar is not None
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        rects = self._haar.detectMultiScale(
            gray,
            scaleFactor=getattr(self, "_scale_factor", 1.1),
            minNeighbors=getattr(self, "_min_neighbors", 4),
            minSize=(self.min_size, self.min_size),
            flags=cv2.CASCADE_SCALE_IMAGE,
        )
        return [FaceBox(int(x), int(y), int(w), int(h)) for (x, y, w, h) in rects]
