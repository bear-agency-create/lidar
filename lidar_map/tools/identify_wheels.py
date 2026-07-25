#!/usr/bin/env python3
"""Solo each motor 3s — user identifies which physical wheel."""
import serial
import time

ser = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.3)
time.sleep(2.0)
ser.reset_input_buffer()

labels = [
    ("1", "FL slot — Driver1 MotA (pins ENA2 IN3/4)"),
    ("2", "FR slot — Driver2 MotA (pins ENA8 IN9/10)"),
    ("3", "RL slot — Driver1 MotB (pins ENB7 IN5/6)"),
    ("4", "RR slot — Driver2 MotB (pins ENB13 IN11/12)"),
]

print("WATCH THE ROBOT — one motor at a time")
for cmd, name in labels:
    print(f"\n>>> NOW: {name}  (3 seconds)")
    ser.write(f"{cmd}\n".encode())
    ser.flush()
    time.sleep(3.0)
    ser.write(b"x\n")
    ser.flush()
    time.sleep(1.5)
    print("   (pause)")

ser.write(b"STOP\n")
print("\nDONE — tell me for 1/2/3/4 which wheel: front-left / front-right / rear-left / rear-right")
ser.close()
