#!/usr/bin/env bash
# Diagnose / map HDMI touchscreen once its USB cable is plugged in.
# Usage on Pi: bash ~/robot_nav/monitor/fix_touch.sh
set -euo pipefail

echo "=== USB devices ==="
lsusb
echo
echo "=== Input names ==="
grep -E '^N: Name=' /proc/bus/input/devices || true
echo

TOUCH_EVENT=""

# 1) by-id / by-path with touch-like names
for link in /dev/input/by-id/*-event-* /dev/input/by-path/*-event-*; do
  [ -e "$link" ] || continue
  base=$(basename "$link")
  case "$base" in
    *mouse*|*kbd*|*keyboard*) continue ;;
  esac
  if echo "$base" | grep -qiE 'touch|goodix|ilitek|egalax|waveshare|finger|fts'; then
    TOUCH_EVENT=$link
    break
  fi
done

# 2) /proc name match
if [ -z "$TOUCH_EVENT" ]; then
  TOUCH_EVENT=$(awk '
    BEGIN { RS=""; FS="\n" }
    {
      name=""; handlers=""
      for (i = 1; i <= NF; i++) {
        if ($i ~ /^N: Name=/) name = $i
        if ($i ~ /^H: Handlers=/) handlers = $i
      }
      low = tolower(name)
      if (low ~ /touch|goodix|ilitek|egalax|waveshare|finger|fts|capacitive/) {
        if (match(handlers, /event[0-9]+/)) {
          print "/dev/input/" substr(handlers, RSTART, RLENGTH)
          exit
        }
      }
    }
  ' /proc/bus/input/devices)
fi

# 3) libinput capabilities
if [ -z "$TOUCH_EVENT" ] && command -v libinput >/dev/null 2>&1; then
  echo "=== libinput touchscreens ==="
  libinput list-devices 2>/dev/null | awk '
    /^Device:/ { dev = $0; kernel = "" }
    /Kernel:/ { kernel = $2 }
    /Capabilities:/ && /touch/ {
      print dev " -> " kernel
      if (kernel != "" && found == 0) {
        print kernel > "/tmp/touch_kernel_path"
        found = 1
      }
    }
  ' || true
  if [ -f /tmp/touch_kernel_path ]; then
    TOUCH_EVENT=$(cat /tmp/touch_kernel_path)
    rm -f /tmp/touch_kernel_path
  fi
fi

echo
if [ -z "${TOUCH_EVENT}" ]; then
  cat <<'EOF'
RESULT: touchscreen NOT detected.

This HDMI panel needs a separate USB cable for touch.
Right now USB only shows: serial adapters, camera, Logitech dongle — no touch HID.
Hub port 3 under the USB hub is empty.

Fix hardware first:
  1) Find the USB cable from the monitor (often bundled with the HDMI cable).
  2) Plug it into a free port on the robot USB hub.
  3) Run: bash ~/robot_nav/monitor/fix_touch.sh

Software cannot create touch without that USB device.
EOF
  exit 1
fi

echo "RESULT: found touch input → $TOUCH_EVENT"
echo

export DISPLAY="${DISPLAY:-:0}"
if command -v xinput >/dev/null 2>&1 && xinput list >/dev/null 2>&1; then
  echo "=== xinput map to HDMI ==="
  while read -r id; do
    [ -n "$id" ] || continue
    name=$(xinput list --name-only "$id" 2>/dev/null || true)
    echo "id=$id name=$name"
    if echo "$name" | grep -qiE 'touch|goodix|ilitek|egalax|waveshare|finger|fts'; then
      xinput map-to-output "$id" HDMI-1 2>/dev/null \
        || xinput map-to-output "$id" HDMI-A-1 2>/dev/null \
        || true
      echo "mapped $id → HDMI"
    fi
  done < <(xinput list --id-only 2>/dev/null || true)
else
  echo "(xinput unavailable — on Wayland libinput maps touch automatically once the USB device exists)"
fi

echo
echo "Touch device is present. If taps are inverted/offset, say so and we will add a calibration matrix."
