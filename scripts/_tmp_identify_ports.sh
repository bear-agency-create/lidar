#!/usr/bin/env bash
set -eo pipefail
pass() { echo raspberry | sudo -S "$@"; }

pass systemctl stop robot-nav.service || true
pass systemctl stop robot-nav-watchdog.timer || true
pkill -9 -f '/lidar_map/drive_encoders.py' || true
pkill -9 -f '/lidar_map/main.py' || true
pkill -9 -f '/cspc_lidar/cspc_lidar' || true
pkill -9 -f 'ros2 run cspc_lidar' || true
fuser -k /dev/ttyUSB0 /dev/ttyUSB1 2>/dev/null || true
sleep 3

echo "=== lsusb / sys ==="
lsusb
ls -l /dev/ttyUSB* /dev/serial/by-path/ /dev/serial/by-id/ 2>/dev/null || true

echo "=== careful identify @115200 then @230400 ==="
python3 - <<'PY'
import serial, time, os

def exclusive_open(port, baud):
    # Toggle DTR to reset CH340 target if Mega
    s = serial.Serial()
    s.port = port
    s.baudrate = baud
    s.timeout = 0.3
    s.dsrdtr = False
    s.rtscts = False
    s.open()
    return s

for port in ("/dev/ttyUSB0", "/dev/ttyUSB1"):
    print("====", port, "====")
    # 115200 text probe for Mega
    try:
        s = exclusive_open(port, 115200)
        # Mega resets on open; wait for boot
        time.sleep(2.2)
        s.reset_input_buffer()
        boot = s.read(500)
        print("boot115200", repr(boot[:120]))
        s.write(b"PING\n")
        time.sleep(0.5)
        r = s.read(300)
        print("PING", repr(r[:120]))
        s.close()
    except Exception as e:
        print("115200 ERR", e)
    time.sleep(0.5)
    # 230400 raw for LiDAR (do not confuse with garbled mega)
    try:
        s = exclusive_open(port, 230400)
        time.sleep(0.2)
        s.reset_input_buffer()
        time.sleep(1.5)
        d = s.read(8192)
        print("raw230400 n", len(d), "head", d[:24].hex() if d else "EMPTY")
        # Heuristic: many 0xAA or COIN sync patterns, or high entropy continuous stream
        if d:
            aa = d.count(0xAA)
            print("count_AA", aa, "uniq", len(set(d)))
        s.close()
    except Exception as e:
        print("230400 ERR", e)
    time.sleep(0.3)
PY
