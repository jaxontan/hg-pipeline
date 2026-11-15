# Stack — 《老汤》 short-drama pipeline

Two machines, one job. This file records what actually runs where, so nobody installs a 4 GB
model on the wrong box or expects a render to happen locally.

```
Windows workstation  ── authoring, orchestration, assembly ──┐
  C:\Users\admin\Desktop\manju                               │  repo, docs, .blend builders,
  Blender · Python · SSH driver · edited cut                  │  keyframe/clip drivers, assembly
                                                             │
                                                   SSH ──────┘  (paramiko, password from env)
                                                             │
DGX Spark (promaxgb10-a1b2)  ── inference only ──────────────┘
  ~/Desktop/AIGC-Model      models, ComfyUI, venv/, app/venv-tts/
  1.9 TB · 196 GB used · 1.6 TB free
```

**Rule 0:** nothing is written outside those two roots. Every Spark command is
`cd ~/Desktop/AIGC-Model && source env.sh >/dev/null && <cmd>`.

---

## 1. This machine (Windows) — verified 14 Nov

| Component | Version | Role |
|---|---|---|
| Windows + Git Bash | — | the shell every command in the docs assumes |
| Python | **3.12.10** | all of `win/*.py` |
| `paramiko` | **5.1.0** | the only third-party Python package this repo needs — SSH/SFTP driver |
| Blender | **5.2.3 LTS** (`C:\Program Files\Blender Foundation\Blender 5.2`) | sets, props, rigs, guides, keyframe sources |
| Node.js | 22.23.4 | present, not used by the pipeline |
| git | 2.56.0.windows.2 | present; the folder **is** a git repo since 14 Nov (initial commit = docs, `win/`, `spark/`, `reference/`, text assets; media and binaries gitignored) |
| `ffmpeg` | **N-128889** (13 Nov 2026), repo-local at `win/tools/ffmpeg` | Phase 5: cut, scale, burn captions + regulatory marks, mux. GPL build, so it carries libass and freetype — both are mandatory here |

**Deliberately not installed here:** no ComfyUI, no model weights, no `venv/`, no CUDA. This box
never runs inference. `numpy`, `pillow` and `requests` are absent too — local scripts use only the
standard library (`wave`, `json`, `hashlib`), which is why the voice measurement and the audition
concatenation run without a venv.

**On PATH or not:** `ffmpeg` is deliberately **not** on PATH. `win/assemble.py` calls the binary in
`win/tools/` by absolute path, so the version that made a master is the version recorded in that
master's report. Phase 5 no longer needs anything installed system-wide.

**Still missing: Jianying itself.** `pyJianYingDraft` 0.3.1 now lives in a repo-local venv,
`win/venv_jianying` (Python 3.12, gitignored) — created under a Rule 3 approval on 14 Nov, and the
draft in `work/laotang_ep01/jianying_drafts/` was generated with it. What is not installed is the
Jianying application, so the draft has **not** been opened in the app; `plan.md` §7.5 still asks the
operator to pin the Jianying version (≤5.8) first. The edit itself (dynamic 花字, per-line sound
design) remains the human pass.

---

## 2. Model stack (lives on the Spark, 51.52 GB declared / 37.34 GB downloaded)

Generated from `spark/models/MANIFEST.json`; each row carries a sha256, SPDX id and licence URL.
Licence gate is Rule 2: nothing is downloaded before its row exists.

| id | lane | size | licence | used by |
|---|---|---|---|---|
| `z_image_turbo_int8_convrot` | zimage-turbo | 6.20 GB | Apache-2.0 | keyframes |
| `qwen_3_4b_fp8_mixed` | zimage-turbo | 5.63 GB | Apache-2.0 | keyframes (text encoder) |
| `ae` | zimage-turbo | 0.34 GB | Apache-2.0 | keyframes (VAE) |
| `z_image_turbo_fun_controlnet_2_1_lite` | zimage-turbo | 2.02 GB | Apache-2.0 | keyframes, previz-control |
| `wan2.2_ti2v_5B_fp16` | wan-i2v | 10.00 GB | Apache-2.0 | clips |
| `wan_umt5_xxl_fp8_e4m3fn_scaled` | wan-i2v | 6.74 GB | Apache-2.0 | clips (text encoder) |
| `wan2.2_vae` | wan-i2v | 1.41 GB | Apache-2.0 | clips (VAE) |
| `qwen3_tts_voicedesign_1_7b` | tts | 4.52 GB | Apache-2.0 | voice |
| `qwen3_tts_base_1_7b` | tts | 4.54 GB | Apache-2.0 | voice-clone — **declared, not downloaded** |
| `latentsync_1_6` | lip-sync | 9.64 GB | OpenRAIL++ | lip-sync (ByteDance/LatentSync-1.6) — **declared, not downloaded** |
| `faster_whisper_small` | asr | 0.49 GB | MIT | subtitle, lip-sync, voice measurement |

Everything in the picture and voice lanes is Apache-2.0, so `territory: both` holds for every shot
in ep01 (Rule 5). `qwen3_tts_base_1_7b` is the only tool that would give 苏念 an actual speaker
identity — VoiceDesign derives the voice from prompt text and cannot hold one (see
`newsession1.md` §6.5.2).

**Python environments on the Spark, never mixed:**

| env | contents | why separate |
|---|---|---|
| `venv/` | ComfyUI: transformers 5.22.2, torch 2.14.1+cu130 | image/video lanes |
| `app/venv-tts/` | Python 3.12.3, torch 2.14.1+cu130, torchaudio 2.11.1+cu130, transformers **4.57.3**, qwen-tts 0.1.1, faster-whisper 1.2.1, ctranslate2 4.9.0, librosa, sox 1.5.0 (5.9 GB) | qwen-tts requires transformers 4.x, which ComfyUI's venv cannot be |

`torchaudio 2.11.1` against `torch 2.14.1` is the only build that exists; installed with `--no-deps`
from the test channel. Re-test `import torchaudio.compliance.kaldi` after any torch upgrade.

### 2.1 Software around the weights (not in `MANIFEST.json` — the gate only covers weights)

| Component | Version / form | Note |
|---|---|---|
| ComfyUI | `app/ComfyUI` @ **`b894a86`** | the engine for lanes 2–3 |
| cgroup cap | `COMFY_MEMORY_MAX=44G` via `systemd-run -p MemoryMax=` | a **policy we wrote**, not hardware. `versions.md`: raising it is a decision, not a tweak |
| SageAttention | compiled + proved 13 Nov | `--use-sage-attention` |
| gateway | `http://192.168.1.103:8000`, bearer `FREEFIELD_TOKEN` from `env.local` (mode 600) | the only entry point; Windows never holds the token on disk |
| `custom_nodes/ComfyUI-VideoHelperSuite` | installed | video I/O for the clip lane |
| `custom_nodes/comfyui-sameface` | installed, **untracked** | a real face-consistency route; needs licence + provenance review before anything load-bearing uses it |
| `ZImageTurnBuilder`, `ZImageTextEncoder` | **do not exist in this build** | checked 14 Nov with `grep -rlo`; the multi-turn “no-LoRA” scheme in the Pipeline 2.0 brief has no implementation here |

Z-Image support itself is native: `comfy/supported_models.py`, `comfy/model_base.py`,
`comfy/ldm/lumina/controlnet.py`, `comfy/latent_formats.py`.
`QwenImageDiffsynthControlnet` lives in `comfy_extras/nodes_model_patch.py`; `KSamplerAdvanced` in
`nodes.py` (which is what makes step-handoff possible).

---

## 3. Pipeline

| Phase | Where | Entry point | Output |
|---|---|---|---|
| 0. Sets & props | Windows (Blender, headless) | `win/blender_set_template.py`, `blender_set_huoguo.py`, `blender_set_houxiang.py`, `blender_props_laotang.py` | `.blend` + depth/normal/ctrl passes |
| 1. Guides | Windows | same builders (`SIGHTLINE`, `LINKCHECK`, `CHILDCHECK`, `DEPTHSTAT`) | per-rig guide PNGs |
| 2. Keyframes | Spark (zimage-turbo + ControlNet) | `win/submit_keyframe.py`, `win/batch_keyframes.py` | `*_manju_keyframe_NNNNN_.png` |
| 3. Clips | Spark (Wan 2.2 i2v) | `win/submit_clip.py`, `win/batch_clips.py` | `*_manju_clip_NNNNN_.mp4` |
| 4. Voice | Spark (`app/venv-tts`) | `win/tts_lines.py` → `spark/app/tts/render_lines.py`; measure with `measure_lines.py` | `work/<ep>/vo/*.wav` + `VO_MANIFEST.json` + `MEASURE.json` |
| 5. Assembly | Windows | `win/assemble.py` + `win/tools/ffmpeg`; EDL in `work/<ep>/edit.json` | `<ep>_conform.mp4`, `assemble_report.json` |

**Delivery requirements this pipeline is built to (Art.27, 令第16号, in force 2026-09-01).** A
sub-30万 AI episode is **三类**: the platform reviews it and issues the programme number, which must
appear in the 片头 together with the title, and AI-assisted episodes need a label in a prominent
position on every episode. `assemble.py` burns both and **refuses `--final` while
`compliance.program_number` is empty** — the number cannot be invented.

**Step-handoff is available but not default.** `win/submit_keyframe.py --handoff --handoff-split 4`
runs the control patch for steps 0–4 then the unpatched model for 4–8. Measured on `s004`: 7.3 s vs
10.4 s baseline, SSIM 0.894 against it. Off by default until it is tested on more than one shot.

Supporting tools, all in `win/`:

- `spark_ssh.py` / `spark_push.py` — the only way anything reaches the Spark; password from
  `SPARK_PASSWORD`, never stored.
- `mirror_provenance.py` — pulls provenance and re-pins `spark/provenance/MIRROR.json`; `--check`
  fails on drift. Run after every batch, then `bin/doctor.sh`.
- `blender_pose_s002c.py` / `blender_pose_s002d.py` — open a frozen set, pose/link/light, render
  passes, **never save** (assert the `.blend` sha256 is unchanged). This is how a shot gets a rig
  without a 13th camera in the canonical file.
- `validate_workflow.py` — schema check on the workflow JSON before it is submitted.

On the Spark, `bin/`: `restore.sh` (weights from the manifest), `doctor.sh` (boundary + provenance
coverage + mirror drift + manifest), `record-install.sh` (the only sanctioned install path),
`up.sh`/`down.sh`/`status.sh`.

---

## 4. Folder map

```
manju/
├─ AGENTS.md            rules (Rule 0 boundary … Rule 6 blockers) — the binding text
├─ STACK.md             this file
├─ newsession1.md       live handover: state, decisions, gotchas, recipes
├─ versions.md          version history, phase by phase (was HANDOVER.md)
├─ nextblender.md       the Blender/prop/set checklist
├─ plan.md              the original plan
├─ pipeline2-audit.md   what of the "Pipeline 2.0 / 红果" brief is true, false, or absent
├─ reference/           blueprint .docx + legacy/ (old Spark configs, kept for provenance)
├─ win/                 every script that runs on Windows (see §3)
│  └─ tools/ffmpeg/     repo-local ffmpeg — %PATH% untouched (win/get_ffmpeg.sh)
├─ spark/               the mirror of what must exist on the Spark: bin/, app/, models/MANIFEST.json,
│                       provenance/MIRROR.json, DELETE.md
└─ work/
   ├─ sets/            huoguo/ (12 rigs), houxiang/ (3 rigs), _template/
   ├─ props/           props_laotang.blend + turnaround sheets
   ├─ characters/      lead1 MPFB bust + bake
   ├─ story/           shotlist + vo_lines spec
   ├─ laotang_ep01/    keyframes, clips, boards, vo/, edit.json (the cut)
   │  └─ cut/          the delivery master + srt + assemble_report.json
   ├─ ep00_*/          deleted 15 Nov — early validation passes and the 14 Nov step-handoff
   │                   A/B pair. Their provenance records survive in spark/provenance/ep00_*/
   └─ .btmp/           sanctioned scratch: Blender user config/scripts lives here, plus
                       one-off helper scripts. Nothing outside the repo is written by a build.
```

**Canonical vs derived.** `work/**/*.png|mp4|wav` are assets — delete only with a decision, since
keyframes and clips are referenced by provenance. `.blend1` files, `__pycache__`, preview PNGs and
failed renders are derived and safe to remove; that is what the 14 Nov tidy did.

---

## 5. Known gaps on this machine

| Gap | Effect | Smallest fix |
|---|---|---|
| No Jianying (app) | the 10% human pass (花字, sound design) and opening the draft are impossible | install Jianying, pinned ≤ 5.8 (`plan.md` §7.5). `pyJianYingDraft` itself is **done** — `win/venv_jianying` + `win/build_jianying_draft.py` |
| Units longer than a clip | 3.92 s of the 90 s cut has no picture behind it (units 10, 17) | VACE continuation, or cut those two units. Units 2, 4, 12, 18 were re-timed on 14 Nov by moving one cut point each |
| No bed, no SFX | everywhere nobody speaks is digital silence (−91 dB) | needs a music/SFX pass; nothing in the repo supplies one |
| ~~No git repo~~ | **resolved 14 Nov** — `git init` + initial commit (93 files: docs, `win/`, `spark/`, `reference/`, text assets). Large media and ffmpeg binaries excluded via `.gitignore` | — |
| No director agent / no LLM anywhere | prompts, EDL and casting are hand-authored; nothing compiles a beat into a prompt pair | deliberate for ep01 (19 shots, one auteur). A shot compiler is the thing to build before an agent |
| 苏念 identity | VoiceDesign has no speaker state; vo01/vo03 differ by 37 Hz | `bin/restore.sh qwen3_tts_base_1_7b` (4.54 GB) and clone from vo01 |
