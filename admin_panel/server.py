#!/usr/bin/env python3
"""Ticket admin panel: CRUD + barcode preview against monitor/data/tickets.json."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
MONITOR_ROOT = REPO_ROOT / "monitor"
HOST = "127.0.0.1"
PORT = int(os.environ.get("ADMIN_PORT", "8878"))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")
SESSION_TTL_SEC = 60 * 60 * 12
COOKIE_NAME = "ticket_admin_session"

if str(MONITOR_ROOT) not in sys.path:
    sys.path.insert(0, str(MONITOR_ROOT))

from ticket_store import (  # noqa: E402
    delete_ticket,
    ensure_store,
    generate_ticket_code,
    list_tickets,
    tickets_path,
    upsert_ticket,
)

_sessions: dict[str, float] = {}


def _clean_sessions(now: float | None = None) -> None:
    current = time.time() if now is None else now
    expired = [token for token, expires in _sessions.items() if expires <= current]
    for token in expired:
        _sessions.pop(token, None)


def _issue_session() -> str:
    _clean_sessions()
    token = secrets.token_urlsafe(32)
    _sessions[token] = time.time() + SESSION_TTL_SEC
    return token


def _session_valid(token: str | None) -> bool:
    if not token:
        return False
    _clean_sessions()
    expires = _sessions.get(token)
    if expires is None:
        return False
    if expires <= time.time():
        _sessions.pop(token, None)
        return False
    _sessions[token] = time.time() + SESSION_TTL_SEC
    return True


def _password_ok(password: str) -> bool:
    expected = ADMIN_PASSWORD.encode("utf-8")
    got = str(password or "").encode("utf-8")
    digest = hashlib.sha256(got).digest()
    expected_digest = hashlib.sha256(expected).digest()
    return hmac.compare_digest(digest, expected_digest)


class AdminHandler(SimpleHTTPRequestHandler):
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

    def _cookie_token(self) -> str | None:
        raw = self.headers.get("Cookie") or ""
        if not raw:
            return None
        cookie = SimpleCookie()
        try:
            cookie.load(raw)
        except Exception:
            return None
        morsel = cookie.get(COOKIE_NAME)
        return morsel.value if morsel else None

    def _authenticated(self) -> bool:
        return _session_valid(self._cookie_token())

    def _set_session_cookie(self, token: str) -> None:
        self.send_header(
            "Set-Cookie",
            f"{COOKIE_NAME}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_TTL_SEC}",
        )

    def _clear_session_cookie(self) -> None:
        self.send_header(
            "Set-Cookie",
            f"{COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0",
        )

    def _require_auth(self) -> bool:
        if self._authenticated():
            return True
        self._send_json({"ok": False, "error": "unauthorized"}, status=401)
        return False

    def do_GET(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path in {"/", "/index.html"}:
            self.path = "/index.html"
            return super().do_GET()
        if path.startswith("/vendor/"):
            return super().do_GET()
        if path == "/api/health":
            return self._send_json(
                {
                    "ok": True,
                    "ticketsPath": str(tickets_path()),
                    "authenticated": self._authenticated(),
                }
            )
        if path == "/api/session":
            return self._send_json({"ok": True, "authenticated": self._authenticated()})
        if path == "/api/tickets":
            if not self._require_auth():
                return
            tickets = list_tickets()
            tickets.sort(key=lambda item: str(item.get("updatedAt") or ""), reverse=True)
            return self._send_json({"ok": True, "tickets": tickets, "path": str(tickets_path())})
        if path == "/api/tickets/new-code":
            if not self._require_auth():
                return
            return self._send_json({"ok": True, "code": generate_ticket_code()})
        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        data = self._read_json()

        if path == "/api/login":
            if not _password_ok(str(data.get("password") or "")):
                return self._send_json({"ok": False, "error": "invalid_password"}, status=401)
            token = _issue_session()
            body = json.dumps({"ok": True}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self._set_session_cookie(token)
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/logout":
            token = self._cookie_token()
            if token:
                _sessions.pop(token, None)
            body = json.dumps({"ok": True}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self._clear_session_cookie()
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/tickets":
            if not self._require_auth():
                return
            result = upsert_ticket(data)
            status = 200 if result.get("ok") else 400
            return self._send_json(result, status=status)

        self.send_error(404, "Not found")

    def do_PUT(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path == "/api/tickets":
            if not self._require_auth():
                return
            result = upsert_ticket(self._read_json())
            status = 200 if result.get("ok") else 400
            return self._send_json(result, status=status)
        self.send_error(404, "Not found")

    def do_DELETE(self) -> None:  # noqa: N802
        parts = urlsplit(self.path)
        path = parts.path
        if path.startswith("/api/tickets/"):
            if not self._require_auth():
                return
            code = unquote(path[len("/api/tickets/") :])
            if not code:
                query = parse_qs(parts.query)
                code = (query.get("code") or [""])[0]
            result = delete_ticket(code)
            status = 200 if result.get("ok") else 404
            return self._send_json(result, status=status)
        self.send_error(404, "Not found")


def main() -> None:
    store = ensure_store()
    httpd = ThreadingHTTPServer((HOST, PORT), AdminHandler)
    print(f"Ticket admin: http://{HOST}:{PORT}/", flush=True)
    print(f"Tickets file: {store}", flush=True)
    print("Login password: env ADMIN_PASSWORD (default: admin)", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)


if __name__ == "__main__":
    main()
