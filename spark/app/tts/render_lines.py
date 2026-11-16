#!/usr/bin/env python3
"""Render the episode's voice lines with Qwen3-TTS VoiceDesign and record provenance.

Runs on the Spark, inside the folder, with `app/venv-tts` -- never `venv/`. That venv is
ComfyUI's (transformers 5.22.2 / torch 2.14.1) and qwen-tts pins transformers==4.57.3, so
installing it there would downgrade the pipeline that renders the picture.

    app/venv-tts/bin/python app/tts/render_lines.py --lines work/story/vo_lines_<episode>.json

Writes:
    work/<episode>/vo/<id>_<slug>.wav            16-bit PCM at the model's sample rate
    work/<episode>/vo/VO_MANIFEST.json           filename + sha256 + seconds per line
    provenance/<episode>/MODEL_PROVENANCE.json   one entry per line (Rule 1)

`win/tts_lines.py` drives this from Windows, pulls the wavs and verifies them against
VO_MANIFEST.json. The provenance file is rewritten with indent=2 and ASCII escaping, which is
how the ComfyUI-side writer stores it; keeping that byte-shape means the mirror pin only changes
because entries were added, never because the formatter changed.

Provenance is appended here, not on Windows, because Rule 1 attaches the record to the machine
that produced the asset. The pin (`provenance/MIRROR.json`) will therefore drift the moment a
line is rendered -- that is the designed behaviour: run `win/mirror_provenance.py` afterwards.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical(obj) -> bytes:
    """Stable bytes for hashing a spec: sorted keys, no whitespace drift."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def load_manifest_row(manifest_path: Path, model_id: str) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for row in manifest.get("models", []):
        if row["id"] == model_id:
            return row
    sys.exit(f"FAIL: {model_id} is not in {manifest_path} -- add the row before rendering (Rule 2)")


def model_provenance_block(row: dict) -> list[dict]:
    """The models[] list a provenance entry carries: the weights and the speech tokenizer."""
    files = {f["file"]: f for f in row.get("files", [])}
    block = []
    if "model.safetensors" in files:
        block.append({
            "id": row["id"],
            "name": "model.safetensors",
            "spdx": row["spdx"],
            "license_url": row["license_url"],
            "quantisation": row["quantisation"],
            "sha256": files["model.safetensors"]["sha256"],
        })
    if "speech_tokenizer/model.safetensors" in files:
        block.append({
            "id": row["id"] + "_speech_tokenizer",
            "name": "speech_tokenizer/model.safetensors",
            "spdx": row["spdx"],
            "license_url": row["license_url"],
            "quantisation": row["quantisation"],
            "sha256": files["speech_tokenizer/model.safetensors"]["sha256"],
        })
    if not block:
        sys.exit(f"FAIL: {row['id']} has no files[] -- restore.sh needs the per-file rows first")
    return block


def append_provenance(path: Path, entries: list[dict]) -> None:
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = {"episode": path.parent.name, "schema": 1, "entries": []}
    data.setdefault("entries", []).extend(entries)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lines", required=True, help="line spec JSON (see work/story/vo_lines_*.json)")
    ap.add_argument("--episode", required=True)
    ap.add_argument("--out", default=None, help="output dir (default work/<episode>/vo)")
    ap.add_argument("--model", default=None, help="override the model dir from the spec")
    ap.add_argument("--only", default="", help="comma-separated line ids to render")
    ap.add_argument("--overwrite", action="store_true", help="re-render lines whose wav already exists")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, load nothing")
    args = ap.parse_args()

    aigc = Path(os.environ.get("AIGC") or Path(__file__).resolve().parents[2]).resolve()
    spec_path = (aigc / args.lines).resolve() if not Path(args.lines).is_absolute() else Path(args.lines)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    episode = args.episode
    out_dir = Path(args.out) if args.out else aigc / "work" / episode / "vo"
    out_dir.mkdir(parents=True, exist_ok=True)
    prov_path = aigc / "provenance" / episode / "MODEL_PROVENANCE.json"

    model_id = spec.get("model_id", "qwen3_tts_voicedesign_1_7b")
    row = load_manifest_row(aigc / "models" / "MANIFEST.json", model_id)
    model_dir = Path(args.model) if args.model else aigc / "models" / row["dir"] / row["name"]
    if not (model_dir / "model.safetensors").is_file():
        sys.exit(f"FAIL: {model_dir} has no model.safetensors -- run bin/restore.sh {model_id}")

    lines = spec["lines"]
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    if only:
        lines = [ln for ln in lines if ln["id"] in only]
        missing = only - {ln["id"] for ln in lines}
        if missing:
            sys.exit(f"FAIL: no such line id(s): {sorted(missing)}")

    for ln in lines:
        if not ln.get("seed") or int(ln["seed"]) < 1:
            sys.exit(f"FAIL: {ln['id']} needs a seed >= 1 (a zero seed fails the Rule 1 completeness check)")
        if not ln.get("text"):
            sys.exit(f"FAIL: {ln['id']} has no text")

    print(f"episode   : {episode}")
    print(f"model     : {model_dir.relative_to(aigc)}")
    print(f"out       : {out_dir.relative_to(aigc)}")
    print(f"provenance: {prov_path.relative_to(aigc)}")
    print(f"lines     : {len(lines)}")
    for ln in lines:
        target = ln.get("target_seconds")
        print(f"  {ln['id']:6s} {ln['speaker']:6s} seed={ln['seed']:<6d} "
              f"target={target if target else '-'}s  {ln['text'][:28]}")
    if args.dry_run:
        print("dry run -- nothing loaded, nothing written")
        return 0

    import numpy as np
    import soundfile as sf
    import torch
    import transformers
    import qwen_tts
    from qwen_tts import Qwen3TTSModel

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    print(f"\nloading on {device} ...", flush=True)
    model = Qwen3TTSModel.from_pretrained(str(model_dir), device_map=device, dtype=torch.bfloat16)
    print("loaded", flush=True)

    models_block = model_provenance_block(row)
    engine_version = {
        "qwen_tts": getattr(qwen_tts, "__version__", "0.1.1"),
        "transformers": transformers.__version__,
        "torch": torch.__version__,
        "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
    }

    gen = spec.get("generation", {})
    results, new_entries = [], []

    for ln in lines:
        slug = ln.get("slug") or ln["id"]
        name = f"{ln['id']}_{slug}.wav"
        dest = out_dir / name
        if dest.is_file() and not args.overwrite:
            audio, sr = sf.read(str(dest), dtype="float32")
            seconds = len(audio) / float(sr)
            print(f"  SKIP {name} (exists, {seconds:.2f}s) -- use --overwrite to re-render")
            results.append({"id": ln["id"], "file": name, "sha256": sha256_file(dest),
                            "bytes": dest.stat().st_size, "seconds": round(seconds, 3),
                            "sample_rate": sr, "speaker": ln["speaker"], "seed": ln["seed"],
                            "text_sha256": hashlib.sha256(ln["text"].encode("utf-8")).hexdigest()})
            continue

        torch.manual_seed(int(ln["seed"]))
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(int(ln["seed"]))

        params = dict(
            do_sample=gen.get("do_sample", True),
            temperature=gen.get("temperature", 0.9),
            top_p=gen.get("top_p", 1.0),
            top_k=gen.get("top_k", 50),
            repetition_penalty=gen.get("repetition_penalty", 1.05),
            max_new_tokens=gen.get("max_new_tokens", 4096),
        )

        print(f"  GEN  {name} ...", flush=True)
        wavs, sr = model.generate_voice_design(
            text=ln["text"],
            instruct=ln.get("instruct", ""),
            language=ln.get("language", "Chinese"),
            **params,
        )
        if not wavs:
            sys.exit(f"FAIL: {ln['id']} produced no audio")
        audio = np.asarray(wavs[0], dtype="float32")
        sf.write(str(dest), audio, int(sr), subtype="PCM_16")

        seconds = len(audio) / float(sr)
        target = ln.get("target_seconds")
        flag = ""
        if target:
            flag = " OVER" if seconds > float(target) + 0.05 else (" SHORT" if seconds < float(target) * 0.6 else "")
        print(f"       {seconds:.2f}s @ {sr} Hz{flag}  -> {name}", flush=True)

        workflow_sha = hashlib.sha256(canonical({
            "line": {k: ln.get(k) for k in ("id", "speaker", "text", "instruct", "language", "seed")},
            "generation": params,
            "model_id": model_id,
            "model_sha256": models_block[0]["sha256"],
        })).hexdigest()

        job_id = uuid.uuid4().hex[:16]
        new_entries.append({
            "job_id": job_id,
            "episode": episode,
            "shot_id": ln["id"],
            "lane": "tts",
            "territory": ln.get("territory", "both"),
            "prompt_id": job_id,
            "models": models_block,
            "sampler": "qwen3-tts-voice-design",
            "steps": None,
            "cfg": None,
            "seed": int(ln["seed"]),
            "workflow_sha256": workflow_sha,
            "blender_sha256": None,
            "engine_version": engine_version,
            "speaker": ln["speaker"],
            "text": ln["text"],
            "instruct": ln.get("instruct", ""),
            "params": params,
            "outputs": [{
                "node_id": "0",
                "kind": "audio",
                "filename": name,
                "subfolder": "vo",
                "type": "output",
                "sha256": sha256_file(dest),
                "bytes": dest.stat().st_size,
                "sample_rate": int(sr),
                "seconds": round(seconds, 3),
            }],
            "timestamp": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
        results.append({"id": ln["id"], "file": name, "sha256": new_entries[-1]["outputs"][0]["sha256"],
                        "bytes": new_entries[-1]["outputs"][0]["bytes"], "seconds": round(seconds, 3),
                        "sample_rate": int(sr), "speaker": ln["speaker"], "seed": int(ln["seed"]),
                        "text_sha256": hashlib.sha256(ln["text"].encode("utf-8")).hexdigest()})

    if new_entries:
        append_provenance(prov_path, new_entries)
        print(f"\nprovenance: +{len(new_entries)} entries -> {prov_path.relative_to(aigc)}")

    # MERGE, do not replace. `--only vo05` renders a subset, and writing "lines": results then
    # silently deletes every line that was not re-rendered -- it cut a six-entry manifest down to
    # one while all six wavs stayed on disk. The manifest is the record of what the episode
    # contains, so a partial run must only update its own entries.
    manifest_path = out_dir / "VO_MANIFEST.json"
    merged: dict[str, dict] = {}
    if manifest_path.is_file():
        try:
            for old in json.loads(manifest_path.read_text(encoding="utf-8")).get("lines", []):
                merged[old["id"]] = old
        except (json.JSONDecodeError, KeyError):
            print(f"WARN: {manifest_path.name} unreadable -- rebuilding from this run only")
    for r in results:
        merged[r["id"]] = r
    vo_manifest = {
        "episode": episode,
        "model_id": model_id,
        "model_sha256": models_block[0]["sha256"],
        "speech_tokenizer_sha256": models_block[1]["sha256"] if len(models_block) > 1 else None,
        "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lines": list(merged.values()),
    }
    manifest_path.write_text(json.dumps(vo_manifest, indent=2) + "\n", encoding="utf-8")
    print(f"\nmanifest: {len(merged)} line(s) total, {len(results)} rendered this run")

    print("\nid      file                          seconds   bytes     sha256")
    for r in results:
        print(f"{r['id']:6s}  {r['file']:28s}  {r['seconds']:7.2f}  {r['bytes']:>8d}  {r['sha256'][:12]}")
    total = sum(r["seconds"] for r in results)
    print(f"\n{len(results)} line(s), {total:.1f}s of audio")
    print("next: on Windows, python win/tts_lines.py --pull   (then python win/mirror_provenance.py)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
