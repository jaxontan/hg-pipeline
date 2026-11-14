# AGENTS.md — hard rules for every agent working in this repo

These rules are not preferences. They are constraints imposed by the operator and they override any
convenience, default path, or tool behaviour. If a rule blocks you, **stop and ask**; do not route around it.

---

## Rule 0 — Filesystem boundary (non-negotiable, highest priority)

There are exactly **two** writable locations in this project.

| Machine | The only allowed location | Address |
|---|---|---|
| DGX Spark (GB10, Ubuntu 24.04 aarch64) | `~/Desktop/AIGC-Model` | `192.168.1.103` |
| This Windows workstation | `C:\Users\admin\Desktop\manju` | local |

The Spark folder will be **deleted in a single operation** by the operator. Anything written outside it
becomes an untracked remnant on a machine that is meant to return to pristine. Therefore:

1. **Never create, modify, or leave a file outside those two roots** — not a cache, not a temp file, not a
   log, not a lock, not a downloaded weight, not a model output, not a config, not a socket.
2. **Never create a symlink in either direction** across the boundary. A link from the folder pointing out
   dangles the moment the folder is deleted; a link from outside pointing in is a leak by definition.
3. **Assume every tool's default path is wrong.** Before running anything on the Spark, `source env.sh`.
   It redirects `XDG_*`, `HF_HOME`, `HF_HUB_CACHE`, `TORCH_HOME`, `TRITON_CACHE_DIR`, `CUDA_CACHE_PATH`,
   `PIP_CACHE_DIR`, `UV_CACHE_DIR`, `TMPDIR`, `OLLAMA_MODELS`, `BLENDER_USER_*`, `npm_config_cache`.
   Run ComfyUI with explicit `--base-directory`, `--output-directory`, `--input-directory`,
   `--temp-directory` — never with defaults.
4. **`/tmp` is forbidden.** `TMPDIR` is set; if a program ignores it, pass an explicit path.
5. **System-wide installs are allowed — but nothing may be invisible.** `sudo apt`, `pip --user`, `uv`, `snap`, `systemctl`, Docker, or writing to `/usr/local/bin` is permitted **only** through `bin/record-install.sh`, which runs the command and appends a receipt to `app/os/installed.tsv` (what, version, command, date, reversible). An install without a receipt is a defect, because the operator's one-shot wipe can no longer be scripted from the folder. `bin/record-install.sh snapshot` regenerates the full machine inventory (`dpkg --get-selections`, `pip list --user`, `snap list`, `/usr/local/bin`, driver version) into `app/os/`.
6. **No `rm -rf`, `prune`, or `gc` outside the folder.** Inside the folder, destructive operations still need the operator's explicit go-ahead unless they are that agent's own scratch output.
7. **Docker is permitted but not preferred.** Prefer the venv at `app/venv`. If Docker is used, run `record-install.sh` first so `/var/lib/docker` and the image list are in the ledger, mount all project data from the folder, and note in `DELETE.md` that `docker system prune -a` is part of the wipe.
8. **Before you finish any task that touched the Spark, run `bin/doctor.sh` and report its output.**
   Non-empty output is a defect you must fix, not a note you may leave. It checks both leak sites and undeclared installs.

If a rule above prevents you from completing the request, say so plainly and propose the smallest
exception that would unblock it. Never take the exception yourself.

---

## Rule 1 — Everything carries provenance

Every rendered asset gets an entry in `provenance/MODEL_PROVENANCE.json` for its episode:
model id, licence SPDX + link, quantisation, sampler/steps/CFG, seed, workflow hash, Blender file hash,
engine version, timestamp. An asset without provenance cannot be assembled into a master. This is the
actual legal defence; platform 确权 is auxiliary.

## Rule 2 — Licence gate

Before any weight is downloaded, add it to `models/MANIFEST.json` with URL, sha256, SPDX id, and licence
link. Refuse outright:

- licence absent from the repo or model card (no LICENSE file = no commercial rights)
- NonCommercial / research-only / NC-SA terms
- revenue-capped licences for anything load-bearing (see §2.2 boosters — they are operator-gated)
- territory-excluded licences for any shot flagged `territory: global`

Approved licences for load-bearing work: **Apache-2.0, MIT, BSD, OpenRAIL++ (with RAIL use restrictions)**.

## Rule 3 — No new dependencies without approval

The stack is fixed. Do not add a ComfyUI custom node, frontend, workbench, or Python package that is not in
`plan.md` §2 without explicit approval — regardless of star count, novelty, or how neatly it solves the
problem in front of you. The known failure mode is a month of debugging eight half-finished frontends.

## Rule 4 — Assembly runs on Windows

Jianying drafts embed absolute media paths. `pyJianYingDraft` runs on this workstation against local media,
never on the Spark. A draft generated with Linux paths is a broken deliverable.

## Rule 5 — Territory is a field, not a paragraph

Every shot carries `territory: cn | global | both`. Any engine with a territorial licence exclusion may
only render `cn` shots. The global master build must refuse to assemble if it contains one. Do not rely on
memory or good intentions for this.

## Rule 6 — Report, don't improvise

If you are blocked (missing credentials, unverifiable licence, failing build, ambiguous requirement),
report the blocker in one sentence with the smallest next action that would clear it. Do not silently
substitute models, sub-sample work, or "temporarily" write outside the folder.

---

## Repo map

```
manju/                 ← this repo (Windows)
├── AGENTS.md          ← this file: rules for every agent
├── STACK.md           ← what runs on which machine: tools, weights, pipeline
├── newsession1.md     ← live handover (state, decisions, gotchas)
├── HANDOVER.md        ← phase-by-phase history
├── nextblender.md     ← Blender / prop / set checklist
├── plan.md            ← the approved plan and stack decision
├── pipeline2-audit.md ← verdict on the "Pipeline 2.0 / 红果" proposal (14 Nov)
├── win/               ← every script that runs on Windows
│   └── tools/ffmpeg/  ← repo-local ffmpeg (%PATH% untouched; see win/get_ffmpeg.sh)
├── spark/             ← everything destined for ~/Desktop/AIGC-Model
│   ├── env.sh bin/ app/ models/ work/ provenance/ archive/ logs/
├── work/              ← sets, props, characters, keyframes, clips, voice
└── reference/         ← source research (the blueprint .docx) + legacy configs + licences
```

## Stack status

**Decided:** Z-Image Turbo/Base · MOSS-Image SFT · Wan 2.2 A14B + VACE · Wan2.2-Animate-2-14B ·
Kandinsky 6.0 Pro + VSR · Qwen3-TTS VoiceDesign→Base · InfiniteTalk/Wan2.2-S2V + LatentSync ·
AudioCraft · faster-whisper · Blender 5 ARM64 · ComfyUI · pyJianYingDraft (Windows) · in-house daemon.

**Not yet validated** (three assumptions that could force a substitution — see `plan.md` §2.3):
Kandinsky Pro weights are MIT · cu130 aarch64 wheels install in a venv · the FLUX $5M cap figure.

**Operator-gated boosters, not part of the build:** FLUX 3 Klein · MiniMax H3 · LTX-2.5.

## Commands

```
source env.sh          # mandatory before any Spark work — makes the folder hermetic
bin/up.sh              # start ComfyUI + daemon under tmux
bin/status.sh          # queue, GPU, memory, disk
bin/doctor.sh          # boundary leak check — must be clean before you report done
bin/restore.sh         # rebuild the folder from MANIFEST.json after a wipe
```
