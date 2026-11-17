#!/bin/bash
set -uo pipefail
ROOT="$HOME/Desktop/AIGC-PP2"

echo "=== 1. SETUP_LOG.md ==="
if [ ! -f "$ROOT/SETUP_LOG.md" ]; then
  printf '# AIGC-PP2 — Setup Log\n\nChronological record. Newest entries appended at the end.\n' > "$ROOT/SETUP_LOG.md"
fi
{
  echo ""
  echo "---"
  echo ""
  echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) — setup report appended"
  echo ""
  cat "$ROOT/SETUP_REPORT.md"
} >> "$ROOT/SETUP_LOG.md"
echo "SETUP_LOG.md now $(wc -l < "$ROOT/SETUP_LOG.md") lines"

echo
echo "=== 2. move TTS out of staging ==="
S="$ROOT/models/_staging/tts"
if [ -d "$S" ]; then
  mkdir -p "$ROOT/models/tts/speech_tokenizer"
  [ -f "$S/model.safetensors" ] && mv -f "$S/model.safetensors" "$ROOT/models/tts/"
  [ -f "$S/speech_tokenizer/model.safetensors" ] && mv -f "$S/speech_tokenizer/model.safetensors" "$ROOT/models/tts/speech_tokenizer/"
  for f in config.json generation_config.json preprocessor_config.json tokenizer_config.json vocab.json merges.txt; do
    [ -f "$S/$f" ] && mv -f "$S/$f" "$ROOT/models/tts/"
  done
  rm -rf "$ROOT/models/_staging/tts"
fi
rmdir "$ROOT/models/_staging/kandinsky" "$ROOT/models/_staging/klein" \
      "$ROOT/models/_staging/wan5b" "$ROOT/models/_staging" 2>/dev/null
echo "--- models/tts"
ls -lhR "$ROOT/models/tts" 2>/dev/null | tail -n +2 | awk '{print "   ", $5, $9}'
echo "--- staging left:"
du -sh "$ROOT/models/_staging" 2>/dev/null || echo "   (removed)"

echo
echo "=== 3. keep useful scripts inside \$ROOT, purge /tmp ==="
mkdir -p "$ROOT/scripts"
for f in smoke_z.py smoke_klein.py smoke_wan.py schemas.py dump_wan.py dump_tpl.py zgraph.py ztpl2.py kand.py; do
  [ -f "/tmp/$f" ] && cp -f "/tmp/$f" "$ROOT/scripts/" 2>/dev/null
done
rm -f /tmp/*.py /tmp/*.sh
echo "scripts kept:"; ls -1 "$ROOT/scripts"
echo "stray /tmp py/sh left:"; ls -1 /tmp/*.py /tmp/*.sh 2>/dev/null || echo "   none"
