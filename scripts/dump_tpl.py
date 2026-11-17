#!/usr/bin/env python3
import json, os, glob

D = "/home/tdadmin/Desktop/AIGC-PP2/venv/lib/python3.12/site-packages/comfyui_workflow_templates_json/templates"

print("=== all wan templates ===")
for f in sorted(os.listdir(D)):
    if "wan" in f.lower() and f.endswith(".json"):
        print("  ", f)

WANT = [
    "image_flux2_klein_text_to_image.json",
    "video_ltx2_5_t2v.json",
    "video_wan2_2_5b_ti2v.json",
    "video_wan2_2_s2v.json",
    "video_wan2_2_animate.json",
    "video_kandinsky5_t2v.json",
]

for name in WANT:
    p = os.path.join(D, name)
    if not os.path.exists(p):
        print(f"\n--- {name}: NOT FOUND")
        continue
    d = json.load(open(p))
    print(f"\n===== {name}")
    top = [(n.get("type"), n.get("widgets_values")) for n in d.get("nodes", [])]
    print("  top-level:", [t for t in top if t[0] not in ("MarkdownNote", "Note")])
    for sg in d.get("definitions", {}).get("subgraphs", []):
        print(f"  SUBGRAPH '{sg.get('name')}'")
        for n in sg.get("nodes", []):
            if n.get("type") in ("MarkdownNote", "Note"):
                continue
            w = n.get("widgets_values")
            if isinstance(w, list):
                w = [ (str(x)[:60] + "...") if isinstance(x, str) and len(str(x)) > 60 else x for x in w ]
            print(f"    #{n.get('id'):>3} {n.get('type'):<30} {w}")
