# AIGC-Model — the only writable place on this machine

This folder is the entire boundary. Everything this project creates lives here, and
`rm -rf ~/Desktop/AIGC-Model` returns the machine to pristine. See `DELETE.md` for the
full wipe set, including what must be removed outside the folder.

## Start here, every session

```bash
source ~/Desktop/AIGC-Model/env.sh
```

That single command:

- redirects **`HOME` itself inside this folder** — so even a tool that ignores every
  cache variable still writes here
- redirects `HF_HOME`, `HF_HUB_CACHE`, `TORCH_HOME`, `TRITON_CACHE_DIR`, `CUDA_CACHE_PATH`,
  `PIP_CACHE_DIR`, `UV_CACHE_DIR`, `TMPDIR`, `OLLAMA_*`, `BLENDER_USER_*`, `XDG_*`
- puts `venv/bin`, `bin/`, and CUDA on `PATH`
- activates the venv if it exists
- creates the directory skeleton on first run

`MANJU_REAL_HOME` keeps the real home path for the one or two things that must reach it
(`~/.ssh`). Nothing else is allowed out there.

**Do not run ComfyUI or Blender without sourcing `env.sh` first.** Their default paths
are the real home's cache directories, which is exactly the leak this design exists to
prevent.

## Daily commands

| Command | What it does |
|---|---|
| `bin/status.sh` | GPU, unified memory, disk, running services, listening ports. Read-only. |
| `bin/doctor.sh` | Proves the boundary holds: no cache leaks, no outward symlinks, no undeclared installs. **Run before every batch and before saying "done".** |
| `bin/record-install.sh <layer> <cmd>` | The only sanctioned way to change the machine outside this folder. Writes a receipt. |
| `bin/record-install.sh snapshot` | Regenerate the machine inventory. The first run pins the baseline. |
| `bin/record-install.sh ledger` | Show what has been installed since baseline. |

## The rule about installs

System-wide packages are allowed — `apt`, `pip --user`, `uv`, `snap`, `docker`, writing to
`/usr/local/bin` — but **only through `record-install.sh`**, which appends a receipt to
`app/os/installed.tsv`. An install without a receipt is a defect: the operator's one-shot
wipe can no longer be scripted from this folder.

`doctor.sh` fails on undeclared installs.

## Layout

```
env.sh              hermetic environment — source this first
DELETE.md           how to remove every trace, in one shot
README.md           this file
bin/                status, doctor, record-install, restore
app/
  os/               install ledger + baseline machine inventory
  venv/             ComfyUI's python environment (torch 2.14.1, transformers 5.22.2)
  venv-tts/         voice environment, separate on purpose: qwen-tts pins transformers 4.57.3
  tts/              render_lines.py — Qwen3-TTS VoiceDesign, driven by win/tts_lines.py
models/             weights + MANIFEST.json (sha256, SPDX licence, licence link)
  tts/ asr/         directory models: every file listed in the manifest's files[] list
work/               input / output / temp — job scratch
provenance/         MODEL_PROVENANCE.json per episode + MIRROR.json (the pin; see win/mirror_provenance.py)
archive/            finished masters, before they leave for Windows
logs/               run logs
```

## Two rules that are not negotiable here

1. **Nothing is written outside this folder.** Not a cache, not a temp file, not a weight.
   If a tool needs `sudo`, it goes through `record-install.sh`.
2. **Every asset carries provenance.** A rendered file without a `MODEL_PROVENANCE.json`
   entry cannot be assembled into a master. That is the legal defence, and `doctor.sh`
   enforces it — including drift against `provenance/MIRROR.json`, the pin written by
   `win/mirror_provenance.py` on Windows. After any render batch: mirror, then doctor.
