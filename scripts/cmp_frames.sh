#!/bin/bash
ROOT="$HOME/Desktop/AIGC-PP2"
O="$ROOT/outputs/compare/frames"
mkdir -p "$O"
V="$ROOT/outputs/compare/ltx_2pass_00001_.mp4"
ffprobe -v error -show_entries format=duration:stream=codec_type,width,height,nb_frames -of default=nw=1 "$V"
ffmpeg -y -loglevel error -ss 2.0 -i "$V" -frames:v 1 "$O/ltx2pass_t2.png"
ls -lh "$O"
