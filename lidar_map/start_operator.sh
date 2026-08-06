#!/usr/bin/env bash
# Operator console: TUI by default (works over SSH). OPERATOR_UI=tk for desktop.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export ROBOT_API="${ROBOT_API:-http://127.0.0.1:8765}"
export ROBOT_LOG="${ROBOT_LOG:-$HOME/robot_nav/logs/lidar_map.log}"
export OPERATOR_UI="${OPERATOR_UI:-tui}"
cd "$ROOT"
exec python3 "$ROOT/operator_console.py"
