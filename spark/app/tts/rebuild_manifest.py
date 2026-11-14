#!/usr/bin/env python3
"""Reconstruct work/<episode>/vo/VO_MANIFEST.json from the wavs that are on disk.

`render_lines.py` used to rewrite the manifest from the current run's results only, so a
`--only vo06 --overwrite` pass cut a six-entry manifest down to one entry while all six wavs
stayed put. That is the same class of failure as two provenance entries for one asset: a record
that no longer describes the folder.

This rebuilds it from the spec and the files. Nothing is invented — an entry is only written for a
wav that exists, with its real sha256, byte count and duration. The header fields (model_id and
both weight hashes) are carried over from the existing manifest, because this script did not
render anything and has no business guessing which weights produced the files.

    app/venv-tts/bin/python app/tts/rebuild_manifest.py --episode laotang_ep01 --dry-run
    app/venv-tts/bin/python app/tts/rebuild_manifest.py --episode laotang_ep01
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import wave
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def wav_seconds(path: Path) -> tuple[float, int, int]:
    with wave.open(str(path), "rb") as w:
        frames, rate = w.getnframes(), w.getframerate()
    return frames / float(rate), int(rate), path.stat().st_size


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", required=True)
    ap.add_argument("--spec", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    aigc = Path(os.environ.get("AIGC") or Path(__file__).resolve().parents[2]).resolve()
    vo = aigc / "work" / args.episode / "vo"
    manifest_path = vo / "VO_MANIFEST.json"
    spec_path = Path(args.spec) if args.spec else aigc / "work" / "story" / f"vo_lines_{args.episode}.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    header = {"episode": args.episode, "model_id": spec.get("model_id")}
    if manifest_path.is_file():
        old = json.loads(manifest_path.read_text(encoding="utf-8"))
        for key in ("model_id", "model_sha256", "speech_tokenizer_sha256", "generated_utc"):
            if old.get(key):
                header[key] = old[key]
    if not header.get("model_sha256"):
        print("FAIL: no model_sha256 to carry over -- render one line first", file=sys.stderr)
        return 1

    lines, missing = [], []
    for ln in spec["lines"]:
        name = f"{ln['id']}_{ln['slug']}.wav"
        path = vo / name
        if not path.is_file():
            missing.append(ln["id"])
            continue
        seconds, rate, size = wav_seconds(path)
        lines.append({
            "id": ln["id"],
            "file": name,
            "sha256": sha256_file(path),
            "bytes": size,
            "seconds": round(seconds, 3),
            "sample_rate": rate,
            "speaker": ln["speaker"],
            "seed": int(ln["seed"]),
            "text_sha256": hashlib.sha256(ln["text"].encode("utf-8")).hexdigest(),
        })

    print(f"{len(lines)} of {len(spec['lines'])} line(s) present on disk")
    for r in lines:
        print(f"  {r['id']:6s} {r['file']:30s} {r['seconds']:6.2f}s  {r['sha256'][:12]}")
    if missing:
        print(f"  MISSING (no entry written): {', '.join(missing)}")

    if args.dry_run:
        print("\ndry run -- manifest unchanged")
        return 0

    header["lines"] = lines
    manifest_path.write_text(json.dumps(header, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"\nwrote {manifest_path.relative_to(aigc)}: {len(lines)} entry(ies)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
