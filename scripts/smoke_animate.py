#!/usr/bin/env python3
"""Wan2.2 Animate 14B (v1) smoke test: transfer motion from a driving clip to a character still.

Uses the core WanAnimateToVideo node (the bundled template targets Animate *2*, which we
have not downloaded). Model on disk: wan2.2_animate_14B_int8_convrot + wan_2.1_vae + clip_vision_h.
"""
import json, time, urllib.request, urllib.error, subprocess, sys

HOST = "http://127.0.0.1:9090"
REF = sys.argv[1] if len(sys.argv) > 1 else "smoke_ref.png"
DRIVE = sys.argv[2] if len(sys.argv) > 2 else "smoke_drive.mp4"
W, H = 480, 832
LEN = 49

def post(p, o):
    r = urllib.request.Request(HOST + p, data=json.dumps(o).encode(),
                               headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=120))

def get(p):
    return json.load(urllib.request.urlopen(HOST + p, timeout=120))

def mem():
    return subprocess.run(["bash", "-c", "free -g | awk '/^Mem:/{print $7\"Gi\"}'"],
                          capture_output=True, text=True).stdout.strip()

NEG = ("色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，"
       "最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，"
       "画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，"
       "杂乱的背景，三条腿，背景人很多，倒着走")

POS = ("Character description: a middle-aged Chinese man in a navy Mao suit, short greying hair, "
       "slightly stocky, walking down a small-town street at dusk. "
       "Background description: 1980s Chinese county town street, low-saturation film look.")

wf = {
    "1":  {"class_type": "UNETLoader", "inputs": {"unet_name": "wan2.2_animate_14B_int8_convrot.safetensors", "weight_dtype": "default"}},
    "2":  {"class_type": "CLIPLoader", "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan"}},
    "3":  {"class_type": "VAELoader", "inputs": {"vae_name": "wan_2.1_vae.safetensors"}},
    "4":  {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": "clip_vision_h.safetensors"}},
    "5":  {"class_type": "CLIPTextEncode", "inputs": {"text": POS, "clip": ["2", 0]}},
    "6":  {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": ["2", 0]}},
    "7":  {"class_type": "LoadImage", "inputs": {"image": REF}},
    "8":  {"class_type": "LoadVideo", "inputs": {"file": DRIVE}},
    "9":  {"class_type": "GetVideoComponents", "inputs": {"video": ["8", 0]}},
    "10": {"class_type": "CLIPVisionEncode", "inputs": {"clip_vision": ["4", 0], "image": ["7", 0], "crop": "none"}},
    "11": {"class_type": "WanAnimateToVideo", "inputs": {
        "positive": ["5", 0], "negative": ["6", 0], "vae": ["3", 0],
        "width": W, "height": H, "length": LEN, "batch_size": 1,
        "continue_motion_max_frames": 5, "video_frame_offset": 0,
        "clip_vision_output": ["10", 0], "reference_image": ["7", 0],
        "pose_video": ["9", 0]}},
    "12": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["1", 0], "shift": 5.0}},
    "13": {"class_type": "KSampler", "inputs": {
        "model": ["12", 0], "seed": 20261116, "steps": 10, "cfg": 5.0,
        "sampler_name": "uni_pc", "scheduler": "simple",
        "positive": ["11", 0], "negative": ["11", 1], "latent_image": ["11", 2], "denoise": 1.0}},
    "14": {"class_type": "TrimVideoLatent", "inputs": {"samples": ["13", 0], "trim_amount": ["11", 3]}},
    "15": {"class_type": "VAEDecode", "inputs": {"samples": ["14", 0], "vae": ["3", 0]}},
    "16": {"class_type": "CreateVideo", "inputs": {"images": ["15", 0], "fps": 16.0}},
    "17": {"class_type": "SaveVideo", "inputs": {"video": ["16", 0], "filename_prefix": "smoketest/animate",
                                                 "format": "mp4", "codec": "h264"}},
}

print(f"ref={REF} drive={DRIVE} {W}x{H} len={LEN}")
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
                print("ERROR:", json.dumps(m[1])[:4000])
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
    if time.time() - t0 > 3600:
        print("TIMEOUT")
        break
print(f"total {time.time()-t0:.1f}s | mem after: {mem()}")
