#!/usr/bin/env python3
import serial
import time

ser = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.3)
time.sleep(2.5)
ser.reset_input_buffer()
print("banner")
t0 = time.time()
while time.time() - t0 < 1.5:
    line = ser.readline().decode(errors="ignore").strip()
    if line:
        print(line)

print("ALL_FWD 4s")
t0 = time.time()
while time.time() - t0 < 4:
    ser.write(b"SET_ROBOT_VELOCITY 500 0 0\n")
    ser.flush()
    time.sleep(0.12)
ser.write(b"STOP\n")
time.sleep(0.5)

for label, cmd in [("FL", "1"), ("FR", "2"), ("RL", "3"), ("RR", "4")]:
    print("SOLO", label, "2s")
    ser.write(f"{cmd}\n".encode())
    ser.flush()
    time.sleep(2.0)
    ser.write(b"x\n")
    ser.flush()
    time.sleep(0.4)

print("DONE")
ser.close()
