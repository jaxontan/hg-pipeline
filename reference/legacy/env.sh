#!/bin/bash
# Strict Zero-Residue Isolation for ~/Desktop/AIGC-Model
# Every cache, temp file, compiler artifact, and $HOME stays inside $AIGC.
export AIGC=/home/tdadmin/Desktop/AIGC-Model
export HOME=$AIGC/home
export HF_HOME=$AIGC/hf
export HF_HUB_CACHE=$AIGC/hf/hub
export PIP_CACHE_DIR=$AIGC/.cache/pip
export XDG_CACHE_HOME=$AIGC/.cache
export XDG_CONFIG_HOME=$AIGC/.config
export XDG_DATA_HOME=$AIGC/.local/share
export TRITON_CACHE_DIR=$AIGC/.cache/triton
export TORCHINDUCTOR_CACHE_DIR=$AIGC/.cache/inductor
export TORCH_HOME=$AIGC/.cache/torch
export TMPDIR=$AIGC/tmp
export CUDA_HOME=/usr/local/cuda
export CPATH=$AIGC/sysroot/usr/include/python3.12:$AIGC/sysroot/usr/include${CPATH:+:$CPATH}
export PATH=$AIGC/venv/bin:$CUDA_HOME/bin:$PATH
mkdir -p "$HOME" "$HF_HUB_CACHE" "$PIP_CACHE_DIR" "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" \
         "$TRITON_CACHE_DIR" "$TORCHINDUCTOR_CACHE_DIR" "$TORCH_HOME" "$TMPDIR" \
         "$AIGC/logs" "$AIGC/models" \
         "$AIGC/ephemeral_io/input" "$AIGC/ephemeral_io/output" "$AIGC/ephemeral_io/temp"
if [ -f "$AIGC/venv/bin/activate" ]; then
    . "$AIGC/venv/bin/activate"
fi
