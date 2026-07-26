# Smart Camera

Отдельное направление: `arduino/` · `lidar_map/` · **`camera/`**

## Сейчас: USB webcam + YuNet

По умолчанию: USB (`CAMERA_INDEX=1`), детект **OpenCV YuNet** (не Haar).

```bash
cd camera
pip install -r requirements.txt
python main.py
```

- Зелёная рамка + точки глаз/носа/рта, score на рамке.
- **Digital center** — лицо держится в центре кадра.
- Выход: `q` / `Esc`.
- Не та камера → в `.env` смени `CAMERA_INDEX` (`0` или `1`).
- Слишком мало детектов → `FACE_DETECT_SCORE=0.45`.

## Позже: Tapo C200

```env
CAMERA_SOURCE=rtsp
TAPO_HOST=...
TAPO_USER=...
TAPO_PASSWORD=...
CAMERA_DRY_RUN=0
CAMERA_DIGITAL_CENTER=0
```

## Файлы

| Файл | Роль |
|------|------|
| `main.py` | цикл детекта / трека |
| `stream.py` | USB + RTSP |
| `face_detect.py` | Haar faces |
| `proximity.py` | близко / приближается |
| `tracker.py` | lock + offset |
| `digital_center.py` | цифровое удержание центра (USB) |
| `ptz.py` | pan/tilt Tapo (позже) |
