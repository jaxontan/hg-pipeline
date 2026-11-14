
import json, os, shutil, sys, time
from pathlib import Path

models_dir = Path("/home/tdadmin/Desktop/AIGC-Model/models")
files = json.loads((models_dir / ".manifest.json").read_text(encoding="utf-8"))
todo = [m for m in files if not (models_dir / m["dir"] / m["name"]).exists()]
total_gb = sum(m.get("gb", 0) for m in todo)
print(f"{len(files)} model files in requested packs; {len(todo)} missing ({total_gb:.2f} GB)")

if False:
    for m in todo:
        gated = " (gated - requires HF_TOKEN)" if m.get("gated") else ""
        print(f"  [missing] {m['dir']}/{m['name']}  ({m.get('gb', 0):.2f} GB)  from {m['repo']}{gated}")
    sys.exit(0)

from huggingface_hub import hf_hub_download
tmp = models_dir / ".incoming"
token = '' or os.environ.get("HF_TOKEN") or None
failed = []

for idx, m in enumerate(todo, start=1):
    dest = models_dir / m["dir"] / m["name"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"[{idx}/{len(todo)}] Downloading {m['dir']}/{m['name']} ({m.get('gb', 0):.2f} GB) from {m['repo']} ...", flush=True)
    t0 = time.time()
    try:
        dl_path = hf_hub_download(
            repo_id=m["repo"],
            filename=m["file"],
            local_dir=tmp / m["repo"].replace("/", "__"),
            token=token,
        )
        shutil.move(dl_path, dest)
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(Path("/home/tdadmin/Desktop/AIGC-Model/hf/hub"), ignore_errors=True)
        Path("/home/tdadmin/Desktop/AIGC-Model/hf/hub").mkdir(parents=True, exist_ok=True)
        print(f"  -> Saved {dest} in {time.time() - t0:.1f}s", flush=True)
    except Exception as e:
        failed.append(m["name"])
        print(f"  [FAILED] {m['name']}: {type(e).__name__}: {str(e)[:200]}", flush=True)
        if m.get("gated"):
            print(f"    Accept license at https://huggingface.co/{m['repo']} and pass --hf-token", flush=True)

shutil.rmtree(tmp, ignore_errors=True)
if failed:
    sys.exit(f"Failed to download {len(failed)} file(s): {failed}")
print("All requested pack models are present in /home/tdadmin/Desktop/AIGC-Model/models!")
print("DOWNLOAD_COMPLETE")
