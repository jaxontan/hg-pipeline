#!/bin/bash
# Voice lane: separate venv because qwen-tts pins transformers 4.57.3 while ComfyUI needs 5.x
set -uo pipefail
ROOT="$HOME/Desktop/AIGC-PP2"
LOG="$ROOT/logs/venv-tts.log"
: > "$LOG"

echo "=== $(date -u) create venv-tts ===" >> "$LOG"
python3 -m venv "$ROOT/venv-tts" >> "$LOG" 2>&1
VP="$ROOT/venv-tts/bin"

# keep pip/HF caches inside ROOT
export PIP_CACHE_DIR="$ROOT/cache/pip"
export HF_HOME="$ROOT/cache/hf"
export TMPDIR="$ROOT/tmp"
export HF_HUB_DISABLE_XET=1
mkdir -p "$PIP_CACHE_DIR" "$TMPDIR"

"$VP/pip" install -q --upgrade pip >> "$LOG" 2>&1
echo "-- pip $(  "$VP/pip" --version)" >> "$LOG"

echo "=== torch cu130 ===" >> "$LOG"
"$VP/pip" install torch torchaudio --index-url https://download.pytorch.org/whl/cu130 >> "$LOG" 2>&1
echo "-- torch exit=$?" >> "$LOG"

echo "=== qwen-tts ===" >> "$LOG"
"$VP/pip" install qwen-tts >> "$LOG" 2>&1
echo "-- qwen-tts exit=$?" >> "$LOG"

echo "=== verify ===" >> "$LOG"
"$VP/python" - <<'PY' >> "$LOG" 2>&1
import torch, transformers
print("torch", torch.__version__, "cuda", torch.cuda.is_available())
print("transformers", transformers.__version__)
import qwen_tts, inspect
print("qwen_tts", getattr(qwen_tts, "__version__", "?"), "->", [n for n in dir(qwen_tts) if not n.startswith("_")])
from qwen_tts import Qwen3TTSModel
print("Qwen3TTSModel methods:", [m for m in dir(Qwen3TTSModel) if not m.startswith("_")])
print("generate_voice_design sig:", inspect.signature(Qwen3TTSModel.generate_voice_design))
PY
echo "=== done $(date -u) ===" >> "$LOG"
