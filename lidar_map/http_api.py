"""HTTP API + static web UI for the drive/map console."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from typing import Any

from config import WEB_UI_PATH
from logutil import get_logger

log = get_logger("http")

_HTML_CACHE: bytes | None = None


def load_html() -> bytes:
    global _HTML_CACHE
    if _HTML_CACHE is None:
        _HTML_CACHE = WEB_UI_PATH.read_text(encoding="utf-8").encode("utf-8")
        log.info("web UI loaded (%s bytes) from %s", len(_HTML_CACHE), WEB_UI_PATH)
    return _HTML_CACHE


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
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            # Access log → file only (avoid flooding stdout)
            log.debug("http " + fmt, *args)

        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                body = load_html()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if path.startswith("/api/scan"):
                send_json(self, bridge.snapshot())
                return
            self.send_error(404)

        def do_POST(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
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
