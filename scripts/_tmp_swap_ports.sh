#!/usr/bin/env bash
set -eo pipefail
pass() { echo raspberry | sudo -S "$@"; }

echo "=== stop stack ==="
pass systemctl stop robot-nav.service || true
pass systemctl stop robot-nav-watchdog.timer || true
pkill -9 -f '/lidar_map/drive_encoders.py' || true
pkill -9 -f '/lidar_map/main.py' || true
pkill -9 -f '/cspc_lidar/cspc_lidar' || true
pkill -9 -f 'ros2 run cspc_lidar' || true
fuser -k /dev/ttyUSB0 /dev/ttyUSB1 2>/dev/null || true
sleep 2

echo "=== by-path ==="
ls -l /dev/serial/by-path/

echo "=== identify which is Mega / LiDAR ==="
python3 - <<'PY'
import serial, time

def try_ping(port):
    try:
        s = serial.Serial(port, 115200, timeout=0.5)
        time.sleep(0.4)
        s.reset_input_buffer()
        s.write(b"PING\n")
        time.sleep(0.4)
        r = s.read(200)
        s.close()
        return r
    except Exception as e:
        return f"ERR:{e}"

def try_raw(port, baud=230400, sec=1.0):
    try:
        s = serial.Serial(port, baud, timeout=0.2)
        time.sleep(0.05)
        s.reset_input_buffer()
        time.sleep(sec)
        d = s.read(8192)
        s.close()
        return d
    except Exception as e:
        return None

mega = None
lidar = None
for p in ("/dev/ttyUSB0", "/dev/ttyUSB1"):
    ping = try_ping(p)
    raw = try_raw(p)
    n = len(raw) if isinstance(raw, (bytes, bytearray)) else -1
    print(p, "PING", repr(ping)[:80], "RAW_n", n)
    if isinstance(ping, (bytes, bytearray)) and b"PONG" in ping:
        mega = p
    if n > 50:
        lidar = p

print("DETECTED mega=", mega, "lidar=", lidar)
with open("/tmp/_port_map.txt", "w") as f:
    f.write(f"MEGA={mega or ''}\nLIDAR={lidar or ''}\n")
PY

# shellcheck disable=SC1091
source /tmp/_port_map.txt
if [[ -z "$MEGA" || -z "$LIDAR" || "$MEGA" == "$LIDAR" ]]; then
  echo "FALLBACK: USB0=lidar (has raw packets), USB1=mega"
  LIDAR=/dev/ttyUSB0
  MEGA=/dev/ttyUSB1
fi

echo "USING MEGA=$MEGA LIDAR=$LIDAR"
pass ln -sfn "$(basename "$MEGA")" /dev/ttyMEGA
pass ln -sfn "$(basename "$LIDAR")" /dev/ttyLIDAR
ls -l /dev/ttyMEGA /dev/ttyLIDAR

# Persist udev by current by-path
MEGA_PATH=$(udevadm info -q property -n "$MEGA" | awk -F= '/^ID_PATH=/{print $2; exit}')
LIDAR_PATH=$(udevadm info -q property -n "$LIDAR" | awk -F= '/^ID_PATH=/{print $2; exit}')
echo "MEGA_PATH=$MEGA_PATH LIDAR_PATH=$LIDAR_PATH"
cat >/tmp/99-robot-serial.rules <<EOF
# Auto-fixed $(date -Is)
ACTION=="add", SUBSYSTEM=="tty", ENV{ID_PATH}=="$LIDAR_PATH", SYMLINK+="ttyLIDAR", MODE="0666", GROUP="dialout"
ACTION=="add", SUBSYSTEM=="tty", ENV{ID_PATH}=="$MEGA_PATH", SYMLINK+="ttyMEGA", MODE="0666", GROUP="dialout"
# Hub layout fallback
ACTION=="add", SUBSYSTEM=="tty", ENV{ID_PATH}=="platform-xhci-hcd.1-usb-0:1.4:1.0", SYMLINK+="ttyLIDAR", MODE="0666", GROUP="dialout"
ACTION=="add", SUBSYSTEM=="tty", ENV{ID_PATH}=="platform-xhci-hcd.1-usb-0:1.3:1.0", SYMLINK+="ttyMEGA", MODE="0666", GROUP="dialout"
EOF
pass cp /tmp/99-robot-serial.rules /etc/udev/rules.d/99-robot-serial.rules
pass udevadm control --reload-rules

echo "=== verify mega PING via symlink ==="
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
sleep 14

source /opt/ros/jazzy/setup.bash
source /home/pi/ws_ros2/install/setup.bash
echo "=== /scan hz ==="
timeout 8 ros2 topic hz /scan 2>&1 | head -15 || true
curl -fsS --max-time 3 http://127.0.0.1:8765/api/scan/health; echo
python3 - <<'PY'
import json, urllib.request
j=json.load(urllib.request.urlopen('http://127.0.0.1:8765/api/scan', timeout=3))
print({k:j.get(k) for k in ('ok','error','odom_ok','stale','points') if k in j or True})
print('points_n', len(j.get('points') or []), 'odom', j.get('odom_ok'), 'err', j.get('error'))
PY
tail -25 /tmp/lidar_usb0.log 2>/dev/null || true
pgrep -af cspc_lidar || true
echo DONE
