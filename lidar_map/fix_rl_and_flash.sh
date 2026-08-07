#!/usr/bin/env bash
set -eo pipefail
export PATH="$HOME/bin:$PATH"
pkill -9 -f drive_encoders.py || true
pkill -9 -f 'lidar_map/main.py' || true
fuser -k /dev/ttyUSB1 2>/dev/null || true
fuser -k /dev/ttyMEGA 2>/dev/null || true
sleep 2
MEGA="$(readlink -f /dev/ttyMEGA 2>/dev/null || true)"
if [[ -z "$MEGA" || ! -e "$MEGA" ]]; then MEGA=/dev/ttyUSB1; fi
echo "MEGA=$MEGA"
arduino-cli compile --fqbn arduino:avr:mega /home/pi/robot_nav/arduino/MecanumTeleopBridge
arduino-cli upload -p "$MEGA" --fqbn arduino:avr:mega /home/pi/robot_nav/arduino/MecanumTeleopBridge
echo FLASH_OK
sleep 2
python3 <<'PY'
import serial, time
s = serial.Serial("/dev/ttyUSB1", 115200, timeout=0.4)
time.sleep(2.0)
s.reset_input_buffer()
for c in [b"PING\n", b"TEST_WHEEL 2 1 2000\n", b"STOP\n", b"TEST_WHEEL 2 -1 2000\n", b"STOP\n"]:
    print(">>", c.decode().strip(), flush=True)
    s.write(c)
    t = time.time()
    while time.time() - t < 3.2:
        line = s.readline().decode("ascii", "ignore").strip()
        if line and not line.startswith("POS "):
            print("<<", line, flush=True)
s.close()
print("TEST_DONE", flush=True)
PY
bash /home/pi/robot_nav/lidar_map/start_drive_map.sh
echo ALL_DONE
