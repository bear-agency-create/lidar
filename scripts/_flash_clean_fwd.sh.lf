#!/bin/bash
set -e
pkill -9 -f drive_encoders.py || true
pkill -9 -f lidar_map/main.py || true
pkill -9 -f cspc_lidar || true
fuser -k /dev/ttyMEGA /dev/ttyUSB0 2>/dev/null || true
sleep 1
export PATH="$HOME/bin:$PATH"
MEGA="$(readlink -f /dev/ttyMEGA)"
echo "MEGA=$MEGA"
arduino-cli compile --fqbn arduino:avr:mega /home/pi/robot_nav/arduino/CleanFwdBack
arduino-cli upload -p "$MEGA" --fqbn arduino:avr:mega /home/pi/robot_nav/arduino/CleanFwdBack
echo FLASH_CLEAN_OK
sleep 2
python3 - <<'PY'
import serial, time
s = serial.Serial("/dev/ttyMEGA", 115200, timeout=0.5)
time.sleep(2.5)
s.reset_input_buffer()
print("boot", s.read(200))
s.write(b"w\n")
time.sleep(2.2)
print("after_w", s.read(200))
s.write(b"x\n")
time.sleep(0.3)
print("stop", s.read(100))
s.close()
print("DONE_CLEAN")
PY
