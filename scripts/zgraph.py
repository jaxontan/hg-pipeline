#!/usr/bin/env python3
import json, urllib.request, os

base = "/home/tdadmin/Desktop/AIGC-PP2/venv/lib/python3.12/site-packages/comfyui_workflow_templates_json/templates"
d = json.load(open(os.path.join(base, "image_z_image_turbo_int8.json")))
print("=== subgraph definitions ===")
for sg in d.get("definitions", {}).get("subgraphs", []):
    print("subgraph id:", sg.get("id"), "| name:", sg.get("name"))
    for n in sg.get("nodes", []):
        print(f"  #{n.get('id'):>3} {n.get('type'):<26} widgets={n.get('widgets_values')}")
    print("  inputs:", [(i.get("name"), i.get("type")) for i in sg.get("inputs", [])])
    print("  outputs:", [(o.get("name"), o.get("type")) for o in sg.get("outputs", [])])

print()
print("=== CLIPLoader / UNETLoader schema from live server ===")
oi = json.load(urllib.request.urlopen("http://127.0.0.1:9090/object_info", timeout=60))
for node in ["UNETLoader", "CLIPLoader", "VAELoader", "KSampler", "EmptySD3LatentImage",
             "CLIPTextEncode", "ModelSamplingAuraFlow", "SaveImage"]:
    if node not in oi:
        print(f"  {node}: MISSING")
        continue
    inp = oi[node].get("input", {})
    req = inp.get("required", {})
    print(f"\n  {node}:")
    for k, v in req.items():
        # v = [type, opts]
        t = v[0] if isinstance(v, list) else v
        opts = v[1] if isinstance(v, list) and len(v) > 1 else {}
        if isinstance(t, list):
            print(f"    {k}: enum={t[:12]}{'...' if len(t)>12 else ''}")
        else:
            print(f"    {k}: {t}  {opts if opts else ''}")
