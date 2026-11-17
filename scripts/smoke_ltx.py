#!/usr/bin/env python3
"""LTX-2.5 22B (distilled, nvfp4) smoke test: single pass with synced audio.

Derived from the official video_ltx2_5_t2v template's first pass only:
  EmptyLTXVLatentVideo + LTXVEmptyLatentAudio -> concat -> sampler (dual-CFG, manual sigmas)
  -> separate -> VAEDecodeTiled + LTXVAudioVAEDecode -> CreateVideo

Differences from the template:
  * model file: nvfp4 instead of int8-convrot (that is the quantisation we downloaded)
  * the TextGenerateLTX2Prompt helper is bypassed; our prompt goes straight into CLIPTextEncode
  * the spatial upsampler + second refine pass is skipped (that is the production "2-pass" mode)
"""
import json, time, urllib.request, urllib.error, subprocess, sys

HOST = "http://127.0.0.1:9090"
W, H, LEN, FPS = 512, 768, 97, 24.0

POS = ("1980s Chinese county town street at dusk, low-saturation film look. A middle-aged man in a navy "
       "Mao suit walks slowly along a cobbled lane holding an enamel mug, warm street lamp just switched on, "
       "a cyclist passes in the background, soft film grain, muted colours, cinematic slow camera pan.")
NEG = "pc game, console game, video game, cartoon, childish, ugly, blurry, static"

def post(p, o):
    r = urllib.request.Request(HOST + p, data=json.dumps(o).encode(),
                               headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=120))

def get(p):
    return json.load(urllib.request.urlopen(HOST + p, timeout=120))

def mem():
    return subprocess.run(["bash", "-c", "free -g | awk '/^Mem:/{print $7\"Gi\"}'"],
                          capture_output=True, text=True).stdout.strip()

SIGMAS = "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"

wf = {
    "1":  {"class_type": "UNETLoader", "inputs": {"unet_name": "ltx-2.5-22b-distilled-transformer-nvfp4.safetensors", "weight_dtype": "default"}},
    "2":  {"class_type": "CLIPLoader", "inputs": {"clip_name": "gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors", "type": "ltxv"}},
    "3":  {"class_type": "VAELoader", "inputs": {"vae_name": "ltx-2.5-video-vae-bf16.safetensors"}},
    "4":  {"class_type": "VAELoader", "inputs": {"vae_name": "ltx-2.5-audio-vae-bf16.safetensors"}},
    "5":  {"class_type": "CLIPTextEncode", "inputs": {"text": POS, "clip": ["2", 0]}},
    "6":  {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": ["2", 0]}},
    "7":  {"class_type": "LTXVConditioning", "inputs": {"positive": ["5", 0], "negative": ["6", 0], "frame_rate": FPS}},
    "8":  {"class_type": "EmptyLTXVLatentVideo", "inputs": {"width": W, "height": H, "length": LEN, "batch_size": 1}},
    "9":  {"class_type": "LTXVEmptyLatentAudio", "inputs": {"frames_number": LEN, "frame_rate": 25.0, "batch_size": 1, "audio_vae": ["4", 0]}},
    "10": {"class_type": "LTXVConcatAVLatent", "inputs": {"video_latent": ["8", 0], "audio_latent": ["9", 0]}},
    "11": {"class_type": "RandomNoise", "inputs": {"noise_seed": 20261116}},
    "12": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler_ancestral"}},
    "13": {"class_type": "ManualSigmas", "inputs": {"sigmas": SIGMAS}},
    "14": {"class_type": "LTXVDualCFGGuider", "inputs": {"model": ["1", 0], "positive": ["7", 0],
                                                         "negative": ["7", 1], "video_cfg": 1.0, "audio_cfg": 1.0}},
    "15": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["11", 0], "guider": ["14", 0],
                                                             "sampler": ["12", 0], "sigmas": ["13", 0],
                                                             "latent_image": ["10", 0]}},
    "16": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["15", 0]}},
    "17": {"class_type": "VAEDecodeTiled", "inputs": {"samples": ["16", 0], "vae": ["3", 0],
                                                      "tile_size": 512, "overlap": 64,
                                                      "temporal_size": 64, "temporal_overlap": 8}},
    "18": {"class_type": "LTXVAudioVAEDecode", "inputs": {"samples": ["16", 1], "audio_vae": ["4", 0]}},
    "19": {"class_type": "CreateVideo", "inputs": {"images": ["17", 0], "fps": FPS, "audio": ["18", 0]}},
    "20": {"class_type": "SaveVideo", "inputs": {"video": ["19", 0], "filename_prefix": "smoketest/ltx",
                                                 "format": "mp4", "codec": "h264"}},
}

print(f"LTX single pass {W}x{H} len={LEN} @ {FPS}fps")
print("mem before:", mem())
t0 = time.time()
try:
    r = post("/prompt", {"prompt": wf, "client_id": "smoke"})
except urllib.error.HTTPError as e:
    print("SUBMIT FAILED", e.code)
    print(e.read().decode()[:6000])
    raise SystemExit(1)
pid = r["prompt_id"]
print("queued", pid)

last = None
while True:
    time.sleep(5)
    h = get(f"/history/{pid}")
    if pid in h:
        e = h[pid]
        st = e.get("status", {})
        print("status:", st.get("status_str"))
        for m in (st.get("messages") or []):
            if m[0] in ("execution_error", "execution_interrupted"):
                print("ERROR:", json.dumps(m[1])[:5000])
        for _, out in (e.get("outputs") or {}).items():
            for k, v in out.items():
                if isinstance(v, list):
                    for it in v:
                        if isinstance(it, dict) and "filename" in it:
                            print(f"  {k}: {it.get('subfolder')}/{it.get('filename')}")
        break
    q = get("/queue")
    cur = len(q.get("queue_running", []))
    if cur != last:
        print(f"  t={time.time()-t0:6.1f}s running={cur} mem={mem()}")
        last = cur
    if time.time() - t0 > 4800:
        print("TIMEOUT")
        break
print(f"total {time.time()-t0:.1f}s | mem after: {mem()}")
