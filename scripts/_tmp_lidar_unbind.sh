#!/usr/bin/env bash
set -eo pipefail
pass() { echo raspberry | sudo -S "$@"; }

echo "=== dmesg usb/ch341 ==="
pass dmesg -T 2>/dev/null | grep -iE 'ttyUSB|ch341|1a86|usb.*err|disconnect' | tail -40 || true

echo "=== authorized state ==="
for d in /sys/bus/usb/devices/2-2 /sys/bus/usb/devices/4-1; do
  echo -n "$d auth="; cat "$d/authorized" 2>/dev/null; echo -n " power="; cat "$d/power/level" 2>/dev/null; echo
done

pass systemctl stop robot-nav.service || true
pass systemctl stop robot-nav-watchdog.timer || true
pkill -9 -f cspc_lidar || true
pkill -9 -f '/lidar_map/' || true
sleep 1

echo "=== force remove+rescan LiDAR ==="
# Unbind ch341 interface then rebind
if [[ -e /sys/bus/usb/drivers/ch341/4-1:1.0 ]]; then
  echo 'unbind 4-1:1.0'
  echo '4-1:1.0' | pass tee /sys/bus/usb/drivers/ch341/unbind
  sleep 1
fi
echo 0 | pass tee /sys/bus/usb/devices/4-1/authorized
sleep 2
echo "auth now=$(cat /sys/bus/usb/devices/4-1/authorized) ttys=$(ls /dev/ttyUSB* 2>/dev/null | tr '\n' ' ')"
echo 1 | pass tee /sys/bus/usb/devices/4-1/authorized
sleep 2
if [[ ! -e /sys/bus/usb/drivers/ch341/4-1:1.0 ]]; then
  echo '4-1:1.0' | pass tee /sys/bus/usb/drivers/ch341/bind || true
fi
sleep 2
ls -l /dev/ttyUSB*
dmesg | tail -20

# Ensure symlinks
pass ln -sfn ttyUSB0 /dev/ttyMEGA
pass ln -sfn ttyUSB1 /dev/ttyLIDAR

# Confirm mega still USB0
python3 - <<'PY'
import serial,time
s=serial.Serial('/dev/ttyUSB0',115200,timeout=0.5); time.sleep(2); s.reset_input_buffer(); s.write(b'PING\n'); time.sleep(0.4); print('USB0',repr(s.read(40))); s.close()
s=serial.Serial('/dev/ttyUSB1',230400,timeout=0.2); time.sleep(0.1); s.reset_input_buffer(); time.sleep(2); d=s.read(8192); print('USB1 n',len(d), d[:24].hex() if d else 'EMPTY'); s.close()
PY

# Does usbreset exist?
command -v usbreset || true
ls /home/pi/ws_ros2/src/cspc_lidar_sdk_ros2/sdk/ | head

echo "=== check start_scan command in SDK ==="
grep -n 'start_scan\|lidar_start\|write_data\|A5\|0xaa' /home/pi/ws_ros2/src/cspc_lidar_sdk_ros2/sdk/lidar_data_processing.cpp | head -40
