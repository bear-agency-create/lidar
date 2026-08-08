#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PORT="${ADMIN_PORT:-8878}"
export ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"
echo "Ticket admin: http://127.0.0.1:${PORT}/"
echo "Password: ${ADMIN_PASSWORD}"
echo "Tickets file: ../monitor/data/tickets.json"
echo "Stop with Ctrl+C"
exec python3 server.py
