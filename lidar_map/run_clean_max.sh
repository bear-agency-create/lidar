#!/bin/bash
# Max-power idle run: stop stack → flash CleanFwdBack → AUTO fwd/back.
# Run on the Pi when ready:  bash ~/robot_nav/lidar_map/run_clean_max.sh
set -euo pipefail
export PATH="$HOME/bin:$PATH"

echo "=== stop nav stack (free Mega serial) ==="
sudo systemctl stop robot-nav-watchdog.timer 2>/dev/null || true
sudo systemctl stop robot-nav.service 2>/dev/null || true
pkill -9 -f lidar_map/drive_encoders.py || true
pkill -9 -f lidar_map/main.py || true
pkill -9 -f cspc_lidar || true
fuser -k /dev/ttyMEGA /dev/ttyUSB0 2>/dev/null || true
sleep 1

if [ -e /dev/ttyMEGA ]; then
  MEGA="$(readlink -f /dev/ttyMEGA)"
elif [ -e /dev/ttyUSB0 ]; then
  MEGA=/dev/ttyUSB0
else
  echo "ERROR: no Mega serial" >&2
  exit 1
fi
echo "MEGA=$MEGA"

SKETCH="$HOME/robot_nav/arduino/CleanFwdBack"
echo "=== flash CleanFwdBack MAX (PWM 255) ==="
arduino-cli compile --fqbn arduino:avr:mega "$SKETCH"
arduino-cli upload -p "$MEGA" --fqbn arduino:avr:mega "$SKETCH"
echo FLASH_OK
sleep 2

echo "=== AUTO: full-power FWD 2.5s → gap → BACK 2.5s ==="
echo "Clear the floor. Starting in 3s..."
sleep 3
python3 - <<PY
import serial, time
s = serial.Serial("$MEGA", 115200, timeout=0.5)
time.sleep(2.2)
s.reset_input_buffer()
boot = s.read(200)
print("boot:", boot)
s.write(b"AUTO\n")
t0 = time.time()
while time.time() - t0 < 12.0:
    line = s.readline()
    if line:
        print(line.decode("ascii", "ignore").rstrip())
    if b"AUTO_DONE" in line:
        break
s.write(b"x\n")
time.sleep(0.2)
print("stop:", s.read(80))
s.close()
print("DONE — idle run finished")
PY
