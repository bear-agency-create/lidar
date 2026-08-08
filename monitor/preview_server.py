#!/usr/bin/env python3
"""Local kiosk preview: UI + ticket lookup without ROS/lidar_map."""

from __future__ import annotations

import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 8877

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from map_route import build_route_preview  # noqa: E402
from ticket_store import (  # noqa: E402
    ensure_store,
    lookup_ticket as store_lookup_ticket,
    tickets_path,
)

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


def lookup_ticket(raw_code: Any) -> dict[str, Any]:
    ensure_store(tickets_path())
    return store_lookup_ticket(raw_code, tickets_path(), mark_scanned=True)


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
        if path == "/api/map/preview":
            query = parse_qs(urlsplit(self.path).query)
            seed_raw = (query.get("seed") or [None])[0]
            seed = int(seed_raw) if seed_raw and str(seed_raw).lstrip("-").isdigit() else None
            result = build_route_preview(seed=seed)
            status = 200 if result.get("ok") else 404
            return self._send_json(result, status=status)
        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path == "/api/ticket/lookup":
            data = self._read_json()
            result = lookup_ticket(data.get("code"))
            status = 200 if result.get("ok") else 404
            return self._send_json(result, status=status)
        if path in {"/api/escort", "/api/escort/cancel", "/api/escort/heartbeat", "/api/cmd/stop"}:
            return self._send_json({"ok": True, "preview": True, "message": "preview_only"})
        self.send_error(404, "Not found")


def main() -> None:
    store = ensure_store()
    httpd = ThreadingHTTPServer((HOST, PORT), PreviewHandler)
    print(f"Airport kiosk preview: http://{HOST}:{PORT}/", flush=True)
    print(f"Tickets file: {store}", flush=True)
    print("Ticket lookup + destinations API enabled (no ROS).", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)


if __name__ == "__main__":
    main()
