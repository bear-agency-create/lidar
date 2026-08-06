#!/usr/bin/env bash
# Киоск ТОЛЬКО на мониторе робота (не трогает ноут).
# Не убивает Mega/drive. Перезапускает main.py только если :8765 мёртв.
set -euo pipefail

URL="http://127.0.0.1:8765/kiosk"
LOG_DIR="${HOME}/robot_nav/logs"
STACK="${HOME}/robot_nav/lidar_map"
mkdir -p "$LOG_DIR"

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export DISPLAY="${DISPLAY:-:0}"

# Xwayland auth for GNOME
if [ -z "${XAUTHORITY:-}" ] || [ ! -f "${XAUTHORITY:-}" ]; then
  for f in /run/user/"$(id -u)"/.mutter-Xwaylandauth.*; do
    if [ -f "$f" ]; then export XAUTHORITY="$f"; break; fi
  done
fi
[ -n "${XAUTHORITY:-}" ] || { [ -f "$HOME/.Xauthority" ] && export XAUTHORITY="$HOME/.Xauthority"; }

SCREEN_W=1024
SCREEN_H=600
if [ -r /sys/class/graphics/fb0/virtual_size ]; then
  fb=$(cat /sys/class/graphics/fb0/virtual_size)
  SCREEN_W=${fb%,*}
  SCREEN_H=${fb#*,}
fi

set +u
[ -f /opt/ros/jazzy/setup.bash ] && source /opt/ros/jazzy/setup.bash
[ -f "$HOME/ws_ros2/install/setup.bash" ] && source "$HOME/ws_ros2/install/setup.bash"
set -u

# Ensure web UI
code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "$URL" || true)
if [ "$code" != "200" ]; then
  echo "[kiosk] :8765 down — starting main.py"
  pkill -f '/lidar_map/main.py' 2>/dev/null || true
  sleep 1
  nohup python3 "$STACK/main.py" >>"$LOG_DIR/lidar_map.log" 2>&1 &
  for _ in $(seq 1 15); do
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 1 "$URL" || true)
    [ "$code" = "200" ] && break
    sleep 1
  done
fi
echo "[kiosk] HTTP=$code display=${SCREEN_W}x${SCREEN_H}"

# Pick browser
BROWSER=""
if [ -x /snap/bin/chromium ]; then BROWSER=/snap/bin/chromium
elif command -v chromium >/dev/null 2>&1; then BROWSER=chromium
elif command -v chromium-browser >/dev/null 2>&1; then BROWSER=chromium-browser
elif [ -x /snap/bin/firefox ]; then BROWSER=/snap/bin/firefox
fi
[ -n "$BROWSER" ] || { echo "[kiosk] no browser"; exit 1; }

# Kill old kiosk windows on the robot only
pkill -f 'chromium.*(8765/kiosk|--app=http://127.0.0.1:8765/kiosk)' 2>/dev/null || true
pkill -f 'firefox.*(8765/kiosk|--kiosk)' 2>/dev/null || true
sleep 0.5

PROFILE="$HOME/snap/chromium/common/kiosk-profile"
mkdir -p "$PROFILE"

echo "[kiosk] launching $BROWSER on robot monitor (Wayland)"
CHROME_ARGS=(
  --user-data-dir="$PROFILE"
  --kiosk
  --start-fullscreen
  --window-position=0,0
  --window-size="${SCREEN_W},${SCREEN_H}"
  --force-device-scale-factor=1
  --disable-pinch
  --noerrdialogs
  --disable-infobars
  --disable-session-crashed-bubble
  --check-for-update-interval=31536000
  --auto-accept-camera-and-microphone-capture
  --unsafely-treat-insecure-origin-as-secure=http://127.0.0.1:8765,http://localhost:8765
  --ozone-platform=wayland
  --enable-features=UseOzonePlatform
  --app="$URL"
)

if command -v systemd-run >/dev/null 2>&1 && [ -S "$XDG_RUNTIME_DIR/bus" ]; then
  systemd-run --user --collect \
    --setenv=XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR" \
    --setenv=WAYLAND_DISPLAY="$WAYLAND_DISPLAY" \
    --setenv=DISPLAY="$DISPLAY" \
    --setenv=XAUTHORITY="${XAUTHORITY:-}" \
    "$BROWSER" "${CHROME_ARGS[@]}" \
    >>"$LOG_DIR/kiosk_browser.log" 2>&1 || true
else
  nohup env DISPLAY="$DISPLAY" XAUTHORITY="${XAUTHORITY:-}" \
    XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR" WAYLAND_DISPLAY="$WAYLAND_DISPLAY" \
    "$BROWSER" "${CHROME_ARGS[@]}" \
    >>"$LOG_DIR/kiosk_browser.log" 2>&1 &
fi

sleep 2
pgrep -af 'chromium|firefox' | grep -E 'kiosk|8765' | grep -v grep || echo "[kiosk] WARN: browser process not found"
echo "[kiosk] ready on robot screen → $URL"
tail -20 "$LOG_DIR/kiosk_browser.log" 2>/dev/null || true
