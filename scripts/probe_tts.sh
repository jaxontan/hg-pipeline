#!/usr/bin/env bash
ROOT="$HOME/Desktop/AIGC-PP2"
echo "=== offline TTS binaries ==="
for b in espeak espeak-ng flite piper pico2wave festival say; do
  printf '%-12s ' "$b"; command -v "$b" || echo "(absent)"
done
echo
echo "=== existing audio on host ==="
find /usr/share/sounds "$ROOT/ComfyUI" -maxdepth 4 \( -iname '*.wav' -o -iname '*.mp3' -o -iname '*.flac' \) 2>/dev/null | head -10
echo
echo "=== PyPI: qwen-tts ==="
"$ROOT/venv/bin/python" - <<'PY'
import json, urllib.request
for pkg in ("qwen-tts", "qwen3-tts"):
    try:
        d = json.load(urllib.request.urlopen(f"https://pypi.org/pypi/{pkg}/json", timeout=30))
        v = d["info"]["version"]
        print(f"{pkg}: version {v}")
        print("   requires_dist:", (d["info"].get("requires_dist") or [])[:15])
    except Exception as e:
        print(f"{pkg}: {type(e).__name__} {e}")
PY
echo
echo "=== does main venv already have transformers/qwen? ==="
"$ROOT/venv/bin/pip" list 2>/dev/null | grep -iE '^(transformers|accelerate|qwen|librosa|soundfile|onnx)' || echo "   none"
