from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from airport_service import AirportService
from ticket_store import upsert_ticket


class AirportServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.destinations_path = root / "destinations.json"
        self.database_path = root / "tickets.json"
        self.buttons_path = root / "primary_buttons.json"
        self.buttons_path.write_text(
            json.dumps(
                {
                    "buttons": [
                        {"id": "check-in", "kind": "check-in"},
                        {"id": "gates", "kind": "gates"},
                        {"id": "baggage", "kind": "baggage"},
                        {"id": "places", "kind": "places"},
                        {"id": "information", "kind": "information"},
                        {"id": "exit", "kind": "exit"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        self.service = AirportService(
            self.destinations_path,
            self.database_path,
            self.buttons_path,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def configure_destination(self) -> None:
        self.destinations_path.write_text(
            json.dumps(
                {
                    "destinations": [
                        {
                            "id": "check-in-a",
                            "kind": "check-in",
                            "x": 2.5,
                            "y": -1.25,
                            "zone": "A",
                            "labels": {"en": "Check-in A"},
                            "descriptions": {"en": "Main hall"},
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

    def create_ticket_database(self, status: str = "valid") -> None:
        upsert_ticket(
            {
                "code": "ABC-123",
                "passengerName": "A. Passenger",
                "flight": "SU100",
                "departureTime": "10:30",
                "checkIn": "A12",
                "gate": "4",
                "destinationId": "check-in-a",
                "status": status,
            },
            self.database_path,
        )

    def test_unconfigured_destinations_are_not_escorted(self) -> None:
        result = self.service.public_destinations()
        self.assertTrue(result["ok"])
        self.assertFalse(result["configured"])
        self.assertEqual(len(result["destinations"]), 6)
        self.assertEqual(
            [item["kind"] for item in result["destinations"]],
            ["check-in", "baggage", "information", "exit"],
        )
        self.assertTrue(all(not item["enabled"] for item in result["destinations"]))

    def test_destination_coordinates_stay_private(self) -> None:
        self.configure_destination()
        result = self.service.public_destinations()
        self.assertTrue(result["configured"])
        self.assertNotIn("x", result["destinations"][0])
        destination = self.service.get_destination("check-in-a")
        self.assertEqual((destination.x, destination.y), (2.5, -1.25))

    def test_valid_ticket_resolves_escort_destination(self) -> None:
        self.configure_destination()
        self.create_ticket_database()
        result = self.service.lookup_ticket(" ABC-123\n")
        self.assertTrue(result["ok"])
        self.assertEqual(result["ticket"]["flight"], "SU100")
        self.assertTrue(result["ticket"]["canEscort"])

    def test_missing_and_inactive_tickets_are_rejected(self) -> None:
        self.create_ticket_database(status="cancelled")
        self.assertEqual(self.service.lookup_ticket("ABC-123")["error"], "ticket_not_active")
        self.assertEqual(self.service.lookup_ticket("UNKNOWN")["error"], "ticket_not_found")

    def test_ticket_input_is_sanitized_and_bounded(self) -> None:
        self.assertEqual(self.service.normalize_ticket_code(" ABC-1_2 "), "ABC-1_2")
        self.assertEqual(self.service.normalize_ticket_code("A B/C-1_2"), "")
        self.assertEqual(self.service.normalize_ticket_code("A" * 300), "")

    def test_non_finite_destination_coordinates_are_rejected(self) -> None:
        self.destinations_path.write_text(
            json.dumps(
                {
                    "destinations": [
                        {
                            "id": "unsafe",
                            "kind": "exit",
                            "x": "NaN",
                            "y": 1,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        result = self.service.public_destinations()
        self.assertFalse(result["ok"])
        self.assertIsNone(self.service.get_destination("unsafe"))


if __name__ == "__main__":
    unittest.main()
