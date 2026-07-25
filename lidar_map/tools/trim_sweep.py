#!/usr/bin/env python3
"""Find open-loop L/R trim with lowest |heading change| (PID off on Mega)."""
import math
import re
import time
import serial

PORT = "/dev/ttyUSB0"


def parse_pos(line):
    m = re.search(r"X=([-\d.]+) Y=([-\d.]+) Th=([-\d.]+) L=(-?\d+) R=(-?\d+)", line)
    if not m:
        return None
    return tuple(float(m.group(i)) for i in range(1, 6))


def run_burst(ser, seconds=1.6):
    ser.write(b"STOP\n")
    time.sleep(0.15)
    ser.reset_input_buffer()
    ser.write(b"RESET_ODOM\n")
    time.sleep(0.1)
    ser.reset_input_buffer()
    first = last = None
    t0 = time.time()
    while time.time() - t0 < seconds:
        ser.write(b"SET_ROBOT_VELOCITY 420 0 0\n")
        raw = ser.readline().decode("ascii", "ignore").strip()
        if raw.startswith("POS"):
            p = parse_pos(raw)
            if p:
                if first is None:
                    first = p
                last = p
        time.sleep(0.07)
    ser.write(b"STOP\n")
    time.sleep(0.25)
    if not first or not last:
        return None
    dth = last[2] - first[2]
    while dth > math.pi:
        dth -= 2 * math.pi
    while dth < -math.pi:
        dth += 2 * math.pi
    dist = math.hypot(last[0] - first[0], last[1] - first[1])
    return {
        "dth_deg": math.degrees(dth),
        "dist": dist,
        "L": int(last[3] - first[3]),
        "R": int(last[4] - first[4]),
    }


def main():
    ser = serial.Serial(PORT, 115200, timeout=0.2)
    time.sleep(2.0)
    ser.reset_input_buffer()
    ser.write(b"PING\n")
    time.sleep(0.2)
    print("boot", ser.read(200))

    # Disable PID if firmware supports it; also try soft via SET_PID
    for cmd in (b"SET_PID 0 0 0\n", b"SET_KP_YAW 0\n"):
        ser.write(cmd)
        time.sleep(0.05)

    candidates = [
        (100, 100),
        (96, 104),
        (94, 106),
        (92, 108),
        (90, 110),
        (88, 112),
        (94, 112),
        (96, 110),
        (98, 106),
        (102, 98),
        (104, 96),
        (106, 94),
    ]
    results = []
    for a, b in candidates:
        ser.write(f"SET_TRIM {a} {b}\n".encode())
        time.sleep(0.08)
        print(f"TRIM {a}/{b} ...", flush=True)
        r = run_burst(ser)
        if not r:
            print("  no data")
            continue
        score = abs(r["dth_deg"]) + (0 if r["dist"] > 400 else 50)
        print(
            f"  dTh={r['dth_deg']:+.1f}deg dist={r['dist']:.0f}mm "
            f"dL={r['L']} dR={r['R']} score={score:.1f}"
        )
        results.append((score, a, b, r))
        time.sleep(0.6)

    results.sort(key=lambda x: x[0])
    print("\nBEST:")
    for score, a, b, r in results[:5]:
        print(f"  {a}/{b}  dTh={r['dth_deg']:+.1f}  dist={r['dist']:.0f}  score={score:.1f}")
    if results:
        _, a, b, _ = results[0]
        ser.write(f"SET_TRIM {a} {b}\n".encode())
        print(f"\nApplied TRIM {a}/{b}")
    ser.close()


if __name__ == "__main__":
    main()
