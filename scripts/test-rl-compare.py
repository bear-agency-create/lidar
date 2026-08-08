#!/usr/bin/env python3
import re, time, serial
from pathlib import Path

PORT = "/dev/ttyMEGA" if Path("/dev/ttyMEGA").exists() else "/dev/ttyUSB1"
ENC = re.compile(r"ENC FL=(-?\d+) FR=(-?\d+) RL=(-?\d+) RR=(-?\d+)")

ser = serial.Serial(PORT, 115200, timeout=0.2)
time.sleep(2.5)
ser.reset_input_buffer()


def enc():
    ser.reset_input_buffer()
    ser.write(b"ENC?\n")
    t0 = time.time()
    while time.time() - t0 < 0.8:
        m = ENC.search(ser.readline().decode("ascii", "ignore"))
        if m:
            return [int(m.group(i)) for i in range(1, 5)]
    return None


def go(label, lines, hold_cmd, sec=1.5):
    for ln in lines:
        ser.write((ln + "\n").encode())
        time.sleep(0.1)
        print(" ", ser.read(256).decode("ascii", "ignore").strip()[:80])
    e0 = enc()
    t0 = time.time()
    mid = ""
    while time.time() - t0 < sec:
        ser.write((hold_cmd + "\n").encode())
        time.sleep(0.08)
        if 0.5 < time.time() - t0 < 0.7:
            ser.write(b"WHEEL_OUT?\n")
            time.sleep(0.1)
            mid = ser.read(256).decode("ascii", "ignore").strip()
    ser.write(b"STOP\n")
    time.sleep(0.4)
    e1 = enc()
    d = [e1[i] - e0[i] for i in range(4)] if e0 and e1 else None
    print(f"{label}: mid={mid}")
    print(f"  dENC={d} RL={d[2] if d else None}\n")


print("PORT", PORT)
go("ONE_-80", ["STOP"], "ONE_WHEEL 2 -80")
go(
    "MIX_onlyRL_-400",
    ["SET_PIDV 0 0", "SET_RLB 200", "SET_WSCALE 0 0 100 0", "STOP"],
    "SET_ROBOT_VELOCITY -400 0 0",
)
go(
    "MIX_all_-400",
    ["SET_WSCALE 100 100 100 100", "SET_RLB 200", "STOP"],
    "SET_ROBOT_VELOCITY -400 0 0",
)
go(
    "MIX_all_STRR",
    ["SET_WSCALE 100 100 100 100", "SET_RLB 200", "STOP"],
    "SET_ROBOT_VELOCITY 0 -400 0",
)
go("ONE_+80", ["STOP"], "ONE_WHEEL 2 80")
ser.close()
print("DONE")
