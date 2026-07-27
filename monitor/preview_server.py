#!/usr/bin/env python3
"""Local kiosk preview: UI + ticket lookup without ROS/lidar_map."""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 8877
TICKET_CODE_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")

DEMO_TICKETS: dict[str, dict[str, Any]] = {
    "KZzKQhLbySCrKtkfNh9xSD2Q": {
        "passengerName": "Ivanov Alexey",
        "flight": "SU1245",
        "departureTime": "08:40",
        "checkIn": "A03",
        "gate": "12",
        "destinationId": "check-in-a",
        "canEscort": False,
    },
    "KZnbU6xaJONFbGzCxQ-B6u_w": {
        "passengerName": "Petrova Maria",
        "flight": "FZ991",
        "departureTime": "11:15",
        "checkIn": "B07",
        "gate": "18",
        "destinationId": "check-in-a",
        "canEscort": False,
    },
    "KZwcE-kMAIppgkb-OFjxWuNA": {
        "passengerName": "Chen Wei",
        "flight": "CZ3602",
        "departureTime": "14:05",
        "checkIn": "C02",
        "gate": "5",
        "destinationId": "check-in-a",
        "canEscort": False,
    },
    "KZ6kWBB_W8PPYxZM1cFxarTQ": {
        "passengerName": "Karimova Aliya",
        "flight": "U62214",
        "departureTime": "16:50",
        "checkIn": "A11",
        "gate": "9",
        "destinationId": "check-in-a",
        "canEscort": False,
    },
    "KZaXTLNCGPD9Ynmf9hH_zMHw": {
        "passengerName": "John Smith",
        "flight": "TK1470",
        "departureTime": "19:25",
        "checkIn": "D01",
        "gate": "22",
        "destinationId": "check-in-a",
        "canEscort": False,
    },
}

DEMO_DESTINATIONS = {
    "ok": True,
    "configured": False,
    "destinations": [
        {"id": "check-in", "kind": "check-in", "enabled": False, "zone": "", "labels": {}, "descriptions": {}},
        {"id": "gates", "kind": "gates", "enabled": False, "zone": "", "labels": {}, "descriptions": {}},
        {"id": "baggage", "kind": "baggage", "enabled": False, "zone": "", "labels": {}, "descriptions": {}},
        {"id": "places", "kind": "places", "enabled": False, "zone": "", "labels": {}, "descriptions": {}},
        {"id": "information", "kind": "information", "enabled": False, "zone": "", "labels": {}, "descriptions": {}},
        {"id": "exit", "kind": "exit", "enabled": False, "zone": "", "labels": {}, "descriptions": {}},
    ],
}


def ticket_db_paths() -> list[Path]:
    return [
        ROOT / "data" / "airport_tickets.sqlite3",
        Path.home() / "robot_nav" / "data" / "airport_tickets.sqlite3",
    ]


def normalize_ticket_code(value: Any) -> str:
    code = str(value or "").strip()
    return code if TICKET_CODE_RE.fullmatch(code) else ""


def lookup_ticket(raw_code: Any) -> dict[str, Any]:
    code = normalize_ticket_code(raw_code)
    if not code:
        return {"ok": False, "error": "empty_ticket_code"}

    for path in ticket_db_paths():
        if not path.is_file():
            continue
        try:
            with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
                db.row_factory = sqlite3.Row
                row = db.execute(
                    """
                    SELECT passenger_name, flight, departure_time, check_in,
                           gate, destination_id, status
                    FROM tickets
                    WHERE code = ?
                    LIMIT 1
                    """,
                    (code,),
                ).fetchone()
        except sqlite3.Error:
            continue
        if row is None:
            continue
        status = str(row["status"] or "").lower()
        if status not in {"valid", "checked-in", "boarding"}:
            return {"ok": False, "error": "ticket_not_active"}
        return {
            "ok": True,
            "ticket": {
                "passengerName": str(row["passenger_name"] or ""),
                "flight": str(row["flight"] or ""),
                "departureTime": str(row["departure_time"] or ""),
                "checkIn": str(row["check_in"] or ""),
                "gate": str(row["gate"] or ""),
                "destinationId": str(row["destination_id"] or ""),
                "canEscort": False,
            },
        }

    demo = DEMO_TICKETS.get(code)
    if demo:
        return {"ok": True, "ticket": dict(demo)}
    return {"ok": False, "error": "ticket_not_found"}


class PreviewHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def do_GET(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path in {"/", "/index.html", "/kiosk"}:
            self.path = "/airport_ui.html"
            return super().do_GET()
        if path == "/api/airport/destinations":
            return self._send_json(DEMO_DESTINATIONS)
        if path == "/api/airport/status":
            return self._send_json({"ok": True, "online": True, "preview": True})
        if path == "/api/scan":
            return self._send_json({"ok": True, "preview": True, "navigating": False})
        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path == "/api/ticket/lookup":
            data = self._read_json()
            result = lookup_ticket(data.get("code"))
            status = 200 if result.get("ok") else 404
            return self._send_json(result, status=status)
        if path in {"/api/escort", "/api/escort/cancel", "/api/escort/heartbeat"}:
            return self._send_json({"ok": True, "preview": True, "message": "preview_only"})
        self.send_error(404, "Not found")


def main() -> None:
    httpd = ThreadingHTTPServer((HOST, PORT), PreviewHandler)
    print(f"Airport kiosk preview: http://{HOST}:{PORT}/", flush=True)
    print("Ticket lookup + destinations API enabled (no ROS).", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)


if __name__ == "__main__":
    main()
