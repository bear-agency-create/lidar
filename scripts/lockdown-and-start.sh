#!/bin/bash
# Run ON the Pi: start stack+kiosk, block Mac/other controllers until reboot.
set -e
LAPTOP="10.255.210.211"
ROBOT_SELF="10.255.210.201"
# Known/suspected Mac / friend host(s) on this LAN (ARP had .217)
MAC_BLOCK_IPS="${MAC_BLOCK_IPS:-10.255.210.217}"

echo "[lockdown] who is talking to :8765"
ss -tn sport = :8765 || true
echo "[lockdown] neighbors"
ip neigh show || true

echo "[lockdown] iptables DROP (until reboot) for Mac/foreign controllers"
# Keep established, allow laptop + localhost + robot self
sudo iptables -C INPUT -s "$LAPTOP" -j ACCEPT 2>/dev/null || sudo iptables -I INPUT 1 -s "$LAPTOP" -j ACCEPT
sudo iptables -C INPUT -s 127.0.0.1 -j ACCEPT 2>/dev/null || sudo iptables -I INPUT 1 -s 127.0.0.1 -j ACCEPT
sudo iptables -C INPUT -i lo -j ACCEPT 2>/dev/null || sudo iptables -I INPUT 1 -i lo -j ACCEPT

for ip in $MAC_BLOCK_IPS; do
  echo "  DROP $ip (tcp 22,8765 + all)"
  sudo iptables -C INPUT -s "$ip" -j DROP 2>/dev/null || sudo iptables -I INPUT 1 -s "$ip" -j DROP
done

# Also drop anyone else hitting control port except laptop (ephemeral lockdown)
# Insert before general ACCEPT policies: reject non-laptop to 8765
sudo iptables -C INPUT -p tcp --dport 8765 ! -s "$LAPTOP" ! -s 127.0.0.1 -j DROP 2>/dev/null \
  || sudo iptables -I INPUT 1 -p tcp --dport 8765 ! -s "$LAPTOP" ! -s 127.0.0.1 -j DROP
sudo iptables -C INPUT -p tcp --dport 22 ! -s "$LAPTOP" ! -s 127.0.0.1 -j DROP 2>/dev/null \
  || sudo iptables -I INPUT 1 -p tcp --dport 22 ! -s "$LAPTOP" ! -s 127.0.0.1 -j DROP

echo "[lockdown] iptables INPUT:"
sudo iptables -L INPUT -n -v --line-numbers | head -30

echo "[start] drive/map stack"
bash ~/robot_nav/lidar_map/start_drive_map.sh || true
sleep 2

echo "[start] kiosk on robot monitor"
if [ -x ~/robot_nav/monitor/start_kiosk_on_robot.sh ]; then
  bash ~/robot_nav/monitor/start_kiosk_on_robot.sh || true
elif [ -x ~/robot_nav/monitor/start ]; then
  bash ~/robot_nav/monitor/start || true
fi

sleep 2
echo "[check] processes"
pgrep -af 'main.py|drive_encoders|cspc_lidar|chromium' | grep -v grep || true
curl -s -o /dev/null -w "http=%{http_code}\n" http://127.0.0.1:8765/ || true
curl -s -o /dev/null -w "admin=%{http_code}\n" http://127.0.0.1:8765/admin || true
echo "[done] Mac blocked until reboot. Laptop $LAPTOP allowed."
