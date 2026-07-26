# Airport visitor kiosk

The visitor interface is served at `/`. The existing map and teleoperation
console remains available at `/operator`.

The layout is optimized for a 10.1-inch, 1280×800 landscape touchscreen and
also adapts to portrait orientation. A USB/serial barcode scanner can operate
as a keyboard: tap **Scan ticket**, scan the barcode, and the scanner's Enter
key submits it.

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

The default read-only SQLite database is:

`~/robot_nav/data/airport_tickets.sqlite3`

Override it with `AIRPORT_TICKETS_DB_PATH`. The integration expects:

```sql
CREATE TABLE tickets (
    code TEXT PRIMARY KEY,
    passenger_name TEXT,
    flight TEXT,
    departure_time TEXT,
    check_in TEXT,
    gate TEXT,
    destination_id TEXT,
    status TEXT
);
```

`destination_id` must match a calibrated destination. Accepted ticket statuses
are `valid`, `checked-in`, and `boarding`. The browser receives flight details,
but never receives map coordinates.

