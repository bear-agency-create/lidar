#!/usr/bin/env python3
"""Probe RL both polarities and BACK with RLB boost."""
import re, time, serial
from pathlib import Path

PORT = "/dev/ttyMEGA" if Path("/dev/ttyMEGA").exists() else "/dev/ttyUSB1"
ENC = re.compile(r"ENC FL=(-?\d+) FR=(-?\d+) RL=(-?\d+) RR=(-?\d+)")
ser = serial.Serial(PORT, 115200, timeout=0.2)
time.sleep(2.2)
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


def cmd(s, w=0.08):
    ser.write((s + "\n").encode())
    time.sleep(w)
    ser.read(512)


def one(pct, sec=1.0):
    cmd("STOP", 0.15)
    e0 = enc()
    t0 = time.time()
    while time.time() - t0 < sec:
        ser.write(f"ONE_WHEEL 2 {pct}\n".encode())
        time.sleep(0.06)
    cmd("STOP", 0.3)
    e1 = enc()
    d = [e1[i] - e0[i] for i in range(4)] if e0 and e1 else None
    print(f"ONE {pct:+4d}% RL={d[2] if d else None} full={d}")


def vel(label, vx, rlb, sec=1.1):
    cmd("SET_PIDV 0 0")
    cmd(f"SET_RLB {rlb}")
    cmd("SET_WSCALE 100 100 100 100")
    cmd("STOP", 0.15)
    e0 = enc()
    t0 = time.time()
    out = ""
    while time.time() - t0 < sec:
        ser.write(f"SET_ROBOT_VELOCITY {vx} 0 0\n".encode())
        time.sleep(0.07)
        if not out and time.time() - t0 > 0.4:
            ser.write(b"WHEEL_OUT?\n")
            time.sleep(0.1)
            raw = ser.read(512).decode("ascii", "ignore")
            out = next((l for l in raw.splitlines() if "OUT" in l), "?")
    cmd("STOP", 0.3)
    e1 = enc()
    d = [e1[i] - e0[i] for i in range(4)] if e0 and e1 else None
    print(f"{label} RLB={rlb}: {out}")
    print(f"  RL={d[2] if d else None} dENC={d}")


cmd("PING", 0.2)
for p in (100, -100, 80, -80):
    one(p)
    time.sleep(0.3)
for rlb in (100, 185, 250):
    vel("BACK", -400, rlb)
    time.sleep(0.3)
vel("FWD", 400, 100)
ser.close()
print("PROBE_DONE")
