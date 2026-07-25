#!/usr/bin/env python3
"""Short Mega-only motor smoke test on /dev/ttyUSB0."""
import serial
import time

PORT = "/dev/ttyUSB0"
ser = serial.Serial(PORT, 115200, timeout=0.1)
time.sleep(0.4)
ser.reset_input_buffer()
print("burst forward+turn 2.5s on", PORT)
t0 = time.time()
while time.time() - t0 < 2.5:
    ser.write(b"SET_ROBOT_VELOCITY 700.00 1.50\n")
    time.sleep(0.05)
ser.write(b"STOP\n")
print("STOP")
time.sleep(0.3)
for _ in range(8):
    line = ser.readline().decode("ascii", "ignore").strip()
    if line:
        print(line)
ser.close()
