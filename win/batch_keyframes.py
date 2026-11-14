#!/usr/bin/env python3
"""Submit every keyframe in a shots file through win/submit_keyframe.py, one at a time.

The keyframe counterpart to `batch_clips.py`: `batch_clips.py` needs a finished first frame,
which is exactly what this produces. Sequential on purpose — one GPU, and the gateway assigns per
lane, so parallel submits only reorder the queue.

Every entry carries its own `depth` (the blurred `_depth_ctrl.png`, never the sharp pass) and the
`blend` it came from, so `blender_sha256` lands in the provenance record.

    FREEFIELD_TOKEN=... python win/batch_keyframes.py --dry-run
    FREEFIELD_TOKEN=... python win/batch_keyframes.py
    FREEFIELD_TOKEN=... python win/batch_keyframes.py --only x001,x002
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", default=str(REPO / "win" / "shots_laotang_ep01_keyframes.json"))
    ap.add_argument("--episode", default="laotang_ep01")
    ap.add_argument("--only", default="", help="comma-separated shot ids")
    ap.add_argument("--strength", type=float, default=0.85)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    shots = json.loads(Path(args.shots).read_text(encoding="utf-8"))
    only = {s for s in args.only.split(",") if s}
    todo = [s for s in shots if not only or s["shot_id"] in only]
    if not todo:
        print(f"nothing to do (only={args.only!r})")
        return 2

    failures = []
    started = time.perf_counter()
    for i, shot in enumerate(todo, 1):
        depth = REPO / shot["depth"]
        blend = REPO / shot["blend"] if shot.get("blend") else None
        tag = f"[{i}/{len(todo)}] {shot['shot_id']}"

        if not depth.is_file():
            print(f"{tag} MISSING depth pass {depth}")
            failures.append(shot["shot_id"])
            continue
        if blend and not blend.is_file():
            print(f"{tag} MISSING blend {blend}")
            failures.append(shot["shot_id"])
            continue

        cmd = [
            sys.executable, str(REPO / "win" / "submit_keyframe.py"),
            "--episode", args.episode,
            "--shot-id", shot["shot_id"],
            "--prompt", shot["prompt"],
            "--depth-image", str(depth),
            "--control-strength", str(args.strength),
            "--territory", shot.get("territory", "both"),
            "--out-dir", str(REPO / "work"),
        ]
        if blend:
            cmd += ["--blend-file", str(blend)]

        print(f"{tag} depth={depth.name} blend={blend.name if blend else '-'}")
        if args.dry_run:
            continue
        t0 = time.perf_counter()
        res = subprocess.run(cmd, text=True, capture_output=True)
        if res.returncode != 0:
            print(res.stdout[-1500:])
            print(res.stderr[-1500:], file=sys.stderr)
            failures.append(shot["shot_id"])
            continue
        for line in res.stdout.splitlines():
            if line.startswith(("submitted", "pulled", "uploaded")):
                print(f"   {line}")
        print(f"   {shot['shot_id']} done in {time.perf_counter() - t0:.1f}s")

    total = time.perf_counter() - started
    print(f"\nSUMMARY {len(todo) - len(failures)}/{len(todo)} ok in {total:.1f}s"
          + (f"  FAILED: {','.join(failures)}" if failures else ""))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
