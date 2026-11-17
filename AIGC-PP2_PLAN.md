# AIGC-PP2 — Setup Plan (verified, 2026-11-16)

Local AI 漫剧 production pipeline (30 episodes, 60–90 min) on ComfyUI.
Machine: NVIDIA DGX Spark (GB10, 128 GB unified memory, aarch64, Ubuntu 24.04.5 / DGX OS).
Host: `tdadmin@192.168.1.103` (SSH key auth — no password needed).
Project root: `~/Desktop/AIGC-PP2` = `$ROOT`.

> This revision replaces the original plan. Every fact below was **measured on the host**,
> and every license was **read from the actual LICENSE file / model card**. Items the
> previous draft asserted without evidence are marked ⚠ and corrected.

---

## 0. Hard rules

1. **Work only inside `$ROOT`.** All caches, venv, models, logs, temp files live there.
2. **Do not touch the Oracle services or containers.** `ords-26ai` and `oracle-free-26ai` stay up.
3. **Stop, never remove.** `ornith-vllm` is only `docker stop`ed; never `rm`/`rmi`.
4. **No `sudo`, no `apt install`, no system/firewall changes** without asking the human.
5. **No Docker for this project** — images live in `/var/lib/docker`, outside `$ROOT`.
6. **ComfyUI bind is explicit and switchable.** `--listen "${COMFY_BIND:-0.0.0.0}"` (set to `0.0.0.0`
   on 2026-11-16 at the human's request, so the UI is reachable at http://192.168.1.103:9090).
   There is no login and custom nodes run arbitrary code, so use `COMFY_BIND=127.0.0.1` on any
   network that is not trusted. The pipeline CLI always talks to `127.0.0.1`.
7. **Never handle passwords or tokens.** Gated repos are the human's job to accept.
8. **Check disk before every large download.** Ask before any single download over 50 GB.
9. **Log everything** to `$ROOT/SETUP_LOG.md`.
10. **On failure: stop and report the exact error.** No random system-touching workarounds.

---

## 1. Measured baseline (2026-11-16)

| Fact | Value |
|---|---|
| Arch / kernel | `aarch64` / `6.17.0-1032-nvidia` |
| OS | Ubuntu 24.04.5 LTS |
| GPU | NVIDIA GB10, compute capability **12.1** (sm_121) |
| Driver / CUDA | 580.173.02 / CUDA **13.0** (`/usr/local/cuda-13.0`, nvcc 13.0.88) |
| CPU / RAM | 20 cores / 121 GiB unified, 15 GiB swap |
| Disk | 1.9 TB, **1.6 TB free** on `/` |
| Python | 3.12.3, `venv` OK, pip 26.x |
| Already present | `git curl wget ffmpeg rsync unzip`, `python3.12-dev`, `sox` (installed by the prior project, outside the folder) |
| Network | PyPI ~94 MB/s; Hugging Face ~6–7 MB/s |

**Memory note:** `nvidia-smi` reports `memory.total = N/A` — normal on GB10 unified memory, not a fault.
`ornith-vllm` reserved `--gpu-memory-utilization 0.35` ≈ 42 GiB of unified memory while running.
Stopping it raised available RAM from **52 GiB → 98 GiB**. Restart with `docker start ornith-vllm`.

---

## 2. Verified model set (licenses read from the repos)

All rows verified 2026-11-16 against the LICENSE file or model-card front matter.

| Slot | Repo | File(s) | License | Geo block | Revenue cap |
|---|---|---|---|---|---|
| Fast images / keyframes | `Comfy-Org/Z-Image-Turbo` | `z_image_turbo_nvfp4`, `qwen_3_4b_fp4_mixed`, `ae.safetensors` | **Apache-2.0** | none | none |
| Character sheets / multi-ref | `Comfy-Org/Flux-2-Klein-4B` | `flux-2-klein-4b`, `qwen_3_4b_fp4_flux2`, `flux2-vae` | **Apache-2.0** | none | none |
| Acting / action transfer | `Comfy-Org/Wan_2.2_ComfyUI_Repackaged` | `wan2.2_animate_14B_int8_convrot` + relight lora | **Apache-2.0** | none | none |
| Dialogue / lip-sync | `Comfy-Org/Wan_2.2_ComfyUI_Repackaged` | `wan2.2_s2v_14B_fp8_scaled` + `wav2vec2_large_english_fp16` | **Apache-2.0** | none | none |
| T2V / I2V base | `Comfy-Org/Wan_2.2_ComfyUI_Repackaged` | `wan2.2_ti2v_5B_fp16`, `umt5_xxl_fp8_e4m3fn_scaled`, `wan2.2_vae` | **Apache-2.0** | none | none |
| Multi-shot + audio | `comfyicu/LTX-2.5` | `ltx-2.5-22b-distilled-transformer-nvfp4`, `gemma4-12b-...-int8-convrot`, video+audio VAE | LTX-2 Community | **none** | ≥ $10 M/yr → paid licence |
| Backup video | `kabachuha/Kandinsky-6.0-Lite-distill-5s-int8-convrot` | 1 file, 3.25 GB | **MIT** | none | none |
| Voice | `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign` | `model.safetensors` + tokenizer | **Apache-2.0** | none | none |

### Excluded, with the reason

| Repo | Why |
|---|---|
| `MiniMaxAI/MiniMax-H3` | Licence §I.5: **Excluded Territories = EU, UK, Republic of Korea, USA.** Also requires displaying "MiniMax H3" in the UI, and written authorisation above $20 M/yr. Fine for China-only distribution (红果), not for YouTube/TikTok. |
| `tencent/HunyuanImage-3.0`, all Tencent Hunyuan models | Licence: "**DOES NOT APPLY IN THE EUROPEAN UNION, UNITED KINGDOM AND SOUTH KOREA**". Same trap as H3. Avoid the whole family. |
| `Qwen/Qwen-Image-2.1` | Qwen **Research** Licence; "Non-Commercial" = research/evaluation only. |
| `black-forest-labs/flux-3-image-klein` | Gated (401 without a token) → licence unreadable without accepting terms. Use `FLUX.2-Klein` (Apache-2.0) instead. |

⚠ The original draft said FLUX Klein was "FLUX Kommunity, free < $5M revenue". **Wrong** — `FLUX.2-klein-4B/9B` are Apache-2.0.
⚠ The original draft listed H3 without noting the *display requirement* and the $20 M clause.

---

## 3. Build (done 2026-11-16)

```bash
# venv + torch
python3 -m venv $ROOT/venv && . $ROOT/venv/bin/activate
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
# -> torch 2.14.1+cu130, cuda True, cap (12,1), bf16 matmul verified
```

- ComfyUI `e9afbcc` (2026-11-15), requirements installed **without** disturbing torch.
- Custom nodes: `ComfyUI-Manager` V3.43, `ComfyUI-VideoHelperSuite`.
- `env.sh` redirects HF/PIP/TORCH/XDG/TMP into `$ROOT`, sets `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`.
- `extra_model_paths.yaml` maps every model class to `$ROOT/models`.

⚠ **GB10-specific flags** — both matter on unified memory:
`--disable-pinned-memory` (pinned host buffers steal from the GPU pool), `--reserve-vram 8`.
⚠ SageAttention is **not** used: it compiles but raises `ValueError: Unsupported CUDA architecture: sm121`.

```bash
# start_comfy.sh (essentials)
python ComfyUI/main.py --listen "${COMFY_BIND:-0.0.0.0}" --port 9090 \
  --extra-model-paths-config "$ROOT/extra_model_paths.yaml" \
  --output-directory "$ROOT/outputs" --input-directory "$ROOT/assets/input" \
  --temp-directory "$ROOT/tmp" --disable-auto-launch \
  --disable-pinned-memory --reserve-vram 8
```

Port **9090**. Bind is `0.0.0.0` by default (see hard rule 6) — override with `COMFY_BIND`.

⚠ `huggingface-cli` is deprecated → use `hf download`. `ComfyUI-Manager`'s model list is
not a licence source; always read the repo's own LICENSE.

---

## 4. Smoke tests — all measured on the host (recorded in `SETUP_LOG.md`)

| Model | Settings | Time | Output | Verdict |
|---|---|---|---|---|
| Z-Image-Turbo NVFP4 | 832×1216, 8 steps, res_multistep/simple, cfg 1.0 | **9.0 s** | 1 still | ✅ keyframes |
| FLUX.2-Klein-4B | 896×1152, 4 steps, euler, Flux2Scheduler | **6.0 s** | 1 still | ✅ settei sheets |
| Wan2.2 TI2V 5B | 704×1280, 121 f, 20 steps, uni_pc/simple, cfg 5, shift 8 | **324.6 s** (13.5 s/it) | 5.0 s @24 fps | ✅ motion |
| Wan2.2 S2V 14B fp8 + 4-step LoRA | 480×832, 93 f, 4 steps, euler/simple, cfg 1 | **130.5 s** | 5.8 s @16 fps **+ audio** | ✅ lip-sync |
| Wan2.2 Animate 14B int8 | 480×832, 49 f, 10 steps, uni_pc/simple, cfg 5, shift 5 | **275.5 s** (25.3 s/it) | 3.06 s @16 fps | ✅ motion transfer |
| LTX-2.5 22B nvfp4 (single pass) | 512×768, 97 f, 8 sigmas, euler_ancestral, dual-CFG 1/1 | **50.1 s** | 4.04 s @24 fps **+ audio** | ✅ **best ratio** |
| Qwen3-TTS 1.7B VoiceDesign | separate `venv-tts`, bf16, `generate_voice_design` | 27 s load + **5.7 s** per 5.8 s line | 24 kHz wav | ✅ |
| Kandinsky 6.0 Lite int8-convrot | — | — | — | ❌ needs unmerged PR #16825 |

### Quality comparison, same shot (photoreal cinematic, decided 2026-11-17)

| Engine | Resolution | Time | × realtime | Verdict |
|---|---|---|---|---|
| **LTX-2.5 two-pass** | 1024×1536 | 125.1 s | 31× | **production engine** — era-correct signage, real car/cyclist, cinematic DOF |
| Wan2.2 TI2V 5B | 704×1280 | 455.2 s | 90× | correct mood, but dark and soft; use as draft / I2V fallback |
| Wan2.2 Animate 14B | 480×832 | 375.7 s | 123× | smeared; AI-generated driving clip is not a usable pose source |
| LTX-2.5 single pass | 512×768 | 50.1 s | 12× | animatic / preview mode |

Style locked to **photoreal cinematic** (user decision). Animate requires real camera footage as the
pose source, plus more steps, before it is usable.

### Throughput, measured

Real-time multiples (generation seconds ÷ clip seconds):

| Lane | × realtime | 90 min of finished video |
|---|---|---|
| LTX-2.5 single pass | ~12× | ~18 h |
| Wan2.2 S2V | ~22× | ~33 h |
| Wan2.2 TI2V 5B | ~64× | ~96 h |
| Wan2.2 Animate | ~90× | ~135 h |

So a 30-episode show should lean on **LTX-2.5 for establishing/非对白 shots** and S2V only for
actual dialogue; Animate is a per-shot tool, not a bulk one.

### Lessons from the smoke tests

- **S2V needs a scene-frame reference, not a settei sheet.** Given a white-background character
  sheet it reproduced a white background and near-static pose. Feed it a full scene frame
  (LTX / Z-Image) and it becomes a dialogue shot.
- **The 4-step lightx2v LoRA is a T2V LoRA.** It works in S2V but damps motion; the official
  template's 10-step / cfg 6 path is the quality setting.
- **LTX-2.5 is the only lane that makes audio natively**, which makes it the cheapest source of
  ambience and rough timing before TTS.
- **Animate is 5× slower than S2V at half the frame count** — reserve it for action beats.
- The bundled Animate template targets **Animate 2** (`wan_animate_2_distill_int8_convrot`),
  which is not in `Comfy-Org/Wan_2.2_ComfyUI_Repackaged`. v1 works through the core
  `WanAnimateToVideo` node.

---

## 5. Character consistency

Z-Image-Turbo is text-only; keyframe consistency across 30 episodes needs either
FLUX.2-Klein multi-reference or a fixed character sheet + LoRA later. Decide before episode 2.

## 6. Cleanup (only when the human says so)

```bash
# stop ComfyUI, then:
rm -rf ~/Desktop/AIGC-PP2
docker start ornith-vllm
```
Copy finished episodes and character assets out first.
