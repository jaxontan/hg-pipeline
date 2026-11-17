#!/bin/bash
ROOT="$HOME/Desktop/AIGC-PP2"
O="$ROOT/outputs/compare/frames"
mkdir -p "$O"
ffmpeg -y -loglevel error -ss 2.0 -i "$ROOT/outputs/compare/wan_t2v_00001_.mp4" -frames:v 1 "$O/wan_t2.png"
# animate run #2 writes animate_00002_
A="$ROOT/outputs/smoketest/animate_00002_.mp4"
[ -f "$A" ] || A="$ROOT/outputs/smoketest/animate_00001_.mp4"
ffmpeg -y -loglevel error -ss 1.5 -i "$A" -frames:v 1 "$O/animate_t15.png"
for f in "$O/ltx2pass_t2.png" "$O/wan_t2.png" "$O/animate_t15.png"; do
  echo "$(basename $f): $(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$f" 2>/dev/null)"
done
ffprobe -v error -show_entries format=duration,size -of default=nw=1 "$ROOT/outputs/compare/wan_t2v_00001_.mp4"
ffprobe -v error -show_entries format=duration,size -of default=nw=1 "$A"
ls -lh "$O"
