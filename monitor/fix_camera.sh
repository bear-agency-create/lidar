#!/usr/bin/env bash
# Make the USB webcam usable for the airport kiosk barcode scanner.
# Usage: bash ~/robot_nav/monitor/fix_camera.sh
set -euo pipefail

echo "=== USB camera ==="
lsusb | grep -iE 'cam|sonix|uvc|09da' || echo "(no camera-like USB device)"
echo
echo "=== USB tree (camera must be on a 480M/5000M port, NOT 12M hub) ==="
lsusb -t || true
echo

echo "=== video group / nodes ==="
id
groups
ls -la /dev/video* 2>/dev/null || echo "NO /dev/video* — uvcvideo did not create a device"

if ! groups | grep -qw video; then
  echo "Adding user to video group (re-login needed)…"
  echo raspberry | sudo -S usermod -aG video "$USER" || true
fi

echo
echo "=== load uvcvideo ==="
echo raspberry | sudo -S modprobe uvcvideo || true
echo raspberry | sudo -S dmesg | grep -iE 'uvc|09da|video chain|video[0-9]' | tail -20 || true

echo
echo "=== snap chromium camera plug ==="
if command -v snap >/dev/null 2>&1 && snap list chromium >/dev/null 2>&1; then
  echo raspberry | sudo -S snap connect chromium:camera || true
  echo raspberry | sudo -S snap connect chromium:audio-record || true
  snap connections chromium | grep -iE 'camera|audio|media' || true
fi

echo
if [ ! -e /dev/video0 ] && [ ! -e /dev/video1 ]; then
  cat <<'EOF'
RESULT: camera USB is present but Linux has NO /dev/video*.

Likely cause (seen on this robot): A4Tech/Sonix webcam is plugged into a
USB 1.1 (12 Mbps) hub. UVC then logs "No valid video chain found".

Fix hardware:
  1) Unplug the webcam from the slow hub.
  2) Plug it into a USB 2.0/3.0 port on the Pi (or a real high-speed hub).
  3) Re-run: bash ~/robot_nav/monitor/fix_camera.sh

Until /dev/video0 exists, the browser cannot open the camera.
EOF
  exit 1
fi

echo "RESULT: video device OK"
ls -la /dev/video*
if command -v v4l2-ctl >/dev/null 2>&1; then
  v4l2-ctl --list-devices || true
fi
echo "Browser/kiosk can use getUserMedia now (restart monitor/start if Chromium was already open)."
