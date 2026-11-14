#!/bin/bash
set -e
. "/home/tdadmin/Desktop/AIGC-Model/env.sh"
mkdir -p "/home/tdadmin/Desktop/AIGC-Model/models/diffusion_models" "/home/tdadmin/Desktop/AIGC-Model/models/text_encoders" "/home/tdadmin/Desktop/AIGC-Model/models/vae" "/home/tdadmin/Desktop/AIGC-Model/models/loras" "/home/tdadmin/Desktop/AIGC-Model/models/checkpoints" "/home/tdadmin/Desktop/AIGC-Model/models/clip_vision" "/home/tdadmin/Desktop/AIGC-Model/models/latent_upscale_models" "/home/tdadmin/Desktop/AIGC-Model/models/upscale_models" "/home/tdadmin/Desktop/AIGC-Model/models/model_patches" "/home/tdadmin/Desktop/AIGC-Model/models/geometry_estimation" "/home/tdadmin/Desktop/AIGC-Model/models/background_removal" "/home/tdadmin/Desktop/AIGC-Model/models/frame_interpolation" "/home/tdadmin/Desktop/AIGC-Model/models/audio_encoders" "/home/tdadmin/Desktop/AIGC-Model/models/embeddings" "/home/tdadmin/Desktop/AIGC-Model/models/detection"
cd "$AIGC"

echo "=== [1/5] Creating isolated Python 3.12 virtualenv in $AIGC/venv ==="
if [ ! -d "$AIGC/venv" ]; then
    python3 -m venv "$AIGC/venv"
fi
. "$AIGC/venv/bin/activate"
pip install --progress-bar off -U pip wheel setuptools

echo "=== [2/5] Installing PyTorch CUDA 13.0 (aarch64 GB10) ==="
if ! python -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
    pip install --progress-bar off torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
fi
python -c "import torch; print('Verified PyTorch:', torch.__version__, 'CUDA:', torch.version.cuda, 'Device:', torch.cuda.get_device_name(0))"

echo "=== [3/5] Installing pinned ComfyUI (e3bee7f) ==="
if [ ! -d "$AIGC/comfy/.git" ]; then
    git clone https://github.com/Comfy-Org/ComfyUI.git "$AIGC/comfy"
fi
cd "$AIGC/comfy"
git checkout --quiet e3bee7ffcb7d6547ed0bcd15221792f3b8646b17
pip install --progress-bar off -r "$AIGC/comfy/requirements.txt"

echo "=== [4/5] Installing pinned Custom Nodes ==="

if [ ! -d "$AIGC/comfy/custom_nodes/ComfyUI-LTXVideo/.git" ]; then
    git clone https://github.com/Lightricks/ComfyUI-LTXVideo "$AIGC/comfy/custom_nodes/ComfyUI-LTXVideo"
fi
cd "$AIGC/comfy/custom_nodes/ComfyUI-LTXVideo" && git checkout --quiet 44c8a36b7c31ee00b4271daed11dc2a4aa481140
if [ -f "$AIGC/comfy/custom_nodes/ComfyUI-LTXVideo/requirements.txt" ]; then
    pip install --progress-bar off -r "$AIGC/comfy/custom_nodes/ComfyUI-LTXVideo/requirements.txt"
fi


if [ ! -d "$AIGC/comfy/custom_nodes/ComfyUI-CrossViewWarp/.git" ]; then
    git clone https://github.com/comfyrob/ComfyUI-CrossViewWarp "$AIGC/comfy/custom_nodes/ComfyUI-CrossViewWarp"
fi
cd "$AIGC/comfy/custom_nodes/ComfyUI-CrossViewWarp" && git checkout --quiet fbb1e93c7193329ff3ce7c17f95166b539687876
if [ -f "$AIGC/comfy/custom_nodes/ComfyUI-CrossViewWarp/requirements.txt" ]; then
    pip install --progress-bar off -r "$AIGC/comfy/custom_nodes/ComfyUI-CrossViewWarp/requirements.txt"
fi


echo "=== [5/5] Installing comfy-api-proxy, aiohttp, huggingface_hub & isolated ffmpeg ==="
pip install --progress-bar off "comfy-api-proxy==0.1.6" aiohttp "huggingface_hub[hf-xet]" imageio-ffmpeg
python - <<'PYEOF'
import os, pathlib, imageio_ffmpeg
venv_bin = pathlib.Path(os.environ["AIGC"]) / "venv" / "bin"
ffmpeg_exe = pathlib.Path(imageio_ffmpeg.get_ffmpeg_exe())
target = venv_bin / "ffmpeg"
if not target.exists():
    target.symlink_to(ffmpeg_exe)
print("Linked isolated ffmpeg ->", target.resolve())
PYEOF

echo "=== Cleaning pip cache inside $AIGC/.cache/pip to save disk space ==="
rm -rf "$AIGC/.cache/pip"/*
echo "SETUP_COMPLETE"
