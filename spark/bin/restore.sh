#!/usr/bin/env bash
# restore.sh — verify and download weights strictly from models/MANIFEST.json.
# Enforces Rule 0 (boundary) and Rule 2 (licence + sha256 gate).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AIGC="${AIGC:-$(cd "$SCRIPT_DIR/.." && pwd)}"
# shellcheck disable=SC1091
source "$AIGC/env.sh"

"$AIGC/venv/bin/python" - "$@" <<'PY'
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from huggingface_hub import hf_hub_download

aigc = Path(os.environ["AIGC"])
manifest_path = aigc / "models" / "MANIFEST.json"
if not manifest_path.is_file():
    sys.exit(f"FAIL: missing {manifest_path}")

manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
approved = set(manifest.get("approved_spdx", ["Apache-2.0", "MIT", "BSD-3-Clause", "BSD-2-Clause", "OpenRAIL++"]))
argv = sys.argv[1:]
unknown = [a for a in argv if a.startswith("--") and a != "--provenance-only"]
if unknown:
    sys.exit(f"FAIL: unknown flag(s): {unknown}")
prov_only = "--provenance-only" in argv
only_ids = {a for a in argv if not a.startswith("--")}

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def entry_files(m):
    """Flatten a manifest row into (repo_path, relative_name, size, sha256) tuples.

    Single-file rows (the picture models) flatten to one tuple. Directory models — Qwen3-TTS is
    weights + config.json + speech_tokenizer/ — list every file, because restoring a bare
    .safetensors with no config is not a usable model.
    """
    if m.get("files"):
        return [(f["file"], f.get("name") or f["file"], f.get("size", 0), f["sha256"]) for f in m["files"]]
    return [(m["file"], m["name"], m.get("size", 0), m.get("sha256", ""))]


def entry_dest(m, rel):
    base = aigc / "models" / m["dir"]
    return base / m["name"] / rel if m.get("files") else base / rel


entries = manifest.get("models", [])
if prov_only:
    entries = []
if only_ids:
    entries = [m for m in entries if m["id"] in only_ids]
    missing_ids = only_ids - {m["id"] for m in entries}
    if missing_ids:
        sys.exit(f"FAIL: unknown model id(s): {sorted(missing_ids)}")

# Rule 2 licence gate before downloading anything
for m in entries:
    spdx = m.get("spdx", "")
    lic_url = m.get("license_url", "")
    if spdx not in approved or not lic_url:
        sys.exit(f"FAIL [Rule 2]: {m.get('id')} rejected (spdx={spdx!r}, license_url={lic_url!r})")
    for repo_path, rel, size, sha in entry_files(m):
        if not sha or len(sha) != 64:
            sys.exit(f"FAIL [Rule 2]: {m.get('id')} / {repo_path} has no sha256 — refusing to download")

def verify_provenance(root: Path) -> int:
    """Rule 1: every episode's provenance must be present, pinned, and internally complete.

    The pin is `provenance/MIRROR.json`, written on Windows by `win/mirror_provenance.py` and
    carried here with the repo. If a file no longer matches its pin, the Spark copy gained
    entries after the last mirror — restore would hand back a folder whose legal record is
    behind its assets, so that is a failure, not a warning.
    """
    files = sorted(root.glob("*/MODEL_PROVENANCE.json"))
    if not files:
        print("FAIL [Rule 1]: no provenance/*/MODEL_PROVENANCE.json in the restored folder")
        return 1

    rc = 0
    pin_path = root / "MIRROR.json"
    pinned = {}
    if pin_path.is_file():
        pinned = json.loads(pin_path.read_text(encoding="utf-8")).get("files", {})
        for rel, info in sorted(pinned.items()):
            path = root / rel
            if not path.is_file():
                print(f"FAIL [Rule 1]: pinned {rel} is missing after restore")
                rc = 1
                continue
            actual = sha256_file(path)
            if actual != info["sha256"]:
                print(f"FAIL [Rule 1]: {rel} does not match the pin (got {actual[:12]}, "
                      f"pin {info['sha256'][:12]}) — run win/mirror_provenance.py on Windows "
                      f"and copy the repo again")
                rc = 1
            else:
                print(f"OK   provenance {rel} ({info['entries']} entries, pinned)")
        for path in files:
            rel = f"{path.parent.name}/{path.name}"
            if rel not in pinned:
                print(f"FAIL [Rule 1]: {rel} is not in MIRROR.json — unpinned provenance")
                rc = 1
    else:
        print("WARN [Rule 1]: provenance/MIRROR.json is missing — hashes not checked")

    required = ("shot_id", "territory", "models", "seed", "workflow_sha256", "engine_version", "outputs")
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            print(f"FAIL [Rule 1]: {path.relative_to(root.parent)} is not valid JSON: {exc}")
            rc = 1
            continue
        for i, e in enumerate(data.get("entries", [])):
            missing = [k for k in required if not e.get(k)]
            if missing:
                print(f"FAIL [Rule 1]: {path.parent.name} entry {i} "
                      f"({e.get('shot_id', '?')}) missing {missing}")
                rc = 1
            for m in e.get("models", []):
                if not m.get("spdx") or not m.get("sha256"):
                    print(f"FAIL [Rule 1]: {path.parent.name} entry {i} model "
                          f"{m.get('id', '?')} has no spdx/sha256")
                    rc = 1
    return rc


token = os.environ.get("HF_TOKEN") or None
incoming = aigc / "tmp" / "hf_restore"
if entries:
    incoming.mkdir(parents=True, exist_ok=True)

for idx, m in enumerate(entries, 1):
    files = entry_files(m)
    label = f"{m['dir']}/{m['name']}"
    if m.get("files"):
        label += f" ({len(files)} files)"

    pending = []
    for repo_path, rel, size, sha in files:
        dest = entry_dest(m, rel)
        if dest.is_file():
            actual = sha256_file(dest)
            if actual == sha.lower():
                continue
            print(f"[{idx}/{len(entries)}] CORRUPT {dest} (got {actual}, expected {sha}) — re-downloading",
                  flush=True)
            dest.unlink()
        pending.append((repo_path, rel, size, sha, dest))

    if not pending:
        print(f"[{idx}/{len(entries)}] OK   {label} (sha256 verified)", flush=True)
        continue

    print(f"[{idx}/{len(entries)}] GET  {label} ({sum(p[2] for p in pending)/1e9:.2f} GB) "
          f"from {m['repo']}", flush=True)
    dl_dir = incoming / m["repo"].replace("/", "__")
    for repo_path, rel, size, sha, dest in pending:
        dl_path = Path(hf_hub_download(
            repo_id=m["repo"],
            filename=repo_path,
            local_dir=str(dl_dir),
            token=token,
        ))
        actual = sha256_file(dl_path)
        if actual != sha.lower():
            sys.exit(f"FAIL: sha256 mismatch for {label} / {rel}: got {actual}, expected {sha}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(dl_path), str(dest))
        print(f"       SAVED & VERIFIED {dest.relative_to(aigc)}", flush=True)

if entries:
    shutil.rmtree(incoming, ignore_errors=True)
    print("restore.sh: all requested weights present and sha256-verified.")
else:
    print("restore.sh: no weights requested (--provenance-only).")

rc = verify_provenance(aigc / "provenance")
if rc:
    sys.exit("restore.sh: FAILED — provenance is incomplete or has drifted (see above)")
print("restore.sh: provenance verified against MIRROR.json.")
PY
