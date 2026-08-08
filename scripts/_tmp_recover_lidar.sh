#!/usr/bin/env bash
set -eo pipefail
SUDO="sudo -S"
pass() { echo raspberry | $SUDO "$@"; }

echo "=== stop stack ==="
pass systemctl stop robot-nav.service || true
pass systemctl stop robot-nav-watchdog.timer || true
pkill -9 -f '/lidar_map/drive_encoders.py' || true
pkill -9 -f '/lidar_map/main.py' || true
pkill -9 -f '/cspc_lidar/cspc_lidar' || true
pkill -9 -f 'ros2 run cspc_lidar' || true
fuser -k /dev/ttyUSB0 /dev/ttyUSB1 /dev/ttyMEGA /dev/ttyLIDAR 2>/dev/null || true
sleep 2

echo "=== USB soft reset LiDAR ==="
LIDAR_DEV="$(readlink -f /dev/ttyLIDAR 2>/dev/null || echo /dev/ttyUSB1)"
for d in /sys/bus/usb/devices/*/tty/"$(basename "$LIDAR_DEV")"; do
  if [[ -e "$d" ]]; then
    USB_DEV="$(dirname "$(dirname "$d")")"
    echo "reset $USB_DEV"
    echo 0 | pass tee "$USB_DEV/authorized" >/dev/null || true
    sleep 1
    echo 1 | pass tee "$USB_DEV/authorized" >/dev/null || true
  fi
done
sleep 2
pass udevadm trigger --subsystem-match=tty || true
sleep 1
ls -l /dev/ttyLIDAR /dev/ttyMEGA /dev/ttyUSB* || true

echo "=== mega ping ==="
python3 - <<'PY'
import serial, time
s = serial.Serial("/dev/ttyMEGA", 115200, timeout=0.5)
time.sleep(0.35)
s.reset_input_buffer()
s.write(b"PING\n")
time.sleep(0.4)
print("MEGA", repr(s.read(200)))
s.close()
PY

echo "=== start stack ==="
pass systemctl start robot-nav.service
pass systemctl start robot-nav-watchdog.timer || true
sleep 12

echo "=== scan ==="
source /opt/ros/jazzy/setup.bash
source /home/pi/ws_ros2/install/setup.bash
timeout 6 ros2 topic hz /scan 2>&1 | head -12 || true
curl -fsS --max-time 3 http://127.0.0.1:8765/api/scan/health || true
echo
echo "=== lidar log tail ==="
tail -40 /tmp/lidar_usb0.log 2>/dev/null || true
journalctl -u robot-nav -n 30 --no-pager 2>/dev/null || true
echo DONE
