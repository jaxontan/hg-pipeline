#!/usr/bin/env python3
import json, time, urllib.request, subprocess

HOST = "http://127.0.0.1:9090"

def post(path, obj):
    req = urllib.request.Request(HOST + path, data=json.dumps(obj).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=60))

def get(path):
    return json.load(urllib.request.urlopen(HOST + path, timeout=60))

PROMPT = (
    "1980年代中国县城老街，黄昏，穿藏蓝中山装的中年男人背影，手里拎着搪瓷缸，"
    "低饱和胶片质感，颗粒感，电影感构图，暖色路灯，写实，二维动画赛璐璐风格，"
    "高细节，竖构图"
)

wf = {
    "1":  {"class_type": "UNETLoader",             "inputs": {"unet_name": "z_image_turbo_nvfp4.safetensors", "weight_dtype": "default"}},
    "2":  {"class_type": "CLIPLoader",             "inputs": {"clip_name": "qwen_3_4b_fp4_mixed.safetensors", "type": "lumina2"}},
    "3":  {"class_type": "VAELoader",              "inputs": {"vae_name": "ae.safetensors"}},
    "4":  {"class_type": "ModelSamplingAuraFlow",  "inputs": {"model": ["1", 0], "shift": 3.0}},
    "5":  {"class_type": "CLIPTextEncode",         "inputs": {"text": PROMPT, "clip": ["2", 0]}},
    "6":  {"class_type": "ConditioningZeroOut",    "inputs": {"conditioning": ["5", 0]}},
    "7":  {"class_type": "EmptySD3LatentImage",    "inputs": {"width": 832, "height": 1216, "batch_size": 1}},
    "8":  {"class_type": "KSampler",               "inputs": {"model": ["4", 0], "seed": 20261116, "steps": 8, "cfg": 1.0,
                                                              "sampler_name": "res_multistep", "scheduler": "simple",
                                                              "positive": ["5", 0], "negative": ["6", 0],
                                                              "latent_image": ["7", 0], "denoise": 1.0}},
    "9":  {"class_type": "VAEDecode",              "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
    "10": {"class_type": "SaveImage",              "inputs": {"images": ["9", 0], "filename_prefix": "smoketest/zimage"}},
}

print("free before:", subprocess.run(["bash","-c","free -g | awk '/^Mem:/{print $7\"Gi avail\"}'"],
                                     capture_output=True, text=True).stdout.strip())
t0 = time.time()
try:
    r = post("/prompt", {"prompt": wf, "client_id": "smoketest"})
except urllib.error.HTTPError as e:
    print("SUBMIT FAILED", e.code)
    print(e.read().decode()[:4000])
    raise SystemExit(1)
pid = r["prompt_id"]
print("queued", pid)

last = None
while True:
    time.sleep(1)
    h = get(f"/history/{pid}")
    if pid in h:
        entry = h[pid]
        st = entry.get("status", {})
        print("status:", st.get("status_str"), "completed:", st.get("completed"))
        if st.get("messages"):
            for m in st["messages"]:
                if m[0] in ("execution_error", "execution_interrupted"):
                    print("MESSAGE:", m[0], json.dumps(m[1])[:2000])
        for node_id, out in (entry.get("outputs") or {}).items():
            for img in (out.get("images") or []):
                print("  IMAGE:", img.get("subfolder"), img.get("filename"), img.get("type"))
        break
    q = get("/queue")
    running = len(q.get("queue_running", []))
    if running != last:
        print(f"  t={time.time()-t0:6.1f}s running={running}")
        last = running
    if time.time() - t0 > 900:
        print("TIMEOUT"); break

print(f"total {time.time()-t0:.1f}s")
print("free after:", subprocess.run(["bash","-c","free -g | awk '/^Mem:/{print $7\"Gi avail\"}'"],
                                    capture_output=True, text=True).stdout.strip())
