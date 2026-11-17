#!/bin/bash
set -uo pipefail
ROOT="$HOME/Desktop/AIGC-PP2"

{
  echo ""
  echo "---"
  echo ""
  echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) — smoke test round 2 (all models)"
  echo ""
  echo "| Model | Settings | Time | Output | Verdict |"
  echo "|---|---|---|---|---|"
  echo "| Z-Image-Turbo NVFP4 | 832x1216, 8 steps | 9.0 s | still | OK |"
  echo "| FLUX.2-Klein-4B | 896x1152, 4 steps | 6.0 s | still | OK |"
  echo "| Wan2.2 TI2V 5B | 704x1280, 121f, 20 steps | 324.6 s | 5.04 s @24fps | OK |"
  echo "| Wan2.2 S2V 14B + 4-step LoRA | 480x832, 93f, 4 steps, cfg1 | 130.5 s | 5.81 s @16fps + audio | OK |"
  echo "| Wan2.2 Animate 14B int8 | 480x832, 49f, 10 steps, cfg5, shift5 | 275.5 s | 3.06 s @16fps | OK |"
  echo "| LTX-2.5 22B nvfp4 single pass | 512x768, 97f, 8 sigmas | 50.1 s | 4.04 s @24fps + audio | OK |"
  echo "| Qwen3-TTS 1.7B VoiceDesign | venv-tts, bf16 | 27 s load + 5.7 s | 5.76 s @24kHz | OK |"
  echo "| Kandinsky 6.0 Lite int8-convrot | - | - | - | FAIL: needs PR #16825 |"
  echo ""
  echo "Findings:"
  echo "- LTX-2.5 is ~12x realtime and the only lane that generates audio natively -> primary video engine."
  echo "- S2V lip-sync confirmed (mouth opens/closes over the line) but a white-background settei"
  echo "  reference yields a white background and a static pose; it needs a full scene frame as ref."
  echo "- Animate transfers identity + motion; 90x realtime, so per-shot only."
  echo "- Voice lane needs its own venv: qwen-tts pins transformers 4.57.3, ComfyUI needs 5.x."
  echo "  venv-tts installed at \$ROOT/venv-tts (6.1 GB)."
  echo "- No native Qwen3-TTS node in ComfyUI; the only TTS nodes are paid cloud APIs."
  echo "  -> TTS is a CLI lane writing wav into assets/audio, consumed by LoadAudio."
  echo "- extra_model_paths.yaml was missing latent_upscale_models; added + ComfyUI restarted."
  echo "- Animate template targets Animate 2 (not in the Wan2.2 repackaged repo); v1 driven via WanAnimateToVideo."
  echo ""
  echo "Outputs: outputs/smoketest/{animate_00001_,s2v_00001_,ltx_00001_}.mp4"
} >> "$ROOT/SETUP_LOG.md"

echo "SETUP_LOG.md: $(wc -l < "$ROOT/SETUP_LOG.md") lines"
echo
echo "=== final state ==="
du -sh "$ROOT" "$ROOT/models" "$ROOT/venv" "$ROOT/venv-tts" 2>/dev/null
df -h "$ROOT" | tail -1
echo
ls -lh "$ROOT/outputs/smoketest/"*.mp4 "$ROOT/outputs/smoketest/"*.png 2>/dev/null | awk '{print "  ", $5, $9}'
echo
echo "=== stray files outside ROOT (should only be these) ==="
ls -1 /tmp/*.py /tmp/*.sh 2>/dev/null || echo "  none"
