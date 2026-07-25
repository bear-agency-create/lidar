#!/usr/bin/env python3
"""Diagnose Mega motor commands. Stop robot_driver first."""
import json
import time
from pathlib import Path

import serial

PORT = "/dev/ttyUSB0"
CMD = Path("/tmp/robot_cmd.json")


def main() -> None:
    ser = serial.Serial(PORT, 115200, timeout=0.25)
    time.sleep(2.0)
    ser.reset_input_buffer()
    print("=== banner ===")
    t0 = time.time()
    while time.time() - t0 < 1.2:
        line = ser.readline().decode(errors="ignore").strip()
        if line:
            print(line)

    print("=== letter w 3s ===")
    t0 = time.time()
    while time.time() - t0 < 3.0:
        ser.write(b"w\n")
        ser.flush()
        time.sleep(0.2)
    ser.write(b"x\n")
    ser.flush()
    time.sleep(0.4)

    print("=== SET_ROBOT_VELOCITY 600 3s ===")
    t0 = time.time()
    while time.time() - t0 < 3.0:
        ser.write(b"SET_ROBOT_VELOCITY 600.00 0.00 0.00\n")
        ser.flush()
        time.sleep(0.15)
    ser.write(b"STOP\n")
    ser.flush()
    print("=== serial tests done ===")
    ser.close()

    # leave a fresh cmd file for driver after restart
    CMD.write_text(
        json.dumps({"vx": 0.0, "vy": 0.0, "w": 0.0, "t": time.time()}),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
