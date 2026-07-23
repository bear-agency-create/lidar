#!/usr/bin/env python3
import serial
import time

ser = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.3)
time.sleep(2)
ser.reset_input_buffer()

def run(name, cmd, sec=3.0):
    print("===", name, cmd)
    t0 = time.time()
    while time.time() - t0 < sec:
        ser.write((cmd + "\n").encode())
        ser.flush()
        time.sleep(0.12)
        while ser.in_waiting:
            line = ser.readline().decode(errors="ignore").strip()
            if line.startswith("ACK") or line.startswith("READY"):
                print(line)
    ser.write(b"STOP\n")
    ser.flush()
    time.sleep(0.7)

run("FWD", "SET_ROBOT_VELOCITY 500 0 0")
run("BACK", "SET_ROBOT_VELOCITY -500 0 0")
run("STRAFE_L", "SET_ROBOT_VELOCITY 0 500 0")
run("STRAFE_R", "SET_ROBOT_VELOCITY 0 -500 0")
run("YAW_L", "SET_ROBOT_VELOCITY 0 0 1500")
run("YAW_R", "SET_ROBOT_VELOCITY 0 0 -1500")
print("DONE")
ser.close()
