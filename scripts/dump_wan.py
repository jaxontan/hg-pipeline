#!/usr/bin/env python3
import json, os

D = "/home/tdadmin/Desktop/AIGC-PP2/venv/lib/python3.12/site-packages/comfyui_workflow_templates_json/templates"
WANT = ["video_wan2_2_5B_ti2v.json",
        "video_wan2_2_14B_s2v.json",
        "video_wan_animate2_distilled.json"]

for name in WANT:
    p = os.path.join(D, name)
    if not os.path.exists(p):
        print(f"\n--- {name}: NOT FOUND"); continue
    d = json.load(open(p))
    print(f"\n===== {name}")
    print("  top:", [(n.get("type"), n.get("widgets_values")) for n in d.get("nodes", [])
                     if n.get("type") not in ("MarkdownNote", "Note")])
    for sg in d.get("definitions", {}).get("subgraphs", []):
        print(f"  SUBGRAPH '{sg.get('name')}'")
        for n in sg.get("nodes", []):
            if n.get("type") in ("MarkdownNote", "Note"):
                continue
            w = n.get("widgets_values")
            if isinstance(w, list):
                w = [(str(x)[:70] + "...") if isinstance(x, str) and len(str(x)) > 70 else x for x in w]
            print(f"    #{n.get('id'):>3} {n.get('type'):<30} {w}")
        print("    inputs:", [(i.get("name"), i.get("type")) for i in sg.get("inputs", [])])
        print("    outputs:", [(o.get("name"), o.get("type")) for o in sg.get("outputs", [])])
