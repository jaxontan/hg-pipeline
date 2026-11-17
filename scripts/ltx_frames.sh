#!/bin/bash
ROOT="$HOME/Desktop/AIGC-PP2"
V="$ROOT/outputs/smoketest/ltx_00001_.mp4"
O="$ROOT/outputs/smoketest/ltx_frames"
mkdir -p "$O"
ffprobe -v error -show_entries format=duration:stream=codec_type,width,height,nb_frames,r_frame_rate -of default=nw=1 "$V"
for t in 0.5 2.0 3.5; do ffmpeg -y -loglevel error -ss $t -i "$V" -frames:v 1 "$O/t${t}.png"; done
ffmpeg -y -loglevel error -i "$V" -vn -ac 1 -ar 24000 "$O/audio.wav"
python3 - <<'PY'
import wave, numpy as np, os
p = os.path.expanduser("~/Desktop/AIGC-PP2/outputs/smoketest/ltx_frames/audio.wav")
w = wave.open(p)
n = w.getnframes(); sr = w.getframerate()
a = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768
print(f"audio {n/sr:.2f}s @{sr}Hz peak={abs(a).max():.3f} rms={np.sqrt((a**2).mean()):.4f}")
PY
ls -lh "$O"
