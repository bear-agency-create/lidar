"""Vision pipeline: USB/RTSP → YuNet face → track → digital center."""

from __future__ import annotations

import logging
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np

log = logging.getLogger("camera.vision")

_MODELS = Path(__file__).resolve().parent / "models"
_YUNET = _MODELS / "face_detection_yunet_2023mar.onnx"


# --- geometry / faces ---------------------------------------------------------


@dataclass(frozen=True)
class FaceBox:
    x: int
    y: int
    w: int
    h: int
    score: float = 1.0
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


@dataclass
class TrackState:
    face: FaceBox | None
    offset_x: float
    offset_y: float
    locked: bool
    lost_frames: int


@dataclass
class ProximityState:
    area_frac: float
    close: bool
    approaching: bool
    in_zone: bool


# --- capture ------------------------------------------------------------------


class FrameSource:
    def open(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError

    def read(self) -> np.ndarray | None:
        raise NotImplementedError

    def _is_open(self) -> bool:
        raise NotImplementedError

    def frames(self) -> Iterator[np.ndarray]:
        while True:
            if not self._is_open():
                try:
                    self.open()
                except RuntimeError as exc:
                    log.warning("%s — retry in 1.5s", exc)
                    time.sleep(1.5)
                    continue
            frame = self.read()
            if frame is None:
                log.warning("frame drop — reconnect")
                self.close()
                time.sleep(0.5)
                continue
            yield frame


class UsbStream(FrameSource):
    def __init__(self, index: int = 0, width: int = 640, height: int = 480) -> None:
        self.index = index
        self.width = width
        self.height = height
        self._cap: cv2.VideoCapture | None = None

    def _is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def open(self) -> None:
        self.close()
        backend = cv2.CAP_DSHOW if sys.platform.startswith("win") else cv2.CAP_ANY
        self._cap = cv2.VideoCapture(self.index, backend)
        if not self._cap.isOpened():
            self._cap = cv2.VideoCapture(self.index)
        if not self._cap.isOpened():
            raise RuntimeError(
                f"Не удалось открыть USB-камеру index={self.index}. "
                "Попробуй CAMERA_INDEX=0 или 1"
            )
        if self.width > 0:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        if self.height > 0:
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        log.info("USB camera opened index=%s size=%sx%s", self.index, w, h)

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def read(self) -> np.ndarray | None:
        if not self._is_open():
            return None
        ok, frame = self._cap.read()  # type: ignore[union-attr]
        return frame if ok and frame is not None else None


class RtspStream(FrameSource):
    def __init__(self, url: str, reconnect_sec: float = 2.0) -> None:
        self.url = url
        self.reconnect_sec = reconnect_sec
        self._cap: cv2.VideoCapture | None = None

    def _is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def open(self) -> None:
        self.close()
        self._cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not self._cap.isOpened():
            raise RuntimeError(f"Не удалось открыть RTSP: {self._safe_url()}")
        log.info("RTSP opened %s", self._safe_url())

    def _safe_url(self) -> str:
        if "@" in self.url:
            return "rtsp://***@" + self.url.split("@", 1)[1]
        return self.url

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def read(self) -> np.ndarray | None:
        if not self._is_open():
            return None
        ok, frame = self._cap.read()  # type: ignore[union-attr]
        return frame if ok and frame is not None else None

    def frames(self) -> Iterator[np.ndarray]:
        while True:
            if not self._is_open():
                try:
                    self.open()
                except RuntimeError as exc:
                    log.warning("%s — retry in %.1fs", exc, self.reconnect_sec)
                    time.sleep(self.reconnect_sec)
                    continue
            frame = self.read()
            if frame is None:
                log.warning("frame drop — reconnect")
                self.close()
                time.sleep(self.reconnect_sec)
                continue
            yield frame


def open_source(
    source: str,
    *,
    index: int = 0,
    width: int = 640,
    height: int = 480,
    rtsp_url: str | None = None,
) -> FrameSource:
    src = source.strip().lower()
    if src in ("usb", "webcam", "local"):
        return UsbStream(index=index, width=width, height=height)
    if src in ("rtsp", "tapo"):
        if not rtsp_url:
            raise RuntimeError("rtsp_url required for CAMERA_SOURCE=rtsp")
        return RtspStream(rtsp_url)
    raise RuntimeError(f"Unknown CAMERA_SOURCE={source!r} (use usb|rtsp)")


# --- detect / track / proximity / digital center ------------------------------


class FaceDetector:
    def __init__(
        self,
        score_threshold: float = 0.55,
        nms_threshold: float = 0.3,
        top_k: int = 20,
        min_size: int = 24,
        model_path: str | None = None,
        scale_factor: float = 1.1,
        min_neighbors: int = 4,
    ) -> None:
        self.score_threshold = score_threshold
        self.min_size = min_size
        self._input_size: tuple[int, int] | None = None
        self._yunet: cv2.FaceDetectorYN | None = None
        self._haar: cv2.CascadeClassifier | None = None
        self.backend = "none"
        path = Path(model_path) if model_path else _YUNET
        if path.is_file() and hasattr(cv2, "FaceDetectorYN"):
            self._yunet = cv2.FaceDetectorYN.create(
                str(path), "", (320, 320), score_threshold, nms_threshold, top_k
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

    def detect(self, frame_bgr: np.ndarray) -> list[FaceBox]:
        if self._yunet is not None:
            return self._detect_yunet(frame_bgr)
        return self._detect_haar(frame_bgr)

    def _detect_yunet(self, frame_bgr: np.ndarray) -> list[FaceBox]:
        h, w = frame_bgr.shape[:2]
        size = (w, h)
        if self._input_size != size:
            self._yunet.setInputSize(size)  # type: ignore[union-attr]
            self._input_size = size
        try:
            lab = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            l2 = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(l)
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
            if score < self.score_threshold or bw < self.min_size or bh < self.min_size:
                continue
            lms: list[tuple[float, float]] = []
            if len(row) >= 14:
                for i in range(4, 14, 2):
                    lms.append((float(row[i]), float(row[i + 1])))
            xi = max(0, min(int(round(x)), w - 1))
            yi = max(0, min(int(round(y)), h - 1))
            wi = max(1, min(int(round(bw)), w - xi))
            hi = max(1, min(int(round(bh)), h - yi))
            out.append(FaceBox(xi, yi, wi, hi, score=score, landmarks=tuple(lms)))
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


class FaceTracker:
    def __init__(self, iou_sticky: float = 0.25, lost_frames_max: int = 12) -> None:
        self.iou_sticky = iou_sticky
        self.lost_frames_max = lost_frames_max
        self._locked: FaceBox | None = None
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
        candidates = faces
        if area_ok is not None:
            candidates = [f for f in faces if area_ok.get(id(f), True)]
        chosen: FaceBox | None = None
        if self._locked is not None and candidates:
            best_iou, best = 0.0, None
            for f in candidates:
                iou = self._locked.iou(f)
                if iou > best_iou:
                    best_iou, best = iou, f
            if best is not None and best_iou >= self.iou_sticky:
                chosen = best
        if chosen is None and candidates:
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
        cx, cy = frame_w * 0.5, frame_h * 0.5
        ox = (chosen.cx - cx) / max(1.0, cx)
        oy = (chosen.cy - cy) / max(1.0, cy)
        return TrackState(chosen, float(ox), float(oy), True, 0)


class ProximityEstimator:
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

    def evaluate(self, face: FaceBox | None, frame_w: int, frame_h: int) -> ProximityState:
        frame_area = max(1, frame_w * frame_h)
        if face is None:
            self._hist.clear()
            return ProximityState(0.0, False, False, False)
        area_frac = float(face.area) / float(frame_area)
        approaching = False
        if self._hist:
            prev = sorted(self._hist)[len(self._hist) // 2]
            approaching = (area_frac - prev) >= self.approach_delta
        self._hist.append(area_frac)
        return ProximityState(
            area_frac,
            area_frac >= self.close_area_frac,
            approaching,
            area_frac >= self.min_area_frac,
        )


def digital_center_view(
    frame: np.ndarray,
    face: FaceBox | None,
    *,
    smooth: float = 0.35,
    state: dict | None = None,
) -> tuple[np.ndarray, FaceBox | None, dict]:
    h, w = frame.shape[:2]
    st = state if state is not None else {}
    target_cx = float(face.cx) if face is not None else w * 0.5
    target_cy = float(face.cy) if face is not None else h * 0.5
    cx = float(st.get("cx", target_cx))
    cy = float(st.get("cy", target_cy))
    cx = cx * (1.0 - smooth) + target_cx * smooth
    cy = cy * (1.0 - smooth) + target_cy * smooth
    st["cx"], st["cy"] = cx, cy
    shift_x = int(round(w * 0.5 - cx))
    shift_y = int(round(h * 0.5 - cy))
    M = np.float32([[1, 0, shift_x], [0, 1, shift_y]])
    out = cv2.warpAffine(
        frame, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE
    )
    new_face = None
    if face is not None:
        lms = tuple((lx + shift_x, ly + shift_y) for lx, ly in face.landmarks)
        new_face = FaceBox(
            face.x + shift_x,
            face.y + shift_y,
            face.w,
            face.h,
            score=face.score,
            landmarks=lms,
        )
    return out, new_face, st


def draw_overlay(frame, track: TrackState, prox: ProximityState, faces, backend: str = "") -> None:
    h, w = frame.shape[:2]
    cv2.line(frame, (w // 2, 0), (w // 2, h), (60, 60, 60), 1)
    cv2.line(frame, (0, h // 2), (w, h // 2), (60, 60, 60), 1)

    def _draw(f: FaceBox, color, thickness: int = 1) -> None:
        cv2.rectangle(frame, (f.x, f.y), (f.x + f.w, f.y + f.h), color, thickness)
        for lx, ly in f.landmarks:
            cv2.circle(frame, (int(lx), int(ly)), 2, color, -1)
        if f.score < 1.0:
            cv2.putText(
                frame,
                f"{f.score:.2f}",
                (f.x, max(16, f.y - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
                cv2.LINE_AA,
            )

    for f in faces:
        if track.face is not None and f is track.face:
            continue
        _draw(f, (80, 80, 255), 1)
    if track.face is not None:
        color = (0, 220, 0) if track.locked else (0, 165, 255)
        _draw(track.face, color, 2)
        cv2.circle(frame, (int(track.face.cx), int(track.face.cy)), 4, color, -1)
    label = (
        f"{backend} lock={track.locked} close={prox.close} approach={prox.approaching} "
        f"area={prox.area_frac:.3f} ox={track.offset_x:+.2f} oy={track.offset_y:+.2f}"
    )
    cv2.putText(
        frame, label, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (240, 240, 240), 1, cv2.LINE_AA
    )
