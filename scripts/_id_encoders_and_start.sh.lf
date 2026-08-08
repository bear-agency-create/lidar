#!/bin/bash
set -e
export PATH="$HOME/bin:$PATH"
set +u
source /opt/ros/jazzy/setup.bash
source "$HOME/ws_ros2/install/setup.bash"
set -u

echo "=== CURRENT MAP ==="
ls -l /dev/ttyMEGA /dev/ttyLIDAR /dev/ttyUSB* 2>&1
echo "MEGA  = $(readlink -f /dev/ttyMEGA)  path=$(basename $(dirname $(dirname $(readlink -f /sys/class/tty/$(basename $(readlink -f /dev/ttyMEGA))/device))) 2>/dev/null || true)"
echo "LIDAR = $(readlink -f /dev/ttyLIDAR)"

pkill -9 -f cspc_lidar || true
pkill -9 -f drive_encoders.py || true
pkill -9 -f lidar_map/main.py || true
fuser -k /dev/ttyUSB0 /dev/ttyUSB1 /dev/ttyMEGA /dev/ttyLIDAR 2>/dev/null || true
sleep 1

MEGA=$(readlink -f /dev/ttyMEGA)
echo "=== ENCODER ID on $MEGA ==="
python3 - <<PY
import serial, time, re
port = "$MEGA"
s = serial.Serial(port, 115200, timeout=0.3)
time.sleep(2.3)
s.reset_input_buffer()
# confirm firmware
s.write(b"PING\n"); time.sleep(0.2)
print("ping", s.read(80))

def enc():
    s.reset_input_buffer()
    s.write(b"ENC?\n")
    time.sleep(0.15)
    raw = s.read(300).decode("ascii", "ignore")
    m = re.search(r"ENC FL=([-\d]+) FR=([-\d]+) RL=([-\d]+) RR=([-\d]+)", raw)
    if not m:
        print("raw", raw[:120])
        return None
    return [int(m.group(i)) for i in range(1,5)]

names = ["FL", "FR", "RL", "RR"]
print("pins: FL50/51 FR48/49 RL52/53 RR46/47")
print("baseline", enc())

# Pulse each wheel via TEST_WHEEL idx dir ms (firmware command)
for idx, name in enumerate(names):
    before = enc()
    if before is None:
        continue
    s.write(f"TEST_WHEEL {idx} 1 700\n".encode())
    # wait for test to finish (~700ms + margin)
    t0 = time.time()
    while time.time() - t0 < 2.0:
        line = s.readline().decode("ascii", "ignore").strip()
        if line:
            if "TEST_WHEEL" in line or "OK" in line or "ERR" in line:
                print(" ", line)
    after = enc()
    if after is None:
        print(f"{name}: no ENC reply")
        continue
    d = [after[i] - before[i] for i in range(4)]
    print(f"{name} pulse -> dENC FL={d[0]} FR={d[1]} RL={d[2]} RR={d[3]}  after={after}")
    s.write(b"HARD_STOP\n"); time.sleep(0.25)
    s.read(100)

print("=== SUMMARY ===")
print("Alive encoder = wheel whose own count changes on its pulse.")
print("FL historically DEAD in this robot firmware.")
s.close()
PY

echo "=== START STACK on stable symlinks ==="
MEGA_DEV=/dev/ttyMEGA LIDAR_DEV=/dev/ttyLIDAR bash "$HOME/robot_nav/lidar_map/start_drive_map.sh"
sleep 4
pgrep -a python3 | grep -E 'drive_encoders|main.py|cspc' || true
curl -s -o /dev/null -w "http=%{http_code}\n" http://127.0.0.1:8765/
echo "UI=http://$(hostname -I | awk '{print $1}'):8765/"
