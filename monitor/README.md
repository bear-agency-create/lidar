# Monitor — экран 10.1″ для пассажира

Четвёртое направление робота рядом с `arduino/`, `lidar_map/` и `camera/`.

Сенсорный интерфейс аэропорта Казань: небо при старте, 6 главных кнопок,
скан билета, проводка роботом.

## 6 главных кнопок

Порядок и состав задаются в **`primary_buttons.json`** — можно менять когда угодно,
без правки HTML:

```json
{
  "buttons": [
    {"id": "check-in", "kind": "check-in"},
    {"id": "gates", "kind": "gates"},
    {"id": "baggage", "kind": "baggage"},
    {"id": "places", "kind": "places"},
    {"id": "information", "kind": "information"},
    {"id": "exit", "kind": "exit"}
  ]
}
```

По умолчанию на экране:

| Кнопка | Назначение |
|--------|------------|
| Регистрация | стойки check-in |
| Багаж | выдача / приём багажа |
| Информация | стойка помощи |
| Выход | выход из терминала |

Координаты для проводки робота — в `~/robot_nav/config/airport_destinations.json`
(см. `AIRPORT_KIOSK.md`).

## Содержимое

| Файл | Назначение |
|------|------------|
| `airport_ui.html` | интерфейс киоска |
| `airport_service.py` | билеты + точки назначения |
| `primary_buttons.json` | **6 главных кнопок (редактируемые)** |
| `assets/` | небо, облака, логотип, самолёт |
| `AIRPORT_KIOSK.md` | настройка на роботе |

## Превью

```bash
cd monitor
python3 preview_server.py
```

Открыть: `http://127.0.0.1:8877/`

`preview_server.py` поднимает не только UI, но и API:
- `/api/map/preview` для карты регистрации,
- `/api/ticket/lookup` для билетов,
- `/api/airport/*` для статуса/кнопок.

Карта регистрации берётся из:
1. `monitor/data/remembered_occupancy.json` (локальный приоритет),
2. `~/robot_nav/maps/remembered_occupancy.json`,
3. fallback на demo-карту.

UI автоматически масштабируется под размер экрана устройства и включает облегчённый режим эффектов на слабом железе.

На роботе интерфейс отдаётся с `:8765/` через `lidar_map/` (см. `AIRPORT_KIOSK.md`).

## Тесты

```bash
python3 -m unittest discover -s monitor -p "test_airport*.py" -v
```
