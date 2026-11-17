#!/usr/bin/env python3
import json, urllib.request
repo = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
d = json.load(urllib.request.urlopen(
    f"https://huggingface.co/api/models/{repo}/tree/main?recursive=true", timeout=60))
for it in d:
    print(f"{it.get('size',0)/1e6:9.2f} MB  {it.get('path')}")
