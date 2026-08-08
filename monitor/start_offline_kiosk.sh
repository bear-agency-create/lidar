#!/usr/bin/env bash
# Offline airport kiosk preview (no internet, no ROS, no Pi).
set -euo pipefail
cd "$(dirname "$0")"
PORT="${PORT:-8877}"
echo "Offline kiosk: http://127.0.0.1:${PORT}/"
echo "Sample tickets: data/tickets.json (and data/sample_ticket_codes.txt)"
echo "Admin panel: cd ../admin_panel && ./start.sh"
echo "Stop with Ctrl+C"
exec python3 preview_server.py
