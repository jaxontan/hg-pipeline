#!/bin/bash
set -uo pipefail
ROOT="$HOME/Desktop/AIGC-PP2"
cd "$ROOT" || exit 1
. "$ROOT/env.sh"

echo "=== versions ==="
venv/bin/python - <<'PY'
import torch, sys
print("python", sys.version.split()[0])
print("torch", torch.__version__, "cuda", torch.version.cuda, "avail", torch.cuda.is_available())
print("device", torch.cuda.get_device_capability(0))
import transformers; print("transformers", transformers.__version__)
PY
echo "comfyui: $(git -C ComfyUI log -1 --format='%h %ad' --date=short)"
echo "venv-tts transformers: $(venv-tts/bin/python -c 'import transformers;print(transformers.__version__)' 2>/dev/null)"
echo

echo "=== model sizes by class ==="
for d in diffusion_models text_encoders vae audio_encoders loras clip_vision latent_upscale_models tts; do
  echo "--- $d ($(du -sh "$ROOT/models/$d" 2>/dev/null | cut -f1))"
  find "$ROOT/models/$d" -type f -printf '%8.2f GB  %P\n' 2>/dev/null | awk '{printf "   %s %s %s\n", $1, $2, $3}'
done
echo
echo "models total: $(du -sh "$ROOT/models" | cut -f1)"
echo "project total: $(du -sh "$ROOT" | cut -f1)"
echo "venv: $(du -sh "$ROOT/venv" | cut -f1)  venv-tts: $(du -sh "$ROOT/venv-tts" | cut -f1)"
echo "disk: $(df -h "$ROOT" | tail -1 | awk '{print $3" used, "$4" free"}')"
echo
echo "=== custom nodes ==="
ls -1 ComfyUI/custom_nodes 2>/dev/null
echo
echo "=== outputs / projects so far ==="
du -sh outputs projects 2>/dev/null
