#!/usr/bin/env python3
import json, urllib.request
oi = json.load(urllib.request.urlopen("http://127.0.0.1:9090/object_info", timeout=120))
keys = sorted(oi.keys())
print("=== nodes matching tts/audio/speech/voice ===")
for k in keys:
    kl = k.lower()
    if any(s in kl for s in ("tts", "speech", "voice", "audiogen")):
        print("  ", k)
print()
print("=== audio-related utility nodes ===")
for k in keys:
    if k in ("LoadAudio", "SaveAudio", "CreateVideo", "SaveVideo", "AudioEncoderLoader",
             "AudioEncoderEncode", "WanSoundImageToVideo", "WanSoundImageToVideoExtend",
             "WanFirstLastFrameToVideo", "LoadImage", "LoadVideo", "WanAnimateToVideo",
             "ImageOnlyCheckpointLoader", "WanVideoEncode", "WanVideoDecode"):
        print("  ", k, "->", oi[k].get("output"))
