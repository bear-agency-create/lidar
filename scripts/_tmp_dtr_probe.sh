#!/usr/bin/env bash
set -eo pipefail
pkill -9 -f cspc_lidar || true
fuser -k /dev/ttyUSB1 2>/dev/null || true
sleep 1

python3 - <<'PY'
import serial, time

# Try DTR/RTS combinations — some LiDARs gate motor/data on these lines
for dtr in (False, True):
  for rts in (False, True):
    s = serial.Serial()
    s.port = '/dev/ttyUSB1'
    s.baudrate = 230400
    s.timeout = 0.2
    s.dtr = dtr
    s.rts = rts
    s.open()
    time.sleep(0.3)
    s.reset_input_buffer()
    # CSPC/COIN often start with 0xA5 0x20 / 0xA5 0x60 style; also try SDK pkt
    for pkt in (bytes([0xA5,0x20]), bytes([0xA5,0x60]), bytes([0xA5,0x90]),
                bytes([0xAA,0x55,0xF2,0x00]), bytes([0xAA,0x55,0xF0,0x00])):
      s.write(pkt)
      time.sleep(0.6)
      d = s.read(4096)
      if d:
        print(f'DTR={dtr} RTS={rts} pkt={pkt.hex()} n={len(d)} hex={d[:24].hex()}')
        s.close()
        raise SystemExit
    # also listen without cmd
    time.sleep(0.5)
    d = s.read(4096)
    print(f'DTR={dtr} RTS={rts} listen n={len(d)}')
    s.close()
    time.sleep(0.2)
print('NO DATA with any DTR/RTS')
PY

# Keep stack up for motor testing
echo raspberry | sudo -S systemctl start robot-nav.service
echo raspberry | sudo -S systemctl start robot-nav-watchdog.timer || true
sleep 6
python3 - <<'PY'
import json,urllib.request
j=json.load(urllib.request.urlopen('http://127.0.0.1:8765/api/scan',timeout=3))
print('ui ok',j.get('ok'),'odom',j.get('odom_ok'),'err',j.get('error'))
# confirm mega still answers via drive path
print('pose', j.get('pose'))
PY
grep -n 'RAMP_START\|PWM_FLOOR' /home/pi/robot_nav/arduino/MecanumTeleopBridge/MecanumTeleopBridge.ino | head -10
echo DONE
