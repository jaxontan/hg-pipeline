#!/usr/bin/env bash
# Hermetic environment for ~/Desktop/AIGC-Model.
# Source before ANY work on this machine:   source ~/Desktop/AIGC-Model/env.sh
#
# Design: HOME itself is redirected inside the folder, so even a tool that
# ignores every env var still writes inside the boundary. The real home is
# kept in MANJU_REAL_HOME for the few things that must reach it (~/.ssh).

export MANJU_REAL_HOME="${MANJU_REAL_HOME:-$HOME}"
export AIGC="${AIGC:-$MANJU_REAL_HOME/Desktop/AIGC-Model}"
export MANJU_BOUNDARY="$AIGC"

if [ ! -d "$AIGC" ]; then
  echo "env.sh: $AIGC missing — refusing to set a boundary on nothing" >&2
  return 1 2>/dev/null || exit 1
fi

export HOME="$AIGC/home"

export XDG_CACHE_HOME="$AIGC/.cache"
export XDG_CONFIG_HOME="$AIGC/.config"
export XDG_DATA_HOME="$AIGC/.local/share"
export XDG_STATE_HOME="$AIGC/.local/state"

export HF_HOME="$AIGC/hf"
export HF_HUB_CACHE="$AIGC/hf/hub"
export HUGGINGFACE_HUB_CACHE="$HF_HUB_CACHE"
export TRANSFORMERS_CACHE="$HF_HUB_CACHE"
export DIFFUSERS_CACHE="$HF_HUB_CACHE"

export TORCH_HOME="$AIGC/.cache/torch"
export TORCHINDUCTOR_CACHE_DIR="$AIGC/.cache/inductor"
export TRITON_CACHE_DIR="$AIGC/.cache/triton"
export CUDA_CACHE_PATH="$AIGC/.cache/cuda"
export CUDA_CACHE_MAXSIZE=4294967296

export PIP_CACHE_DIR="$AIGC/.cache/pip"
export UV_CACHE_DIR="$AIGC/.cache/uv"
export POETRY_CACHE_DIR="$AIGC/.cache/poetry"
export npm_config_cache="$AIGC/.cache/npm"
export TMPDIR="$AIGC/tmp"
export TMUX_TMPDIR="$TMPDIR"

export OLLAMA_MODELS="$AIGC/models/ollama"
export OLLAMA_HOME="$AIGC/app/ollama"

export BLENDER_USER_CONFIG="$AIGC/.config/blender"
export BLENDER_USER_SCRIPTS="$AIGC/.config/blender/scripts"
export BLENDER_USER_DATAFILES="$AIGC/.config/blender/datafiles"

export CUDA_HOME="/usr/local/cuda"
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"
export MANJU_EPHEMERAL=1

export PATH="$AIGC/venv/bin:$AIGC/bin:$CUDA_HOME/bin:$PATH"

for d in "$HOME" "$HF_HUB_CACHE" "$XDG_CACHE_HOME" "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" \
         "$XDG_STATE_HOME" "$TORCH_HOME" "$TRITON_CACHE_DIR" "$CUDA_CACHE_PATH" \
         "$PIP_CACHE_DIR" "$UV_CACHE_DIR" "$TMPDIR" "$AIGC/bin" "$AIGC/app/os" \
         "$AIGC/models" "$AIGC/work/input" "$AIGC/work/output" "$AIGC/work/temp" \
         "$AIGC/provenance" "$AIGC/archive" "$AIGC/logs"; do
  [ -d "$d" ] || mkdir -p "$d"
done

if [ -f "$AIGC/venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  . "$AIGC/venv/bin/activate"
fi

if [ -f "$AIGC/env.local" ]; then
  # shellcheck disable=SC1091
  set -a
  . "$AIGC/env.local"
  set +a
fi

echo "AIGC boundary : $AIGC"
echo "real home     : $MANJU_REAL_HOME  (use this for ~/.ssh, nothing else)"
echo "scratch       : $TMPDIR"
echo "weights       : $HF_HOME"
echo "rule 0        : nothing is written outside the boundary (see AGENTS.md)"
