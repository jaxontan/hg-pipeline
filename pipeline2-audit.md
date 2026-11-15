# Audit — the "火锅 Pipeline 2.0 / 红果工业化" proposal

Received 14 Nov 2026 as a paste. This note separates what I could verify from what I could not, and
records which parts apply to *this* project. Everything below is either checked against this repo,
or checked against a primary source with the link given. Anything else stays unverified.

**Verdict in one line:** the platform-compliance section is broadly right and worth acting on; the
hardware section rests on a misreading of our own config; the technical section is aimed at a
different show that has not been made yet, and would discard one that has.

---

## 1. Verified true

### The regulation exists and says what the brief says

《微短剧发展管理办法》, 国家广播电视总局令第16号 — passed 2026-07-27, published 2026-07-30,
**effective 2026-09-01**. Eight chapters, 54 articles.

- Art. 5 — three classes by investment and subject; 备案公示 + 发行许可.
- Art. 25 — eleven prohibited content categories (拜金主义, 奢靡之风, 淫秽赌博, 渲染暴力 …).
- Art. 26 — 剧名/台词/字幕 must use 国家通用语言文字; foreign lyrics and titles need Chinese subtitles.
- **Art. 27 — 片头 must show 剧名、许可证号、批准文件编号、节目编号 in a prominent position**;
  writers/directors credited at the head of ep 1 or the tail of the last episode.
- AI-generated micro-drama — **a label in a prominent position on every episode**.

Per the 2026-08-17 《管理提示（微短剧分类分层标准）》, the AI thresholds are **80万 / 30万 RMB**:
≥80万 or special subject → 一类 (总局备案, 《微短剧发行许可证》); 30–80万 → 二类 (省级批准文件);
<30万 → 三类 (播出单位 pre-broadcast review + programme number). Real-person drama uses 300万/100万.

Sources: [gov.cn 国务院公报](https://www.gov.cn/gongbao/2026/issue_13006/202609/content_7082247.html),
[nrta.gov.cn 令第16号](https://www.nrta.gov.cn/art/2026/7/31/art_1588_73827.html),
[广东省广电局 政策解读](https://gbdsj.gd.gov.cn/zwgk/zcjd/content/post_4968123.html).

**Consequence for us:** a 90-second AI episode costs far under 30万, so it is **三类** — the platform
reviews it and issues the programme number. Art. 27's header block and the per-episode AI label are
hard requirements, and neither is in our assembly step yet (there is no assembly step).

### Audio-first is the correct criticism

The brief says our order is inverted. It is, and our own measurements prove it:

| line | measured speech | frames @24 fps | aligned 4n+1 | our clip |
|---|---|---|---|---|
| vo01 | 2.94 s | 70.5 | **73** (3.04 s) | 121 |
| vo02 | 4.12 s | 99.0 | **101** (4.21 s) | 121 |
| vo03 | 1.75 s | 42.0 | **45** (1.88 s) | 121 |
| vo04 | 1.47 s | 35.2 | **37** (1.54 s) | 121 |
| vo05 | 0.86 s | 20.6 | **25** (1.04 s) | 121 |
| vo06 | 2.11 s | 50.7 | **53** (2.21 s) | 121 |

`work/comfy_workflows/manju_i2v.json` hardcodes `Wan22ImageToVideoLatent: [704, 1280, 121, 1]` — every
clip is 5.04 s no matter what is said in it. We got away with it because shots were cut generously
and trimmed downstream, but **vo05 is generated at 4.8× the length its line needs**. That is wasted
compute on every take, and for lip-sync it is the wrong shape entirely: the mouth would have to
move for 0.86 s inside a 5.04 s clip.

121 = 4×30+1, so the 4n+1 rule is real and our existing clips already satisfy it — the constraint is
confirmed from our own workflow, not from the brief.

---

## 2. Verified wrong

### "44 GB 红线" is not a hardware limit — it is a setting we wrote

The brief treats 44 GB as a physical wall and therefore rules out any model above 11.66 GB. In this
repo, 44 GB is `COMFY_MEMORY_MAX` in `spark/bin/up.sh`, passed to `systemd-run -p MemoryMax=` as a
**cgroup cap on a unified-memory DGX Spark**. `versions.md` already states the position:

> 5B fp16 (10 GB) + umt5 fp8 (6.7 GB) fits inside the 44 G cap. A14B does not — raising
> `COMFY_MEMORY_MAX` is a decision, not a tweak.

So the "red line" is our own policy, not silicon. The brief's arithmetic (32.34 GB used, 11.66 GB
free) is correct against the manifest — that part checks out — but the conclusion drawn from it is
not: choosing a lip-sync model because it fits a cap we invented is choosing for the wrong reason.
The real constraint is time per take and whether the model handles flat 2D faces at all.

### It is written for a show that does not exist, at the cost of one that does

The sample payload is `HG_202611_XIANXIA_001`, 退婚书, 柳家, 国漫写实 — a different series. Meanwhile
ep01 is finished: 19 units, 18 canonical clips, provenance pinned at 66 entries, six VO lines
rendered and measured. Its "第 1–2 天 … 生成主角标准设定图" step is work we completed in earlier
phases. Adopting Pipeline 2.0 as written means re-rendering a finished episode to change its pipeline.

### Node names that do not exist in our build

The brief builds its no-LoRA consistency argument on `ZImageTextEncoder` and `ZImageTurnBuilder`
nodes with multi-turn `thinking_content`. Our actual workflows:

| workflow | nodes | control |
|---|---|---|
| `manju_keyframe_control.json` | 14 — `QwenImageDiffsynthControlnet`, `ModelPatchLoader`, `ModelSamplingAuraFlow` | single `KSampler` |
| `manju_i2v.json` | 12 — `Wan22ImageToVideoLatent`, `ModelSamplingSD3` | single `KSampler` |

Neither encoder-turn node appears, and one `KSampler`, not two — so **no step-handoff exists today**.
Whether `ZImageTurnBuilder` ships in our ComfyUI build (`b894a86`) is unverified; it must be checked
on the Spark before anything is designed around it. The step-handoff half is cheap to test on its own
and does not depend on that answer: two `Advanced KSampler`s, control on steps 0–4, plain on 4–8.

---

## 3. The parts that are simply our gaps

Independent of whether the brief is right, these are true and already listed in `STACK.md` §5:

| gap | what it blocks |
|---|---|
| `ffmpeg` not installed | the entire concat/scale/burn-in assembly the brief specifies |
| no `pyJianYingDraft`, no Jianying | the "AI 90% + 人工 10%" draft handoff |
| no compliance capture step | Art. 27 header, per-episode AI label, the four proof-screenshot classes |
| no git repo | none of this is revertible |

---

## 4. What I would do, in order

1. **Add the compliance block to assembly first.** It is cheap, it is legally required, and it does
   not depend on any model decision: 片头 剧名 + 节目编号, and the AI label in each episode.
   **DONE 14 Nov** — burned in `win/assemble.py`, frames checked at t=2 and t=34.
2. **Install `ffmpeg`** (Rule 3) and write the assembly step. **DONE 14 Nov** — N-128889, repo-local
   at `win/tools/ffmpeg`, `--final` refuses while 节目编号 is empty.
3. **Test audio-first on ep02 only**, with the 4n+1 table above as the spec. Do not re-render ep01.
   **BLOCKED** — there is no ep02. The table stands ready as its spec.
4. **Test dual-KSampler step-handoff** on one existing keyframe. **DONE 14 Nov** — see below.
5. **Check whether `ZImageTurnBuilder` exists on the Spark.** **DONE 14 Nov — it does not.**
6. Weights (`LatentSync`, `MusicGen`, `qwen3_tts_base`) go through the Rule 2 licence gate as manifest
   rows *before* download, with verified sizes — the brief's 5.20 / 0.63–1.80 GB figures are unverified.
   **DONE 14 Nov (partial).**
   - `latentsync_1_6` added to `spark/models/MANIFEST.json`: OpenRAIL++ (approved), 9.64 GB total
     across 9 files (UNet 5.07 GB, SyncNet 1.61 GB, whisper/tiny 75 MB, + 6 auxiliary). The brief's
     5.20 GB was the UNet only — the full bundle is ~9.64 GB. All sha256s verified from the HF Xet
     pointer (X-Linked-ETag). Download not yet triggered.
   - `qwen3_tts_base_1_7b` already gated (4.54 GB, Apache-2.0) — no change.
   - `MusicGen` **refused outright** (Rule 2): weights are CC-BY-NC 4.0, non-commercial. A commercial
     short drama cannot use them. Commercial alternative: ACE-Step 1.5 (MIT) or YuE (Apache-2.0),
     but either is a new model → Rule 3 approval needed before it enters the manifest. Smallest next
     action: operator picks ACE-Step 1.5 (4 GB VRAM, runs on the Spark's 44 GB cap) and approves the
     Rule 3 addition; then add its manifest row.

### 4a. Step 5 result — the multi-turn argument has no implementation here

`grep -rlo` across `app/ComfyUI` at commit `b894a86`:

| name | result |
|---|---|
| `ZImageTurnBuilder` | **not found anywhere** |
| `ZImageTextEncoder` | **not found anywhere** |
| Z-Image support | present — `comfy/supported_models.py`, `model_base.py`, `ldm/lumina/controlnet.py`, `latent_formats.py` |
| `QwenImageDiffsynthControlnet` | present — `comfy_extras/nodes_model_patch.py` |
| `KSamplerAdvanced` | present — `nodes.py` |

So the brief's centrepiece — multi-turn `thinking_content` carrying 80–90 % of a character's identity
without a LoRA — **is not a feature of this install**. The encoder is loaded through `CLIPLoader` as a
plain `lumina2` text encoder; there is no conversation state and no turn node to hand it to. Treat
that whole section as a proposal for a node that would have to be written, not a capability we lack
by configuration.

Incidentally the box also carries `custom_nodes/comfyui-sameface` and `ComfyUI-VideoHelperSuite`.
sameface is an untracked route to face consistency — worth a licence and provenance look before it is
used for anything, but it is a real option where the turn nodes are not.

### 4b. Step 4 result — step-handoff works, and it is cheaper

One shot (`s004`), one seed (`420261113`), identical prompt and depth guide, two arms:
baseline = one `KSampler` with the control patch over all 8 steps; handoff = `KSamplerAdvanced`
0–4 with the patch, then a second sampler 4–8 on the unpatched model.

| arm | wall | bytes | sha256 |
|---|---|---|---|
| A baseline | **10.4 s** | 1 176 358 | `724047f9…` |
| B handoff 0–4 | **7.3 s** | 1 202 027 | `de3381ef…` |

SSIM between them **0.894** — composition, pose, wardrobe and background all hold, which is what the
test needed to show. Looking at them side by side, B's skin is a touch cleaner and less contrasty;
A is slightly crisper. Neither is broken. The side-by-side was
`work/ep00_p5_handoff/_cmp_small.png` with a face crop at `_cmp_face.png` — that folder was deleted on
15 Nov, so the numbers here (SSIM 0.894) are the surviving evidence; re-derive a pair from the master
if the comparison is ever needed again.

The speed is the interesting part: the second half runs without paying for the ControlNet patch, so
handoff is ~30 % faster *and* preserves framing. n=1 and one seed — this is a feasibility result, not
a quality verdict. A real decision needs the same pair on a close-up and a wide, several seeds each.

Code: `win/submit_keyframe.py --handoff --handoff-split 4`. Off by default; the proven recipe is
unchanged.

## 5. What I would not do

Re-render ep01. Its clips are canonical, hashed and pinned; changing the pipeline underneath them
would desync provenance for no gain on a finished episode. Pipeline 2.0 is a template for ep02+.
