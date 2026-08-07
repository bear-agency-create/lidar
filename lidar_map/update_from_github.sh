#!/usr/bin/env bash
# Pull latest from GitHub and install ALL packages into ~/robot_nav, then optionally restart.
set -eo pipefail

REPO="${REPO:-https://github.com/bear-agency-create/lidar.git}"
CLONE_DIR="${CLONE_DIR:-$HOME/lidar}"
TARGET="${TARGET:-$HOME/robot_nav/lidar_map}"
RESTART="${RESTART:-1}"
FLASH="${FLASH:-0}"

mkdir -p "$(dirname "$TARGET")" "$HOME/robot_nav/logs" "$HOME/robot_nav/maps"

if [ -d "$CLONE_DIR/.git" ]; then
  git -C "$CLONE_DIR" fetch origin
  git -C "$CLONE_DIR" reset --hard origin/main
else
  git clone "$REPO" "$CLONE_DIR"
fi

echo "GitHub: $(git -C "$CLONE_DIR" log -1 --oneline)"

# Full install — every package the stack needs (not only lidar_map).
rm -rf "$TARGET"
cp -a "$CLONE_DIR/lidar_map" "$TARGET"

if [ -d "$CLONE_DIR/arduino" ]; then
  rm -rf "$HOME/robot_nav/arduino"
  cp -a "$CLONE_DIR/arduino" "$HOME/robot_nav/arduino"
fi
if [ -d "$CLONE_DIR/monitor" ]; then
  rm -rf "$HOME/robot_nav/monitor"
  cp -a "$CLONE_DIR/monitor" "$HOME/robot_nav/monitor"
fi
if [ -d "$CLONE_DIR/camera" ]; then
  rm -rf "$HOME/robot_nav/camera"
  cp -a "$CLONE_DIR/camera" "$HOME/robot_nav/camera"
fi
if [ -d "$CLONE_DIR/scripts" ]; then
  rm -rf "$HOME/robot_nav/scripts"
  cp -a "$CLONE_DIR/scripts" "$HOME/robot_nav/scripts"
fi
if [ -f "$CLONE_DIR/README.md" ]; then
  cp -a "$CLONE_DIR/README.md" "$HOME/robot_nav/README.md"
fi

# Make every helper executable
find "$TARGET" "$HOME/robot_nav/monitor" "$HOME/robot_nav/camera" \
  -type f \( -name '*.sh' -o -name 'start' \) -exec chmod +x {} + 2>/dev/null || true
find "$HOME/robot_nav/scripts" -type f -name '*.sh' -exec chmod +x {} + 2>/dev/null || true

echo "Installed:"
echo "  lidar_map -> $TARGET"
echo "  monitor   -> $HOME/robot_nav/monitor"
echo "  arduino   -> $HOME/robot_nav/arduino"
echo "  camera    -> $HOME/robot_nav/camera"

if [ "$FLASH" = "1" ] && [ -x "$TARGET/flash_smooth.sh" ] && [ -e /dev/ttyMEGA ]; then
  echo "--- flashing Mega firmware ---"
  bash "$TARGET/flash_smooth.sh" || echo "WARN: Mega flash failed"
fi

if [ "$RESTART" = "1" ]; then
  export LIDAR_DEV="${LIDAR_DEV:-/dev/ttyLIDAR}" MEGA_DEV="${MEGA_DEV:-/dev/ttyMEGA}"
  "$TARGET/start_drive_map.sh"
else
  echo "Installed (RESTART=0, not restarted)."
fi
