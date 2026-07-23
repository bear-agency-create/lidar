#!/usr/bin/env python3
"""Exclusive Mega serial test — stop robot_driver first."""
import serial
import time

PORT = "/dev/ttyUSB0"


def main() -> None:
    ser = serial.Serial(PORT, 115200, timeout=0.4)
    time.sleep(2.0)
    ser.reset_input_buffer()
    print("--- banner ---")
    t0 = time.time()
    while time.time() - t0 < 2.0:
        line = ser.readline().decode(errors="ignore").strip()
        if line:
            print(repr(line))

    print("--- send w (forward) 4s ---")
    ser.write(b"w\n")
    ser.flush()
    t0 = time.time()
    while time.time() - t0 < 4.0:
        line = ser.readline().decode(errors="ignore").strip()
        if line:
            print(line)

    print("--- STOP ---")
    ser.write(b"x\n")
    ser.flush()
    time.sleep(0.5)

    print("--- SET_ROBOT_VELOCITY 700 ---")
    ser.write(b"SET_ROBOT_VELOCITY 700.00 0.00 0.00\n")
    ser.flush()
    t0 = time.time()
    while time.time() - t0 < 4.0:
        line = ser.readline().decode(errors="ignore").strip()
        if line:
            print(line)

    ser.write(b"STOP\n")
    ser.flush()
    print("DONE")
    ser.close()


if __name__ == "__main__":
    main()
