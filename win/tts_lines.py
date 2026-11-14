#!/usr/bin/env python3
"""Render the episode's voice lines on the Spark and pull them to Windows.

Phase 4 of the pipeline, and the first voice path in `win/`. It does not synthesise anything
itself: inference runs on the Spark under `app/venv-tts` (never `venv/`, which is ComfyUI's and
pins transformers 5.22.2 while qwen-tts needs 4.57.3). This script is the driver:

    1. read the line spec (work/story/vo_lines_laotang_ep01.json) and sanity-check it
    2. upload it to the Spark
    3. run app/tts/render_lines.py there, streaming its output
    4. pull every wav into work/<episode>/vo/ and re-verify the sha256 the Spark recorded
    5. print the table, and remind you to mirror provenance

The wavs must end up here because assembly runs on Windows (Rule 4): a Jianying draft embeds
absolute local media paths. Provenance is written on the Spark, where the asset is produced;
the pin in spark/provenance/MIRROR.json therefore drifts until you mirror.

    $env:SPARK_PASSWORD = "..."
    python win/tts_lines.py --dry-run
    python win/tts_lines.py
    python win/tts_lines.py --only vo01,vo03
    python win/tts_lines.py --pull-only          # just fetch + verify what is already there
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import posixpath
import sys
import time
from pathlib import Path

import paramiko

HOST = os.environ.get("SPARK_HOST", "192.168.1.103")
USER = os.environ.get("SPARK_USER", "tdadmin")
REPO = Path(__file__).resolve().parent.parent
REMOTE_ROOT = "Desktop/AIGC-Model"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def connect() -> paramiko.SSHClient:
    password = os.environ.get("SPARK_PASSWORD")
    if not password:
        sys.exit("SPARK_PASSWORD is not set")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=password, timeout=10,
                   allow_agent=False, look_for_keys=False)
    return client


def run_stream(client: paramiko.SSHClient, command: str, timeout: int) -> int:
    """Run remotely, printing output as it arrives -- a render can take minutes per line."""
    chan = client.get_transport().open_session()
    chan.settimeout(timeout)
    chan.exec_command(command)
    while True:
        if chan.recv_ready():
            sys.stdout.write(chan.recv(8192).decode("utf-8", "replace"))
            sys.stdout.flush()
        elif chan.exit_status_ready():
            while chan.recv_ready():
                sys.stdout.write(chan.recv(8192).decode("utf-8", "replace"))
            break
        else:
            time.sleep(0.2)
    return chan.recv_exit_status()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lines", default="work/story/vo_lines_laotang_ep01.json")
    ap.add_argument("--episode", default=None)
    ap.add_argument("--only", default="")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="validate the spec, touch nothing")
    ap.add_argument("--pull-only", action="store_true", help="skip rendering, just pull + verify")
    ap.add_argument("--timeout", type=int, default=3600)
    args = ap.parse_args()

    spec_path = REPO / args.lines
    if not spec_path.is_file():
        sys.exit(f"FAIL: no line spec at {spec_path}")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    episode = args.episode or spec.get("episode")
    if not episode:
        sys.exit("FAIL: spec has no episode and none was passed")

    lines = spec["lines"]
    if args.only:
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        lines = [ln for ln in lines if ln["id"] in wanted]
        missing = wanted - {ln["id"] for ln in lines}
        if missing:
            sys.exit(f"FAIL: no such line id(s): {sorted(missing)}")
    for ln in lines:
        if not ln.get("text"):
            sys.exit(f"FAIL: {ln['id']} has no text")
        if not ln.get("seed") or int(ln["seed"]) < 1:
            sys.exit(f"FAIL: {ln['id']} needs a seed >= 1")

    local_dir = REPO / "work" / episode / "vo"
    local_dir.mkdir(parents=True, exist_ok=True)

    print(f"episode : {episode}")
    print(f"spec    : {args.lines} ({len(lines)} line(s))")
    print(f"local   : work/{episode}/vo/")
    for ln in lines:
        target = ln.get("target_seconds")
        print(f"  {ln['id']:6s} {ln['speaker']:6s} seed={ln['seed']:<7d} target={target or '-':>4}s  {ln['text'][:24]}")

    if args.dry_run:
        print("\ndry run -- spec is valid, nothing uploaded")
        return 0

    client = connect()
    try:
        sftp = client.open_sftp()
        home = sftp.normalize(".")
        remote_root = posixpath.join(home, REMOTE_ROOT)
        remote_spec = posixpath.join(remote_root, "work", "story", spec_path.name)
        remote_vo = posixpath.join(remote_root, "work", episode, "vo")

        sftp.put(str(spec_path), remote_spec)
        print(f"\nuploaded spec -> work/story/{spec_path.name}")

        if not args.pull_only:
            cmd = (
                f"cd {remote_root} && source env.sh >/dev/null && "
                f"app/venv-tts/bin/python app/tts/render_lines.py "
                f"--lines work/story/{spec_path.name} --episode {episode}"
            )
            if args.only:
                cmd += f" --only {args.only}"
            if args.overwrite:
                cmd += " --overwrite"
            print(f"\n$ {cmd}\n", flush=True)
            rc = run_stream(client, cmd + " 2>&1", args.timeout)
            if rc != 0:
                sys.exit(f"FAIL: remote render exited {rc}")

        manifest_remote = posixpath.join(remote_vo, "VO_MANIFEST.json")
        with sftp.open(manifest_remote) as f:
            manifest = json.loads(f.read().decode("utf-8"))

        print(f"\npulling {len(manifest['lines'])} wav(s) -> work/{episode}/vo/")
        bad = []
        for item in manifest["lines"]:
            remote = posixpath.join(remote_vo, item["file"])
            local = local_dir / item["file"]
            sftp.get(remote, str(local))
            actual = sha256_file(local)
            ok = actual == item["sha256"]
            print(f"  {'OK  ' if ok else 'FAIL'} {item['file']:30s} {item['seconds']:6.2f}s  {actual[:12]}")
            if not ok:
                bad.append((item["file"], actual, item["sha256"]))

        local_manifest = local_dir / "VO_MANIFEST.json"
        local_manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        sftp.close()
    finally:
        client.close()

    if bad:
        print("\nFAIL: these wavs did not match the hash the Spark recorded:", file=sys.stderr)
        for name, got, want in bad:
            print(f"  {name}: got {got}, want {want}", file=sys.stderr)
        return 1

    total = sum(i["seconds"] for i in manifest["lines"])
    print(f"\n{len(manifest['lines'])} line(s), {total:.1f}s, verified against the Spark.")
    print("next: python win/mirror_provenance.py   (provenance gained entries)")
    print("      bin/doctor.sh on the Spark should then pass again")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
