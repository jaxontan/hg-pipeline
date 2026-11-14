#!/usr/bin/env python3
"""Run a command on the Spark over SSH, password from SPARK_PASSWORD.

Nothing is written to the local filesystem: no known_hosts entry, no key.
The password is read from the environment, never from a file in the repo.

    $env:SPARK_PASSWORD = "..."          # PowerShell
    python win/spark_ssh.py "hostname"
    python win/spark_ssh.py --timeout 300 "sudo -n true"
"""
from __future__ import annotations

import argparse
import os
import sys

import paramiko

HOST = os.environ.get("SPARK_HOST", "192.168.1.103")
USER = os.environ.get("SPARK_USER", "tdadmin")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("command", nargs=argparse.REMAINDER)
    args = ap.parse_args()

    command = " ".join(args.command)

    password = os.environ.get("SPARK_PASSWORD")
    if not password:
        sys.exit("SPARK_PASSWORD is not set")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        HOST,
        username=USER,
        password=password,
        timeout=10,
        allow_agent=False,
        look_for_keys=False,
    )
    try:
        stdin, stdout, stderr = client.exec_command(command, timeout=args.timeout, get_pty=False)
        stdin.close()
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        code = stdout.channel.recv_exit_status()
    finally:
        client.close()

    sys.stdout.write(out)
    if err.strip():
        sys.stderr.write(err)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
