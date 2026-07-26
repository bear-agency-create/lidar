#!/usr/bin/env python3
"""Умная камера: захват лица + удержание в центре.

Сейчас по умолчанию — USB webcam.
Tapo RTSP/PTZ остаётся на потом (CAMERA_SOURCE=rtsp).
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import cv2

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import config
from digital_center import digital_center_view
from face_detect import FaceDetector
from proximity import ProximityEstimator
from stream import open_source
from tracker import FaceTracker, TrackState

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("camera.main")


def _draw_face(frame, f, color, thickness: int = 1) -> None:
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


def draw_overlay(frame, track, prox, faces, backend: str = "") -> None:
    h, w = frame.shape[:2]
    cv2.line(frame, (w // 2, 0), (w // 2, h), (60, 60, 60), 1)
    cv2.line(frame, (0, h // 2), (w, h // 2), (60, 60, 60), 1)
    for f in faces:
        if track.face is not None and f is track.face:
            continue
        _draw_face(frame, f, (80, 80, 255), 1)
    if track.face is not None:
        f = track.face
        color = (0, 220, 0) if track.locked else (0, 165, 255)
        _draw_face(frame, f, color, 2)
        cv2.circle(frame, (int(f.cx), int(f.cy)), 4, color, -1)
    label = (
        f"{backend} lock={track.locked} close={prox.close} approach={prox.approaching} "
        f"area={prox.area_frac:.3f} ox={track.offset_x:+.2f} oy={track.offset_y:+.2f}"
    )
    cv2.putText(
        frame,
        label,
        (10, 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (240, 240, 240),
        1,
        cv2.LINE_AA,
    )


def main() -> int:
    log.info(
        "smart camera source=%s index=%s dry_run=%s digital_center=%s preview=%s",
        config.CAMERA_SOURCE,
        config.CAMERA_INDEX,
        config.DRY_RUN,
        config.DIGITAL_CENTER,
        config.SHOW_PREVIEW,
    )

    detector = FaceDetector(
        score_threshold=config.DETECT_SCORE,
        nms_threshold=config.DETECT_NMS,
        min_size=config.DETECT_MIN_SIZE,
        scale_factor=config.DETECT_SCALE,
        min_neighbors=config.DETECT_MIN_NEIGHBORS,
    )
    log.info("face detector backend=%s", detector.backend)
    tracker = FaceTracker(
        iou_sticky=config.TRACK_IOU_STICKY,
        lost_frames_max=config.TRACK_LOST_FRAMES,
    )
    proximity = ProximityEstimator(
        min_area_frac=config.FACE_MIN_AREA_FRAC,
        close_area_frac=config.FACE_CLOSE_AREA_FRAC,
        approach_delta=config.APPROACH_DELTA,
    )

    ptz = None
    if config.CAMERA_SOURCE in ("rtsp", "tapo") and not config.DRY_RUN:
        from ptz import PtzController

        ptz = PtzController(
            config.TAPO_HOST,
            config.TAPO_USER,
            config.TAPO_PASSWORD,
            deadzone=config.CENTER_DEADZONE,
            gain_x=config.PTZ_GAIN_X,
            gain_y=config.PTZ_GAIN_Y,
            sign_x=config.PTZ_SIGN_X,
            sign_y=config.PTZ_SIGN_Y,
            max_step=config.PTZ_MAX_STEP,
            min_step=config.PTZ_MIN_STEP,
            cmd_interval_sec=config.PTZ_CMD_INTERVAL_SEC,
            dry_run=False,
        )
    elif config.CAMERA_SOURCE in ("usb", "webcam", "local"):
        log.info("USB mode: hardware PTZ off, digital center=%s", config.DIGITAL_CENTER)

    rtsp = None
    if config.CAMERA_SOURCE in ("rtsp", "tapo"):
        rtsp = config.rtsp_url()

    stream = open_source(
        config.CAMERA_SOURCE,
        index=config.CAMERA_INDEX,
        width=config.CAMERA_WIDTH,
        height=config.CAMERA_HEIGHT,
        rtsp_url=rtsp,
    )
    frame_interval = 1.0 / max(1.0, config.TARGET_FPS)
    n = 0
    t0 = time.time()
    dig_state: dict = {}

    try:
        for frame in stream.frames():
            loop_t = time.time()
            h, w = frame.shape[:2]
            frame_area = max(1, w * h)
            faces = detector.detect(frame)

            area_flags = {
                id(f): (float(f.area) / float(frame_area)) >= config.FACE_MIN_AREA_FRAC
                for f in faces
            }

            track = tracker.update(
                faces,
                w,
                h,
                require_in_zone=True,
                area_ok=area_flags,
            )
            prox = proximity.evaluate(track.face, w, h)

            if (
                ptz is not None
                and track.locked
                and track.face is not None
                and (prox.in_zone or prox.close or prox.approaching)
            ):
                ptz.center_on_offset(track.offset_x, track.offset_y)

            view = frame
            view_faces = faces
            view_track_face = track.face
            if config.DIGITAL_CENTER and config.CAMERA_SOURCE in ("usb", "webcam", "local"):
                view, shifted, dig_state = digital_center_view(
                    frame, track.face if track.locked else None, state=dig_state
                )
                view_track_face = shifted
                # для оверлея достаточно целевого лица
                view_faces = [shifted] if shifted is not None else []

            n += 1
            if n % config.LOG_EVERY_N == 0:
                fps = n / max(1e-3, time.time() - t0)
                log.info(
                    "fps=%.1f faces=%s lock=%s area=%.3f close=%s approach=%s ox=%+.2f oy=%+.2f",
                    fps,
                    len(faces),
                    track.locked,
                    prox.area_frac,
                    prox.close,
                    prox.approaching,
                    track.offset_x,
                    track.offset_y,
                )

            if config.SHOW_PREVIEW:
                draw_track = TrackState(
                    view_track_face,
                    track.offset_x,
                    track.offset_y,
                    track.locked,
                    track.lost_frames,
                )
                draw_overlay(view, draw_track, prox, view_faces, backend=detector.backend)
                cv2.imshow("smart camera (USB)", view)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):
                    log.info("quit by user")
                    break

            elapsed = time.time() - loop_t
            sleep = frame_interval - elapsed
            if sleep > 0:
                time.sleep(sleep)
    except KeyboardInterrupt:
        log.info("KeyboardInterrupt")
    finally:
        stream.close()
        if config.SHOW_PREVIEW:
            cv2.destroyAllWindows()
        log.info("stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
