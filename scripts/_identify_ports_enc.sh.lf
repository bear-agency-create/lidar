#!/bin/bash
set -e
echo "=== ALL TTY / USB ==="
ls -la /dev/ttyUSB* /dev/ttyACM* /dev/ttyAMA* /dev/ttyLIDAR /dev/ttyMEGA 2>&1 || true
echo
echo "=== by-id ==="
ls -la /dev/serial/by-id/ 2>&1 || true
echo
echo "=== by-path ==="
ls -la /dev/serial/by-path/ 2>&1 || true
echo
echo "=== lsusb ==="
lsusb 2>&1 || true
echo
echo "=== dmesg USB recent ==="
dmesg -T 2>/dev/null | grep -iE 'ttyUSB|ch34|1a86|cdc_acm|USB Serial' | tail -50 || true
echo
echo "=== holders ==="
fuser -v /dev/ttyUSB0 /dev/ttyUSB1 /dev/ttyACM0 /dev/ttyMEGA /dev/ttyLIDAR 2>&1 || true
echo
echo "=== processes ==="
pgrep -af 'cspc_lidar|drive_encoders|lidar_map/main' || true
echo
echo "=== udev rules ==="
ls /etc/udev/rules.d/*lidar* /etc/udev/rules.d/*mega* /etc/udev/rules.d/*robot* 2>/dev/null || true
grep -rH 'ttyLIDAR\|ttyMEGA\|1a86\|ATTRS' /etc/udev/rules.d/ 2>/dev/null | head -40 || true
echo
python3 - <<'PY'
import glob, os, serial, time, subprocess

print("=== PORT PROBE (PING / READY / ENC) ===")
# free mega briefly if drive holds it
subprocess.call("pkill -9 -f drive_encoders.py", shell=True)
subprocess.call("pkill -9 -f cspc_lidar", shell=True)
time.sleep(1.2)

ports = sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))
if not ports:
    print("NO USB SERIAL PORTS")
for port in ports:
    name = os.path.basename(port)
    print(f"\n--- {port} ---")
    # usb ids
    base = f"/sys/class/tty/{name}/device"
    cur = os.path.realpath(base) if os.path.exists(base) else None
    if cur:
        for _ in range(8):
            vids = []
            for f in ["idVendor", "idProduct", "product", "serial", "manufacturer"]:
                p = os.path.join(cur, f)
                if os.path.exists(p):
                    vids.append(f"{f}={open(p).read().strip()}")
            if any(x.startswith("idVendor") for x in vids):
                print(" ", "; ".join(vids))
                break
            cur = os.path.dirname(cur)
    try:
        s = serial.Serial(port, 115200, timeout=0.4)
        time.sleep(2.4)  # mega reset
        s.reset_input_buffer()
        boot = s.read(400)
        print(" boot:", repr(boot[:200]))
        for cmd in (b"PING\n", b"ENC?\n"):
            s.write(cmd)
            time.sleep(0.35)
            print(" ", cmd.strip().decode(), "->", repr(s.read(200)))
        # also try lidar baud briefly
        s.close()
    except Exception as e:
        print(" ERR115200", e)
        continue
    # lidar-ish: 230400 noise check
    try:
        s = serial.Serial(port, 230400, timeout=0.3)
        time.sleep(0.2)
        s.reset_input_buffer()
        time.sleep(0.5)
        raw = s.read(64)
        print(" baud230400 bytes", len(raw), "sample", raw[:16].hex() if raw else "-")
        s.close()
    except Exception as e:
        print(" ERR230400", e)

print("\n=== ENCODER PIN MAP (from firmware) ===")
print("FL A/B = 50/51  (known DEAD in firmware comments)")
print("FR A/B = 48/49")
print("RL A/B = 52/53")
print("RR A/B = 46/47")
print("Encoders are ON the Mega GPIO, not a separate USB device.")
print("Recognition = ENC? on Mega serial while wheels move.")
PY
