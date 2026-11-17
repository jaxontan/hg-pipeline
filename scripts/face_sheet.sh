#!/bin/bash
ROOT="$HOME/Desktop/AIGC-PP2"
V="$ROOT/outputs/smoketest/s2v_00001_.mp4"
O="$ROOT/outputs/smoketest/s2v_face"
mkdir -p "$O"
# face is upper-middle of a 480x832 frame -> crop 240x240 around (240,190)
for t in 0.2 1.0 1.8 2.6 3.4 4.2; do
  ffmpeg -y -loglevel error -ss $t -i "$V" -frames:v 1 -vf "crop=240:240:120:90" "$O/f_${t}.png"
done
# tile them into one contact sheet for comparison
ffmpeg -y -loglevel error -pattern_type glob -i "$O/f_*.png" -filter_complex "tile=3x2" "$O/sheet.png"
ls -lh "$O"
echo "--- ltx progress"
tail -5 "$ROOT/logs/smoke_ltx.out" 2>/dev/null
tail -8 "$ROOT/logs/comfyui.log"
