#!/usr/bin/env bash
set -eo pipefail
pass() { echo raspberry | sudo -S "$@"; }

pass systemctl stop robot-nav.service || true
pkill -9 -f cspc_lidar || true
pkill -9 -f '/lidar_map/drive_encoders.py' || true
pkill -9 -f '/lidar_map/main.py' || true
fuser -k /dev/ttyUSB0 /dev/ttyUSB1 2>/dev/null || true
sleep 1

DEV=/sys/bus/usb/devices/4-1
echo "=== reset $DEV ==="
ls -l /dev/ttyUSB1 || true
cat "$DEV/idVendor" "$DEV/idProduct" "$DEV/product" 2>/dev/null || true
echo 0 | pass tee "$DEV/authorized" >/dev/null
sleep 3
echo "after deauth:"; ls /dev/ttyUSB* 2>&1 || true
echo 1 | pass tee "$DEV/authorized" >/dev/null
sleep 4
echo "after reauth:"; ls -l /dev/ttyUSB* /dev/ttyLIDAR /dev/ttyMEGA 2>&1 || true
pass ln -sfn ttyUSB0 /dev/ttyMEGA
# ttyUSB numbers may shuffle after reset — re-identify
python3 - <<'PY'
import serial, time, os, subprocess

ports = sorted(p for p in os.listdir('/dev') if p.startswith('ttyUSB'))
print('ports', ports)
mega=None
lidar_cand=[]
for p in ports:
    path=f'/dev/{p}'
    try:
        s=serial.Serial(path,115200,timeout=0.4)
        time.sleep(2.0)
        s.reset_input_buffer()
        s.write(b'PING\n')
        time.sleep(0.4)
        r=s.read(200)
        s.close()
        print(path,'PING',repr(r[:60]))
        if b'PONG' in r:
            mega=path
            continue
    except Exception as e:
        print(path,'115200',e)
    try:
        s=serial.Serial(path,230400,timeout=0.2)
        time.sleep(0.1); s.reset_input_buffer(); time.sleep(1.2)
        d=s.read(8192); s.close()
        print(path,'raw230400',len(d), d[:16].hex() if d else 'EMPTY')
        if len(d)>20:
            lidar_cand.append(path)
    except Exception as e:
        print(path,'230400',e)

# if no lidar data, still map non-mega as lidar
lidar=None
if lidar_cand:
    lidar=lidar_cand[0]
elif mega:
    for p in ports:
        path=f'/dev/{p}'
        if path!=mega:
            lidar=path
print('MAP mega',mega,'lidar',lidar)
open('/tmp/_port_map.txt','w').write(f'MEGA={mega or ""}\nLIDAR={lidar or ""}\n')
PY
source /tmp/_port_map.txt
echo "USING MEGA=$MEGA LIDAR=$LIDAR"
[[ -n "$MEGA" ]] && pass ln -sfn "$(basename "$MEGA")" /dev/ttyMEGA
[[ -n "$LIDAR" ]] && pass ln -sfn "$(basename "$LIDAR")" /dev/ttyLIDAR
ls -l /dev/ttyMEGA /dev/ttyLIDAR

echo "=== start only lidar node briefly ==="
source /opt/ros/jazzy/setup.bash
source /home/pi/ws_ros2/install/setup.bash
: > /tmp/lidar_usb0.log
nohup ros2 run cspc_lidar cspc_lidar --ros-args \
  -r __node:=cspc_lidar \
  -p port:=/dev/ttyLIDAR \
  -p frame_id:=laser_frame \
  -p baudrate:=230400 \
  -p frequency:=8.0 \
  -p version:=4 \
  -p reversion:=true \
  -p auto_reconnect:=true \
  >/tmp/lidar_usb0.log 2>&1 &
sleep 10
timeout 6 ros2 topic hz /scan 2>&1 | head -12 || true
tail -40 /tmp/lidar_usb0.log
echo DONE
