# Airport visitor monitor (10.1″ kiosk)

Touchscreen interface for the Kazan airport assistance robot: animated sky opening,
multilingual wayfinding, ticket scan, and safe escort to calibrated destinations.

Optimized for **1280×800** landscape (10.1-inch monitor). Also works in portrait.

## Contents

| Path | Purpose |
|---|---|
| `airport_ui.html` | Full kiosk UI (attract screen, services, ticket scan, escort) |
| `airport_service.py` | Destination config + SQLite ticket lookup |
| `assets/` | Sky, clouds, Kazan airport logo, aircraft sprites |
| `test_airport_*.py` | Unit tests |
| `AIRPORT_KIOSK.md` | Deployment and configuration |
| `integration/lidar_map/` | Robot stack hooks (`http_api`, `config`, `bridge`, `main`) |

## Languages

Russian, English, Chinese (中文), Tatar (Татарча).

## Quick preview

From the repo root:

```bash
cd monitor
python3 -m http.server 8877
```

Open `http://127.0.0.1:8877/airport_ui.html`

For full robot integration (navigation, ticket API, escort), run the lidar stack
with the files in `integration/lidar_map/` merged into `lidar_map/` — see
`AIRPORT_KIOSK.md`.

## Tests

```bash
python3 -m unittest discover -s monitor -p "test_airport*.py" -v
```
