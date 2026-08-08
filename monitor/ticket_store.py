"""File-backed ticket store (JSON). Shared by kiosk preview and admin panel."""

from __future__ import annotations

import json
import re
import secrets
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TICKET_CODE_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
ACTIVE_STATUSES = frozenset({"valid", "checked-in", "boarding"})
ALLOWED_STATUSES = frozenset({"valid", "checked-in", "boarding", "cancelled", "used"})

MONITOR_ROOT = Path(__file__).resolve().parent
DEFAULT_TICKETS_PATH = MONITOR_ROOT / "data" / "tickets.json"

_lock = threading.RLock()

SEED_TICKETS: list[dict[str, Any]] = [
    {
        "code": "KZzKQhLbySCrKtkfNh9xSD2Q",
        "passengerName": "Ivanov Alexey",
        "flight": "SU1245",
        "departureTime": "08:40",
        "checkIn": "A03",
        "gate": "12",
        "destinationId": "check-in",
        "status": "valid",
    },
    {
        "code": "KZnbU6xaJONFbGzCxQ-B6u_w",
        "passengerName": "Petrova Maria",
        "flight": "FZ991",
        "departureTime": "11:15",
        "checkIn": "B07",
        "gate": "18",
        "destinationId": "check-in",
        "status": "valid",
    },
    {
        "code": "KZwcE-kMAIppgkb-OFjxWuNA",
        "passengerName": "Chen Wei",
        "flight": "CZ3602",
        "departureTime": "14:05",
        "checkIn": "C02",
        "gate": "5",
        "destinationId": "check-in",
        "status": "checked-in",
    },
    {
        "code": "KZ6kWBB_W8PPYxZM1cFxarTQ",
        "passengerName": "Karimova Aliya",
        "flight": "U62214",
        "departureTime": "16:50",
        "checkIn": "A11",
        "gate": "9",
        "destinationId": "check-in",
        "status": "boarding",
    },
    {
        "code": "KZaXTLNCGPD9Ynmf9hH_zMHw",
        "passengerName": "John Smith",
        "flight": "TK1470",
        "departureTime": "19:25",
        "checkIn": "D01",
        "gate": "22",
        "destinationId": "check-in",
        "status": "valid",
    },
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_ticket_code(value: Any) -> str:
    code = str(value or "").strip()
    return code if TICKET_CODE_RE.fullmatch(code) else ""


def generate_ticket_code(prefix: str = "KZ") -> str:
    raw = secrets.token_urlsafe(18).replace("-", "").replace("_", "")
    body = (raw + secrets.token_hex(8))[:22]
    return normalize_ticket_code(f"{prefix}{body}") or f"KZ{secrets.token_hex(11)}"


def tickets_path(override: Path | None = None) -> Path:
    return Path(override) if override is not None else DEFAULT_TICKETS_PATH


def _blank_ticket() -> dict[str, Any]:
    return {
        "code": "",
        "passengerName": "",
        "flight": "",
        "departureTime": "",
        "checkIn": "",
        "gate": "",
        "destinationId": "check-in",
        "status": "valid",
        "updatedAt": utc_now_iso(),
        "lastScannedAt": None,
    }


def _normalize_record(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    code = normalize_ticket_code(raw.get("code") or raw.get("ticketCode"))
    if not code:
        return None
    status = str(raw.get("status") or "valid").strip().lower()
    if status not in ALLOWED_STATUSES:
        status = "valid"
    ticket = _blank_ticket()
    ticket.update(
        {
            "code": code,
            "passengerName": str(raw.get("passengerName") or raw.get("passenger_name") or "").strip(),
            "flight": str(raw.get("flight") or "").strip(),
            "departureTime": str(
                raw.get("departureTime") or raw.get("departure_time") or ""
            ).strip(),
            "checkIn": str(raw.get("checkIn") or raw.get("check_in") or "").strip(),
            "gate": str(raw.get("gate") or "").strip(),
            "destinationId": str(
                raw.get("destinationId") or raw.get("destination_id") or "check-in"
            ).strip()
            or "check-in",
            "status": status,
            "updatedAt": str(raw.get("updatedAt") or utc_now_iso()),
            "lastScannedAt": raw.get("lastScannedAt") or None,
        }
    )
    return ticket


def _read_file(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    items = payload.get("tickets") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        return []
    tickets: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        ticket = _normalize_record(item)
        if ticket is None or ticket["code"] in seen:
            continue
        seen.add(ticket["code"])
        tickets.append(ticket)
    return tickets


def _write_file(path: Path, tickets: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updatedAt": utc_now_iso(),
        "tickets": tickets,
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def ensure_store(path: Path | None = None) -> Path:
    target = tickets_path(path)
    with _lock:
        if not target.is_file():
            seeded = []
            for item in SEED_TICKETS:
                ticket = _normalize_record(item)
                if ticket is not None:
                    seeded.append(ticket)
            _write_file(target, seeded)
        return target


def list_tickets(path: Path | None = None) -> list[dict[str, Any]]:
    target = ensure_store(path)
    with _lock:
        return deepcopy(_read_file(target))


def get_ticket(code: Any, path: Path | None = None) -> dict[str, Any] | None:
    normalized = normalize_ticket_code(code)
    if not normalized:
        return None
    for ticket in list_tickets(path):
        if ticket["code"] == normalized:
            return ticket
    return None


def public_ticket_view(ticket: dict[str, Any], *, can_escort: bool = False) -> dict[str, Any]:
    return {
        "passengerName": ticket.get("passengerName") or "",
        "flight": ticket.get("flight") or "",
        "departureTime": ticket.get("departureTime") or "",
        "checkIn": ticket.get("checkIn") or "",
        "gate": ticket.get("gate") or "",
        "destinationId": ticket.get("destinationId") or "",
        "status": ticket.get("status") or "",
        "updatedAt": ticket.get("updatedAt"),
        "lastScannedAt": ticket.get("lastScannedAt"),
        "canEscort": bool(can_escort),
    }


def lookup_ticket(raw_code: Any, path: Path | None = None, *, mark_scanned: bool = True) -> dict[str, Any]:
    code = normalize_ticket_code(raw_code)
    if not code:
        return {"ok": False, "error": "empty_ticket_code"}
    target = ensure_store(path)
    with _lock:
        tickets = _read_file(target)
        for index, ticket in enumerate(tickets):
            if ticket["code"] != code:
                continue
            status = str(ticket.get("status") or "").lower()
            if status not in ACTIVE_STATUSES:
                return {"ok": False, "error": "ticket_not_active"}
            if mark_scanned:
                ticket = dict(ticket)
                ticket["lastScannedAt"] = utc_now_iso()
                tickets[index] = ticket
                _write_file(target, tickets)
            return {"ok": True, "ticket": public_ticket_view(ticket)}
    return {"ok": False, "error": "ticket_not_found"}


def upsert_ticket(raw: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    ticket = _normalize_record(raw)
    if ticket is None:
        return {"ok": False, "error": "invalid_ticket"}
    if not ticket["passengerName"] or not ticket["flight"]:
        return {"ok": False, "error": "missing_required_fields"}

    target = ensure_store(path)
    with _lock:
        tickets = _read_file(target)
        ticket["updatedAt"] = utc_now_iso()
        replaced = False
        for index, existing in enumerate(tickets):
            if existing["code"] == ticket["code"]:
                ticket["lastScannedAt"] = existing.get("lastScannedAt")
                if raw.get("keepLastScanned") is False:
                    ticket["lastScannedAt"] = None
                tickets[index] = ticket
                replaced = True
                break
        if not replaced:
            tickets.append(ticket)
        _write_file(target, tickets)
        return {"ok": True, "ticket": deepcopy(ticket), "created": not replaced}


def delete_ticket(code: Any, path: Path | None = None) -> dict[str, Any]:
    normalized = normalize_ticket_code(code)
    if not normalized:
        return {"ok": False, "error": "empty_ticket_code"}
    target = ensure_store(path)
    with _lock:
        tickets = _read_file(target)
        next_tickets = [item for item in tickets if item["code"] != normalized]
        if len(next_tickets) == len(tickets):
            return {"ok": False, "error": "ticket_not_found"}
        _write_file(target, next_tickets)
        return {"ok": True, "deleted": normalized}
