#!/usr/bin/env python3
"""One-shot Mega motor/encoder diagnostic (open-loop + mild PI)."""
import re
import sys
import time

import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyMEGA"


def enc_now(s: serial.Serial):
    s.write(b"ENC?\n")
    t0 = time.time()
    while time.time() - t0 < 0.5:
        line = s.readline().decode(errors="ignore").strip()
        m = re.match(r"ENC FL=(-?\d+) FR=(-?\d+) RL=(-?\d+) RR=(-?\d+)", line)
        if m:
            return [int(m.group(i)) for i in range(1, 5)]
    return None


def burst(s: serial.Serial, label: str, cmd: str, dur: float = 1.5) -> None:
    a = enc_now(s)
    t0 = time.time()
    while time.time() - t0 < dur:
        s.write((cmd + "\n").encode())
        time.sleep(0.05)
    s.write(b"STOP\n")
    time.sleep(0.15)
    b = enc_now(s)
    if a is None or b is None:
        print(label, "ENC fail", a, b)
        return
    d = [b[i] - a[i] for i in range(4)]
    tps = [round(x / dur) for x in d]
    print(
        f"{label}: dFL={d[0]:6d} dFR={d[1]:6d} dRL={d[2]:6d} dRR={d[3]:6d}  TPS={tps}"
    )


def wait_ready(s: serial.Serial, timeout: float = 4.0) -> None:
    """Mega resets on Serial open (DTR); wait for firmware banner."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        line = s.readline().decode(errors="ignore").strip()
        if line:
            print("boot:", line)
            if "READY" in line:
                return
    print("warn: no READY banner")


def main() -> None:
    s = serial.Serial(PORT, 115200, timeout=0.08)
    wait_ready(s)
    s.reset_input_buffer()
    for cmd in ["SET_PIDV 0 0", "STOP"]:
        s.write((cmd + "\n").encode())
        time.sleep(0.05)
    time.sleep(0.2)
    s.reset_input_buffer()

    print("open-loop PIDV=0")
    burst(s, "FWD", "SET_ROBOT_VELOCITY 120 0 0", 1.5)
    burst(s, "BACK", "SET_ROBOT_VELOCITY -120 0 0", 1.5)
    burst(s, "STRL", "SET_ROBOT_VELOCITY 0 120 0", 1.2)
    burst(s, "STRR", "SET_ROBOT_VELOCITY 0 -120 0", 1.2)

    s.write(b"SET_PIDV 120 400\n")
    time.sleep(0.1)
    print("closed-loop PIDV=120 400")
    burst(s, "FWD_PI", "SET_ROBOT_VELOCITY 120 0 0", 1.5)
    burst(s, "BACK_PI", "SET_ROBOT_VELOCITY -120 0 0", 1.5)
    s.write(b"STOP\n")
    s.close()
    print("done")


if __name__ == "__main__":
    main()
