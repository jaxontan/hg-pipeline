#!/bin/bash
set -uo pipefail
ROOT="$HOME/Desktop/AIGC-PP2"
cd "$ROOT" || exit 1

echo "=== patch extra_model_paths.yaml ==="
if ! grep -q 'latent_upscale_models' "$ROOT/extra_model_paths.yaml"; then
  sed -i 's|^  model_patches: model_patches|  model_patches: model_patches\n  latent_upscale_models: latent_upscale_models|' "$ROOT/extra_model_paths.yaml"
  echo "added latent_upscale_models"
else
  echo "already present"
fi
cat "$ROOT/extra_model_paths.yaml"

echo
echo "=== restart ComfyUI ==="
pkill -f 'ComfyUI/main.py' 2>/dev/null
for i in $(seq 1 30); do
  pgrep -f 'ComfyUI/main.py' >/dev/null || break
  sleep 1
done
pgrep -f 'ComfyUI/main.py' && { echo "STILL RUNNING - abort"; exit 1; }

nohup bash "$ROOT/start_comfy.sh" > /dev/null 2>&1 &
echo "launched pid $!"

for i in $(seq 1 90); do
  if curl -s --max-time 3 http://127.0.0.1:9090/system_stats >/dev/null 2>&1; then
    echo "ComfyUI UP after ~${i}s"
    break
  fi
  sleep 1
done

. "$ROOT/env.sh"
python - <<'PY'
import json, urllib.request
d = json.load(urllib.request.urlopen("http://127.0.0.1:9090/object_info/LatentUpscaleModelLoader", timeout=60))
print("upscaler options:", d["LatentUpscaleModelLoader"]["input"]["required"]["model_name"][0][:5])
d = json.load(urllib.request.urlopen("http://127.0.0.1:9090/object_info/LoadAudio", timeout=60))
print("audio options:", d["LoadAudio"]["input"]["required"]["audio"][0][:5])
PY
