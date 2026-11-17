#!/usr/bin/env python3
"""List animate/s2v related files in the Wan repackaged repos + sizes."""
import json, urllib.request

def ls(repo, needle=""):
    url = f"https://huggingface.co/api/models/{repo}/tree/main?recursive=true"
    try:
        d = json.load(urllib.request.urlopen(url, timeout=60))
    except Exception as e:
        print(f"{repo}: ERR {e}")
        return
    print(f"=== {repo}")
    for it in d:
        p = it.get("path", "")
        sz = it.get("size") or 0
        if needle.lower() in p.lower():
            print(f"   {sz/1e9:7.2f} GB  {p}")
    print()

ls("Comfy-Org/Wan_2.2_ComfyUI_Repackaged", "animate")
ls("Comfy-Org/Wan_2.2_ComfyUI_Repackaged", "s2v")
ls("Comfy-Org/Wan_2.2_ComfyUI_Repackaged", "vae")
