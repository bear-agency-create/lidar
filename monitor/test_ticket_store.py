from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ticket_store import (
    delete_ticket,
    lookup_ticket,
    upsert_ticket,
)


class TicketStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "tickets.json"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_upsert_lookup_and_scan_stamp(self) -> None:
        created = upsert_ticket(
            {
                "code": "KZTESTCODE123456789012",
                "passengerName": "Test User",
                "flight": "SU1",
                "departureTime": "09:00",
                "checkIn": "A01",
                "gate": "1",
                "destinationId": "check-in",
                "status": "valid",
            },
            self.path,
        )
        self.assertTrue(created["ok"])
        result = lookup_ticket("KZTESTCODE123456789012", self.path, mark_scanned=True)
        self.assertTrue(result["ok"])
        self.assertEqual(result["ticket"]["flight"], "SU1")
        self.assertTrue(result["ticket"]["lastScannedAt"])

        updated = upsert_ticket(
            {
                "code": "KZTESTCODE123456789012",
                "passengerName": "Test User",
                "flight": "SU2",
                "departureTime": "10:00",
                "checkIn": "A02",
                "gate": "2",
                "destinationId": "check-in",
                "status": "valid",
            },
            self.path,
        )
        self.assertTrue(updated["ok"])
        latest = lookup_ticket("KZTESTCODE123456789012", self.path, mark_scanned=False)
        self.assertEqual(latest["ticket"]["flight"], "SU2")
        self.assertEqual(latest["ticket"]["gate"], "2")

    def test_delete_ticket(self) -> None:
        upsert_ticket(
            {
                "code": "KZDELETEME1234567890123",
                "passengerName": "Gone",
                "flight": "X1",
                "status": "valid",
            },
            self.path,
        )
        self.assertTrue(delete_ticket("KZDELETEME1234567890123", self.path)["ok"])
        self.assertEqual(
            lookup_ticket("KZDELETEME1234567890123", self.path)["error"],
            "ticket_not_found",
        )


if __name__ == "__main__":
    unittest.main()
