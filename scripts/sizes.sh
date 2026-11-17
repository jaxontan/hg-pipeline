#!/bin/bash
ROOT="$HOME/Desktop/AIGC-PP2"
for d in diffusion_models text_encoders vae audio_encoders loras clip_vision latent_upscale_models; do
  echo "--- $d"
  find "$ROOT/models/$d" -type f -printf '%s %p\n' | sort -k2 | while read -r sz p; do
    printf '   %6.2f GB  %s\n' "$(echo "$sz" | awk '{print $1/1e9}')" "$(basename "$p")"
  done
done
echo "--- tts"
find "$ROOT/models/tts" -type f -printf '%s %p\n' | sort -k2 | while read -r sz p; do
  printf '   %6.2f GB  %s\n' "$(echo "$sz" | awk '{print $1/1e9}')" "${p#$ROOT/models/tts/}"
done
