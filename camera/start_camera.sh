#!/usr/bin/env bash
# Запуск умной камеры на Pi (отдельно от start_drive_map.sh).
set -eo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

export CAMERA_SHOW_PREVIEW="${CAMERA_SHOW_PREVIEW:-0}"
exec python3 main.py
