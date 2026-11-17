#!/usr/bin/env bash
# AIGC-PP2 ComfyUI launcher.  GB10 tuned:
#   --disable-pinned-memory  unified memory: pinned host buffers steal from the GPU pool
#   --reserve-vram 8         leave headroom for the desktop/compositor
#   NOTE: SageAttention is NOT usable on GB10 - sageattn raises
#         ValueError: Unsupported CUDA architecture: sm121
#
# Bind: ComfyUI has no authentication and custom nodes run arbitrary Python.
#   COMFY_BIND=0.0.0.0  (default) reachable from the LAN, e.g. http://192.168.1.103:9090
#   COMFY_BIND=127.0.0.1          localhost only - use when the box is on an untrusted network
set -uo pipefail
ROOT="$HOME/Desktop/AIGC-PP2"
cd "$ROOT" || exit 1
. "$ROOT/env.sh"

exec python ComfyUI/main.py \
  --listen "${COMFY_BIND:-0.0.0.0}" --port 9090 \
  --extra-model-paths-config "$ROOT/extra_model_paths.yaml" \
  --output-directory "$ROOT/outputs" \
  --input-directory "$ROOT/assets/input" \
  --temp-directory "$ROOT/tmp" \
  --disable-auto-launch \
  --disable-pinned-memory \
  --reserve-vram 8 \
  >> "$ROOT/logs/comfyui.log" 2>&1
