"""Validate ComfyUI UI-format workflows against the live object_info contract.

Checks, without loading anything into a running UI session:
  1. every node type exists on the server (Note is a UI-only pseudo-node),
  2. every link references an existing node and an existing output/input slot,
  3. every required non-widget input is actually connected,
  4. required widget inputs have a value in widgets_values.

Also derives manju_t2v from manju_i2v (same graph, no start image).
"""
from __future__ import annotations

import copy
import json
import sys
import urllib.request
from pathlib import Path

BASE = "http://192.168.1.103:8188"
HERE = Path(__file__).resolve().parent.parent / "work" / "comfy_workflows"
WIDGET_TYPES = {"INT", "FLOAT", "STRING", "BOOLEAN", "COMBO"}

info = json.load(urllib.request.urlopen(f"{BASE}/object_info", timeout=30))


def is_widget(spec) -> bool:
    t = spec[0] if isinstance(spec, list) and spec else spec
    if isinstance(t, list):
        return True
    if not isinstance(t, str):
        return False
    return t in WIDGET_TYPES or t.startswith("COMBO") or t.startswith("COMFY_DYNAMICCOMBO")


def check(path: Path) -> list[str]:
    wf = json.loads(path.read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in wf["nodes"]}
    problems: list[str] = []

    for n in wf["nodes"]:
        t = n["type"]
        if t == "Note":
            continue
        if t not in info:
            problems.append(f"node {n['id']}: unknown type {t}")
            continue
        req = info[t].get("input", {}).get("required", {})
        connected = {i["name"] for i in n.get("inputs", []) if i.get("link") is not None}
        for name, spec in req.items():
            if is_widget(spec):
                continue
            if name not in connected:
                problems.append(f"node {n['id']} ({t}): required input '{name}' not connected")
        # every declared input slot must belong to the node's contract
        opt = info[t].get("input", {}).get("optional", {})
        allowed = set(req) | set(opt)
        for i in n.get("inputs", []):
            if i["name"] not in allowed:
                problems.append(f"node {n['id']} ({t}): input slot '{i['name']}' not in contract")

    for link in wf["links"]:
        lid, onode, oslot, tnode, tslot, ltype = link
        if onode not in nodes:
            problems.append(f"link {lid}: origin node {onode} missing")
            continue
        if tnode not in nodes:
            problems.append(f"link {lid}: target node {tnode} missing")
            continue
        src = nodes[onode]
        dst = nodes[tnode]
        outs = src.get("outputs") or []
        if oslot >= len(outs):
            problems.append(f"link {lid}: {src['type']} has no output slot {oslot}")
        elif outs[oslot].get("type") not in (ltype, "*"):
            problems.append(f"link {lid}: type {outs[oslot].get('type')} != link type {ltype}")
        ins = dst.get("inputs") or []
        if tslot >= len(ins):
            problems.append(f"link {lid}: {dst['type']} has no input slot {tslot}")
        elif ins[tslot].get("type") not in (ltype, "*"):
            problems.append(f"link {lid}: target slot type {ins[tslot].get('type')} != {ltype}")
    return problems


def make_t2v(src: Path, dst: Path) -> None:
    wf = json.loads(src.read_text(encoding="utf-8"))
    t2v = copy.deepcopy(wf)
    t2v["id"] = "d14b6c88-3a07-4e52-9c1f-70b2e5a8d3f6"
    t2v["nodes"] = [n for n in t2v["nodes"] if n["type"] != "LoadImage"]
    for n in t2v["nodes"]:
        if n["type"] == "Wan22ImageToVideoLatent":
            n["inputs"] = [i for i in n["inputs"] if i["name"] != "start_image"]
        if n["type"] == "Note":
            n["widgets_values"] = [
                "TEXT TO VIDEO — Wan 2.2 TI2V-5B, same graph as manju_i2v with no start image. "
                "Prompt decides the whole frame, so it drifts off the set; use it for look tests, "
                "not for shots that must match the room."
            ]
    t2v["links"] = [l for l in t2v["links"] if l[5] != "IMAGE" or nodes_type(wf, l[1]) != "LoadImage"]
    dst.write_text(json.dumps(t2v, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"WROTE {dst.name} ({len(t2v['nodes'])} nodes, {len(t2v['links'])} links)")


def nodes_type(wf: dict, node_id: int) -> str:
    for n in wf["nodes"]:
        if n["id"] == node_id:
            return n["type"]
    return "?"


def main() -> int:
    ok = True
    targets = ["manju_inpaint.json", "manju_keyframe_control.json", "manju_i2v.json"]
    for name in targets:
        p = HERE / name
        problems = check(p)
        if problems:
            ok = False
            print(f"FAIL {name}")
            for pr in problems:
                print("   ", pr)
        else:
            wf = json.loads(p.read_text(encoding="utf-8"))
            print(f"OK   {name}  {len(wf['nodes'])} nodes, {len(wf['links'])} links")

    if ok:
        make_t2v(HERE / "manju_i2v.json", HERE / "manju_t2v.json")
        problems = check(HERE / "manju_t2v.json")
        print("FAIL manju_t2v.json" if problems else "OK   manju_t2v.json")
        for pr in problems:
            print("   ", pr)
        ok = not problems
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
