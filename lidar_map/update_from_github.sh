#!/usr/bin/env bash
# Pull latest code from GitHub and install into ~/robot_nav/lidar_map, then restart.
set -eo pipefail

REPO="${REPO:-https://github.com/bear-agency-create/lidar.git}"
CLONE_DIR="${CLONE_DIR:-$HOME/lidar}"
TARGET="${TARGET:-$HOME/robot_nav/lidar_map}"
RESTART="${RESTART:-1}"

mkdir -p "$(dirname "$TARGET")"

if [ -d "$CLONE_DIR/.git" ]; then
  git -C "$CLONE_DIR" fetch origin
  git -C "$CLONE_DIR" reset --hard origin/main
else
  git clone "$REPO" "$CLONE_DIR"
fi

echo "GitHub: $(git -C "$CLONE_DIR" log -1 --oneline)"

rm -rf "$TARGET"
cp -a "$CLONE_DIR/lidar_map" "$TARGET"
[ -d "$CLONE_DIR/arduino" ] && cp -a "$CLONE_DIR/arduino" "$HOME/robot_nav/arduino"

chmod +x "$TARGET/start_drive_map.sh" "$TARGET/update_from_github.sh"

if [ "$RESTART" = "1" ]; then
  "$TARGET/start_drive_map.sh"
else
  echo "Installed to $TARGET (RESTART=0, not restarted)."
fi
