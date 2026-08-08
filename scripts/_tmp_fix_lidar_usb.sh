#!/usr/bin/env bash
set -eo pipefail
pass() { echo raspberry | sudo -S "$@"; }

pass systemctl stop robot-nav.service || true
pass systemctl stop robot-nav-watchdog.timer || true
pkill -9 -f '/lidar_map/drive_encoders.py' || true
pkill -9 -f '/lidar_map/main.py' || true
pkill -9 -f '/cspc_lidar/cspc_lidar' || true
fuser -k /dev/ttyUSB0 /dev/ttyUSB1 2>/dev/null || true
sleep 1

echo "=== correct symlinks: MEGA=USB0 LIDAR=USB1 ==="
pass ln -sfn ttyUSB0 /dev/ttyMEGA
pass ln -sfn ttyUSB1 /dev/ttyLIDAR

# Restore udev to physical paths (Mega on hcd.0:2, LiDAR on hcd.1:1)
cat >/tmp/99-robot-serial.rules <<'EOF'
# Direct USB: Mega on xhci-hcd.0 port2, LiDAR on xhci-hcd.1 port1
ACTION=="add", SUBSYSTEM=="tty", ENV{ID_PATH}=="platform-xhci-hcd.1-usb-0:1:1.0", SYMLINK+="ttyLIDAR", MODE="0666", GROUP="dialout"
ACTION=="add", SUBSYSTEM=="tty", ENV{ID_PATH}=="platform-xhci-hcd.0-usb-0:2:1.0", SYMLINK+="ttyMEGA", MODE="0666", GROUP="dialout"
# Hub layout fallback
ACTION=="add", SUBSYSTEM=="tty", ENV{ID_PATH}=="platform-xhci-hcd.1-usb-0:1.4:1.0", SYMLINK+="ttyLIDAR", MODE="0666", GROUP="dialout"
ACTION=="add", SUBSYSTEM=="tty", ENV{ID_PATH}=="platform-xhci-hcd.1-usb-0:1.3:1.0", SYMLINK+="ttyMEGA", MODE="0666", GROUP="dialout"
EOF
pass cp /tmp/99-robot-serial.rules /etc/udev/rules.d/99-robot-serial.rules
pass udevadm control --reload-rules

echo "=== soft-reset LiDAR USB (xhci-hcd.1) ==="
# Find USB device for ttyUSB1
for d in /sys/bus/usb/devices/*/tty/ttyUSB1; do
  [[ -e "$d" ]] || continue
  USB_DEV="$(dirname "$(dirname "$d")")"
  echo "authorized cycle $USB_DEV"
  echo 0 | pass tee "$USB_DEV/authorized" >/dev/null
  sleep 2
  echo 1 | pass tee "$USB_DEV/authorized" >/dev/null
done
sleep 3

# Also try usbreset via unbind/bind of the CH340 interface if present
if [[ -e /sys/bus/usb/drivers/ch341 ]]; then
  for d in /sys/bus/usb/drivers/ch341/*; do
    base="$(basename "$d")"
    [[ "$base" == *:* ]] || continue
    # only the LiDAR one: under hcd.1
    real="$(readlink -f "$d" || true)"
    echo "ch341 candidate $base -> $real"
  done
fi

ls -l /dev/ttyUSB* /dev/ttyMEGA /dev/ttyLIDAR 2>&1 || true
lsusb

echo "=== raw after reset ==="
python3 - <<'PY'
import serial, time
for port, baud in (("/dev/ttyUSB0", 115200), ("/dev/ttyUSB1", 230400), ("/dev/ttyUSB1", 115200)):
    try:
        s = serial.Serial(port, baud, timeout=0.3)
        if baud == 115200 and "USB0" in port:
            time.sleep(2.0)
            s.reset_input_buffer()
            s.write(b"PING\n")
            time.sleep(0.4)
            print(port, baud, "PING", repr(s.read(80)))
        else:
            time.sleep(0.1)
            s.reset_input_buffer()
            time.sleep(1.2)
            d = s.read(4096)
            print(port, baud, "n", len(d), "hex", d[:20].hex() if d else "EMPTY")
        s.close()
    except Exception as e:
        print(port, baud, "ERR", e)
PY

echo "=== start stack ==="
pass systemctl start robot-nav.service
pass systemctl start robot-nav-watchdog.timer || true
sleep 15

source /opt/ros/jazzy/setup.bash
source /home/pi/ws_ros2/install/setup.bash
timeout 8 ros2 topic hz /scan 2>&1 | head -15 || true
curl -fsS --max-time 3 http://127.0.0.1:8765/api/scan/health; echo
python3 - <<'PY'
import json, urllib.request
j=json.load(urllib.request.urlopen('http://127.0.0.1:8765/api/scan', timeout=3))
print('ok', j.get('ok'), 'odom', j.get('odom_ok'), 'err', j.get('error'), 'pts', len(j.get('points') or []))
PY
tail -30 /tmp/lidar_usb0.log 2>/dev/null || true
echo DONE
