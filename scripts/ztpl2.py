#!/usr/bin/env python3
import json, glob, os
base = "/home/tdadmin/Desktop/AIGC-PP2/venv/lib/python3.12/site-packages/comfyui_workflow_templates_json/templates"
for name in ["image_z_image_turbo.json", "image_z_image_turbo_int8.json"]:
    p = os.path.join(base, name)
    if not os.path.exists(p):
        continue
    d = json.load(open(p))
    print("=" * 70)
    print(name)
    print("top keys:", list(d.keys()))
    for n in d.get("nodes", []):
        print(f"  #{n.get('id'):>3} {n.get('type'):<28} widgets={n.get('widgets_values')}")
    # links
    print("  links:", d.get("links"))
    print("  models:", json.dumps(d.get("models"), indent=1)[:800] if d.get("models") else None)
    print()
