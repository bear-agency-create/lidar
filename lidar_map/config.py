"""Shared constants for lidar map + teleop stack."""

from __future__ import annotations

import math
import os
from pathlib import Path

from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy

SCAN_QOS = QoSProfile(
    depth=10,
    reliability=ReliabilityPolicy.RELIABLE,
    history=HistoryPolicy.KEEP_LAST,
)

ODOM_QOS = QoSProfile(
    depth=10,
    reliability=ReliabilityPolicy.BEST_EFFORT,
    history=HistoryPolicy.KEEP_LAST,
)

PORT = 8765
HOST = "0.0.0.0"

MIN_RANGE_SHOW = 0.05
MIN_RANGE_MAP = 0.10
MAX_RANGE = 12.0

MAP_SIZE_M = 40.0
MAP_RES = 0.05
MAP_CELLS = int(MAP_SIZE_M / MAP_RES)

MAP_PATH = Path(os.path.expanduser("~/robot_nav/maps/remembered_occupancy.json"))
LOG_PATH = Path(os.path.expanduser("~/robot_nav/logs/lidar_map.log"))
LOG_DIR = LOG_PATH.parent
AIRPORT_DESTINATIONS_PATH = Path(
    os.environ.get(
        "AIRPORT_DESTINATIONS_PATH",
        os.path.expanduser("~/robot_nav/config/airport_destinations.json"),
    )
)
AIRPORT_TICKETS_DB_PATH = Path(
    os.environ.get(
        "AIRPORT_TICKETS_DB_PATH",
        os.path.expanduser("~/robot_nav/data/airport_tickets.sqlite3"),
    )
)
AIRPORT_KIOSK_ALLOWED_CLIENTS = frozenset(
    item.strip()
    for item in os.environ.get(
        "AIRPORT_KIOSK_ALLOWED_CLIENTS",
        "127.0.0.1,::1",
    ).split(",")
    if item.strip()
)
AUTOSAVE_SEC = 5.0

# Physical footprint: 82 × 56 cm
ROBOT_LENGTH_M = 0.82
ROBOT_WIDTH_M = 0.56
ROBOT_RADIUS_M = 0.50  # ~half-diagonal of the body
NAV_CLEARANCE_M = 0.34

_HL = ROBOT_LENGTH_M * 0.5
_HW = ROBOT_WIDTH_M * 0.5
FRAME_POSTS_XY: list[tuple[float, float]] = [
    (_HL, _HW),
    (_HL, -_HW),
    (-_HL, _HW),
    (-_HL, -_HW),
    (0.0, _HW),
    (0.0, -_HW),
]
FRAME_POST_HALF_ANGLE = math.radians(10.0)
FRAME_POST_RANGE_MARGIN = 0.20
FRAME_BODY_PAD = 0.06

ICP_MAX_DIST = 0.55
ICP_ITERS = 10
ICP_STRIDE = 2
ICP_MAX_POINTS = 120
MAP_HIT_STRIDE = 1
CSM_YAW_SPAN = math.radians(50.0)
CSM_YAW_STEP = math.radians(3.0)
CSM_XY_SPAN = 0.22
CSM_XY_STEP = 0.11
MIN_MATCH_SCORE = 0.22
MIN_MATCHES_ICP = 30
CSM_REFINE_YAW_SPAN = math.radians(12.0)
CSM_REFINE_YAW_STEP = math.radians(2.0)
CSM_REFINE_XY_SPAN = 0.12
CSM_REFINE_XY_STEP = 0.06
MIN_REFINE_SCORE = 0.35

CMD_VX_MAX = 0.85
CMD_VY_MAX = 0.70
CMD_W_MAX = 1.6
# Keep teleop alive across Wi‑Fi / browser hiccups (drive_encoders STALE_SEC=0.9).
CMD_WATCHDOG_SEC = 1.0
CMD_FILE = Path("/tmp/robot_cmd.json")
ODOM_STALE_SEC = 1.0

TEMP_TTL_SEC = 2.0
TEMP_CELL_VAL = 50
TEMP_INFLATE = max(2, int(round(0.12 / MAP_RES)))
NAV_ROBOT_R = max(3, int(math.ceil(NAV_CLEARANCE_M / MAP_RES)))
NAV_GOAL_TOL = 0.25
NAV_V = 0.55
NAV_VY_MAX = 0.50
NAV_W_MAX = 0.70
NAV_YAW_KP = 0.70
NAV_YAW_DEAD = 0.18
NAV_CTE_GAIN = 1.15
# Escort (walk-with-passenger) vs autonomous cruise scale for pursuit cmds.
NAV_ESCORT_SPEED_SCALE = 0.42
NAV_AUTO_SPEED_SCALE = 1.0

HIT_BLOB = 1
OCC_DISPLAY = 0.55
OCC_SOLID = 1.0
OCC_EDGE = 0.85

WEB_UI_PATH = Path(__file__).resolve().parent / "web_ui.html"
OPERATOR_PANEL_PATH = Path(__file__).resolve().parent / "operator_panel.html"


def _resolve_monitor_root() -> Path:
    """Find monitor/ next to lidar_map (robot_nav or repo root)."""
    here = Path(__file__).resolve().parent
    candidates = [
        here.parents[0] / "monitor",  # unlikely flat
        here.parents[1] / "monitor",  # ~/robot_nav/monitor or repo/monitor
        Path.home() / "robot_nav" / "monitor",
        Path.home() / "lidar" / "monitor",
    ]
    for path in candidates:
        if (path / "airport_ui.html").is_file():
            return path
    return here.parents[1] / "monitor"


_MONITOR_ROOT = _resolve_monitor_root()
AIRPORT_UI_PATH = _MONITOR_ROOT / "airport_ui.html"
PRIMARY_BUTTONS_PATH = _MONITOR_ROOT / "primary_buttons.json"
