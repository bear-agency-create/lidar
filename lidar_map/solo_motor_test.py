#!/usr/bin/env python3
import serial
import time

ser = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.3)
time.sleep(2)
ser.reset_input_buffer()

def drain(sec: float) -> None:
    t0 = time.time()
    while time.time() - t0 < sec:
        line = ser.readline().decode(errors="ignore").strip()
        if line:
            print(line)

for label, cmd in [("FL", "1"), ("FR", "2"), ("RL", "3"), ("RR", "4")]:
    print(f"=== SOLO {label} 2.5s — WATCH WHICH WHEEL ===")
    ser.write(f"{cmd}\n".encode())
    ser.flush()
    drain(2.5)
    ser.write(b"x\n")
    ser.flush()
    time.sleep(0.5)

print("=== YAW LEFT 3s ===")
t0 = time.time()
while time.time() - t0 < 3:
    ser.write(b"SET_ROBOT_VELOCITY 0 0 1500\n")
    ser.flush()
    time.sleep(0.15)
ser.write(b"STOP\n")
time.sleep(0.4)

print("=== YAW RIGHT 3s ===")
t0 = time.time()
while time.time() - t0 < 3:
    ser.write(b"SET_ROBOT_VELOCITY 0 0 -1500\n")
    ser.flush()
    time.sleep(0.15)
ser.write(b"STOP\n")
print("DONE")
ser.close()
