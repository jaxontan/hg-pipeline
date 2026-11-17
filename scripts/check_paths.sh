#!/bin/bash
ROOT="$HOME/Desktop/AIGC-PP2"
echo "=== extra_model_paths.yaml ==="
cat "$ROOT/extra_model_paths.yaml"
echo
echo "=== folder_paths knows about upscale? ==="
cd "$ROOT" && . ./env.sh
python - <<'PY'
import sys, os
sys.path.insert(0, os.path.expanduser("~/Desktop/AIGC-PP2/ComfyUI"))
import folder_paths
for k in ("latent_upscale_models", "upscale_models", "audio_encoders", "clip_vision", "tts"):
    try:
        print(f"  {k}: {folder_paths.get_folder_paths(k) if hasattr(folder_paths,'get_folder_paths') else 'n/a'}")
    except Exception as e:
        print(f"  {k}: ERR {e}")
print("  all keys:", [k for k in dir(folder_paths) if "folder" in k.lower()][:10])
try:
    print("  latent upscalers:", folder_paths.get_filename_list("latent_upscale_models"))
except Exception as e:
    print("  get_filename_list(latent_upscale_models) ERR:", e)
PY
