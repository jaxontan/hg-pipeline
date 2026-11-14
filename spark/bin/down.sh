#!/usr/bin/env bash
# down.sh — unload models and stop the tmux supervisor session cleanly.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AIGC="${AIGC:-$(cd "$SCRIPT_DIR/.." && pwd)}"
# shellcheck disable=SC1091
source "$AIGC/env.sh" >/dev/null

if [ -n "${FREEFIELD_TOKEN:-}" ]; then
  curl -sf -X POST -H "Authorization: Bearer $FREEFIELD_TOKEN" \
    -H "Content-Type: application/json" -d '{"unload_vram": true}' \
    http://127.0.0.1:8000/freefield/scrub >/dev/null 2>&1 || true
fi

if tmux has-session -t manju 2>/dev/null; then
  tmux kill-session -t manju
fi

for pat in "$AIGC/app/gateway.py" "$AIGC/app/ComfyUI/main.py"; do
  pids=$(pgrep -f "$pat" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    kill $pids 2>/dev/null || true
    for _ in $(seq 1 15); do
      pgrep -f "$pat" >/dev/null 2>&1 || break
      sleep 1
    done
    pids=$(pgrep -f "$pat" 2>/dev/null || true)
    [ -n "$pids" ] && kill -9 $pids 2>/dev/null || true
  fi
done

echo "down.sh: manju services stopped"
