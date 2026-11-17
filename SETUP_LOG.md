# AIGC-PP2 SETUP LOG

Host: 192.168.1.103 (DGX Spark GB10)
Started: 2026-11-16T13:07:26Z

## Baseline (measured, not assumed)

| Fact | Value |
|---|---|
| Arch | aarch64 |
| Kernel | 6.17.0-1032-nvidia |
| OS | Ubuntu 24.04.5 LTS |
| GPU | NVIDIA GB10, compute cap 12.1 |
| Driver | 580.173.02 |
| CUDA toolkit | /usr/local/cuda-13.0 (Cuda compilation tools, release 13.0, V13.0.88) |
| Python | Python 3.12.3 |
| Disk avail | 1.6T |
| RAM avail (after stopping ornith-vllm) | 115Gi |

## Actions

- ornith-vllm container **stopped** (not removed). Restart: `docker start ornith-vllm`
- ornith-vllm reserved ~42 GiB of unified memory; stopping it raised available RAM from 52 GiB to 98 GiB.
- Oracle containers (`ords-26ai`, `oracle-free-26ai`) left running, untouched.
- Deleted `~/Desktop/AIGC-Model` at operator request (full wipe, incl. laotang_ep01 work and 51 G models).

---

## 2026-11-16T15:29:34Z — setup report appended

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

---

## 2026-11-16T15:47:47Z — smoke test round 2 (all models)

| Model | Settings | Time | Output | Verdict |
|---|---|---|---|---|
| Z-Image-Turbo NVFP4 | 832x1216, 8 steps | 9.0 s | still | OK |
| FLUX.2-Klein-4B | 896x1152, 4 steps | 6.0 s | still | OK |
| Wan2.2 TI2V 5B | 704x1280, 121f, 20 steps | 324.6 s | 5.04 s @24fps | OK |
| Wan2.2 S2V 14B + 4-step LoRA | 480x832, 93f, 4 steps, cfg1 | 130.5 s | 5.81 s @16fps + audio | OK |
| Wan2.2 Animate 14B int8 | 480x832, 49f, 10 steps, cfg5, shift5 | 275.5 s | 3.06 s @16fps | OK |
| LTX-2.5 22B nvfp4 single pass | 512x768, 97f, 8 sigmas | 50.1 s | 4.04 s @24fps + audio | OK |
| Qwen3-TTS 1.7B VoiceDesign | venv-tts, bf16 | 27 s load + 5.7 s | 5.76 s @24kHz | OK |
| Kandinsky 6.0 Lite int8-convrot | - | - | - | FAIL: needs PR #16825 |

Findings:
- LTX-2.5 is ~12x realtime and the only lane that generates audio natively -> primary video engine.
- S2V lip-sync confirmed (mouth opens/closes over the line) but a white-background settei
  reference yields a white background and a static pose; it needs a full scene frame as ref.
- Animate transfers identity + motion; 90x realtime, so per-shot only.
- Voice lane needs its own venv: qwen-tts pins transformers 4.57.3, ComfyUI needs 5.x.
  venv-tts installed at $ROOT/venv-tts (6.1 GB).
- No native Qwen3-TTS node in ComfyUI; the only TTS nodes are paid cloud APIs.
  -> TTS is a CLI lane writing wav into assets/audio, consumed by LoadAudio.
- extra_model_paths.yaml was missing latent_upscale_models; added + ComfyUI restarted.
- Animate template targets Animate 2 (not in the Wan2.2 repackaged repo); v1 driven via WanAnimateToVideo.

Outputs: outputs/smoketest/{animate_00001_,s2v_00001_,ltx_00001_}.mp4

---

## 2026-11-16T16:12:34Z — quality comparison, same shot, photoreal cinematic

Beat: 1970s county-town street at dusk, man in navy Mao suit with enamel mug walking toward
camera, cyclist behind, warm lamp, wet cobbles.

| Engine | Resolution | Frames | Time | x realtime | Verdict |
|---|---|---|---|---|---|
| LTX-2.5 two-pass | 1024x1536 | 97 | 125.1 s | 31x | best detail, era-correct signage, real car/cyclist, cinematic DOF |
| Wan2.2 TI2V 5B | 704x1280 | 121 | 455.2 s | 90x | correct mood and props, but dark, soft, less detail |
| Wan2.2 Animate 14B | 480x832 | 49 | 375.7 s | 123x | smeared/ghosted; AI-generated driving clip is not a usable pose source |

Conclusions:
- LTX-2.5 two-pass is the production engine. 1024x1536 at 31x realtime beats 704x1280 at 90x.
- Wan T2V 5B is the cheap draft/preview engine and the I2V fallback when a first frame must be locked.
- Animate needs real (camera) driving footage plus more steps; do not feed it AI-generated video.
- Single-pass LTX (12x) is the animatic/preview mode; two-pass for final.

Outputs: outputs/compare/{ltx_2pass,wan_t2v}_00001_.mp4, outputs/smoketest/animate_00002_.mp4

---

## 2026-11-16T16:55:15Z — pipeline layer verified end to end

Built: pipeline/ (comfy client, graph builders, config, manifest, CLI, assembler),
workflows/*.api.json exported for all 7 lanes, PIPELINE.md.

CLI chain, project=verify, media never touched by hand:
  image    image_fast      832x1216            18.0 s
  video    video_ltx_final 1024x1536 / 97f    180.4 s  (cold, after model swap)
  voice    Qwen3-TTS       6.08 s wav         10.6 s
  dialogue video_s2v       97f auto from wav  224.1 s  (also cold)
  assemble 2 shots -> projects/verify/verify.mp4, 1080x1920 @24fps, 10.16 s

manifest.jsonl records lane, prompt, params, graph_hash (sha256[:16]) and elapsed per take.
Dialogue now uses an LTX scene frame as the reference, so the lip-sync shot has a real
background instead of the white settei void seen in the first S2V test.

Bind change (user request): ComfyUI moved from 127.0.0.1:9090 to 0.0.0.0:9090.
  start_comfy.sh now uses --listen ${COMFY_BIND:-0.0.0.0}; verified LISTEN 0.0.0.0:9090,
  GET http://192.168.1.103:9090/system_stats returns 200 from the Windows desktop.
  Risk accepted knowingly: no auth + arbitrary code via custom nodes. Localhost-only
  restore is 'COMFY_BIND=127.0.0.1 bash start_comfy.sh'. CLI still targets 127.0.0.1.

---

## 2026-11-16T16:59:27Z — how to inspect a workflow

Added 'pipeline.cli describe [--lane NAME]': prints a lane as a numbered node list with
settings plus every wiring edge. Refactored export to share lane_graph().

Confirmed the installed frontend (comfyui_frontend_package) exposes loadApiJson, so
workflows/*.api.json can be dragged into the UI and are rebuilt as a node graph.
Copied all 7 api.json to the Windows desktop under AIGC-PP2/workflows/ for that purpose.

Workflow has three layers: pipeline/config.json (parameters) -> pipeline/graphs.py
(wiring) -> workflows/*.api.json (exported snapshot). Edit config/graphs, then re-export;
the .api.json files are generated artefacts and should not be hand-edited.

---

## 2026-11-16T17:04:41Z — README.md

Wrote README.md (539 lines) as the project entry point: what the project is, the stack
(GB10 / CUDA 13.0 / torch 2.14.1+cu130 / ComfyUI 0.45.0 / the two venvs), the verified
model table with licences, the excluded models and why, all 7 lanes described node by node
with settings and measured cost, the measured comparison + season budget, known limits,
operations and the uninstall path.

Also corrected two stale statements in AIGC-PP2_PLAN.md: hard rule 6 still claimed
127.0.0.1-only (now documents the switchable COMFY_BIND), and section 3 still listed
--use-sage-attention as required (it raises sm121 and was removed).

## 2026-11-17 — keyframe-first production workflow

Added three reference-conditioned lanes, a director layer and an episode runner. Originals of
every changed file are in `tmp/backup_20261117/`.

New / changed files: `pipeline/graphs.py` (+`image_ref`, `ltx_i2v`), `pipeline/config.json`
(+`image_ref`, `video_ltx_i2v`, `video_ltx_talk`), `pipeline/director.py` (new),
`pipeline/produce.py` (new), `pipeline/cli.py` (+`image --ref`, `video --image`, `talk`,
`produce`, assemble flags), `pipeline/assemble.py` (cover fit, ASS subtitles, loudnorm, label,
voice-over mix; default behaviour unchanged), `pipeline/voice.py` (+`--batch`),
`workflows/PRODUCTION_WORKFLOW.md`, `workflows/templates/{bible,episode}.json`, 10 exported
graphs, README §1/§4/§5.10/§7/§8/§10, PIPELINE.md (appended section).

Measured (GB10, ComfyUI 0.45.0; a Blender process held one CPU core throughout):

| Run | Result |
|---|---|
| `image_ref` 1024×1536, 2 refs | 21.0 s |
| `image_ref` 1088×1920, 2 refs | 18–21 s warm, 27–36 s after a swap |
| `video_ltx_i2v` 1024×1536, 97 f | 204.6 s (cold) |
| `video_ltx_i2v` 1088×1920, 49 / 73 / 97 f | 129 s / 180–192 s / 241–246 s |
| `video_ltx_talk` 1024×1536, 169 f | 315.7 s |
| `video_ltx_talk` 1088×1920, 97 / 113 f | 240–252 s / 290–297 s |
| `video_ltx_talk` with video CFG 2.5 | 362 s, harsher picture — rejected |
| `video_s2v` fallback from a keyframe, 65 f | 150.8 s |
| demo ep00, 6 shots, 20.9 s: assets / keyframes / voice / animatic / video | 52 s / 97 s / 52 s / 5 s / 21.4 min |

Findings:
- Klein `ReferenceLatent` holds face, wardrobe and location across shots (demo contact sheet).
- 544×960 → 1088×1920 works; assembly crops 8 px instead of letterboxing.
- **`video_ltx_talk` painted garbled captions into demo shot S04 in 4 of 4 takes** (new seed,
  reworded prompt, new keyframe, CFG 2.5 + negative). S01 was clean in 2 of 2. Cause unknown.
  Workaround added: per-shot `"talk_lane": "video_s2v"`.
- `push_in` as first phrased zoomed to an extreme close-up within 4 s; softened.
- Modern cars appear in 1983 street shots whether or not the prompt says "no cars".
- `LTXVEmptyLatentAudio` in the two text-only LTX lanes uses 25 fps against 24 fps video
  (3.88 s audio on 4.04 s clips). Left as is; new lanes pass the real fps.
- Lip-sync was judged from frame strips only; nobody has listened to the takes yet.

Probe leftovers: `outputs/probe/`, `assets/input/probe_*`, `tmp/*.py|*.sh`, `tmp/view/`.
