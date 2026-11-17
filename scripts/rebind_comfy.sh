#!/bin/bash
# Restart ComfyUI on the new bind address and verify.
set -uo pipefail
ROOT="$HOME/Desktop/AIGC-PP2"
cd "$ROOT" || exit 1
. "$ROOT/env.sh"

echo "=== stop ==="
pkill -f 'ComfyUI/main.py' 2>/dev/null
for i in $(seq 1 30); do
  pgrep -f 'ComfyUI/main.py' >/dev/null || break
  sleep 1
done
pgrep -f 'ComfyUI/main.py' && { echo "STILL RUNNING - abort"; exit 1; }

echo "=== start ==="
nohup bash "$ROOT/start_comfy.sh" > /dev/null 2>&1 &
echo "launched pid $!"

for i in $(seq 1 120); do
  if curl -s --max-time 3 http://127.0.0.1:9090/system_stats >/dev/null 2>&1; then
    echo "ComfyUI UP after ~${i}s"
    break
  fi
  sleep 1
done

echo
echo "=== listening sockets on 9090 ==="
ss -ltn 2>/dev/null | grep 9090 || echo "  none"

echo
echo "=== reachable from the host's LAN address ==="
IP=$(hostname -I | awk '{print $1}')
echo "host ip: $IP"
curl -s --max-time 10 "http://$IP:9090/system_stats" | head -c 200
echo
echo
echo "=== queue ==="
curl -s --max-time 10 http://127.0.0.1:9090/queue
echo
echo "=== launcher bind line ==="
grep -n 'listen' "$ROOT/start_comfy.sh"
