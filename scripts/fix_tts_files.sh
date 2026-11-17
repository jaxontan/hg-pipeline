#!/bin/bash
set -uo pipefail
ROOT="$HOME/Desktop/AIGC-PP2"
cd "$ROOT" || exit 1
. "$ROOT/env.sh"
LOG="$ROOT/logs/downloads4.log"
: > "$LOG"

echo "=== Qwen3-TTS remaining configs $(date -u) ===" | tee -a "$LOG"
hf download Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign \
  speech_tokenizer/config.json \
  speech_tokenizer/configuration.json \
  speech_tokenizer/preprocessor_config.json \
  --local-dir "$ROOT/models/_tts_stage" 2>&1 | tail -3 | tee -a "$LOG"

mkdir -p "$ROOT/models/tts/speech_tokenizer"
for f in config.json configuration.json preprocessor_config.json; do
  s="$ROOT/models/_tts_stage/speech_tokenizer/$f"
  if [ -f "$s" ]; then cp -f "$s" "$ROOT/models/tts/speech_tokenizer/"; echo "ok $f" | tee -a "$LOG"
  else echo "MISSING $f" | tee -a "$LOG"; fi
done
rm -rf "$ROOT/models/_tts_stage"
echo "--- models/tts/speech_tokenizer:" | tee -a "$LOG"
ls -lh "$ROOT/models/tts/speech_tokenizer" | tee -a "$LOG"
