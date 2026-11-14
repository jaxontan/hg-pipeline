#!/usr/bin/env python3
"""Mirror provenance/ from the Spark into the repo, with a pin file that makes drift visible.

Why: `provenance/` is the Rule 1 legal defence and it is produced on the Spark, while the repo
is the only thing that survives the operator's one-shot wipe of `~/Desktop/AIGC-Model`.
`bin/restore.sh` rebuilds weights from `models/MANIFEST.json`; provenance has no such source,
so it has to be mirrored and the mirror has to be checkable. This tool writes both halves:

    spark/provenance/<episode>/MODEL_PROVENANCE.json     the data
    spark/provenance/MIRROR.json                         the pin (sha256 + entry count + time)

`restore.sh` and `doctor.sh` verify against the pin, so a stale mirror fails loudly instead of
looking fine. A snapshot that drifts is worse than no snapshot.

    python win/mirror_provenance.py            # pull everything, rewrite MIRROR.json
    python win/mirror_provenance.py --check    # compare only, exit 1 on drift
    python win/mirror_provenance.py --force    # allow a pull that would shrink the repo copy

Read-only on the Spark: nothing is written there. Password from SPARK_PASSWORD, as with
`spark_ssh.py` - never from a file in the repo.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import posixpath
import sys
from pathlib import Path

import paramiko

HOST = os.environ.get("SPARK_HOST", "192.168.1.103")
USER = os.environ.get("SPARK_USER", "tdadmin")
REPO = Path(__file__).resolve().parent.parent
REMOTE_ROOT = "Desktop/AIGC-Model/provenance"
LOCAL_ROOT = REPO / "spark" / "provenance"
PIN = LOCAL_ROOT / "MIRROR.json"


def connect() -> paramiko.SSHClient:
    password = os.environ.get("SPARK_PASSWORD")
    if not password:
        sys.exit("SPARK_PASSWORD is not set")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=password, timeout=10,
                   allow_agent=False, look_for_keys=False)
    return client


def remote_files(sftp: paramiko.SFTPClient) -> list[str]:
    """Every MODEL_PROVENANCE.json under the Spark's provenance/, as paths relative to it."""
    home = sftp.normalize(".")
    root = posixpath.join(home, REMOTE_ROOT)
    found: list[str] = []
    for episode in sorted(sftp.listdir(root)):
        path = posixpath.join(root, episode)
        try:
            if not sftp.stat(path).st_mode & 0o040000:  # not a directory
                continue
        except IOError:
            continue
        try:
            names = sftp.listdir(path)
        except IOError:
            continue
        for name in sorted(names):
            if name == "MODEL_PROVENANCE.json":
                found.append(posixpath.join(episode, name))
    return found


def count_entries(path: Path) -> int:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return -1
    return len(data.get("entries", []))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="compare only, write nothing, exit 1 on drift")
    ap.add_argument("--force", action="store_true", help="allow the repo copy to lose entries")
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

    args = ap.parse_args()

    client = connect()
    try:
        sftp = client.open_sftp()
        rels = remote_files(sftp)
        if not rels:
            sys.exit("FAIL: no MODEL_PROVENANCE.json found on the Spark - nothing to mirror")

        pulled: dict[str, dict] = {}
        drift = False
        for rel in rels:
            remote = posixpath.join(sftp.normalize("."), REMOTE_ROOT, rel)
            local = LOCAL_ROOT / rel
            blob = sftp.open(remote).read()
            sha = hashlib.sha256(blob).hexdigest()
            r_entries = len(json.loads(blob).get("entries", []))
            l_entries = count_entries(local) if local.is_file() else -1
            same = local.is_file() and hashlib.sha256(local.read_bytes()).hexdigest() == sha
            pulled[rel] = {"bytes": len(blob), "sha256": sha, "entries": r_entries}

            status = "same" if same else "NEW "
            if not same:
                drift = True
                if l_entries > r_entries and not args.force:
                    print(f"REFUSE {rel}: repo has {l_entries} entries, Spark has {r_entries} "
                          f"- the Spark copy is older. Re-render first, or pass --force.",
                          file=sys.stderr)
                    return 1
            print(f"{status} {rel:52s} {len(blob):>9,} B  {r_entries:>3} entries  {sha[:12]}")

            if not args.check and not same:
                local.parent.mkdir(parents=True, exist_ok=True)
                local.write_bytes(blob)
    finally:
        client.close()

    if args.check:
        pinned = json.loads(PIN.read_text(encoding="utf-8")) if PIN.is_file() else None
        if pinned is None:
            print("FAIL: no MIRROR.json pin - run without --check to create it", file=sys.stderr)
            return 1
        problems = []
        for rel, info in pulled.items():
            pin = pinned.get("files", {}).get(rel)
            if pin is None:
                problems.append(f"{rel}: not in the pin")
            elif pin["sha256"] != info["sha256"]:
                problems.append(f"{rel}: pin {pin['sha256'][:12]} != live {info['sha256'][:12]} "
                                f"({pin['entries']} -> {info['entries']} entries)")
        for rel in pinned.get("files", {}):
            if rel not in pulled:
                problems.append(f"{rel}: pinned but gone from the Spark")
        if problems:
            print("DRIFT - the repo mirror is not the Spark:", file=sys.stderr)
            for p in problems:
                print(f"  {p}", file=sys.stderr)
            print("  fix: python win/mirror_provenance.py", file=sys.stderr)
            return 1
        print("in sync - repo mirror matches the Spark")
        return 0

    PIN.parent.mkdir(parents=True, exist_ok=True)
    PIN.write_text(json.dumps({
        "schema": 1,
        "note": "Pin for restore.sh and doctor.sh. Regenerate with win/mirror_provenance.py; never hand-edit.",
        "host": HOST,
        "source": f"~/{REMOTE_ROOT}",
        "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files": pulled,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"\npin written -> {PIN.relative_to(REPO)}  ({len(pulled)} file(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
