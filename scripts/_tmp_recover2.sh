#!/usr/bin/env bash
set -eo pipefail
pass() { echo raspberry | sudo -S "$@"; }

echo "=== force symlinks ==="
pass ln -sfn ttyUSB0 /dev/ttyMEGA
pass ln -sfn ttyUSB1 /dev/ttyLIDAR
pass chmod 666 /dev/ttyUSB0 /dev/ttyUSB1 || true
ls -l /dev/ttyMEGA /dev/ttyLIDAR /dev/ttyUSB*

echo "=== identify ports ==="
python3 - <<'PY'
import serial, time

def try_ping(port):
    try:
        s = serial.Serial(port, 115200, timeout=0.4)
        time.sleep(0.25)
        s.reset_input_buffer()
        s.write(b"PING\n")
        time.sleep(0.35)
        r = s.read(200)
        s.close()
        return repr(r)
    except Exception as e:
        return f"ERR {e}"

def try_raw(port, baud):
    try:
        s = serial.Serial(port, baud, timeout=0.2)
        time.sleep(0.05)
        s.reset_input_buffer()
        time.sleep(0.8)
        d = s.read(4096)
        s.close()
        return f"n={len(d)} hex={d[:16].hex() if d else 'EMPTY'}"
    except Exception as e:
        return f"ERR {e}"

for p in ("/dev/ttyUSB0", "/dev/ttyUSB1"):
    print(p, "PING115200", try_ping(p))
    print(p, "RAW230400", try_raw(p, 230400))
PY

echo "=== start robot-nav ==="
pass systemctl start robot-nav.service
pass systemctl start robot-nav-watchdog.timer || true
sleep 12

source /opt/ros/jazzy/setup.bash
source /home/pi/ws_ros2/install/setup.bash
echo "=== hz /scan ==="
timeout 6 ros2 topic hz /scan 2>&1 | head -12 || true
echo "=== health ==="
curl -fsS --max-time 3 http://127.0.0.1:8765/api/scan/health || true
echo
curl -fsS --max-time 3 http://127.0.0.1:8765/ || true
echo
echo "=== lidar log ==="
# find lidar log
ls -lt /tmp/*lidar* 2>/dev/null | head -5
for f in /tmp/lidar*.log /home/pi/robot_nav/logs/*.log; do
  [[ -f "$f" ]] || continue
  echo "--- $f ---"
  tail -20 "$f" || true
done
journalctl -u robot-nav -n 40 --no-pager || true
echo DONE
