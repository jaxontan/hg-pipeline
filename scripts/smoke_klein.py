#!/usr/bin/env python3
import json, time, urllib.request, urllib.error, subprocess, sys

HOST = "http://127.0.0.1:9090"

def post(path, obj):
    req = urllib.request.Request(HOST + path, data=json.dumps(obj).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=60))

def get(path):
    return json.load(urllib.request.urlopen(HOST + path, timeout=60))

def mem():
    return subprocess.run(["bash", "-c", "free -g | awk '/^Mem:/{print $7\"Gi\"}'"],
                          capture_output=True, text=True).stdout.strip()

def run(wf, label, timeout=1800):
    print(f"\n########## {label} ##########")
    print("mem before:", mem())
    t0 = time.time()
    try:
        r = post("/prompt", {"prompt": wf, "client_id": "smoke"})
    except urllib.error.HTTPError as e:
        print("SUBMIT FAILED", e.code)
        print(e.read().decode()[:5000])
        return
    pid = r["prompt_id"]
    print("queued", pid)
    while True:
        time.sleep(2)
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
                        for item in v:
                            if isinstance(item, dict) and "filename" in item:
                                print(f"  {k}: {item.get('subfolder')}/{item.get('filename')}")
            break
        if time.time() - t0 > timeout:
            print("TIMEOUT"); break
    print(f"total {time.time()-t0:.1f}s | mem after: {mem()}")

# ---------- FLUX.2 Klein 4B (distilled, 4 steps) ----------
wf = {
    "1":  {"class_type": "UNETLoader", "inputs": {"unet_name": "flux-2-klein-4b.safetensors", "weight_dtype": "default"}},
    "2":  {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_3_4b_fp4_flux2.safetensors", "type": "flux2"}},
    "3":  {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}},
    "4":  {"class_type": "CLIPTextEncode", "inputs": {
        "text": "角色设定图：中国1970年代县城中年男人，正面全身，立绘，藏蓝色中山装，布鞋，"
                "微胖，短发花白，神情疲惫而温和，白色背景，二维动画赛璐璐上色，清晰线条，高细节，设定集风格",
        "clip": ["2", 0]}},
    "5":  {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["4", 0]}},
    "6":  {"class_type": "CFGGuider", "inputs": {"model": ["1", 0], "positive": ["4", 0],
                                                 "negative": ["5", 0], "cfg": 1.0}},
    "7":  {"class_type": "Flux2Scheduler", "inputs": {"steps": 4, "width": 896, "height": 1152}},
    "8":  {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
    "9":  {"class_type": "RandomNoise", "inputs": {"noise_seed": 20261116}},
    "10": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": 896, "height": 1152, "batch_size": 1}},
    "11": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["9", 0], "guider": ["6", 0],
                                                              "sampler": ["8", 0], "sigmas": ["7", 0],
                                                              "latent_image": ["10", 0]}},
    "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["3", 0]}},
    "13": {"class_type": "SaveImage", "inputs": {"images": ["12", 0], "filename_prefix": "smoketest/klein"}},
}
run(wf, "FLUX.2-Klein-4B distilled (896x1152, 4 steps)")
