#!/usr/bin/env python3
"""Full dump of the Wan S2V and Animate templates, including subgraph I/O mapping."""
import json, os

D = "/home/tdadmin/Desktop/AIGC-PP2/venv/lib/python3.12/site-packages/comfyui_workflow_templates_json/templates"

def short(x, n=90):
    if isinstance(x, str) and len(x) > n:
        return x[:n] + "..."
    return x

for name in ["video_wan2_2_14B_s2v.json", "video_wan_animate2_distilled.json"]:
    p = os.path.join(D, name)
    print("=" * 78)
    print(name, "|", "EXISTS" if os.path.exists(p) else "MISSING")
    if not os.path.exists(p):
        continue
    d = json.load(open(p))

    def dump_graph(nodes, indent="  "):
        for n in nodes:
            t = n.get("type")
            if t in ("MarkdownNote", "Note"):
                continue
            w = n.get("widgets_values")
            if isinstance(w, list):
                w = [short(x) for x in w]
            ins = n.get("inputs") or []
            wired = [(i.get("name"), i.get("link")) for i in ins if i.get("link") is not None]
            print(f"{indent}#{n.get('id'):>3} {t:<32} w={w}")
            if wired:
                print(f"{indent}      wired_in={wired}  out={[(o.get('name'), o.get('links')) for o in (n.get('outputs') or [])]}")

    print("\n-- top-level nodes")
    dump_graph(d.get("nodes", []))
    for sg in d.get("definitions", {}).get("subgraphs", []):
        print(f"\n-- SUBGRAPH id={sg.get('id')} name={sg.get('name')!r}")
        print("   inputs :", [(i.get("name"), i.get("type"), i.get("linkIds")) for i in sg.get("inputs", [])])
        print("   outputs:", [(o.get("name"), o.get("type"), o.get("linkIds")) for o in sg.get("outputs", [])])
        dump_graph(sg.get("nodes", []), "   ")
        print("   links:", sg.get("links"))
    print()
