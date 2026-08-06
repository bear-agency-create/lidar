#!/usr/bin/env python3
"""Local admin panel for the laptop: serves UI + reverse-proxies the robot API/map/kiosk."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PANEL = ROOT / "operator_panel.html"
ROBOT = os.environ.get("ROBOT_API", "http://10.255.210.201:8765").rstrip("/")
HOST = os.environ.get("ADMIN_HOST", "127.0.0.1")
PORT = int(os.environ.get("ADMIN_PORT", "8878"))
OPEN_BROWSER = os.environ.get("ADMIN_OPEN", "1") not in {"0", "false", "no"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("admin " + (fmt % args) + "\n")

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in {"/", "/admin", "/operator-panel", "/panel", "/admin-panel"}:
            html = PANEL.read_text(encoding="utf-8")
            # Same-origin relative /api /map /kiosk → this proxy (do not inject ADMIN_ROBOT).
            return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
        return self._proxy("GET")

    def do_POST(self) -> None:  # noqa: N802
        return self._proxy("POST")

    def _proxy(self, method: str) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length > 0 else b""
        url = ROBOT + self.path
        req = urllib.request.Request(url, data=raw if method == "POST" else None, method=method)
        if method == "POST":
            req.add_header("Content-Type", self.headers.get("Content-Type", "application/json"))
        # Do not forward browser Origin — robot used to 403 Origin:null / proxy origins.
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                body = resp.read()
                ctype = resp.headers.get("Content-Type", "application/octet-stream")
                return self._send(resp.status, body, ctype)
        except urllib.error.HTTPError as exc:
            body = exc.read()
            ctype = exc.headers.get("Content-Type", "application/json") if exc.headers else "application/json"
            return self._send(exc.code, body or str(exc).encode(), ctype)
        except Exception as exc:  # noqa: BLE001
            payload = json.dumps(
                {"ok": False, "error": "robot_unreachable", "detail": str(exc), "robot": ROBOT}
            ).encode()
            return self._send(502, payload, "application/json")


def main() -> None:
    if not PANEL.is_file():
        raise SystemExit(f"missing {PANEL}")
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}/admin"
    print(f"Admin panel: {url}", flush=True)
    print(f"Map:         http://{HOST}:{PORT}/map", flush=True)
    print(f"Proxy → {ROBOT}", flush=True)
    if OPEN_BROWSER:
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001
            pass
    httpd.serve_forever()


if __name__ == "__main__":
    main()
