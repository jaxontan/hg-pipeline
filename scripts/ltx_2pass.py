#!/usr/bin/env python3
"""LTX-2.5 two-pass (production mode): draft at 512x768, latent-upscale x2, refine at 1024x1536.

Follows the official video_ltx2_5_t2v template: pass 1 = 9 sigmas from empty latent,
pass 2 = 4 sigmas starting at 0.85 on the upsampled latent, audio latent carried through.
"""
import json, time, urllib.request, urllib.error, subprocess

HOST = "http://127.0.0.1:9090"
W, H, LEN, FPS = 512, 768, 97, 24.0

POS = ("Photoreal cinematic: 1970s Chinese county-town street at dusk. A middle-aged man in a navy Mao "
       "suit walks slowly toward camera holding a white enamel mug with a red rim. A cyclist passes behind "
       "him. A warm street lamp flickers on, wet cobblestones, low-saturation film grade, 35mm grain, "
       "shallow depth of field, slow dolly-in.")
NEG = "pc game, console game, video game, cartoon, childish, ugly, blurry, static, text, watermark"

SIG1 = "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"
SIG2 = "0.85, 0.7250, 0.4219, 0.0"

def post(p, o):
    r = urllib.request.Request(HOST + p, data=json.dumps(o).encode(),
                               headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=120))

def get(p):
    return json.load(urllib.request.urlopen(HOST + p, timeout=120))

def mem():
    return subprocess.run(["bash", "-c", "free -g | awk '/^Mem:/{print $7\"Gi\"}'"],
                          capture_output=True, text=True).stdout.strip()

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
    # ---- pass 1 ----
    "11": {"class_type": "RandomNoise", "inputs": {"noise_seed": 20261116}},
    "12": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler_ancestral"}},
    "13": {"class_type": "ManualSigmas", "inputs": {"sigmas": SIG1}},
    "14": {"class_type": "LTXVDualCFGGuider", "inputs": {"model": ["1", 0], "positive": ["7", 0],
                                                         "negative": ["7", 1], "video_cfg": 1.0, "audio_cfg": 1.0}},
    "15": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["11", 0], "guider": ["14", 0],
                                                             "sampler": ["12", 0], "sigmas": ["13", 0],
                                                             "latent_image": ["10", 0]}},
    "16": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["15", 0]}},
    # ---- upscale ----
    "17": {"class_type": "LatentUpscaleModelLoader", "inputs": {"model_name": "ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors"}},
    "18": {"class_type": "LTXVLatentUpsampler", "inputs": {"samples": ["16", 0], "upscale_model": ["17", 0], "vae": ["3", 0]}},
    "19": {"class_type": "LTXVConcatAVLatent", "inputs": {"video_latent": ["18", 0], "audio_latent": ["16", 1]}},
    # ---- pass 2 ----
    "20": {"class_type": "RandomNoise", "inputs": {"noise_seed": 20261117}},
    "21": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler_ancestral"}},
    "22": {"class_type": "ManualSigmas", "inputs": {"sigmas": SIG2}},
    "23": {"class_type": "LTXVDualCFGGuider", "inputs": {"model": ["1", 0], "positive": ["7", 0],
                                                         "negative": ["7", 1], "video_cfg": 1.0, "audio_cfg": 1.0}},
    "24": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["20", 0], "guider": ["23", 0],
                                                             "sampler": ["21", 0], "sigmas": ["22", 0],
                                                             "latent_image": ["19", 0]}},
    "25": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["24", 0]}},
    # ---- decode ----
    "26": {"class_type": "VAEDecodeTiled", "inputs": {"samples": ["25", 0], "vae": ["3", 0],
                                                      "tile_size": 512, "overlap": 64,
                                                      "temporal_size": 64, "temporal_overlap": 8}},
    "27": {"class_type": "LTXVAudioVAEDecode", "inputs": {"samples": ["25", 1], "audio_vae": ["4", 0]}},
    "28": {"class_type": "CreateVideo", "inputs": {"images": ["26", 0], "fps": FPS, "audio": ["27", 0]}},
    "29": {"class_type": "SaveVideo", "inputs": {"video": ["28", 0], "filename_prefix": "compare/ltx_2pass",
                                                 "format": "mp4", "codec": "h264"}},
}

print(f"LTX two-pass {W}x{H} -> {W*2}x{H*2}, len={LEN} @{FPS}fps")
print("mem before:", mem())
t0 = time.time()
try:
    r = post("/prompt", {"prompt": wf, "client_id": "compare"})
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
    if time.time() - t0 > 5400:
        print("TIMEOUT")
        break
print(f"total {time.time()-t0:.1f}s | mem after: {mem()}")
