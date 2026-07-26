"""Конфиг умной камеры (USB сейчас, Tapo RTSP — позже)."""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_float(name: str, default: float) -> float:
    raw = _env(name, "")
    if not raw:
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    raw = _env(name, "")
    if not raw:
        return default
    return int(raw)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name, "").lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


# --- Source: usb | rtsp ---
CAMERA_SOURCE = _env("CAMERA_SOURCE", "usb").lower()  # default: USB webcam
CAMERA_INDEX = _env_int("CAMERA_INDEX", 1)  # 0 часто встроенная; USB обычно 1
CAMERA_WIDTH = _env_int("CAMERA_WIDTH", 1280)
CAMERA_HEIGHT = _env_int("CAMERA_HEIGHT", 720)

# --- Tapo (когда CAMERA_SOURCE=rtsp) ---
TAPO_HOST = _env("TAPO_HOST", "172.21.2.114")
TAPO_USER = _env("TAPO_USER", "")
TAPO_PASSWORD = _env("TAPO_PASSWORD", "")
TAPO_STREAM = _env("TAPO_STREAM", "stream2")
TAPO_RTSP_PORT = _env_int("TAPO_RTSP_PORT", 554)

# --- Runtime ---
SHOW_PREVIEW = _env_bool("CAMERA_SHOW_PREVIEW", True)
# USB без мотора: PTZ по умолчанию выключен; для Tapo можно поставить 0
DRY_RUN = _env_bool("CAMERA_DRY_RUN", CAMERA_SOURCE != "rtsp")
# Цифровое «удержание в центре» для USB (кроп кадра вокруг лица)
DIGITAL_CENTER = _env_bool("CAMERA_DIGITAL_CENTER", True)
TARGET_FPS = _env_float("CAMERA_TARGET_FPS", 15.0)
LOG_EVERY_N = _env_int("CAMERA_LOG_EVERY_N", 30)

# --- Face / proximity ---
FACE_MIN_AREA_FRAC = _env_float("FACE_MIN_AREA_FRAC", 0.006)
FACE_CLOSE_AREA_FRAC = _env_float("FACE_CLOSE_AREA_FRAC", 0.035)
APPROACH_DELTA = _env_float("FACE_APPROACH_DELTA", 0.003)
DETECT_SCORE = _env_float("FACE_DETECT_SCORE", 0.55)
DETECT_NMS = _env_float("FACE_DETECT_NMS", 0.3)
DETECT_MIN_SIZE = _env_int("FACE_DETECT_MIN_SIZE", 28)
# legacy Haar (если нет YuNet-модели)
DETECT_SCALE = _env_float("FACE_DETECT_SCALE", 1.1)
DETECT_MIN_NEIGHBORS = _env_int("FACE_DETECT_MIN_NEIGHBORS", 4)

TRACK_IOU_STICKY = _env_float("FACE_TRACK_IOU_STICKY", 0.25)
TRACK_LOST_FRAMES = _env_int("FACE_TRACK_LOST_FRAMES", 12)

# --- PTZ (только Tapo) ---
CENTER_DEADZONE = _env_float("PTZ_CENTER_DEADZONE", 0.08)
PTZ_GAIN_X = _env_float("PTZ_GAIN_X", 25.0)
PTZ_GAIN_Y = _env_float("PTZ_GAIN_Y", 18.0)
PTZ_SIGN_X = _env_float("PTZ_SIGN_X", 1.0)
PTZ_SIGN_Y = _env_float("PTZ_SIGN_Y", -1.0)
PTZ_MAX_STEP = _env_float("PTZ_MAX_STEP", 20.0)
PTZ_MIN_STEP = _env_float("PTZ_MIN_STEP", 2.0)
PTZ_CMD_INTERVAL_SEC = _env_float("PTZ_CMD_INTERVAL_SEC", 0.35)


def rtsp_url() -> str:
    if not TAPO_USER or not TAPO_PASSWORD:
        raise RuntimeError(
            "Задайте TAPO_USER и TAPO_PASSWORD (Camera account в приложении Tapo)"
        )
    return (
        f"rtsp://{TAPO_USER}:{TAPO_PASSWORD}"
        f"@{TAPO_HOST}:{TAPO_RTSP_PORT}/{TAPO_STREAM}"
    )
