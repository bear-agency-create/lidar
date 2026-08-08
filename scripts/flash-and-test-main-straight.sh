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
if [[ -z "$MEGA" || ! -e "$MEGA" ]]; then
  MEGA=/dev/ttyUSB1
fi
echo "FLASH_PORT=$MEGA"
"$CLI" upload -p "$MEGA" --fqbn arduino:avr:mega "$ROOT/arduino/MecanumTeleopBridge"

echo raspberry | sudo -S systemctl start robot-nav.service
for _ in $(seq 1 15); do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 1 http://127.0.0.1:8765/ || true)"
  [[ "$code" == "200" ]] && break
  sleep 1
done
echo "HTTP=$code"

python3 <<'PY'
import json
import time
import urllib.request

URL = "http://127.0.0.1:8765"

def post(path: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload or {}).encode()
    req = urllib.request.Request(
        URL + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=2) as response:
        return json.loads(response.read().decode())

def run(label: str, vx: float, seconds: float = 2.0) -> None:
    print(f"MAIN_{label}_START vx={vx}", flush=True)
    deadline = time.monotonic() + seconds
    last = None
    while time.monotonic() < deadline:
        last = post("/api/cmd", {"vx": vx, "vy": 0.0, "w": 0.0})
        time.sleep(0.08)
    print(f"MAIN_{label}_API={last}", flush=True)
    print(f"MAIN_{label}_STOP={post('/api/cmd/stop')}", flush=True)

run("FWD", 1.0)
time.sleep(1.0)
run("BACK", -1.0)
time.sleep(0.5)
post("/api/cmd/stop")
print("MAIN_STRAIGHT_TEST_DONE", flush=True)
PY

echo raspberry | sudo -S systemctl start robot-nav-watchdog.timer || true
systemctl is-active robot-nav
curl -s -o /dev/null -w 'PANEL_HTTP=%{http_code}\n' http://127.0.0.1:8765/operator-panel
echo MAIN_DEPLOY_DONE
