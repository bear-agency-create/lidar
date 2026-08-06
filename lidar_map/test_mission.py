#!/usr/bin/env python3
"""Unit tests for mission waypoint ordering."""

from __future__ import annotations

import unittest

from mission import mission_public, normalize_waypoints


class MissionTests(unittest.TestCase):
    def test_first_point_is_first_to_visit(self) -> None:
        wps = normalize_waypoints(
            [
                {"x": 1, "y": 0, "label": "first"},
                {"x": 2, "y": 0, "label": "second"},
                {"x": 3, "y": 0, "label": "third"},
            ]
        )
        self.assertEqual([w["label"] for w in wps], ["first", "second", "third"])
        self.assertEqual([w["seq"] for w in wps], [0, 1, 2])

    def test_mission_public_slices(self) -> None:
        wps = normalize_waypoints(
            [{"x": 0, "y": 0, "label": "A"}, {"x": 1, "y": 1, "label": "B"}]
        )
        pub = mission_public(wps, 1, "running")
        self.assertEqual(pub["current"]["label"], "B")
        self.assertEqual(len(pub["done"]), 1)
        self.assertEqual(pub["done"][0]["label"], "A")
        self.assertEqual(len(pub["remaining"]), 1)

    def test_empty_raises(self) -> None:
        with self.assertRaises(ValueError):
            normalize_waypoints([])


if __name__ == "__main__":
    unittest.main()
