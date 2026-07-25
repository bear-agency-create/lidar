#!/usr/bin/env python3
import serial
import time


def peek(port: str, baud: int, seconds: float = 2.0) -> None:
    try:
        ser = serial.Serial(port, baud, timeout=0.15)
    except Exception as e:
        print(port, "open fail", e)
        return
    time.sleep(0.3)
    ser.reset_input_buffer()
    lines = []
    t0 = time.time()
    while time.time() - t0 < seconds:
        raw = ser.readline()
        if not raw:
            continue
        line = raw.decode("ascii", "ignore").strip()
        if line:
            lines.append(line)
    ser.close()
    print("===", port, "@", baud, "n=", len(lines))
    for line in lines[:8]:
        print(" ", line)


def motor_burst(port: str) -> None:
    try:
        ser = serial.Serial(port, 115200, timeout=0.1)
    except Exception as e:
        print(port, e)
        return
    time.sleep(0.2)
    ser.reset_input_buffer()
    print("TEST MOTORS", port)
    for _ in range(50):
        # strong forward + yaw (legacy 2-arg)
        ser.write(b"SET_ROBOT_VELOCITY 600.00 1.20\n")
        time.sleep(0.05)
    ser.write(b"STOP\n")
    time.sleep(0.2)
    got = []
    for _ in range(12):
        line = ser.readline().decode("ascii", "ignore").strip()
        if line:
            got.append(line)
    print(" after", got[:6])
    ser.close()
    time.sleep(0.4)


def main() -> None:
    for port in ("/dev/ttyUSB0", "/dev/ttyUSB1"):
        peek(port, 115200)
    for port in ("/dev/ttyUSB0", "/dev/ttyUSB1"):
        peek(port, 230400)
    for port in ("/dev/ttyUSB0", "/dev/ttyUSB1"):
        motor_burst(port)
    print("done")


if __name__ == "__main__":
    main()
