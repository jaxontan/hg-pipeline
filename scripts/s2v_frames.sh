#!/bin/bash
ROOT="$HOME/Desktop/AIGC-PP2"
V="$ROOT/outputs/smoketest/s2v_00001_.mp4"
O="$ROOT/outputs/smoketest/s2v_frames"
mkdir -p "$O"
for t in 0.0 2.0 4.0; do ffmpeg -y -loglevel error -ss $t -i "$V" -frames:v 1 "$O/t${t}.png"; done
ls -lh "$O"
