# AIGC-PP2 — Setup Report

Date: 2026-11-16
Host: `tdadmin@192.168.1.103` — NVIDIA DGX Spark (GB10)
Root: `~/Desktop/AIGC-PP2`

---

## 1. System facts

| Item | Value |
|---|---|
| Arch / kernel | aarch64 / 6.17.0-1032-nvidia |
| OS | Ubuntu 24.04.5 LTS |
| GPU | NVIDIA GB10, compute capability **12.1** |
| Driver / CUDA | 580.173.02 / CUDA 13.0 (nvcc 13.0.88) |
| CPU / RAM | 20 cores / 121 GiB unified + 15 GiB swap |
| Python | 3.12.3 |
| torch | **2.14.1+cu130**, `cuda.is_available()==True`, bf16 matmul verified |
| ComfyUI | 0.45.0, commit `e9afbcc` (2026-11-15) |
| Nodes | 1100 |
| Custom nodes | ComfyUI-Manager V3.43, ComfyUI-VideoHelperSuite |
| Disk | 1.9 TB total, ~317 GB used, **~1.5 TB free** |
| RAM before build | 52 GiB available |
| RAM after stopping ornith-vllm | 98 GiB available |

---

## 2. Resources freed

- `ornith-vllm` container **stopped** (not removed). It reserved `--gpu-memory-utilization 0.35` ≈ 42 GiB of unified memory.
  Restart command: **`docker start ornith-vllm`**
- Oracle containers `ords-26ai` and `oracle-free-26ai` were **not touched**.
- `~/Desktop/AIGC-Model` was deleted at operator request (full wipe, including the `laotang_ep01` work and 51 GB of models).

---

## 3. What works — verified by actual generation

| Model | Files | Settings | Time | Verdict |
|---|---|---|---|---|
| Z-Image-Turbo (NVFP4) | `z_image_turbo_nvfp4` + `qwen_3_4b_fp4_mixed` + `ae` | 832×1216, 8 steps, res_multistep/simple, cfg 1.0 | **9.0 s** | ✅ excellent |
| FLUX.2-Klein-4B distilled | `flux-2-klein-4b` + `qwen_3_4b_fp4_flux2` + `flux2-vae` | 896×1152, 4 steps, euler, Flux2Scheduler | **6.0 s** | ✅ character sheets |
| Wan2.2 TI2V 5B | `wan2.2_ti2v_5B_fp16` + `umt5_xxl_fp8` + `wan2.2_vae` | 704×1280, 121 frames, 20 steps, uni_pc/simple, cfg 5, shift 8 | **324.6 s** (13.5 s/it) | ✅ real motion |

Samples: `outputs/smoketest/zimage_00001_.png`, `klein_00001_.png`, `wan5b_00001_.mp4`.

Downloaded but **not yet smoke-tested**: Wan2.2 S2V 14B, Wan2.2 Animate 14B, LTX-2.5 22B, Qwen3-TTS.

Downloaded but **not usable**: Kandinsky 6.0 Lite int8-convrot.

---

## 4. Problems found and how they were resolved

1. **SageAttention is unusable on GB10.** Version 2.2.0 compiles (after patching `-std=c++17` → `-std=c++20`, required by torch 2.14), but `sageattn()` raises
   `ValueError: Unsupported CUDA architecture: sm121`.
   → Flag removed from the launcher. Do not re-add it.
2. **Hugging Face Xet transport hangs** on this network (stalled at a fixed byte count, twice).
   → `HF_HUB_DISABLE_XET=1` in `env.sh`; downloads then run at 11–100 MB/s.
3. **`huggingface-cli` is deprecated** → `hf download` (huggingface_hub 2.4.0).
4. **Kandinsky 6.0 Lite int8-convrot is a test quantisation** requiring the unmerged ComfyUI PR #16825 ("only after Pi-Flow support"). It will not load on 0.45.0. It is the optional backup slot, so this is not blocking.
5. **The official Wan/LTX templates need more companion files than the plan listed**: `wan_2.1_vae`, `clip_vision_h`, the `lightx2v` 4-step LoRA, and the LTX latent upscaler. All were downloaded.
6. **GB10 flags omitted by the original plan** are now in `start_comfy.sh`: `--disable-pinned-memory --reserve-vram 8`.

---

## 5. Licence audit (verified against the actual LICENSE text)

| Model | Licence | Geography | Revenue cap | YouTube/TikTok |
|---|---|---|---|---|
| Z-Image-Turbo | Apache-2.0 | none | none | ✅ |
| FLUX.2-Klein-4B | Apache-2.0 | none | none | ✅ |
| Wan2.2 (Animate / S2V / TI2V) | Apache-2.0 | none | none | ✅ |
| Kandinsky 6.0 Lite | MIT / Apache-2.0 | none | none | ✅ |
| Qwen3-TTS | Apache-2.0 | none | none | ✅ |
| LTX-2.5 | LTX-2 Community | **none** | ≥ $10 M/yr → paid licence | ✅ under $10 M |
| **MiniMax H3** | H3 Community | **EU, UK, Korea, USA excluded** | ≥ $20 M/yr | ❌ |
| **Tencent Hunyuan (all)** | Tencent Community | **EU, UK, South Korea excluded** | 100 M MAU | ❌ |
| Qwen-Image-2.1 | Qwen Research | — | non-commercial only | ❌ |

H3 is the **only** geography-restricted model in the original plan; LTX-2.5 and FLUX Klein were blocked by nothing but unverified notes. H3 also requires displaying "MiniMax H3" in the product UI.

---

## 6. How to use it

From your laptop:

```bash
ssh -L 9090:localhost:9090 tdadmin@192.168.1.103
```

Then open <http://localhost:9090>.

ComfyUI binds **127.0.0.1 only** (no auth, custom nodes run arbitrary code).
The old project bound `0.0.0.0:8188` with no auth — that is fixed.

Start / stop:

```bash
~/Desktop/AIGC-PP2/start_comfy.sh     # foreground
tail -f ~/Desktop/AIGC-PP2/logs/comfyui.log
```

---

## 7. Disk used by models

115 GB total in `~/Desktop/AIGC-PP2/models` (from 1.6 TB free → 1.5 TB free).

---

## 8. Still to do

- Smoke-test Wan2.2 **S2V 14B** (dialogue/lip-sync) — official template is a multi-pass subgraph and needs `wan_2.1_vae` + `lightx2v` LoRA (both present).
- Smoke-test Wan2.2 **Animate 14B** — needs `clip_vision_h` (present) and a driving video.
- Smoke-test **LTX-2.5 22B** — official template is a two-pass graph with audio; needs the latent upscaler (present).
- Smoke-test **Qwen3-TTS** and wire it into the voice lane.
- Character consistency: freeze a character sheet from FLUX.2-Klein and reuse it as the reference for every shot.

---

## 9. Cleanup (only on request)

```bash
rm -rf ~/Desktop/AIGC-PP2
docker start ornith-vllm
```
