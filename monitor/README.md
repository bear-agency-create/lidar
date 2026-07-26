# Monitor — экран 10.1″ для пассажира

Четвёртое направление робота рядом с `arduino/`, `lidar_map/` и `camera/`.

Сенсорный интерфейс аэропорта Казань: небо при старте, 4 главные кнопки,
скан билета, проводка роботом.

## 4 главные кнопки

Порядок и состав задаются в **`primary_buttons.json`** — можно менять когда угодно,
без правки HTML:

```json
{
  "buttons": [
    {"id": "check-in", "kind": "check-in"},
    {"id": "baggage", "kind": "baggage"},
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
| `primary_buttons.json` | **4 главные кнопки (редактируемые)** |
| `assets/` | небо, облака, логотип, самолёт |
| `AIRPORT_KIOSK.md` | настройка на роботе |

## Превью

```bash
cd monitor
python3 -m http.server 8877
```

Открыть: `http://127.0.0.1:8877/airport_ui.html`

На роботе интерфейс отдаётся с `:8765/` через `lidar_map/` (см. `AIRPORT_KIOSK.md`).

## Тесты

```bash
python3 -m unittest discover -s monitor -p "test_airport*.py" -v
```
