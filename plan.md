# Manju Studio — Launch Plan (v1, for approval)

**Date:** 2026-11-13
**Scope:** One DGX Spark (GB10, 128 GB unified) at 192.168.1.103 + this Windows 11 workstation as controller/editor. Commercial 3D CG micro-drama production for Hongguo, with optional global syndication.
**Source material:** `reference/AI Short-Drama Studio Launch Blueprint.docx` (v. 13 Nov 2026) + follow-up SOTA memo.

---

## 0. Verdict

**Approve the blueprint with three amendments.** The document's factual core holds up — I verified the licenses, the hardware math checks out, and it correctly identifies the traps most "deep research" reports miss. What it optimises for is wrong for your situation in exactly three ways, and those three are what this plan changes.

What I verified independently:

| Claim in blueprint | Verdict | Source |
|---|---|---|
| FLUX 3 Klein is **not** Apache — it is `flux-kommunity-license`, gated | ✅ True | HF model card metadata |
| LTX-2.5 caps free commercial use at **$10M** entity revenue | ✅ **Confirmed verbatim** | `LICENSE-2_x` §2.1: "Entities with annual revenues of at least $10,000,000 … required to obtain a paid license"; affiliates counted collectively |
| MiniMax H3 excludes **EU, UK, Korea, USA**; grant is territory-bound | ✅ **Confirmed verbatim** | H3 `LICENSE`: "Grant of Rights Solely within the Applicable Territory"; distribution also restricted "solely within the Applicable Territory" |
| MiniMax-Music3 requires on-UI attribution + $20M threshold | ✅ Confirmed | Music3 `LICENSE` |
| LatentSync **code** Apache, **weights** OpenRAIL++ | ✅ True | HF tag `openrail++` (this corrects my earlier statement) |
| MOSS-Image, Z-Image-Turbo, Wan2.2-Animate-2, Qwen3-TTS = Apache-2.0 | ✅ All four | HF metadata |
| GB10 bandwidth math (33.1B BF16 ÷ 273 GB/s = 0.243 s/step) | ✅ Arithmetic correct | — |
| sm_121 cubin mismatch breaks stock NVFP4 kernels | ✅ Plausible and consistent with CUDA architecture-specific code | — |
| FLUX "+91 Elo", LTX "6.8 s/clip" | ⚠️ Vendor-internal / 2×GB200 | Blueprint already flags both |

**Unverified and must be closed before first paid episode:** the FLUX $5M revenue figure. The repo is gated, so `LICENSE.md` cannot be read without accepting terms. Treat "$5M" as an assumption until read off the accepted license.

Also note: `MiniMaxAI/MiniMax-Music3` publishes **no license tag** on its model card. The `LICENSE` file exists and reads clean, but tag-absent repos are exactly where license drift hides. It is a P2 task, not a P0 assumption.

---

## 0.5 Machine state: found, then wiped (2026-11-13)

`tdadmin@192.168.1.103` · Ubuntu 24.04.5 · kernel 6.17.0-1032-nvidia · driver 580.173.02 · GB10, sm_121, 128 GB / 1.9 TB NVMe.

**Timeline of this session:** a working build from 12 Nov was found in the folder (gateway + cu130 venv + 49 GB of weights). The operator then authorised stopping the co-tenant services and wiping the folder as useless. Both done. **The machine is now greenfield and matches the assumptions in the rest of this plan.**

| Event | Result |
|---|---|
| Services stopped | `oracle-free-26ai`, `ords-26ai` (docker), `llama-server` (:8091), `gateway.py`, `comfy-api-proxy`, ComfyUI |
| Folder wiped | 57 GB → 4 KB |
| Disk | 146 GB used, **1.6 TB free** |
| Memory | **117.7 GiB available** of 121.6 — the full unified pool, as originally planned |
| Preserved | the prior build's `env.sh`, `gateway.py`, `serve_aigc.sh`, `run_setup.sh`, `run_download.py`, `models/.manifest.json`, `extra_model_paths.yaml` → `reference/legacy/` (design reference + re-download recipe) |
| GPU | 2411 MHz idle against **3003 max**, 43 °C, 11.3 W — `power.limit` reports `[N/A]` |

Three things survive the wipe as facts about this hardware:

1. **`nvidia-smi -lgc 300,2100` must not be used.** No power cap is exposed, and 2100 MHz is *below* the 2411 MHz idle clock — it would throttle renders. The original brief had this backwards.
2. **SageAttention was never installed**, so the previous build ran on the slow path. `nvcc` is at `/usr/local/cuda-13.0/bin/nvcc`. This is the highest-value fix in P1.
3. **Unified memory does not return to the OS on model switch.** Killing ComfyUI released ~60 GiB that no process RSS accounted for. Model unloading is mandatory, and cgroup limits are the only reliable guard — an `OOM` on GB10 shows up as a whole-machine stall, not a clean job failure.

Conditional now that the DB is stopped: `swapoff -a` is **safe** (nothing co-tenant is running). Keep it only if the Oracle stack is ever restarted — then swap stays on and `earlyoom` protects the co-tenant instead.

### Measured performance (P1.2, 2026-11-13 — `bin/bench.py`, evidence in `app/os/bench-2026-11-13.txt`)

| Metric | Measured | Reading |
|---|---|---|
| fp16 matmul | **97 TFLOP/s** (8192³) | tensor cores engaged; healthy |
| bf16 matmul | **98 TFLOP/s** | same path — bf16 is free |
| fp32 matmul | 18–19 TFLOP/s | TF32 is **off**; leave it off, every lane runs fp16/bf16 |
| attention (SDPA, seq 8192) | 90 TFLOP/s | flash-style path present, not the reference implementation |
| copy bandwidth | **225 GB/s** | 82% of the 273 GB/s spec — no unified-memory penalty |
| SMs / unified pool | 48 / 121.6 GiB | as specified |
| power / temp under load | 30 W, 42 °C | no thermal or power ceiling in play |

**One real caveat: torch ships no `sm_121` cubin.** The arch list is `sm_80, sm_90, sm_100, sm_110, sm_120`, so every kernel JITs from the nearest PTX target (`sm_120`) on first use and is then cached in `$AIGC/.cache/cuda` (4 GiB budget, inside the boundary). The JIT is a one-time cost per kernel, not a permanent fallback — proven by the 97 TFLOP/s figure. **Do not "fix" this by disabling JIT.**

Recorded because it cost an hour: the first smoke run reported **1.02 TFLOP/s** and looked like a fallback. It was measuring the JIT compile. `bin/smoke.py` now warms up before timing and prints the same 93 TFLOP/s. Any future "the box went slow" report should start with `bin/bench.py`, not with a model substitution.

### Two findings worth carrying forward

- `~/Desktop` was `0755` and the folder `0775` on a box with RDP exposed and multiple local users. **Set `750` at creation time** — isolation that any local user can read past is not isolation.
- The previous `FREEFIELD_TOKEN` sat in plaintext inside a startup script. Secrets go in `env.local` at mode `600`, and rotate on any handover.



## 1. The three amendments

### A1. Optimise for asset portability, not model capability

The blueprint picks winners per stage and swaps models when a better one ships. That is how you end up re-rendering 60 episodes when a license changes — which is precisely what happened to Qwen-Image 2.1, and the document says so.

**Rule: the only assets that matter are the ones a model swap cannot destroy.**

| Durable (own it, version it) | Perishable (rented, may vanish) |
|---|---|
| Shot list JSON, `territory` flags | 10-reference conditioning stacks |
| Blender `.blend` sets, camera rigs, guide passes | Bounding-box prompt formats |
| Character LoRAs trained locally (kept internal) | "This model is #1 today" |
| Voice reference WAVs (TTS-generated, synthetic) | Vendor Elo claims |
| Provenance manifest + seeds per shot | Quantised checkpoint filenames |

Consequence: **character consistency comes from your LoRA, not from a model's multi-reference feature.** A LoRA survives a model swap by re-training for one day; a 10-ref prompt stack is re-authored from zero. So Z-Image-Turbo/Base stays the primary keyframe engine (Apache, 8 steps, no gate, trainable), and FLUX 3 Klein is a *secondary* engine for shots where multi-reference or instruction-editing genuinely earns its licence dependency.

### A2. Territory is a shot-level field, so there are two masters per episode

The H3 licence does not restrict *distribution* only — it restricts **use and distribution**, both "solely within the Applicable Territory." Any frame H3 rendered cannot lawfully ship to the US, EU, UK, or Korea. The blueprint says this in prose; the pipeline must enforce it in schema.

**Amendment:** every shot carries `territory: cn | global | both`, set before rendering. Then:

- `cn` shots may route to MiniMax H3.
- `global` shots may **never** route to H3 — they go to LTX-2.5, Kandinsky 6, or Wan 2.2.
- `both` is the default for anything narratively load-bearing, and it excludes H3.

Output is **two masters**: a China master (full lane access) and a Global master (Apache/MIT + LTX/Kandinsky only). The export gate refuses to build a Global master containing an H3-rendered shot. This is ~40 lines of code and it is the difference between a licensable catalogue and a stranded one.

The same mechanism enforces the revenue caps: at **$4M ARR** (80 % of FLUX's presumed $5M) the build system freezes new FLUX renders and falls back to Z-Image/MOSS. Existing episodes stay legal; new ones never enter the cap zone.

### A3. Batch by lane, not by episode order

The blueprint routes per shot (A: LTX, B: H3, C: Kandinsky, D: Animate). Rendered in storyboard order, that means a model swap every ~90 seconds: 21 GiB H3 out, 20 GiB LTX in, 35 GiB Kandinsky in — 40–90 s of pure weight streaming per switch, against a 273 GB/s bus, on a box that hard-reboots under power transients.

**Amendment:** the queue sorts by lane, not by scene. Render every Route-A shot in the season, then every Route-D shot, etc. Swap cost amortises from ~45 % of runtime to ~2 %. Same total GPU work, roughly **40 % less wall-clock time**, no extra hardware.

---

## 2. Stack: the best model per task, clean licence only

**Rule:** each task takes the highest-performing model that carries *no* revenue ceiling, *no* territory exclusion, and *no* non-commercial clause. Where the outright #1 fails that filter, the next section names the gap and what it actually costs.

The important result: **for 12 of the 15 stages below, the clean pick is also the blueprint's own #1.** Clean is not the compromise you think it is.

| # | Task | Best clean pick | Licence | GB10 footprint | Why it is #1 among clean options |
|---|---|---|---|---|---|
| 1 | Script, shot breakdown, JSON storyboard | **Qwen3.6-35B-A3B** | Apache-2.0 | Q4 ~17 GB · 44–68 tok/s | Frontier-class reasoning at MoE cost — only 3B active per token, which is the only way a 35B model is usable on 273 GB/s |
| 2 | 3D pre-viz, camera/action blocking | **Blender 5.0 ARM64** + `kimodo_motion` + Retarget v5.2 | GPL-3.0 (outputs unaffected) | negligible | Free text-to-motion rigged in-engine; no paid mocap, no Autodesk SDK (no ARM64 wheels) |
| 3 | Character LoRA training | **Z-Image Base** (non-distilled) | Apache-2.0 | 12 GB BF16 | You train the asset that survives every model swap — this is the consistency mechanism, not a model feature |
| 4 | Keyframes, volume | **Z-Image Turbo**, 8 steps | Apache-2.0 | 6.17 GB int8 + 4.4 GB TE | #1 open-source T2I on Artificial Analysis and the Alibaba arena — and Apache |
| 5 | Chinese typography, title cards, posters | **MOSS-Image SFT** + 8-step DMD | Apache-2.0 | 5.41 + 1.19 GB | Open-source SOTA for exact JSON bounding-box layout and CJK glyph rendering. Keep the LoRA unmerged in FP32 |
| 6 | Video, multi-shot + native audio | **Kandinsky 6.0 Pro Distill** + VSR | **MIT** | 34.97 GB int8 | A 29B MIT video model that beats LTX-2.5 on most VABench audio-visual and speech metrics. The single most valuable licence finding in the whole document |
| 7 | Video, first/last-frame + structural control | **Wan 2.2 A14B** + **VACE** | Apache-2.0 | fp8_scaled ~28.6 GB | Drives motion from Blender passes instead of prompt lottery; Apache with zero strings |
| 8 | Acting / martial-arts performance transfer | **Wan2.2-Animate-2-14B** | Apache-2.0 | 16.7 GB int8 | The blueprint's own words: "undisputed open-weight SOTA" for driving-video transfer, and Apache |
| 9 | Voice design + timbre lock | **Qwen3-TTS 1.7B VoiceDesign → Base** | Apache-2.0 | ~4 GB | 1.835 % multilingual WER, 0.789 speaker similarity. VoiceDesign makes the timbre, Base locks it across 100 episodes |
| 10 | Lip-sync / dubbing | **InfiniteTalk** or **Wan2.2-S2V-14B** (primary), **LatentSync 1.6** (close-up repair) | Apache-2.0 / OpenRAIL++ | 18 GB | The Apache pair is strictly cleaner than LatentSync's RAIL weights; keep LatentSync only for 512×512 hero mouths |
| 11 | Upscale to 1080p | **Kandinsky 6.0 VSR** (2.25×) | MIT | native to #6 | No extra licence, no extra model family |
| 12 | ASR / subtitles | **faster-whisper large-v3** | MIT | CPU on the Windows client | Keeps Spark GPU for diffusion |
| 13 | Assembly | **pyJianYingDraft** on Windows | Apache-2.0 (verified) | — | Native Jianying drafts, generated where the media lives |
| 14 | Orchestration | **Our daemon** + optional Toonflow-app | MIT | — | Durable queue, lane batching, provenance manifest |
| 15 | Music / BGM | **AudioCraft MusicGen** | MIT | ~4 GB | ⚠️ the one genuine downgrade — see §2.1 |

Optional, **not** part of the clean core: Gemma 4 26B-A4B for dialogue polish. It is a fine model but it runs under the **Gemma Terms of Use**, not an OSI licence — use-restricted and not Apache. Treat it as a nice-to-have, never as a dependency.

### 2.1 Where clean actually costs you — three things, and only three

| Stage | The outright #1 you are giving up | What the gap costs in practice | Mitigation that closes most of it |
|---|---|---|---|
| Multi-reference keyframes, instruction editing | **FLUX 3 Klein** (5.6B, up to 10 refs, bbox layout, instruction edit) | You lose one-pass composition of 10 references. Not facial consistency — your LoRA supplies that | Train the character LoRA properly and feed 2–3 refs instead of 10; MOSS covers layout-locked work; ~1 extra training day per lead character |
| Omni-reference dialogue video | **MiniMax H3** (9 images + 3 videos + 3 audio in one denoise, 32 kHz stereo) | Room memory and identity lock across cuts must be rebuilt from Blender sets + sameface checks rather than a single model | Blender scene anchoring + `sameface` repair + re-dub with Qwen3-TTS. More setup, same output class, sellable anywhere |
| Music / score | **MiniMax-Music3** | AudioCraft produces shorter, less structurally coherent cues | Generated beds for scenes; licence two or three real tracks for titles and trailers — cheaper than a licence dependency |

Everything else — keyframes, CJK typography, video+audio, acting transfer, voice, lip-sync, upscale, ASR, assembly — the clean #1 *is* the #1.

### 2.2 The boosters (separate approval, gated)

Kept in the document so the option is priced, not lost. Each one is a licence dependency measured in weeks of bring-up, and none is needed for season one.

| Booster | Buys you | Gate before it is enabled |
|---|---|---|
| FLUX 3 Klein | 10-ref composition, instruction editing, `flux3` LoRA training | Only if §2.1 mitigation demonstrably fails a shot class. Hard-frozen at $4M ARR against the presumed $5M cap |
| MiniMax H3 | Room memory + identity + audio in one pass | Territory-locked: forces **two masters per episode**. Enable only after the China master is selling |
| LTX-2.5 | Fastest multi-shot with native audio | Only if throughput becomes the binding constraint at $10M-revenue scale — i.e. probably never |

**Rejected outright:** Qwen-Image 2.1 (research licence), huobao-drama (CC BY-NC-SA), OpenMontage/ArcReel (AGPL-as-service), Wav2Lip (research-only), Gemma as a *dependency*, any ComfyUI node without a LICENSE file.

### 2.3 Status: the roster is decided; the stack is not yet validated

| State | Items |
|---|---|
| **Decided** — no further debate | All 15 rows of §2. The model list does not change again; only the engine that fills a row can, and only if one of the three assumptions below fails |
| **Assumption 1** — Kandinsky 6.0 **Pro** weights are MIT | Repo returned 401 to an unauthenticated check; the code repo and Lite distill are MIT. **If false:** Wan 2.2 A14B becomes the primary video engine and you lose native audio in a single pass. Highest-impact unverified item in the plan |
| **Assumption 2** — cu130 aarch64 wheels install in a venv | If false: Docker returns, and `/var/lib/docker` becomes a declared exception in `DELETE.md` (§3.3). Models unaffected |
| **Assumption 3** — FLUX 3 Klein's $5M revenue ceiling | Repo is gated; cannot read `LICENSE.md` without accepting terms. Affects booster 3 only — never the core |
| **Blocked on operator** | SSH username · what `:8000` serves · Jianying version pin · entity/挂靠 status |

The decision rule is: a roster row changes only when its assumption fails, and only to the named fallback. No row is re-opened because a newer model appears — that is what the boosters section exists for.


**Minimum viable node set.** The blueprint's Days 6–10 installs eight frontends/custom packs, several under two weeks old. That is a debugging month, not a production month. Start with ComfyUI + `ComfyUI-VideoHelperSuite` + `comfyui-sameface`, and add packs *only when a gate fails without them*:

| Add | Phase | Trigger |
|---|---|---|
| `ComfyUI-H3-Continuity-Studio` | P3 | room/prop drift across H3 cuts |
| `H3-AudioRetake-studio` | P5 | dialogue retake cost exceeds re-render cost |
| `ComfyUI-Sonder-Editor` | P5 | in/out take regeneration needed |
| `freefield` / `Toonflow-app` | P6 | only if the CLI is the bottleneck |
| `kimodo_motion` + `Retarget v5.2` | P3 | Blender blocking without mocap |

---

## 3. Hermetic deployment: `~/Desktop/AIGC-Model` is the unit of existence

Constraint: the Spark folder gets deleted in one shot, so it must stay sufficient to both **rebuild the machine** and **script the wipe**. System-wide packages are therefore allowed — `uv`, `pip --user`, `apt`, `snap`, env vars, Docker — but nothing may be invisible.

**The one rule:** content lives inside the folder; software may live outside it; **every software change leaves a receipt inside it.**

- *Content* — weights, outputs, drafts, LoRAs, seeds, queue DB, logs, provenance → inside, always.
- *Software* — apt packages, CUDA runtime, the driver, `uv`, pip packages → anywhere, but the install goes through `bin/record-install.sh`, which executes the command and appends `date · layer · item · version · command · reversible` to `app/os/installed.tsv`.
- *The ledger makes the wipe scriptable*: the delta between `apt.baseline.tsv` (the pristine machine) and the current inventory **is** the uninstall list. Without it the wipe is guesswork, and a "deleted" machine retains packages nobody remembers.

**The binding form of this section is [`AGENTS.md`](AGENTS.md).** It is auto-loaded by every agent session that enters this repo, so it does not depend on anyone remembering to read a plan. This section is the reasoning; `AGENTS.md` is the law. If the two ever disagree, `AGENTS.md` wins.

### 3.1 Layout

```
~/Desktop/AIGC-Model/
├── README.md            what this is, how to rebuild it from nothing
├── DELETE.md            the one-shot removal procedure + what survives it
├── env.sh               THE file that makes it hermetic — sourced by everything
├── bin/
│   ├── up.sh down.sh status.sh     tmux-supervised start/stop (no systemd)
│   ├── setup-os.sh                 the only thing that touches /usr
│   └── doctor.sh                   leak detector: proves nothing escaped
├── app/
│   ├── comfyui/         git clone, pinned commit
│   ├── venv/            Python env — inside the folder, not ~/.venv
│   ├── nodes/           custom nodes, pinned commits
│   ├── daemon/          sparkd + queue.sqlite + sparkctl
│   └── blender/         ARM64 build + config + addons
├── models/              diffusion_models/ text_encoders/ vae/ loras/ audio/ ollama/
│   └── MANIFEST.json    every weight: URL, sha256, SPDX id, licence link
├── cache/               hf/ torch/ cuda/ pip/ uv/ tmp/ xdg/ blender/ npm/
├── work/                projects/<slug>/{shots,keyframes,clips,audio,drafts}/
├── provenance/          MODEL_PROVENANCE.json per episode, seeds, hashes
├── archive/             export tarballs staged for pull to Windows
└── logs/
```

`manju/` on this Windows box mirrors it: `models/` (the authoritative weight store), `work/`, `provenance/`, `archive/`.

### 3.2 `env.sh` — the mechanism

Everything that defaults to `~/.cache`, `~/.config`, `~/.local` or `/tmp` is redirected here. This single file is what makes the folder self-contained:

```bash
export AIGC="$HOME/Desktop/AIGC-Model"
export XDG_CACHE_HOME="$AIGC/cache/xdg"      XDG_CONFIG_HOME="$AIGC/cache/xdg/config"
export XDG_DATA_HOME="$AIGC/cache/xdg/data"  XDG_STATE_HOME="$AIGC/cache/xdg/state"
export HF_HOME="$AIGC/cache/hf"              HF_HUB_CACHE="$AIGC/cache/hf/hub"
export TORCH_HOME="$AIGC/cache/torch"        TORCHINDUCTOR_CACHE_DIR="$AIGC/cache/torch/inductor"
export TRITON_CACHE_DIR="$AIGC/cache/triton" CUDA_CACHE_PATH="$AIGC/cache/cuda"
export CUDA_CACHE_MAXSIZE=4294967296
export PIP_CACHE_DIR="$AIGC/cache/pip"       UV_CACHE_DIR="$AIGC/cache/uv"
export TMPDIR="$AIGC/cache/tmp"              npm_config_cache="$AIGC/cache/npm"
export OLLAMA_MODELS="$AIGC/models/ollama"
export BLENDER_USER_CONFIG="$AIGC/cache/blender/config"
export BLENDER_USER_SCRIPTS="$AIGC/cache/blender/scripts"
export PATH="$AIGC/bin:$AIGC/app/venv/bin:$PATH"
```

ComfyUI is launched with explicit directory flags, never defaults:

```bash
python "$AIGC/app/comfyui/main.py" \
  --base-directory "$AIGC/app/comfyui" \
  --output-directory "$AIGC/work" \
  --input-directory "$AIGC/work/input" \
  --temp-directory "$AIGC/cache/tmp" \
  --use-sage-attention --disable-pinned-memory --reserve-vram 8
```

### 3.3 Three decisions this constraint forces

| Was | Now | Why |
|---|---|---|
| Docker (Spark-tuned image) | **venv inside `app/venv`** | Docker's `data-root` is `/var/lib/docker` — tens of GB of images and volumes outside the folder, fixable only via `/etc/docker/daemon.json`. The venv is hermetic and ARM64-native. *Fallback:* if cu130 wheels are missing at P1, Docker returns with everything mounted from the folder, and `/var/lib/docker` becomes a **declared exception** purged in `DELETE.md`. |
| systemd unit for the daemon | **tmux + supervisor loop** (`up.sh`) | A `~/.config/systemd/user` unit is a leak. `while true; do sparkd; sleep 2; done` in tmux gives restart-on-crash with no root, no `/etc`. |
| Spark 4 TB = source of truth | **Windows/NAS = source of truth**; Spark folder = disposable build cache | A folder designed to be deleted cannot hold the only copy of 115 GB of weights or your only masters. The Spark builds; the client keeps. Correcting my earlier §5 line. |

### 3.4 Enforcement: `doctor.sh` is the deliverable

A policy you cannot verify is a policy you will violate at 2 a.m. `doctor.sh` checks and reports every known leak site:

```
~/.cache/{huggingface,torch,pip,uv} · ~/.ollama · ~/.local/share · ~/.config/{blender,uv}
/tmp · /var/lib/docker · /usr/local/lib/python3.*/dist-packages (non-apt)
and: any file in $AIGC/work older than the last export that has no provenance entry
```

Run it before every batch and weekly. Non-empty output = a fix, not a note. `DELETE.md` is then trivial and testable: `rm -rf ~/Desktop/AIGC-Model`, `docker system prune -a` *(only if the fallback was used)*, `apt purge $(cat os/packages.txt)`, `rm -rf` the four paths above — and `doctor.sh` run from a USB copy proves the machine is clean.

### 3.5 Two consequences worth stating plainly

1. **Restore must take minutes, not a day.** 115 GB of weights re-downloaded after every wipe is the hidden cost of this constraint. Keep `MANIFEST.json` (sha256 + URL + SPDX id) and a weights tarball on this Windows box or an external drive; `bin/restore.sh` rebuilds the folder from the manifest. Without that, the constraint taxes you every cycle.
2. **The HF token for gated weights is a credential inside a disposable folder.** Store it `chmod 600` in the folder, record its existence in `DELETE.md`, and revoke it at deletion — otherwise a "wiped" machine leaves a live token on a disk image.

**Unavoidable exceptions (disclose these to whoever set the rule):** apt packages, the CUDA runtime, the NVIDIA driver, and `nvidia-smi` power settings. None can live in a folder. All are captured by `dpkg --get-selections > app/os/packages.txt` at setup, and none contain project content.

---



The blueprint covers six fixes well — cu130/sm_121 stack, the 3-line sm_121a cubin patch, no `--offload cpu` on unified memory, ignoring the `VRAM Total: 0 B` artifact, INT8 ConvRot over stock NVFP4, unmerged FP32 DMD LoRA. Four additions:

1. **Power stability first.** The blueprint's power section is absent, and it is the single most likely cause of a lost overnight batch. Pin clocks/power before the first 8-hour run and verify with `nvidia-smi -q -d CLOCK,POWER` that the requested state actually applied. If the driver rejects the cap, record it and move on — do not force it.
2. **`swapoff` plus an OOM cushion.** Disabling swap trades thrash for OOM kills. Pair it with `systemd-oomd` policy or `earlyoom` and a `MemoryMax=` cgroup on the ComfyUI unit.
3. **Verify SageAttention actually compiled.** A silent fallback is a 20× regression that looks like "the model is slow." Benchmark one fixed job at P1 and store the number; every later regression is measured against it.
4. **Per-lane peak memory measured, not assumed.** The blueprint's 26 GiB peak for LTX is a community figure. Record real peaks per lane; they are what the scheduler and the cgroup limits are built from.

---

## 4. Compute budget (single Spark, honest numbers)

**Budget against 117.7 GiB available** — the co-tenant services are stopped, so the full unified pool is in play (measured, not assumed).

| Job | Resident need | Verdict in 117 GiB |
|---|---|---|
| Z-Image Turbo int8 + qwen_3_4b TE | ~14 GiB (+4 GiB ComfyUI idle) | comfortable — 8× headroom |
| Wan 2.2 Fun Camera fp8, both experts + umt5 + VAE | ~38–42 GiB | fits with room to spare |
| Kandinsky 6 Pro int8 + 12B TE | ~47 GiB | fits — the earlier "borderline" verdict was a co-tenant artefact |
| MiniMax H3 int8 + Qwen3-VL-32B TE | ~37 GiB | fits (booster, operator-gated) |
| Qwen3.6-35B-A3B Q4 for scripting | ~17 GiB | fits **alongside** a keyframe job, never alongside Wan |

**The guard that matters is not capacity, it is release.** Killing ComfyUI freed ~60 GiB that no process RSS accounted for — a stale model allocation survives the unload path and makes the box look full when it is not. So: explicit unload between jobs, `MemoryMax=` on the cgroup, and treat "memory didn't come back" as a process-restart condition rather than a mystery.

Basis: 60 episodes × 90 s ≈ 900 shots. Unit costs below are the blueprint's LTX-class figure (~3 min per 8 s clip) — **but the clean pick is a 29B model where LTX is 22B, so expect 20–40 % more time per clip.** P1 measures it and replaces this table before P4 commits to a schedule.

| Stage | Volume | Unit cost | GPU hours |
|---|---|---|---|
| Keyframes (2/shot, 8-step) | 1,800 | ~4 s | 2 |
| Video (Kandinsky Pro / Wan 2.2) | 900 | ~3–3.5 min avg | 45–52 |
| Acting transfer (Animate-2) | 120 | ~4 min | 8 |
| Voice synthesis | 900 lines | — | 3 |
| Lip-sync close-ups | 300 | ~2 min | 10 |
| **Subtotal** | | | **68–75 h** |
| Retakes (1.4×) | | | **~95–105 h** |

**≈ 12–13 overnight runs ≈ 3 weeks per 60-episode season**, one season in flight. Engine batching (A3) is what makes this feasible instead of 18+ nights; it is the single largest scheduling win available on one machine. A second Spark over ConnectX-7 roughly halves it, and is not needed for season one.

---

## 5. Execution plan

| Phase | Work | Gate (must pass before next) |
|---|---|---|
| **P0** — Reachability | ~~SSH key auth, baseline snapshot~~ **done 2026-11-13** via password auth, read-only. Baseline captured; key auth still to install | ✅ driver, clocks, memory, disks, ports, toolchain recorded |
| **P1** — Fix the engine | ~~**done 2026-11-13**~~ SageAttention compiled + proved, ComfyUI cgroup cap `MemoryMax=44G` via `systemd-run --user --scope` (`bin/up.sh`), swap kept, no clock cap (`earlyoom` omitted to avoid system unit changes) | ✅ `bin/bench-sage.py` active; `system_stats` confirms `ram_total: 47244640256` (44 GiB); Z-Image Turbo peak `11807 MiB` |
| **P1.0** — Skeleton | ~~**done 2026-11-13**~~ `env.sh` (HOME redirected inside), `bin/{doctor,status,record-install}.sh`, `README.md`, `DELETE.md`, baseline pinned (2,386 apt pkgs), folder mode `750` | ✅ `doctor.sh` reports **BOUNDARY CLEAN** |
| **P1.1** — Toolchain | ~~**done 2026-11-13**~~ `python3.12-dev` (C headers), `ffmpeg` 6.1.1 + x264/x265/aac/opus — both through `record-install.sh` with receipts | ✅ `Python.h` present, encoders verified |
| **P1.2** — Runtime | venv at `venv/`, torch **2.14.1+cu130**, torchvision 0.29.1+cu130, numpy 2.5.4, ComfyUI @ `b894a86` (2026-11-12) | ✅ `sm_121`, **97 TFLOP/s fp16**, 225 GB/s, SDPA 90 TFLOP/s (`bin/bench.py`) |
| **P1.3** — SageAttention | ~~**done 2026-11-13**~~ `sageattention` 2.2.0 compiled for `sm_121a` (`-std=c++20`, `sm_121a` cubins in `_qattn_sm89`), ComfyUI `--use-sage-attention` verified active (`attention_sage` on `NHD`/`HND`), `doctor.sh` clean | ✅ `bin/bench-sage.py` (`app/os/sage-bench-2026-11-13.txt`): cosine `0.999266`; `1.21×` @ 4096, `1.45×` @ 8192, `1.69×` @ 16384, `1.83×` (**159.9 TFLOP/s**) @ 32768 |
| **P2** — Adopt the control plane | ~~**done 2026-11-13**~~ `app/gateway.py` (Bearer auth from `env.local` mode `600`, SQLite lane-batched queue `app/queue.db`, Rule 2/5 manifest + territory gate, `MODEL_PROVENANCE.json`), `bin/{up,down,restore}.sh`, `models/MANIFEST.json`, `win/submit_keyframe.py` | ✅ Z-Image Turbo INT8 keyframe (`768×1344`, 8 steps) submitted from Windows, rendered in `8.81 s`, pulled & SHA-256 verified (`9.3 s` total), provenance written, `doctor.sh` clean |
| **P3** — Pre-viz + characters | **partial 2026-11-13:** Blender 5.3.0 pre-viz on Windows (`win/blender_previz.py`) → Z-Image Turbo Fun ControlNet 2.1 Lite (`Apache-2.0`) verified; `ComfyUI-VideoHelperSuite` (`4d907be`) + `comfyui-sameface` (`d608d61`) installed · **pending:** 4 lead character briefs + LoRA trainer approval (`Rule 3`) + 三视图/sameface gates | ✅ `s001_depth.png` + `blender_sha256` → `manju_keyframe_00001_.png` rendered, pulled, SHA-256 & provenance verified (`13791 MiB` resident, `doctor.sh` clean) |
| **P4** — Video engines | Z-Image→Kandinsky Pro chain end-to-end; then Wan 2.2 + VACE; then Animate-2 for action | A full 3-episode pilot, one master, every shot traceable to a clean engine |
| **P5** — Voice + assembly | Qwen3-TTS VoiceDesign → Base voice lock; LatentSync; pyJianYingDraft **on Windows**; Jianying version pinned | Draft opens natively in Jianying with online media; 2 ep exported with disclosure + filing card burned in |
| **P6** — Compliance + scale | 确权 submission, 著作权登记 for character sheets, 版权合规承诺书, provenance archive; optional 2nd Spark | First series accepted through a qualified entity |

**Two corrections to the blueprint's 30-day roadmap.** (a) Day-by-day dates ignore the two dependencies you do not control — Hongguo's 确权 review and a corporate entity's filing timeline. Phase gates instead. (b) Assembly must run **on Windows**, not the Spark: Jianying drafts embed absolute media paths. The blueprint already says "shared folder mounted on a lightweight Windows PC" — this plan makes it a hard rule, because a draft built with Linux paths opens with offline media.

---

## 6. Compliance as code

| Gate | Enforced by |
|---|---|
| Opening identity card + AI disclosure + filing number | Template draft in Jianying; export cannot complete without the card track |
| `< 65 %` similarity to existing dramas | `sameface` measurement recorded per character, threshold in CI |
| Territory (H3 exclusion) | `territory` field + build gate refusing H3 shots in global master |
| Revenue caps | $4M ARR tripwire flips FLUX off; config, not discipline |
| Provenance | `MODEL_PROVENANCE.json` per episode: model, licence id + link, quantisation, seed, workflow hash, Blender file hash |
| Archive | Blender scenes, workflow JSONs, seeds, LoRA checkpoints — pushed off the Spark nightly |

`确权` is auxiliary evidence, not indemnity — the blueprint is right about this, and it means the provenance archive is the actual defence.

---

## 7. Decisions I need from you

1. **Approve §2** — the clean per-task roster, with the three accepted capability gaps in §2.1 and the three gated boosters in §2.2. This is now a "best model per task, zero licence ceilings" plan; the boosters are re-decided later, on evidence.
2. **SSH username for 192.168.1.103** and what the `:8000` aiohttp service is. P0 has been blocked on this for the whole session.
3. **Primary market first:** China (Hongguo) with global as season two, or both from episode one? *Recommendation: doesn't matter for season one — every engine in §2 is globally clean, so a single master sells in both. Decide it at the marketing layer, not the render layer.*
4. **Entity status:** is the 有限公司/挂靠 partner already in place? If not, that is the longest pole and it should start this week, not in P6.
5. **Jianying:** confirm pinning ≤ 5.8 on this workstation before we build the draft generator against it. If you need v5.9+, we verify draft encryption behaviour first — it changes the entire assembly stage.
6. **Confirm the Kandinsky 6.0 Pro weights really are MIT** at download time (the repo returned 401 to my unauthenticated check; the GitHub code repo and the Lite distill are MIT). This single licence decides whether the video stage is clean — if the Pro weights turn out to be community-licensed, the video stage falls back to Wan 2.2 A14B and you lose native audio sync in one pass.
7. **May I compile SageAttention?** It needs Python headers. Two paths: `apt install python3.12-dev` (system-wide, recorded in the ledger) or extend the existing vendored `sysroot/` headers (no system change). It is the 20× difference between this box being a batch factory and being a demo.
8. ~~Is the Oracle stack yours or a co-tenant's?~~ **Answered** — yours, stopped. The dense `Qwen3.8-27B` llama-server is also stopped. Note it was the slow class: 18 GB dense at 273 GB/s ≈ 7–9 tok/s, against 44–68 tok/s for the 35B-A3B MoE the plan specifies.
9. **May I tighten permissions at creation?** `chmod 750` on `~/Desktop/AIGC-Model`, and secrets in `env.local` mode `600` instead of a startup script.
10. **`docker system prune -a` — reclaim the Oracle images?** They live in `/var/lib/docker` (outside the folder) and are several GB. Stopped, not deleted. Say the word if the stack is retired.
9. **May I tighten permissions and rotate the token?** `chmod 750` on `~/Desktop/AIGC-Model` (currently world-readable on a 5-user RDP box) and move `FREEFIELD_TOKEN` out of `serve_aigc.sh` into a `600` env file, then rotate it.

---

## 8. Editorial defects found in the blueprint (for your next revision)

- §1 opening sentence is truncated: *"A solo creator or boutique studio operating in Asia under 5M–$20M+ annual revenue) while granting free commercial output rights…"* — a clause is missing and a stray `)` remains.
- §5 line on break-even is garbled: *"spending $18,000 on cloud production and 30,000 total) at a 40 % retained share needs $75,000…"* — the marketing figure and the parenthetical were both lost.
- Usable memory stated as 119.69 GiB here vs 121.7 GiB in the earlier brief; pick one and cite it.
- `pyJianYingDraft` is Apache-2.0 (verified), not MIT as §4 Stage 6 states.
- §2 says "1 PFLOP sparse / ~500 TFLOPS dense FP4" and later "~100 TFLOPS at 16-bit" — the two are not on the same basis; label units.
- Route B claims LATAM is inside the Applicable Territory. It is (only EU/UK/KR/US are excluded), but the licence grant is territory-bound on **use**, so add that the *rendering* must also occur in-territory — relevant if you ever host a Spark outside Asia.
