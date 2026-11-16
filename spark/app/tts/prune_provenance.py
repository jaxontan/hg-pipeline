#!/usr/bin/env python3
"""Keep one provenance entry per (lane, shot_id) — the newest.

`render_lines.py --overwrite` re-renders a line and **appends** a new entry without removing the one
it supersedes. That is deliberate on the render side (nothing is destroyed at render time) but it
leaves the record with two entries for one asset, which is the failure mode this project keeps
paying for: two records that disagree about what is on disk. vo05 reached two entries this way
before anyone noticed.

This removes the superseded ones. Order in the file is the order they were written, so the last
entry for a given (lane, shot_id) is the one whose output currently exists.

    app/venv-tts/bin/python app/tts/prune_provenance.py --episode <episode> --dry-run
    app/venv-tts/bin/python app/tts/prune_provenance.py --episode <episode>

Writes with indent=2 and ASCII escaping, the same as render_lines.py, so the file keeps one shape.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", required=True)
    ap.add_argument("--lane", default="tts", help="only prune this lane (default: tts)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    aigc = Path(os.environ.get("AIGC") or Path(__file__).resolve().parents[2]).resolve()
    path = aigc / "provenance" / args.episode / "MODEL_PROVENANCE.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    entries = doc["entries"]

    # Last occurrence wins: the file is append-ordered, so the newest render of a shot is the one
    # whose wav is on disk.
    keep_idx = {}
    for i, e in enumerate(entries):
        if e.get("lane") != args.lane:
            continue
        keep_idx[e.get("shot_id")] = i

    drop = [
        i for i, e in enumerate(entries)
        if e.get("lane") == args.lane and keep_idx.get(e.get("shot_id")) != i
    ]
    if not drop:
        print(f"nothing to prune: {len(entries)} entries, one per {args.lane} shot already")
        return 0

    print(f"{len(entries)} entries -> drop {len(drop)} superseded {args.lane} entry(ies):")
    for i in drop:
        e = entries[i]
        print(f"  {e.get('shot_id')}  job={str(e.get('job_id'))[:16]}  seed={e.get('seed')}  "
              f"{(e.get('text') or '')[:20]}")

    if args.dry_run:
        print("\ndry run -- provenance unchanged")
        return 0

    remaining = [e for i, e in enumerate(entries) if i not in set(drop)]
    doc["entries"] = remaining
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"\nwrote {path.relative_to(aigc)}: {len(entries)} -> {len(remaining)} entries")
    print("next: on Windows, python win/mirror_provenance.py   (the pin just moved)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
