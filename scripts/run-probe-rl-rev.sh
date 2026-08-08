#!/bin/bash
set -e
export PATH="$HOME/bin:$PATH"
echo raspberry | sudo -S systemctl stop robot-nav-watchdog.timer || true
echo raspberry | sudo -S systemctl stop robot-nav.service || true
pkill -f drive_encoders.py || true
sleep 2
python3 /tmp/probe-rl-rev.py | tee /tmp/probe-rl-rev.out
echo raspberry | sudo -S systemctl start robot-nav.service
sleep 5
echo raspberry | sudo -S systemctl start robot-nav-watchdog.timer || true
systemctl is-active robot-nav
curl -s -o /dev/null -w 'http=%{http_code}\n' http://127.0.0.1:8765/
curl -s -o /dev/null -w 'panel=%{http_code}\n' http://127.0.0.1:8765/operator-panel
curl -s -o /dev/null -w 'admin=%{http_code}\n' http://127.0.0.1:8765/admin
echo PROBE_STACK_DONE
