#!/usr/bin/env bash
set -eo pipefail

mkdir -p ~/lidar ~/robot_nav

if [ -d ~/lidar/.git ]; then
  git -C ~/lidar fetch origin
  git -C ~/lidar reset --hard origin/main
else
  git clone https://github.com/bear-agency-create/lidar.git ~/lidar
fi

git -C ~/lidar log -1 --oneline
chmod +x ~/lidar/lidar_map/update_from_github.sh
RESTART=1 ~/lidar/lidar_map/update_from_github.sh

echo '--- processes ---'
pgrep -af 'main.py|drive_encoders|cspc_lidar' | grep -v grep || true
echo '--- http ---'
curl -s -o /dev/null -w 'http=%{http_code}\n' http://127.0.0.1:8765/ || true
