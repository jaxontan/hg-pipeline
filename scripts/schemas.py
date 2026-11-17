#!/usr/bin/env python3
import json, urllib.request
oi = json.load(urllib.request.urlopen("http://127.0.0.1:9090/object_info", timeout=120))
NODES = ["EmptyFlux2LatentImage", "Flux2Scheduler", "CFGGuider", "SamplerCustomAdvanced",
         "RandomNoise", "KSamplerSelect", "ConditioningZeroOut", "ModelSamplingSD3",
         "Wan22ImageToVideoLatent", "CreateVideo", "SaveVideo", "LoadImage",
         "WanSoundImageToVideo", "AudioEncoderLoader", "AudioEncoderEncode",
         "LatentConcat", "ImageFromBatch", "LoadAudio"]
for n in NODES:
    if n not in oi:
        print(f"{n}: MISSING\n"); continue
    print(f"=== {n}")
    inp = oi[n].get("input", {})
    for kind in ("required", "optional"):
        for k, v in (inp.get(kind) or {}).items():
            t = v[0] if isinstance(v, list) else v
            o = v[1] if isinstance(v, list) and len(v) > 1 else {}
            if isinstance(t, list):
                print(f"   [{kind}] {k}: enum={t[:8]}")
            else:
                print(f"   [{kind}] {k}: {t} {o if o else ''}")
    print("   out:", oi[n].get("output"))
    print()
