#!/usr/bin/env python3
"""Dump the local (non-API) LTX-2.5 t2v template: nodes + widgets, and flag missing models."""
import json, os

D = "/home/tdadmin/Desktop/AIGC-PP2/venv/lib/python3.12/site-packages/comfyui_workflow_templates_json/templates"
for name in ["video_ltx2_5_t2v.json"]:
    p = os.path.join(D, name)
    if not os.path.exists(p):
        print(name, "MISSING")
        print("candidates:", [f for f in sorted(os.listdir(D)) if "ltx" in f.lower()])
        continue
    d = json.load(open(p))
    print("=" * 78)
    print(name)
    print("top-level:")
    for n in d.get("nodes", []):
        t = n.get("type")
        if t in ("MarkdownNote", "Note"):
            continue
        w = n.get("widgets_values")
        if isinstance(w, list):
            w = [(str(x)[:80] + "...") if isinstance(x, str) and len(x) > 80 else x for x in w]
        print(f"  #{n.get('id'):>3} {t:<34} {w}")
    for sg in d.get("definitions", {}).get("subgraphs", []):
        print(f"\n  SUBGRAPH {sg.get('name')!r}")
        for n in sg.get("nodes", []):
            t = n.get("type")
            if t in ("MarkdownNote", "Note"):
                continue
            w = n.get("widgets_values")
            if isinstance(w, list):
                w = [(str(x)[:70] + "...") if isinstance(x, str) and len(str(x)) > 70 else x for x in w]
            print(f"    #{n.get('id'):>3} {t:<32} {w}")
