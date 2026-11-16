#!/usr/bin/env python3
"""Push one file into the Spark folder, and optionally run a command there.

The Spark is the only other writable root, and everything lands under
~/Desktop/AIGC-Model. This is the small tool the driver scripts kept re-implementing inline:

    $env:SPARK_PASSWORD = "..."
    python win/spark_push.py spark/app/tts/measure_lines.py
    python win/spark_push.py spark/app/tts/measure_lines.py --run "app/venv-tts/bin/python app/tts/measure_lines.py --episode <episode>"

The local path is interpreted relative to the repo root and mapped onto the same relative path
under the remote folder, so `spark/app/tts/x.py` becomes `~/Desktop/AIGC-Model/app/tts/x.py`.
Nothing is written locally.
"""
from __future__ import annotations

import argparse
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
    ap.add_argument("files", nargs="+", help="local paths, relative to the repo root")
    ap.add_argument("--run", default=None, help="command to run in the remote folder after the push")
    ap.add_argument("--timeout", type=int, default=1800)
    args = ap.parse_args()

    client = connect()
    try:
        sftp = client.open_sftp()
        home = sftp.normalize(".")
        remote_root = posixpath.join(home, REMOTE_ROOT)
        for name in args.files:
            local = (REPO / name).resolve()
            if not local.is_file():
                sys.exit(f"FAIL: no such file: {local}")
            try:
                rel = local.relative_to(REPO / "spark")
            except ValueError:
                sys.exit(f"FAIL: {name} is not under spark/ -- nothing on the Spark maps to it")
            remote = posixpath.join(remote_root, rel.as_posix())
            sftp.put(str(local), remote)
            print(f"pushed {local.relative_to(REPO).as_posix()} -> {rel.as_posix()}")
        sftp.close()

        if args.run:
            cmd = f"cd {remote_root} && source env.sh >/dev/null && {args.run}"
            print(f"\n$ {cmd}\n", flush=True)
            return run_stream(client, cmd + " 2>&1", args.timeout)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
