# Airport visitor kiosk

The visitor interface is served at `/kiosk`. The map and teleoperation
console is the default page at `/` (also `/operator`).

## Local preview (Windows / no ROS)

From the `monitor/` folder:

```bash
python preview_server.py
```

Open **http://127.0.0.1:8877/** — the UI loads at `/`, ticket lookup and
destination stubs work without `lidar_map`. Sample ticket codes are in
`monitor/data/sample_ticket_codes.txt`.

The layout is optimized for a 10.1-inch, 1280×800 landscape touchscreen and
also adapts to portrait orientation.

**Scan ticket** opens a camera preview and tries to read the barcode with the
browser `BarcodeDetector` API (Chromium/Chrome). You can also type the code
manually in the same dialog. A USB/HID wedge scanner still works as a
keyboard: focus the input, scan, and Enter submits.

Ticket lookup and robot escort endpoints accept requests from the robot itself
only (`127.0.0.1` and `::1` by default). If the kiosk browser runs on a separate
locked-down device, set `AIRPORT_KIOSK_ALLOWED_CLIENTS` to its fixed IP address
before starting the server. Use a comma-separated list; do not expose these
endpoints to the public airport network.

All operator and motion endpoints use the same allowlist. Visitor escort runs
under a short browser heartbeat lease: if the kiosk page closes, reloads for
too long, or loses connection, the backend stops the robot automatically.

## Calibrated destinations

By default, the service reads:

`~/robot_nav/config/airport_destinations.json`

Override the path with `AIRPORT_DESTINATIONS_PATH`. Each `x` and `y` must be a
measured coordinate in the same world frame as the robot's saved occupancy
map. The kiosk never starts navigation to an uncalibrated destination.

```json
{
  "destinations": [
    {
      "id": "check-in-a",
      "kind": "check-in",
      "x": "MEASURED_X_METERS",
      "y": "MEASURED_Y_METERS",
      "zone": "A",
      "labels": {
        "ru": "Регистрация A",
        "en": "Check-in A",
        "zh": "A区值机",
        "tt": "А теркәлүе"
      },
      "descriptions": {
        "ru": "Зал вылета, стойки A01–A12",
        "en": "Departures hall, desks A01–A12",
        "zh": "出发大厅，A01–A12柜台",
        "tt": "Очып китү залы, A01–A12 өстәлләре"
      }
    }
  ]
}
```

The template coordinates are intentionally invalid; replace both with measured
JSON numbers before deployment. Invalid configuration fails closed and leaves
the escort action unavailable.

Supported `kind` values are `check-in`, `gates`, `baggage`, `toilet`,
`information`, and `exit`.

## Ticket database

Tickets are stored in a JSON file:

`monitor/data/tickets.json`

Edit them via the admin panel:

```bash
cd admin_panel
./start.sh
```

Open `http://127.0.0.1:8878/` (password from `ADMIN_PASSWORD`, default `admin`).
The kiosk preview reads the same file on `/api/ticket/lookup`.

Each ticket:

```json
{
  "code": "KZzKQhLbySCrKtkfNh9xSD2Q",
  "passengerName": "Ivanov Alexey",
  "flight": "SU1245",
  "departureTime": "08:40",
  "checkIn": "A03",
  "gate": "12",
  "destinationId": "check-in",
  "status": "valid"
}
```

`destination_id` / `destinationId` should match a calibrated destination when escort is enabled.
Accepted ticket statuses are `valid`, `checked-in`, and `boarding`. The browser receives flight details,
but never receives map coordinates.

