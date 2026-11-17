#!/usr/bin/env bash
# AIGC-PP2 hermetic environment.  Source this in every shell:  source ~/Desktop/AIGC-PP2/env.sh
export ROOT="$HOME/Desktop/AIGC-PP2"
export HF_HOME="$ROOT/cache/hf"
export HUGGINGFACE_HUB_CACHE="$ROOT/cache/hf/hub"
export HF_XET_CACHE="$ROOT/cache/hf/xet"
export HF_HUB_DISABLE_XET=1
export PIP_CACHE_DIR="$ROOT/cache/pip"
export TORCH_HOME="$ROOT/cache/torch"
export TORCHINDUCTOR_CACHE_DIR="$ROOT/cache/torch/inductor"
export TRITON_CACHE_DIR="$ROOT/cache/torch/triton"
export XDG_CACHE_HOME="$ROOT/cache/xdg"
export XDG_CONFIG_HOME="$ROOT/cache/xdg/config"
export TMPDIR="$ROOT/tmp"
export CUDA_HOME=/usr/local/cuda
export PATH="$CUDA_HOME/bin:$ROOT/venv/bin:$PATH"
# GB10 unified memory: let the allocator return freed blocks
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"
mkdir -p "$HF_HOME/hub" "$HF_XET_CACHE" "$PIP_CACHE_DIR" "$TORCH_HOME" "$XDG_CACHE_HOME" "$TMPDIR"
if [ -f "$ROOT/venv/bin/activate" ]; then . "$ROOT/venv/bin/activate"; fi
