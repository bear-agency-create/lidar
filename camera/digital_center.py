"""Цифровое центрирование: сдвиг кадра так, чтобы лицо оказалось в центре (USB)."""

from __future__ import annotations

import cv2
import numpy as np

from face_detect import FaceBox


def digital_center_view(
    frame: np.ndarray,
    face: FaceBox | None,
    *,
    smooth: float = 0.35,
    state: dict | None = None,
) -> tuple[np.ndarray, FaceBox | None, dict]:
    """
    Возвращает (кадр_со_сдвигом, лицо_в_новых_координатах, state).
    Размер кадра не меняется — края добиваются BORDER_REPLICATE.
    """
    h, w = frame.shape[:2]
    st = state if state is not None else {}
    target_cx = float(face.cx) if face is not None else w * 0.5
    target_cy = float(face.cy) if face is not None else h * 0.5
    cx = float(st.get("cx", target_cx))
    cy = float(st.get("cy", target_cy))
    cx = cx * (1.0 - smooth) + target_cx * smooth
    cy = cy * (1.0 - smooth) + target_cy * smooth
    st["cx"], st["cy"] = cx, cy

    # насколько сдвинуть исходник, чтобы (cx,cy) попал в центр
    shift_x = int(round(w * 0.5 - cx))
    shift_y = int(round(h * 0.5 - cy))

    M = np.float32([[1, 0, shift_x], [0, 1, shift_y]])
    out = cv2.warpAffine(
        frame,
        M,
        (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
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
