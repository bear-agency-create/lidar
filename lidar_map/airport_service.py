"""Airport kiosk data access and robot destination resolution."""

from __future__ import annotations

import json
import math
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_SERVICES: tuple[dict[str, Any], ...] = (
    {"id": "check-in", "kind": "check-in", "enabled": False},
    {"id": "gates", "kind": "gates", "enabled": False},
    {"id": "baggage", "kind": "baggage", "enabled": False},
    {"id": "toilet", "kind": "toilet", "enabled": False},
    {"id": "information", "kind": "information", "enabled": False},
    {"id": "exit", "kind": "exit", "enabled": False},
)


@dataclass(frozen=True)
class Destination:
    id: str
    kind: str
    x: float
    y: float
    zone: str
    labels: dict[str, str]
    descriptions: dict[str, str]

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "zone": self.zone,
            "labels": self.labels,
            "descriptions": self.descriptions,
            "enabled": True,
        }


class AirportService:
    """Loads calibrated waypoints and resolves scanned tickets from SQLite."""

    def __init__(self, destinations_path: Path, tickets_db_path: Path) -> None:
        self.destinations_path = destinations_path
        self.tickets_db_path = tickets_db_path

    def _load_destinations(self) -> dict[str, Destination]:
        if not self.destinations_path.exists():
            return {}
        try:
            raw = json.loads(self.destinations_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid destinations file: {exc}") from exc
        items = raw.get("destinations") if isinstance(raw, dict) else None
        if not isinstance(items, list):
            raise ValueError("destinations file must contain a destinations array")

        result: dict[str, Destination] = {}
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("every destination must be an object")
            try:
                destination_id = str(item["id"]).strip()
                kind = str(item["kind"]).strip()
                x = float(item["x"])
                y = float(item["y"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("destination requires id, kind, x and y") from exc
            if not destination_id or destination_id in result:
                raise ValueError("destination ids must be unique and non-empty")
            if not math.isfinite(x) or not math.isfinite(y):
                raise ValueError("destination coordinates must be finite numbers")
            labels = item.get("labels", {})
            descriptions = item.get("descriptions", {})
            if not isinstance(labels, dict) or not isinstance(descriptions, dict):
                raise ValueError("labels and descriptions must be objects")
            result[destination_id] = Destination(
                id=destination_id,
                kind=kind,
                x=x,
                y=y,
                zone=str(item.get("zone", "")).strip(),
                labels={str(k): str(v) for k, v in labels.items()},
                descriptions={str(k): str(v) for k, v in descriptions.items()},
            )
        return result

    def public_destinations(self) -> dict[str, Any]:
        try:
            destinations = self._load_destinations()
        except ValueError as exc:
            return {"ok": False, "error": str(exc), "destinations": list(DEFAULT_SERVICES)}
        if not destinations:
            return {
                "ok": True,
                "configured": False,
                "destinations": list(DEFAULT_SERVICES),
            }
        return {
            "ok": True,
            "configured": True,
            "destinations": [item.public_dict() for item in destinations.values()],
        }

    def get_destination(self, destination_id: str) -> Destination | None:
        try:
            return self._load_destinations().get(destination_id)
        except ValueError:
            return None

    @staticmethod
    def normalize_ticket_code(value: Any) -> str:
        code = str(value or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", code):
            return ""
        return code

    def lookup_ticket(self, raw_code: Any) -> dict[str, Any]:
        code = self.normalize_ticket_code(raw_code)
        if not code:
            return {"ok": False, "error": "empty_ticket_code"}
        if not self.tickets_db_path.exists():
            return {"ok": False, "error": "ticket_database_unavailable"}

        try:
            with sqlite3.connect(f"file:{self.tickets_db_path}?mode=ro", uri=True) as db:
                db.row_factory = sqlite3.Row
                row = db.execute(
                    """
                    SELECT code, passenger_name, flight, departure_time, check_in,
                           gate, destination_id, status
                    FROM tickets
                    WHERE code = ?
                    LIMIT 1
                    """,
                    (code,),
                ).fetchone()
        except sqlite3.Error:
            return {"ok": False, "error": "ticket_database_unavailable"}

        if row is None:
            return {"ok": False, "error": "ticket_not_found"}
        if str(row["status"] or "").lower() not in {"valid", "checked-in", "boarding"}:
            return {"ok": False, "error": "ticket_not_active"}

        destination = self.get_destination(str(row["destination_id"] or ""))
        ticket = {
            "passengerName": str(row["passenger_name"] or ""),
            "flight": str(row["flight"] or ""),
            "departureTime": str(row["departure_time"] or ""),
            "checkIn": str(row["check_in"] or ""),
            "gate": str(row["gate"] or ""),
            "destinationId": str(row["destination_id"] or ""),
            "canEscort": destination is not None,
        }
        return {"ok": True, "ticket": ticket}

