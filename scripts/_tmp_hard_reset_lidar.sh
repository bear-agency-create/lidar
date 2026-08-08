#!/usr/bin/env bash
set -eo pipefail
pass() { echo raspberry | sudo -S "$@"; }

pass systemctl stop robot-nav.service || true
pkill -9 -f '/cspc_lidar/cspc_lidar' || true
pkill -9 -f '/lidar_map/drive_encoders.py' || true
pkill -9 -f '/lidar_map/main.py' || true
fuser -k /dev/ttyUSB0 /dev/ttyUSB1 2>/dev/null || true
sleep 1

echo "=== find LiDAR sysfs ==="
find /sys/bus/usb/devices -name 'ttyUSB1' 2>/dev/null
find /sys/devices -name 'ttyUSB1' 2>/dev/null | head
udevadm info -a -n /dev/ttyUSB1 2>/dev/null | head -40

echo "=== hard reset USB 4-1 (LiDAR CH340) ==="
# Parent device of interface 4-1:1.0 is 4-1
DEV=/sys/bus/usb/devices/4-1
if [[ -d "$DEV" ]]; then
  echo "found $DEV product=$(cat $DEV/product 2>/dev/null) id=$(cat $DEV/idVendor 2>/dev/null):$(cat $DEV/idProduct 2>/dev/null)"
  if [[ -e "$DEV/authorized" ]]; then
    echo 0 | pass tee "$DEV/authorized" >/dev/null
    sleep 2
    echo 1 | pass tee "$DEV/authorized" >/dev/null
    echo authorized_cycled
  fi
  if [[ -e /sys/bus/usb/drivers/usb/unbind ]]; then
    # also try driver rebind of interface
    echo 4-1:1.0 | pass tee /sys/bus/usb/drivers/ch341/unbind 2>/dev/null || true
    sleep 1
    echo 4-1:1.0 | pass tee /sys/bus/usb/drivers/ch341/bind 2>/dev/null || true
  fi
else
  echo "NO $DEV"
  ls /sys/bus/usb/devices/
fi
sleep 3
ls -l /dev/ttyUSB* /dev/ttyLIDAR /dev/ttyMEGA 2>&1 || true

# recreate symlinks if lost
pass ln -sfn ttyUSB0 /dev/ttyMEGA
pass ln -sfn ttyUSB1 /dev/ttyLIDAR

echo "=== probe LiDAR after hard reset ==="
python3 - <<'PY'
import serial, time
for baud in (230400, 115200, 256000, 512000, 768000):
    try:
        s = serial.Serial('/dev/ttyUSB1', baud, timeout=0.2)
        time.sleep(0.05)
        # common CSPC start-ish probe: just listen
        s.reset_input_buffer()
        time.sleep(1.0)
        d = s.read(4096)
        print('baud', baud, 'n', len(d), 'hex', d[:24].hex() if d else 'EMPTY')
        s.close()
    except Exception as e:
        print('baud', baud, 'ERR', e)
PY

echo "=== try manual lidar start bytes then listen ==="
python3 - <<'PY'
import serial, time
# From CSPC SDK style: many use AA 55 packets; try a few known starts
starts = [
    bytes([0xA5, 0x60]),
    bytes([0xA5, 0x20]),
    bytes([0xAA, 0x55, 0x01, 0x00]),
]
s = serial.Serial('/dev/ttyUSB1', 230400, timeout=0.2)
for pkt in starts:
    s.reset_input_buffer()
    s.write(pkt)
    time.sleep(0.8)
    d = s.read(4096)
    print('sent', pkt.hex(), 'got', len(d), d[:32].hex() if d else 'EMPTY')
s.close()
PY

echo "=== check SDK isToF / version path ==="
grep -n 'M1CT_TOF\|isToF\|Starting TOF\|version' /home/pi/ws_ros2/src/cspc_lidar_sdk_ros2/sdk/node_lidar.cpp | head -30
grep -n 'M1CT_TOF\|Starting TOF\|isToF' /home/pi/ws_ros2/src/cspc_lidar_sdk_ros2/sdk/*.cpp | head -40
