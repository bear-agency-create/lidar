#!/usr/bin/env python3
"""Local admin panel launcher with reverse-proxy to the robot API."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PANEL = ROOT / "operator_panel.html"
ROBOT = os.environ.get("ROBOT_API", "http://10.255.210.201:8765").rstrip("/")
HOST = os.environ.get("ADMIN_HOST", "127.0.0.1")
PORT = int(os.environ.get("ADMIN_PORT", "8878"))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("admin " + (fmt % args) + "\n")

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in {"/", "/admin", "/operator-panel", "/panel", "/admin-panel"}:
            html = PANEL.read_text(encoding="utf-8")
            # Inject robot base so relative fetch() still hits this proxy.
            inject = (
                "<script>window.ADMIN_ROBOT="
                + json.dumps(ROBOT)
                + ";</script>"
            )
            html = html.replace("</head>", inject + "</head>", 1)
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
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                body = resp.read()
                ctype = resp.headers.get("Content-Type", "application/json")
                return self._send(resp.status, body, ctype)
        except urllib.error.HTTPError as exc:
            body = exc.read()
            ctype = exc.headers.get("Content-Type", "application/json") if exc.headers else "application/json"
            return self._send(exc.code, body or str(exc).encode(), ctype)
        except Exception as exc:  # noqa: BLE001
            payload = json.dumps({"ok": False, "error": "robot_unreachable", "detail": str(exc), "robot": ROBOT}).encode()
            return self._send(502, payload, "application/json")


def main() -> None:
    if not PANEL.is_file():
        raise SystemExit(f"missing {PANEL}")
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}/admin"
    print(f"Admin panel: {url}", flush=True)
    print(f"Proxy → {ROBOT}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
