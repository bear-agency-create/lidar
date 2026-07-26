"""HTTP API + static web UI for the drive/map console."""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler
from typing import Any
from urllib.parse import urlsplit

from airport_service import AirportService
from config import (
    AIRPORT_DESTINATIONS_PATH,
    AIRPORT_KIOSK_ALLOWED_CLIENTS,
    AIRPORT_TICKETS_DB_PATH,
    AIRPORT_UI_PATH,
    PRIMARY_BUTTONS_PATH,
    WEB_UI_PATH,
)
from logutil import get_logger

log = get_logger("http")

_HTML_CACHE: dict[str, bytes] = {}
_ASSET_CACHE: dict[str, bytes] = {}
_AIRPORT_ASSETS = {
    "/assets/kazan-sky-attract.png": AIRPORT_UI_PATH.parent / "assets" / "kazan-sky-attract.png",
    "/assets/kazan-sky-clear.png": AIRPORT_UI_PATH.parent / "assets" / "kazan-sky-clear.png",
    "/assets/kazan-clouds-left.png": AIRPORT_UI_PATH.parent / "assets" / "kazan-clouds-left.png",
    "/assets/kazan-clouds-right.png": AIRPORT_UI_PATH.parent / "assets" / "kazan-clouds-right.png",
    "/assets/realistic-airliner-top.png": AIRPORT_UI_PATH.parent / "assets" / "realistic-airliner-top.png",
    "/assets/realistic-airliner-symmetric.png": AIRPORT_UI_PATH.parent / "assets" / "realistic-airliner-symmetric.png",
    "/assets/realistic-airliner-balanced.png": AIRPORT_UI_PATH.parent / "assets" / "realistic-airliner-balanced.png",
    "/assets/kazan-airport-logo-white.png": AIRPORT_UI_PATH.parent / "assets" / "kazan-airport-logo-white.png",
}


class KioskNavigationSession:
    """Fail-safe lease for visitor-initiated robot navigation."""

    def __init__(self, bridge, lease_seconds: float = 6.0) -> None:
        self.bridge = bridge
        self.lease_seconds = lease_seconds
        self._lock = threading.Lock()
        self._destination_id: str | None = None
        self._heartbeat = 0.0
        threading.Thread(
            target=self._watchdog,
            daemon=True,
            name="kiosk-navigation-watchdog",
        ).start()

    def start(self, destination_id: str) -> None:
        with self._lock:
            self._destination_id = destination_id
            self._heartbeat = time.monotonic()

    def heartbeat(self) -> dict[str, Any]:
        with self._lock:
            if self._destination_id is None:
                return {"ok": False, "error": "no_active_escort"}
            self._heartbeat = time.monotonic()
            return {"ok": True, "destinationId": self._destination_id}

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "ok": True,
                "active": self._destination_id is not None,
                "destinationId": self._destination_id,
            }

    def finish(self) -> None:
        with self._lock:
            self._destination_id = None
            self._heartbeat = 0.0

    def _watchdog(self) -> None:
        while True:
            time.sleep(1.0)
            expired = False
            with self._lock:
                if (
                    self._destination_id is not None
                    and time.monotonic() - self._heartbeat > self.lease_seconds
                ):
                    self._destination_id = None
                    self._heartbeat = 0.0
                    expired = True
            if expired:
                log.error("kiosk navigation lease expired — stopping robot")
                try:
                    self.bridge.stop_cmd()
                except Exception:  # noqa: BLE001
                    log.exception("failed to stop robot after kiosk lease expiry")


def load_html(path) -> bytes:
    key = str(path)
    if key not in _HTML_CACHE:
        _HTML_CACHE[key] = path.read_text(encoding="utf-8").encode("utf-8")
        log.info("web UI loaded (%s bytes) from %s", len(_HTML_CACHE[key]), path)
    return _HTML_CACHE[key]


def load_asset(path) -> bytes:
    key = str(path)
    if key not in _ASSET_CACHE:
        _ASSET_CACHE[key] = path.read_bytes()
    return _ASSET_CACHE[key]


def read_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    if not raw:
        return {}
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def send_json(handler: BaseHTTPRequestHandler, payload: dict[str, Any], code: int = 200) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def make_handler(bridge):
    airport = AirportService(
        AIRPORT_DESTINATIONS_PATH,
        AIRPORT_TICKETS_DB_PATH,
        PRIMARY_BUTTONS_PATH,
    )
    kiosk_navigation = KioskNavigationSession(bridge)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            # Access log → file only (avoid flooding stdout)
            log.debug("http " + fmt, *args)

        def _allow_kiosk_control(self) -> bool:
            client_ip = str(self.client_address[0])
            origin = self.headers.get("Origin")
            host = self.headers.get("Host", "")
            origin_allowed = not origin or urlsplit(origin).netloc == host
            if client_ip in AIRPORT_KIOSK_ALLOWED_CLIENTS and origin_allowed:
                return True
            send_json(self, {"ok": False, "error": "kiosk_access_denied"}, 403)
            log.warning("blocked control request from %s origin=%s", client_ip, origin or "-")
            return False

        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html", "/kiosk"):
                body = load_html(AIRPORT_UI_PATH)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if path in _AIRPORT_ASSETS:
                body = load_asset(_AIRPORT_ASSETS[path])
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "public, max-age=86400")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if path in ("/operator", "/operator.html"):
                if not self._allow_kiosk_control():
                    return
                body = load_html(WEB_UI_PATH)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if path == "/api/airport/destinations":
                send_json(self, airport.public_destinations())
                return
            if path == "/api/airport/status":
                if not self._allow_kiosk_control():
                    return
                send_json(self, kiosk_navigation.status())
                return
            if path.startswith("/api/scan"):
                if not self._allow_kiosk_control():
                    return
                snapshot = bridge.snapshot()
                if kiosk_navigation.status()["active"] and not snapshot.get("goal"):
                    kiosk_navigation.finish()
                send_json(self, snapshot)
                return
            self.send_error(404)

        def do_POST(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            try:
                content_length = int(self.headers.get("Content-Length", "0") or "0")
            except ValueError:
                send_json(self, {"ok": False, "error": "invalid_content_length"}, 400)
                return
            if content_length < 0 or content_length > 16_384:
                send_json(self, {"ok": False, "error": "request_too_large"}, 413)
                return
            if not self._allow_kiosk_control():
                return
            if path.startswith("/api/cmd/stop"):
                send_json(self, bridge.stop_cmd())
                return
            if path.startswith("/api/cmd"):
                data = read_json_body(self)
                try:
                    vx = float(data.get("vx", 0.0))
                    vy = float(data.get("vy", 0.0))
                    w = float(data.get("w", 0.0))
                except (TypeError, ValueError):
                    send_json(self, {"ok": False, "error": "bad cmd"}, 400)
                    return
                send_json(self, bridge.set_cmd(vx, vy, w))
                return
            if path == "/api/ticket/lookup":
                data = read_json_body(self)
                result = airport.lookup_ticket(data.get("code"))
                send_json(self, result, 200 if result.get("ok") else 404)
                return
            if path == "/api/escort/cancel":
                result = bridge.stop_cmd()
                if result.get("ok"):
                    kiosk_navigation.finish()
                send_json(self, result)
                return
            if path == "/api/escort/heartbeat":
                result = kiosk_navigation.heartbeat()
                send_json(self, result, 200 if result.get("ok") else 409)
                return
            if path == "/api/escort":
                data = read_json_body(self)
                destination_id = str(data.get("destinationId", "")).strip()
                destination = airport.get_destination(destination_id)
                if destination is None:
                    send_json(
                        self,
                        {"ok": False, "error": "destination_not_configured"},
                        404,
                    )
                    return
                result = bridge.set_goal(destination.x, destination.y)
                if result.get("ok"):
                    result["destinationId"] = destination.id
                    kiosk_navigation.start(destination.id)
                send_json(self, result, 200 if result.get("ok") else 409)
                return
            if path.startswith("/api/clear"):
                send_json(self, bridge.clear_map())
                return
            if path.startswith("/api/save"):
                send_json(self, bridge.save_map())
                return
            if path.startswith("/api/freeze"):
                data = read_json_body(self)
                send_json(self, bridge.set_frozen(bool(data.get("frozen", True))))
                return
            if path.startswith("/api/goal"):
                data = read_json_body(self)
                try:
                    gx = float(data.get("x", 0.0))
                    gy = float(data.get("y", 0.0))
                except (TypeError, ValueError):
                    send_json(self, {"ok": False, "error": "bad goal"}, 400)
                    return
                send_json(self, bridge.set_goal(gx, gy))
                return
            self.send_error(404)

    return Handler
