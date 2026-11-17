#!/usr/bin/env python3
import json, time, urllib.request, urllib.error, subprocess

HOST = "http://127.0.0.1:9090"

def post(p, o):
    r = urllib.request.Request(HOST + p, data=json.dumps(o).encode(),
                               headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=60))

def get(p):
    return json.load(urllib.request.urlopen(HOST + p, timeout=60))

def mem():
    return subprocess.run(["bash", "-c", "free -g | awk '/^Mem:/{print $7\"Gi\"}'"],
                          capture_output=True, text=True).stdout.strip()

NEG = ("色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，"
       "最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，"
       "画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，"
       "杂乱的背景，三条腿，背景人很多，倒着走")

wf = {
    "1":  {"class_type": "UNETLoader", "inputs": {"unet_name": "wan2.2_ti2v_5B_fp16.safetensors", "weight_dtype": "default"}},
    "2":  {"class_type": "CLIPLoader", "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan"}},
    "3":  {"class_type": "VAELoader", "inputs": {"vae_name": "wan2.2_vae.safetensors"}},
    "4":  {"class_type": "CLIPTextEncode", "inputs": {
        "text": "1970年代中国县城老街，黄昏，穿藏蓝中山装的中年男人拎着搪瓷缸慢慢走过，"
                "路灯刚亮，暖黄光，远处有人骑自行车经过，胶片质感，低饱和，二维动画赛璐璐风格，"
                "镜头缓慢横移，写实光影，高细节",
        "clip": ["2", 0]}},
    "5":  {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": ["2", 0]}},
    "6":  {"class_type": "ModelSamplingSD3", "inputs": {"model": ["1", 0], "shift": 8.0}},
    "7":  {"class_type": "Wan22ImageToVideoLatent", "inputs": {"vae": ["3", 0], "width": 704,
                                                              "height": 1280, "length": 121, "batch_size": 1}},
    "8":  {"class_type": "KSampler", "inputs": {"model": ["6", 0], "seed": 20261116, "steps": 20, "cfg": 5.0,
                                                "sampler_name": "uni_pc", "scheduler": "simple",
                                                "positive": ["4", 0], "negative": ["5", 0],
                                                "latent_image": ["7", 0], "denoise": 1.0}},
    "9":  {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
    "10": {"class_type": "CreateVideo", "inputs": {"images": ["9", 0], "fps": 24.0}},
    "11": {"class_type": "SaveVideo", "inputs": {"video": ["10", 0], "filename_prefix": "smoketest/wan5b",
                                                 "format": "mp4", "codec": "h264"}},
}

print("mem before:", mem())
t0 = time.time()
try:
    r = post("/prompt", {"prompt": wf, "client_id": "smoke"})
except urllib.error.HTTPError as e:
    print("SUBMIT FAILED", e.code); print(e.read().decode()[:5000]); raise SystemExit(1)
pid = r["prompt_id"]; print("queued", pid)

last = None
while True:
    time.sleep(5)
    h = get(f"/history/{pid}")
    if pid in h:
        e = h[pid]; st = e.get("status", {})
        print("status:", st.get("status_str"))
        for m in (st.get("messages") or []):
            if m[0] in ("execution_error", "execution_interrupted"):
                print("ERROR:", json.dumps(m[1])[:3000])
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
    if time.time() - t0 > 2700:
        print("TIMEOUT"); break
print(f"total {time.time()-t0:.1f}s | mem after: {mem()}")
