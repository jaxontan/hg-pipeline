#!/usr/bin/env python3
"""Run every shot in a shots file through win/submit_clip.py, one clip at a time.

Sequential on purpose: the Spark has one GPU, and the gateway assigns per-lane, so
submitting in parallel only reorders the queue without finishing anything sooner.
A failed shot is logged and the batch continues; the exit code reports how many failed.

    FREEFIELD_TOKEN=... python win/batch_clips.py --shots win/shots_laotang_ep01.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", default=str(REPO / "win" / "shots_laotang_ep01.json"))
    ap.add_argument("--episode", default="laotang_ep01")
    ap.add_argument("--only", default="", help="comma-separated shot ids to run")
    ap.add_argument("--length", type=int, default=121)
    ap.add_argument("--steps", type=int, default=30)
    ap.add_argument("--shift", type=float, default=8.0)
    ap.add_argument("--cfg", type=float, default=5.0)
    ap.add_argument("--seed", type=int, default=420261113)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not os.environ.get("FREEFIELD_TOKEN"):
        sys.exit("FREEFIELD_TOKEN is required (read it from the Spark's env.local)")

    shots = json.loads(Path(args.shots).read_text(encoding="utf-8"))
    if args.only:
        wanted = {s.strip() for s in args.only.split(",")}
        shots = [s for s in shots if s["shot_id"] in wanted]

    print(f"batch: {len(shots)} shot(s) from {Path(args.shots).name}", flush=True)
    failed: list[tuple[str, str]] = []
    t_batch = time.perf_counter()

    for i, shot in enumerate(shots, 1):
        sid = shot["shot_id"]
        frame = Path(shot["first_frame"])
        print(f"\n[{i}/{len(shots)}] {sid}  <- {frame.name}", flush=True)
        if not frame.is_file():
            failed.append((sid, f"first frame missing: {frame}"))
            print(f"  SKIP: {frame} missing", flush=True)
            continue
        cmd = [
            sys.executable, str(REPO / "win" / "submit_clip.py"),
            "--episode", args.episode,
            "--shot-id", sid,
            "--first-frame", str(frame),
            "--prompt", shot["prompt"],
            "--length", str(args.length),
            "--steps", str(args.steps),
            "--shift", str(args.shift),
            "--cfg", str(args.cfg),
            "--seed", str(args.seed),
        ]
        if args.dry_run:
            print("  DRY RUN:", " ".join(cmd[-6:]), flush=True)
            continue
        t0 = time.perf_counter()
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        out = (proc.stdout or "").strip()
        if out:
            print("  " + out.replace("\n", "\n  "), flush=True)
        if proc.returncode != 0:
            err = (proc.stderr or "").strip().splitlines()
            failed.append((sid, err[-1] if err else f"exit {proc.returncode}"))
            print(f"  FAILED after {time.perf_counter() - t0:.0f}s", flush=True)

    total = time.perf_counter() - t_batch
    print(f"\nbatch finished in {total / 60:.1f} min; {len(shots) - len(failed)}/{len(shots)} ok", flush=True)
    for sid, why in failed:
        print(f"  FAILED {sid}: {why}", flush=True)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
