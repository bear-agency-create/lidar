#!/usr/bin/env python3
"""Entry point: wire drive + lidar/map + HTTP UI and run."""

from __future__ import annotations

import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

# Allow `python3 main.py` / `python3 server.py` from any cwd
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import rclpy

from config import HOST, MAP_PATH, PORT
from http_api import make_handler
from logutil import get_logger, rotate_if_huge, setup_logging
from bridge import ScanBridge


def main() -> None:
    setup_logging("robot")
    rotate_if_huge()
    log = get_logger("main")
    log.info("starting lidar_map stack HOST=%s PORT=%s", HOST, PORT)

    rclpy.init()
    bridge = ScanBridge()
    httpd = ThreadingHTTPServer((HOST, PORT), make_handler(bridge))

    def spin() -> None:
        while rclpy.ok():
            rclpy.spin_once(bridge, timeout_sec=0.05)

    threading.Thread(target=spin, daemon=True, name="ros-spin").start()
    print(f"http://0.0.0.0:{PORT}/  (drive mode + web teleop)", flush=True)
    print(f"map memory: {MAP_PATH}", flush=True)
    log.info("HTTP listening on %s:%s map=%s", HOST, PORT, MAP_PATH)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log.info("KeyboardInterrupt — shutting down")
    finally:
        try:
            bridge.stop_cmd()
        except Exception as exc:  # noqa: BLE001
            log.warning("stop_cmd on shutdown: %s", exc)
        try:
            bridge.save_map()
        except OSError as exc:
            log.warning("save_map on shutdown: %s", exc)
        httpd.server_close()
        bridge.destroy_node()
        rclpy.shutdown()
        log.info("shutdown complete")


if __name__ == "__main__":
    main()
