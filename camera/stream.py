"""Захват видео: USB webcam или RTSP (Tapo)."""

from __future__ import annotations

import logging
import sys
import time
from typing import Iterator

import cv2
import numpy as np

log = logging.getLogger("camera.stream")


class FrameSource:
    """Общий интерфейс источника кадров."""

    def open(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError

    def read(self) -> np.ndarray | None:
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

    def _is_open(self) -> bool:
        raise NotImplementedError

    def __enter__(self) -> "FrameSource":
        self.open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class UsbStream(FrameSource):
    """Локальная USB / встроенная веб-камера."""

    def __init__(
        self,
        index: int = 0,
        width: int = 640,
        height: int = 480,
    ) -> None:
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
            # fallback без явного backend
            self._cap = cv2.VideoCapture(self.index)
        if not self._cap.isOpened():
            raise RuntimeError(
                f"Не удалось открыть USB-камеру index={self.index}. "
                "Попробуй CAMERA_INDEX=1"
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
        if not ok or frame is None:
            return None
        return frame


class RtspStream(FrameSource):
    """RTSP (Tapo C200 и др.)."""

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
        if not ok or frame is None:
            return None
        return frame

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
