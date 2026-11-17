#!/bin/bash
ROOT="$HOME/Desktop/AIGC-PP2"
V="$ROOT/outputs/smoketest/animate_00001_.mp4"
O="$ROOT/outputs/smoketest/animate_frames"
mkdir -p "$O"
ffprobe -v error -show_entries format=duration:stream=width,height,nb_frames,r_frame_rate -of default=nw=1 "$V"
for t in 0.0 1.5 3.0; do
  ffmpeg -y -loglevel error -ss $t -i "$V" -frames:v 1 "$O/t${t}.png"
done
ls -lh "$O"
