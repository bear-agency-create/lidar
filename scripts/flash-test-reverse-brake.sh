#!/bin/bash
set -euo pipefail

ROOT=/home/pi/robot_nav
CLI=/home/pi/bin/arduino-cli

echo raspberry | sudo -S systemctl stop robot-nav-watchdog.timer || true
echo raspberry | sudo -S systemctl stop robot-nav.service || true
pkill -9 -f drive_encoders.py || true
fuser -k /dev/ttyMEGA 2>/dev/null || true
fuser -k /dev/ttyUSB1 2>/dev/null || true
sleep 2

"$CLI" compile --fqbn arduino:avr:mega "$ROOT/arduino/MecanumTeleopBridge"
MEGA="$(readlink -f /dev/ttyMEGA 2>/dev/null || true)"
if [[ -z "$MEGA" || ! -e "$MEGA" ]]; then MEGA=/dev/ttyUSB1; fi
"$CLI" upload -p "$MEGA" --fqbn arduino:avr:mega "$ROOT/arduino/MecanumTeleopBridge"

echo raspberry | sudo -S systemctl start robot-nav.service
for _ in $(seq 1 15); do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 1 http://127.0.0.1:8765/ || true)"
  [[ "$code" == "200" ]] && break
  sleep 1
done

python3 <<'PY'
import json
import time
import urllib.request

URL = "http://127.0.0.1:8765"

def post(path, body=None):
    req = urllib.request.Request(
        URL + path,
        data=json.dumps(body or {}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=2) as response:
        return json.loads(response.read().decode())

def stream(vy, seconds):
    deadline = time.monotonic() + seconds
    response = None
    while time.monotonic() < deadline:
        response = post("/api/cmd", {"vx": 0.0, "vy": vy, "w": 0.0})
        time.sleep(0.06)
    return response

print("RIGHT_START", stream(-0.70, 1.2), flush=True)
# Deliberately reverse immediately, with no stop or pause.
print("LEFT_IMMEDIATE", stream(+0.70, 1.2), flush=True)
print("BRAKE", post("/api/cmd/stop"), flush=True)
time.sleep(1.0)
# Confirm the latched brake releases on the next valid command.
print("RIGHT_AFTER_BRAKE", stream(-0.55, 0.8), flush=True)
print("FINAL_BRAKE", post("/api/cmd/stop"), flush=True)
print("REVERSAL_BRAKE_TEST_DONE", flush=True)
PY

echo raspberry | sudo -S systemctl start robot-nav-watchdog.timer || true
systemctl is-active robot-nav
curl -s -o /dev/null -w 'PANEL_HTTP=%{http_code}\n' http://127.0.0.1:8765/
echo REVERSAL_DEPLOY_DONE
