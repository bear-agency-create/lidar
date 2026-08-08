#!/usr/bin/env python3
import re
import time
from pathlib import Path

import serial

port = "/dev/ttyMEGA" if Path("/dev/ttyMEGA").exists() else "/dev/ttyUSB1"
enc_re = re.compile(r"ENC FL=(-?\d+) FR=(-?\d+) RL=(-?\d+) RR=(-?\d+)")
ser = serial.Serial(port, 115200, timeout=0.3)
time.sleep(2.2)


def enc():
    ser.reset_input_buffer()
    ser.write(b"ENC?\n")
    deadline = time.time() + 0.8
    while time.time() < deadline:
        match = enc_re.search(ser.readline().decode("ascii", "ignore"))
        if match:
            return [int(match.group(i)) for i in range(1, 5)]
    return None


commands = (
    ("UP", "1000 0 0"),
    ("DOWN", "-1000 0 0"),
    ("LEFT", "0 1000 0"),
    ("RIGHT", "0 -1000 0"),
)
for name, values in commands:
    ser.write(b"STOP\n")
    time.sleep(0.2)
    before = enc()
    deadline = time.time() + 0.8
    while time.time() < deadline:
        ser.write(f"SET_ROBOT_VELOCITY {values}\n".encode())
        time.sleep(0.05)
    ser.write(b"STOP\n")
    time.sleep(0.25)
    after = enc()
    delta = [after[i] - before[i] for i in range(4)] if before and after else None
    print(f"ARROW_{name} delta={delta}")
ser.close()
