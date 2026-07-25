"""Central logging for the robot stack."""

from __future__ import annotations

import logging
import sys
import tempfile
from pathlib import Path

from config import LOG_DIR, LOG_PATH

_CONFIGURED = False
_ACTIVE_LOG_PATH = LOG_PATH


def setup_logging(name: str = "robot", level: int = logging.INFO) -> logging.Logger:
    """Configure root robot logger once: file + stdout."""
    global _CONFIGURED, _ACTIVE_LOG_PATH
    log = logging.getLogger(name)
    if _CONFIGURED and log.handlers:
        return log

    log_path = LOG_PATH
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        log_path = Path(tempfile.gettempdir()) / "lidar_map.log"
    _ACTIVE_LOG_PATH = log_path

    log.setLevel(level)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    fh.setLevel(level)
    log.addHandler(fh)

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    sh.setLevel(level)
    log.addHandler(sh)

    alias = logging.getLogger("lidar_map")
    alias.handlers = log.handlers
    alias.setLevel(level)
    alias.propagate = False

    log.propagate = False
    _CONFIGURED = True
    log.info("logging ready → %s", log_path)
    return log


def get_logger(name: str) -> logging.Logger:
    if not _CONFIGURED:
        setup_logging()
    return logging.getLogger(name)


def rotate_if_huge(max_mb: float = 20.0) -> None:
    """Simple size-based rotate to keep SD card healthy."""
    path = _ACTIVE_LOG_PATH
    try:
        if not path.is_file():
            return
        if path.stat().st_size < max_mb * 1024 * 1024:
            return
        bak = Path(str(path) + ".1")
        if bak.exists():
            bak.unlink()
        path.replace(bak)
    except OSError:
        pass
