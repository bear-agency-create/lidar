from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
HTML_PATH = ROOT / "airport_ui.html"
HTTP_PATH = ROOT.parent / "lidar_map" / "http_api.py"


class AirportUiAssetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = HTML_PATH.read_text(encoding="utf-8")
        cls.http_source = HTTP_PATH.read_text(encoding="utf-8")

    def test_every_local_image_exists_and_is_served(self) -> None:
        asset_paths = set(re.findall(r'(?:src=|url\()["\']?(assets/[^"\')]+)', self.html))
        self.assertTrue(asset_paths)
        for asset_path in asset_paths:
            with self.subTest(asset=asset_path):
                self.assertTrue((ROOT / asset_path).is_file())
                self.assertIn(f'"/{asset_path}"', self.http_source)

    def test_real_cloud_layers_replace_generated_round_blobs(self) -> None:
        self.assertIn('class="attract-cloud left"', self.html)
        self.assertIn('class="attract-cloud right"', self.html)
        self.assertNotIn(".welcome-art::after", self.html)
        cloud_css = self.html.split(".attract-cloud {", 1)[1].split("}", 1)[0]
        self.assertNotIn("radial-gradient", cloud_css)

    def test_route_plane_has_takeoff_and_landing_cycle(self) -> None:
        self.assertIn('class="plane" src="assets/realistic-airliner-clean.png"', self.html)
        self.assertIn("plane-mover", self.html)
        self.assertRegex(
            self.html,
            r"animation:\s*routeFlight\s+[^;]*\sinfinite;",
        )
        self.assertRegex(
            self.html,
            r"animation:\s*planeFade\s+[^;]*\sinfinite;",
        )
        keyframes = self.html.split("@keyframes routeFlight", 1)[1].split("}", 6)
        route_animation = "}".join(keyframes)
        self.assertIn("left: 8%", route_animation)
        self.assertIn("left: 92%", route_animation)

    def test_reduced_motion_disables_animation(self) -> None:
        reduced_motion = self.html.split("@media (prefers-reduced-motion: reduce)", 1)[1]
        self.assertIn("animation: none !important", reduced_motion)
        self.assertIn(".plane-mover, .attract-plane", reduced_motion)
        self.assertIn('? 80 : 1800', self.html)
        self.assertIn('screen.classList.add("hidden")', self.html)
        self.assertIn('screen.classList.remove("departing")', self.html)

    def test_scan_modal_has_camera_and_manual_entry(self) -> None:
        self.assertIn('id="scanCamera"', self.html)
        self.assertIn('id="scanVideo"', self.html)
        self.assertIn("getUserMedia", self.html)
        self.assertIn("BarcodeDetector", self.html)
        self.assertIn("vendor/zxing.min.js", self.html)
        self.assertIn("acceptScannedCode", self.html)
        self.assertIn("decodeFromVideoElementContinuously", self.html)
        self.assertIn('id="ticketCode"', self.html)
        self.assertIn("startCameraScan", self.html)
        self.assertIn("stopCameraScan", self.html)
        self.assertIn('data-i18n="manualEntry"', self.html)

    def test_demo_tickets_cover_sample_codes(self) -> None:
        self.assertIn("DEMO_TICKETS", self.html)
        self.assertIn("KZzKQhLbySCrKtkfNh9xSD2Q", self.html)
        self.assertIn("lookupDemoTicket", self.html)

    def test_ticket_go_opens_mode_choice(self) -> None:
        self.assertIn('id="ticketGo"', self.html)
        self.assertIn('id="modePanel"', self.html)
        self.assertIn('id="modeEscort"', self.html)
        self.assertIn('id="modeAuto"', self.html)
        self.assertIn('id="escortRunPanel"', self.html)
        self.assertIn('id="autoRunPanel"', self.html)
        self.assertIn('id="escortMapCanvas"', self.html)
        self.assertIn('data-i18n="modeEscortTitle"', self.html)
        self.assertIn('data-i18n="modeAutoTitle"', self.html)
        self.assertIn('id="escortWait"', self.html)
        self.assertIn('data-i18n="escortWait"', self.html)
        self.assertIn('data-i18n="modeEscortNote"', self.html)
        self.assertIn('data-i18n="modeAutoNote"', self.html)
        self.assertIn('mode: tripMode', self.html)


if __name__ == "__main__":
    unittest.main()

