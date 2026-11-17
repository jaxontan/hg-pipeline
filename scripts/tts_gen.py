#!/usr/bin/env python3
"""First voice line with Qwen3-TTS VoiceDesign, for the S2V lip-sync lane."""
import os, sys, time, inspect
import numpy as np
import torch
import soundfile as sf
from qwen_tts import Qwen3TTSModel

ROOT = os.path.expanduser("~/Desktop/AIGC-PP2")
MODEL_DIR = os.path.join(ROOT, "models", "tts")
OUT_DIR = os.path.join(ROOT, "assets", "audio")
os.makedirs(OUT_DIR, exist_ok=True)

LINE = "老陈，这搪瓷缸子跟了你二十年了，扔了怪可惜的。"
INSTRUCT = "中年男性，沙哑低沉的嗓音，说话缓慢，带一点北方口音，情绪克制而疲惫"

print("from_pretrained sig:", inspect.signature(Qwen3TTSModel.from_pretrained))
print("loading model from", MODEL_DIR)
t0 = time.time()
model = Qwen3TTSModel.from_pretrained(MODEL_DIR, device_map="cuda:0", dtype=torch.bfloat16)
print(f"loaded in {time.time()-t0:.1f}s")

print("supported languages:", model.get_supported_languages() if hasattr(model, "get_supported_languages") else "?")

t0 = time.time()
wavs, sr = model.generate_voice_design(text=LINE, instruct=INSTRUCT, language="Chinese")
print(f"generated {len(wavs)} clip(s) in {time.time()-t0:.1f}s @ {sr} Hz")

for i, w in enumerate(wavs):
    w = np.asarray(w, dtype=np.float32).squeeze()
    dur = len(w) / sr
    path = os.path.join(OUT_DIR, f"line_ep01_{i+1:02d}.wav")
    sf.write(path, w, sr)
    peak = float(np.abs(w).max()) if w.size else 0.0
    print(f"  {path}  {dur:.2f}s  peak={peak:.3f}  rms={float(np.sqrt((w**2).mean())):.4f}")
