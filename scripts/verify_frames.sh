#!/bin/bash
ROOT="$HOME/Desktop/AIGC-PP2"
O="$ROOT/outputs/verify/frames"
mkdir -p "$O"
ffmpeg -y -loglevel error -ss 2.5 -i "$ROOT/outputs/verify/video_s2v/shot_002_00001_.mp4" -frames:v 1 "$O/dialogue.png"
ffmpeg -y -loglevel error -ss 2.0 -i "$ROOT/outputs/verify/video_ltx_final/shot_001_00001_.mp4" -frames:v 1 "$O/shot001.png"
ffmpeg -y -loglevel error -ss 4.5 -i "$ROOT/projects/verify/verify.mp4" -frames:v 1 "$O/episode.png"
ls -lh "$O"
