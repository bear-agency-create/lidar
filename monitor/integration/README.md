# Robot stack integration

These files are copies of the `lidar_map` modules that wire the monitor into
the live robot server on port **8765**.

When deploying on the Pi, ensure `lidar_map/config.py` points `AIRPORT_UI_PATH`
at `../monitor/airport_ui.html` (already set in the repo). Copy or sync
`airport_service.py` into `lidar_map/` so `http_api.py` can import it.

The visitor kiosk is served at `/`. Operator teleop remains at `/operator`.
