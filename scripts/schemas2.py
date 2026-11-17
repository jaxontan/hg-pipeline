#!/usr/bin/env python3
import json, urllib.request
oi = json.load(urllib.request.urlopen("http://127.0.0.1:9090/object_info", timeout=120))
NODES = ["WanSoundImageToVideo", "AudioEncoderEncode", "AudioEncoderLoader", "LoadAudio",
         "LoraLoaderModelOnly", "WanAnimateToVideo", "WanAnimate2ToVideo", "WanAnimate2Cache",
         "ContextWindowsManual", "TrimVideoLatent", "ResizeImageMaskNode", "GetVideoComponents",
         "LoadVideo", "CreateVideo", "SaveVideo", "BasicScheduler", "SamplerCustom",
         "KSamplerSelect", "SaveAudio", "ComfyMathExpression", "ImageFromBatch"]
for n in NODES:
    if n not in oi:
        print(f"### {n}: MISSING\n")
        continue
    print(f"### {n}   out={oi[n].get('output')}")
    inp = oi[n].get("input", {})
    for kind in ("required", "optional"):
        for k, v in (inp.get(kind) or {}).items():
            t = v[0] if isinstance(v, list) else v
            o = v[1] if isinstance(v, list) and len(v) > 1 else {}
            if isinstance(t, list):
                print(f"   [{kind[:3]}] {k}: enum={t[:10]}")
            else:
                print(f"   [{kind[:3]}] {k}: {t} {o if o else ''}")
    print()
