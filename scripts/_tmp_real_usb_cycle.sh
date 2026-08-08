#!/usr/bin/env bash
set -eo pipefail

sudo_cmd() { echo raspberry | sudo -S "$@"; }
sudo_sh() { echo raspberry | sudo -S bash -c "$1"; }

sudo_cmd systemctl stop robot-nav.service || true
sudo_cmd systemctl stop robot-nav-watchdog.timer || true
pkill -9 -f cspc_lidar || true
pkill -9 -f '/lidar_map/drive_encoders.py' || true
pkill -9 -f '/lidar_map/main.py' || true
fuser -k /dev/ttyUSB0 /dev/ttyUSB1 2>/dev/null || true
sleep 1

echo "=== REAL authorized power cycle of 4-1 ==="
sudo_sh 'echo 0 > /sys/bus/usb/devices/4-1/authorized; sleep 1; cat /sys/bus/usb/devices/4-1/authorized; ls /dev/ttyUSB* 2>&1 || true'
sleep 2
sudo_sh 'echo 1 > /sys/bus/usb/devices/4-1/authorized; sleep 2; cat /sys/bus/usb/devices/4-1/authorized; ls -l /dev/ttyUSB*'
sudo_cmd dmesg -T 2>/dev/null | grep -iE 'ttyUSB|ch341|4-1|disconnect|error' | tail -25 || true

# remake symlinks after possible renumber
sleep 1
python3 - <<'PY'
import serial, time, os, subprocess

def sh(cmd):
    subprocess.check_call(cmd, shell=True)

ports = sorted(p for p in os.listdir('/dev') if p.startswith('ttyUSB'))
print('ports', ports)
mega=None
other=[]
for p in ports:
    path=f'/dev/{p}'
    try:
        s=serial.Serial(path,115200,timeout=0.5)
        time.sleep(2.0)
        s.reset_input_buffer(); s.write(b'PING\n'); time.sleep(0.4)
        r=s.read(100); s.close()
        print(path, 'PING', repr(r[:40]))
        if b'PONG' in r:
            mega=path
        else:
            other.append(path)
    except Exception as e:
        print(path, e); other.append(path)

lidar = other[0] if other else None
# if only one other, probe raw
if lidar:
    s=serial.Serial(lidar,230400,timeout=0.2)
    time.sleep(0.1); s.reset_input_buffer(); time.sleep(2.0)
    d=s.read(16384); s.close()
    print('LIDAR', lidar, 'n', len(d), d[:32].hex() if d else 'EMPTY')

print('MAP', mega, lidar)
open('/tmp/_port_map.txt','w').write(f'MEGA={mega}\nLIDAR={lidar}\n')
PY
source /tmp/_port_map.txt
sudo_cmd ln -sfn "$(basename "$MEGA")" /dev/ttyMEGA
sudo_cmd ln -sfn "$(basename "$LIDAR")" /dev/ttyLIDAR
ls -l /dev/ttyMEGA /dev/ttyLIDAR

echo "=== start full stack ==="
sudo_cmd systemctl start robot-nav.service
sudo_cmd systemctl start robot-nav-watchdog.timer || true
sleep 14
source /opt/ros/jazzy/setup.bash
source /home/pi/ws_ros2/install/setup.bash
timeout 8 ros2 topic hz /scan 2>&1 | head -15 || true
python3 - <<'PY'
import json,urllib.request
j=json.load(urllib.request.urlopen('http://127.0.0.1:8765/api/scan',timeout=3))
print('ok',j.get('ok'),'odom',j.get('odom_ok'),'err',j.get('error'),'pts',len(j.get('points') or []))
PY
tail -25 /tmp/lidar_usb0.log || true
echo DONE
