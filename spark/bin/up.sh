#!/usr/bin/env bash
# up.sh — start ComfyUI + Manju gateway under a tmux supervisor session.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AIGC="${AIGC:-$(cd "$SCRIPT_DIR/.." && pwd)}"
# shellcheck disable=SC1091
source "$AIGC/env.sh" >/dev/null

COMFY_MEMORY_MAX="${COMFY_MEMORY_MAX:-44G}"
# Bind address for ComfyUI. 127.0.0.1 keeps it loopback-only; 0.0.0.0 exposes it to the LAN
# so the workstation browser can open the graph editor and the MaskEditor canvas.
# NOTE: ComfyUI itself is unauthenticated — the bearer token on :8000 protects the gateway,
# not this port. Anything on the LAN that can reach :8188 can queue arbitrary workflows.
COMFY_LISTEN="${COMFY_LISTEN:-0.0.0.0}"

if [ "${1:-}" = "--supervise-comfy" ]; then
  cd "$AIGC/app/ComfyUI"
  while true; do
    rc=0
    systemd-run --user --scope -p "MemoryMax=$COMFY_MEMORY_MAX" -- \
      "$AIGC/venv/bin/python" "$AIGC/app/ComfyUI/main.py" \
      --listen "$COMFY_LISTEN" --port 8188 --disable-auto-launch \
      --base-directory "$AIGC/app/ComfyUI" \
      --extra-model-paths-config "$AIGC/app/extra_model_paths.yaml" \
      --output-directory "$AIGC/work/output" \
      --input-directory "$AIGC/work/input" \
      --temp-directory "$AIGC/work/temp" \
      --use-sage-attention --disable-pinned-memory --reserve-vram 8 \
      >> "$AIGC/logs/comfyui.log" 2>&1 || rc=$?
    echo "[$(date -u +%FT%TZ)] comfyui exited ($rc), restarting in 2s" >> "$AIGC/logs/comfyui.log"
    sleep 2
  done
fi

if [ "${1:-}" = "--supervise-gateway" ]; then
  cd "$AIGC"
  while true; do
    rc=0
    "$AIGC/venv/bin/python" "$AIGC/app/gateway.py" >> "$AIGC/logs/gateway.log" 2>&1 || rc=$?
    echo "[$(date -u +%FT%TZ)] gateway exited ($rc), restarting in 2s" >> "$AIGC/logs/gateway.log"
    sleep 2
  done
fi

if [ -z "${FREEFIELD_TOKEN:-}" ]; then
  echo "up.sh: FREEFIELD_TOKEN is not set (put it in $AIGC/env.local with chmod 600)" >&2
  exit 1
fi

cat > "$AIGC/app/extra_model_paths.yaml" <<YAML
manju:
  base_path: $AIGC/models
  diffusion_models: diffusion_models
  text_encoders: text_encoders
  vae: vae
  loras: loras
  checkpoints: checkpoints
  clip_vision: clip_vision
  latent_upscale_models: latent_upscale_models
  upscale_models: upscale_models
  model_patches: model_patches
  geometry_estimation: geometry_estimation
  background_removal: background_removal
  frame_interpolation: frame_interpolation
  audio_encoders: audio_encoders
  embeddings: embeddings
  detection: detection
YAML

if tmux has-session -t manju 2>/dev/null; then
  echo "up.sh: tmux session 'manju' already running"
  exit 0
fi

tmux new-session -d -s manju -n comfyui "$AIGC/bin/up.sh --supervise-comfy"
tmux new-window -t manju -n gateway "$AIGC/bin/up.sh --supervise-gateway"

echo "waiting for ComfyUI (:8188) and gateway (:8000)..."
for _ in $(seq 1 90); do
  if curl -sf http://127.0.0.1:8188/system_stats >/dev/null 2>&1 && \
     curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "up.sh: ComfyUI (MemoryMax=$COMFY_MEMORY_MAX, --use-sage-attention) + gateway (:8000) UP"
    exit 0
  fi
  sleep 1
done

echo "up.sh: timed out waiting for services; tailing logs:" >&2
tail -n 30 "$AIGC/logs/comfyui.log" "$AIGC/logs/gateway.log" >&2 || true
exit 1
