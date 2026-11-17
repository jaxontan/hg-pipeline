#!/usr/bin/env python3
"""Wan2.2 S2V 14B (speech-to-video / lip-sync) smoke test, single pass.

Audio: our own Qwen3-TTS line. Graph mirrors the first pass of the official template,
with the 4-step lightx2v LoRA (cfg 1, 4 steps) instead of 10 steps at cfg 6.
"""
import json, time, urllib.request, urllib.error, subprocess, sys

HOST = "http://127.0.0.1:9090"
REF = sys.argv[1] if len(sys.argv) > 1 else "smoke_ref.png"
AUDIO = sys.argv[2] if len(sys.argv) > 2 else "line_ep01_01.wav"
W, H, LEN = 480, 832, 93

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

POS = ("A middle-aged Chinese man in a navy Mao suit stands in a small-town street at dusk and speaks, "
       "looking at the camera. Natural lip movement matching the speech, subtle head motion, "
       "1980s Chinese county town, low-saturation film look, warm street lamp.")

wf = {
    "1":  {"class_type": "UNETLoader", "inputs": {"unet_name": "wan2.2_s2v_14B_fp8_scaled.safetensors", "weight_dtype": "default"}},
    "2":  {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0],
            "lora_name": "wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors", "strength_model": 1.0}},
    "3":  {"class_type": "ModelSamplingSD3", "inputs": {"model": ["2", 0], "shift": 8.0}},
    "4":  {"class_type": "CLIPLoader", "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan"}},
    "5":  {"class_type": "CLIPTextEncode", "inputs": {"text": POS, "clip": ["4", 0]}},
    "6":  {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": ["4", 0]}},
    "7":  {"class_type": "VAELoader", "inputs": {"vae_name": "wan_2.1_vae.safetensors"}},
    "8":  {"class_type": "AudioEncoderLoader", "inputs": {"audio_encoder_name": "wav2vec2_large_english_fp16.safetensors"}},
    "9":  {"class_type": "LoadAudio", "inputs": {"audio": AUDIO}},
    "10": {"class_type": "AudioEncoderEncode", "inputs": {"audio_encoder": ["8", 0], "audio": ["9", 0]}},
    "11": {"class_type": "LoadImage", "inputs": {"image": REF}},
    "12": {"class_type": "WanSoundImageToVideo", "inputs": {
        "positive": ["5", 0], "negative": ["6", 0], "vae": ["7", 0],
        "width": W, "height": H, "length": LEN, "batch_size": 1,
        "audio_encoder_output": ["10", 0], "ref_image": ["11", 0]}},
    "13": {"class_type": "KSampler", "inputs": {
        "model": ["3", 0], "seed": 20261116, "steps": 4, "cfg": 1.0,
        "sampler_name": "euler", "scheduler": "simple",
        "positive": ["12", 0], "negative": ["12", 1], "latent_image": ["12", 2], "denoise": 1.0}},
    "14": {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": ["7", 0]}},
    "15": {"class_type": "CreateVideo", "inputs": {"images": ["14", 0], "fps": 16.0, "audio": ["9", 0]}},
    "16": {"class_type": "SaveVideo", "inputs": {"video": ["15", 0], "filename_prefix": "smoketest/s2v",
                                                 "format": "mp4", "codec": "h264"}},
}

print(f"ref={REF} audio={AUDIO} {W}x{H} len={LEN} (4-step lora, cfg 1)")
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
