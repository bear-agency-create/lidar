#!/usr/bin/env bash
# One-shot: recover LiDAR + flash power-boost MecanumTeleopBridge.
set -eo pipefail
export PATH="$HOME/bin:$PATH"

echo "=== ports ==="
ls -l /dev/ttyLIDAR /dev/ttyMEGA /dev/ttyUSB* || true

echo "=== stop stack holders of serial ==="
sudo systemctl stop robot-nav.service || true
sudo systemctl stop robot-nav-watchdog.timer || true
sleep 1
# Kill by exact binaries/scripts — avoid broad pkill -f that can kill SSH
pkill -9 -f '/lidar_map/drive_encoders.py' || true
pkill -9 -f '/lidar_map/main.py' || true
pkill -9 -f '/cspc_lidar/cspc_lidar' || true
pkill -9 -f 'ros2 run cspc_lidar' || true
fuser -k /dev/ttyUSB0 /dev/ttyUSB1 /dev/ttyMEGA /dev/ttyLIDAR 2>/dev/null || true
sleep 2

echo "=== USB soft reset LiDAR (ttyUSB1) ==="
LIDAR_DEV="$(readlink -f /dev/ttyLIDAR 2>/dev/null || echo /dev/ttyUSB1)"
# Find sysfs authorized for this ttyUSB
for d in /sys/bus/usb/devices/*/tty/"$(basename "$LIDAR_DEV")"; do
  if [[ -e "$d" ]]; then
    USB_DEV="$(dirname "$(dirname "$d")")"
    echo "reset $USB_DEV"
    echo 0 | sudo tee "$USB_DEV/authorized" >/dev/null || true
    sleep 1
    echo 1 | sudo tee "$USB_DEV/authorized" >/dev/null || true
  fi
done
sleep 2
# Recreate udev symlinks if needed
sudo udevadm trigger --subsystem-match=tty || true
sleep 1
ls -l /dev/ttyLIDAR /dev/ttyMEGA /dev/ttyUSB* || true

echo "=== mega ping ==="
python3 - <<'PY'
import serial, time
port = "/dev/ttyMEGA"
s = serial.Serial(port, 115200, timeout=0.4)
time.sleep(0.25)
s.reset_input_buffer()
s.write(b"PING\n")
time.sleep(0.35)
print("MEGA", repr(s.read(200)))
s.close()
PY

echo "=== lidar raw (may be empty while motor only) ==="
python3 - <<'PY'
import serial, time
port = "/dev/ttyLIDAR"
try:
    s = serial.Serial(port, 230400, timeout=0.2)
    time.sleep(0.05)
    s.reset_input_buffer()
    time.sleep(1.0)
    d = s.read(8192)
    print("LIDAR n=", len(d), "hex=", d[:32].hex() if d else "EMPTY")
    s.close()
except Exception as e:
    print("LIDAR ERR", e)
PY

echo "=== verify ramp constants on Pi ==="
grep -nE 'RAMP_START|RAMP_UP|WHEEL_RAMP_UP|PWM_FLOOR|CRAB_PWM' \
  /home/pi/robot_nav/arduino/MecanumTeleopBridge/MecanumTeleopBridge.ino | head -20

echo "=== flash Mega ==="
MEGA="$(readlink -f /dev/ttyMEGA 2>/dev/null || true)"
if [[ -z "$MEGA" || ! -e "$MEGA" ]]; then MEGA=/dev/ttyUSB0; fi
echo "MEGA=$MEGA"
arduino-cli compile --fqbn arduino:avr:mega /home/pi/robot_nav/arduino/MecanumTeleopBridge
arduino-cli upload -p "$MEGA" --fqbn arduino:avr:mega /home/pi/robot_nav/arduino/MecanumTeleopBridge
echo FLASH_OK
sleep 2

echo "=== start stack ==="
sudo systemctl start robot-nav.service
sudo systemctl start robot-nav-watchdog.timer || true
sleep 8

echo "=== scan health ==="
source /opt/ros/jazzy/setup.bash
source /home/pi/ws_ros2/install/setup.bash
timeout 5 ros2 topic hz /scan 2>&1 | head -8 || true
curl -fsS --max-time 3 http://127.0.0.1:8765/api/scan/health || true
echo
curl -fsS --max-time 3 http://127.0.0.1:8765/api/health 2>/dev/null | head -c 400 || true
echo
echo ALL_DONE
