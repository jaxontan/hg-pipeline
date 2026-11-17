#!/usr/bin/env python3
import urllib.request, re
UA = {"User-Agent": "aigc-pp2"}
def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=45).read().decode("utf-8", "replace")

repo = "kabachuha/Kandinsky-6.0-Lite-distill-5s-int8-convrot"
try:
    t = get(f"https://huggingface.co/{repo}/raw/main/README.md")
except Exception as e:
    print("ERR", e); raise SystemExit
t = re.sub(r"\n{3,}", "\n\n", t)
print(t[:4000])
