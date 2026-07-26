# Smart Camera

Зона ответственности: **`camera/`** (рядом `arduino/`, `lidar_map/`).

## Файлы

| Файл | Роль |
|------|------|
| `main.py` | цикл запуска |
| `vision.py` | USB/RTSP, YuNet, трек, digital center |
| `config.py` | настройки / `.env` |
| `ptz.py` | pan/tilt Tapo (позже) |
| `models/` | YuNet ONNX |

## Запуск (USB)

```bash
cd camera
pip install -r requirements.txt
python main.py
```

`CAMERA_INDEX=1` по умолчанию. Не та камера → `0` в `.env`.  
Выход: `q` / `Esc`.
