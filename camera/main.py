#!/usr/bin/env python3
"""Умная камера: цикл USB/RTSP → лицо → центр.

Сейчас USB; Tapo RTSP/PTZ — позже (CAMERA_SOURCE=rtsp).
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
from vision import (
    FaceDetector,
    FaceTracker,
    ProximityEstimator,
    TrackState,
    digital_center_view,
    draw_overlay,
    open_source,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("camera.main")


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
    else:
        if config.CAMERA_SOURCE in ("usb", "webcam", "local"):
            log.info("USB mode: hardware PTZ off, digital center=%s", config.DIGITAL_CENTER)

    rtsp = config.rtsp_url() if config.CAMERA_SOURCE in ("rtsp", "tapo") else None
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
                faces, w, h, require_in_zone=True, area_ok=area_flags
            )
            prox = proximity.evaluate(track.face, w, h)

            if (
                ptz is not None
                and track.locked
                and track.face is not None
                and (prox.in_zone or prox.close or prox.approaching)
            ):
                ptz.center_on_offset(track.offset_x, track.offset_y)

            view, view_faces, view_track_face = frame, faces, track.face
            if config.DIGITAL_CENTER and config.CAMERA_SOURCE in ("usb", "webcam", "local"):
                view, shifted, dig_state = digital_center_view(
                    frame, track.face if track.locked else None, state=dig_state
                )
                view_track_face = shifted
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
                draw_overlay(
                    view,
                    TrackState(
                        view_track_face,
                        track.offset_x,
                        track.offset_y,
                        track.locked,
                        track.lost_frames,
                    ),
                    prox,
                    view_faces,
                    backend=detector.backend,
                )
                cv2.imshow("smart camera (USB)", view)
                if (cv2.waitKey(1) & 0xFF) in (27, ord("q")):
                    log.info("quit by user")
                    break

            sleep = frame_interval - (time.time() - loop_t)
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
