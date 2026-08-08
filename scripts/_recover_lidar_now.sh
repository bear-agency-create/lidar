#!/bin/bash
set -e
echo raspberry | sudo -S systemctl stop robot-nav.service || true
echo raspberry | sudo -S systemctl stop robot-nav-watchdog.timer || true
pkill -9 -f lidar_map/drive_encoders.py || true
pkill -9 -f lidar_map/main.py || true
pkill -9 -f cspc_lidar || true
fuser -k /dev/ttyUSB0 /dev/ttyUSB1 /dev/ttyMEGA /dev/ttyLIDAR 2>/dev/null || true
sleep 2
LIDAR_DEV=$(readlink -f /dev/ttyLIDAR 2>/dev/null || echo /dev/ttyUSB1)
BN=$(basename "$LIDAR_DEV")
for d in /sys/bus/usb/devices/*/tty/"$BN"; do
  if [ -e "$d" ]; then
    USB_DEV=$(dirname "$(dirname "$d")")
    echo "reset $USB_DEV"
    echo raspberry | sudo -S sh -c "echo 0 > '$USB_DEV/authorized'"
    sleep 1
    echo raspberry | sudo -S sh -c "echo 1 > '$USB_DEV/authorized'"
  fi
done
sleep 3
ls -l /dev/ttyLIDAR /dev/ttyMEGA /dev/ttyUSB* || true
echo raspberry | sudo -S systemctl start robot-nav.service
sleep 12
set +u
source /opt/ros/jazzy/setup.bash
source /home/pi/ws_ros2/install/setup.bash
set -u
timeout 6 ros2 topic hz /scan 2>&1 | head -12 || true
curl -s http://127.0.0.1:8765/api/scan | python3 -c 'import sys,json; j=json.load(sys.stdin); print("scan", j.get("ok"), j.get("error"), "pts", len(j.get("points") or []), "stale", j.get("stale"))'
tail -25 /tmp/lidar_usb0.log || true
echo DONE
