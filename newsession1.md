# New session 1 — start here

Written 2026-11-14 at the end of the picture phase of 《老汤》ep01. Read this, then `AGENTS.md`, then
`versions.md`. This file supersedes the "resume at Phase 3" banner in `versions.md`: **Phase 3 is done.**

> **Revised the same day, after a verification pass** (all 19 clip hashes, `retargets.json`, the `.blend`
> hash, `MANIFEST.json`, the audio map and a fresh `bin/doctor.sh` re-checked — they hold). Changed:
> §3.1 is new (provenance, now mirrored and pinned, with `win/mirror_provenance.py` + `restore.sh` +
> `doctor.sh` behind it), the level counts in §4.1 and the GPU minutes in §4.3 are corrected, §5's
> stale-line list was extended, and §7 was rebuilt.
>
> **Phase 4 was then executed in the same session**, so §6 is no longer a plan — it is a record of what was
> installed, downloaded and rendered, including two findings that contradict what §6 used to say (`sox` is
> a binary not a header package; `torchaudio` has no 2.14 build anywhere). §6.6 lists what is still open,
> §7 and §10 were rewritten around it, and §9 gained four gotchas (13–16) that cost real time.

---

## 1. Where we are, in one paragraph

**The picture for the 90-second episode is finished, and so is the first voice pass.** All 19 units have
a clip — 18 canonical files, because `s001m` serves both unit 3 and unit 10. (Clips are 121 frames ≈ 5.04 s
each; the *units* run 2–8 s and are trimmed to the 90 s cut, so "19 × 5 s" is not the episode length.)
Nothing in the picture track is blocked, nothing needs re-rendering, and the Blender set no longer has to be
opened. **Phase 4 (voice) now exists end to end**: three weight rows are gated and two are downloaded,
`app/venv-tts` holds Qwen3-TTS on its own torch, and `win/tts_lines.py` rendered all six utterances of the
episode into `work/laotang_ep01/vo/` with provenance (66 entries, pinned). **The measuring is done as
well** (§6.5.1–§6.5.2): every line is within one character of ASR error, three were re-rendered to fix
pitch, and the two casting defects the numbers found are recorded with what still needs an ear. What is
left is judgement — three voices to listen to, and the lipsync decision. `STACK.md` records what runs on
which machine and where every weight lives.

**Phase 5 is done too (§11):** the 90 s conform master and the Jianying draft exist, and the §5 doc debt
it used to carry is closed. Everything after this paragraph that says "assembly is the next step",
"ask before creating the venv", or "§5 owes 15 minutes" is superseded by §11.

---

## 2. Hard rules (unchanged — see `AGENTS.md` for the full text)

1. **Two writable roots only:** `C:\Users\admin\Desktop\manju` here, `~/Desktop/AIGC-Model` on the
   Spark (`tdadmin@192.168.1.103`). Nothing outside them, no symlinks across, `/tmp` forbidden.
2. **`source env.sh` before every Spark command.** It is what keeps the folder hermetic.
3. **Licence gate before download.** Every weight goes into `models/MANIFEST.json` with URL, sha256,
   SPDX id and licence link first. No LICENSE file / NC terms / revenue caps / territory exclusions =
   refuse. Load-bearing work: Apache-2.0, MIT, BSD, OpenRAIL++ only.
4. **Every asset carries provenance** in `provenance/<episode>/MODEL_PROVENANCE.json`, and the file is
   mirrored into this repo so a wipe cannot take it (§3.1). An asset without it cannot be assembled
   into a master.
5. **`territory: cn | global | both` on every shot.** All 19 units are `both`.
6. **No new dependencies** — not a ComfyUI node, not a pip package — without explicit approval.
7. **Installs only through `bin/record-install.sh`.**
8. **`bin/doctor.sh` before reporting done** on anything that touched the Spark.

---

## 3. What exists (verified on disk today)

### Windows — `work/laotang_ep01/` (19 files, 18 canonical)

| Unit | Shot | Clip | Size | sha256 |
|---|---|---|---|---|
| 1 | `s002m` | `s002m_manju_clip_00002_.mp4` | 2.0 MB | `400a0397…` |
| 2 | `s011m` | `s011m_manju_clip_00017_.mp4` | 1.9 MB | `a6ce369c…` |
| 3, 10 | `s001m` | `s001m_manju_clip_00001_.mp4` | 1.5 MB | `5b667e14…` |
| 4 | `s003m` | `s003m_manju_clip_00009_.mp4` | 1.6 MB | `3a7ae56b…` |
| 5 | `s002c` | `s002c_manju_clip_00011_.mp4` | 2.6 MB | `39d7dda9…` |
| 6 | `s005m` | `s005m_manju_clip_00005_.mp4` | 0.8 MB | `8e8b291c…` |
| 7 | `s004em` | `s004em_manju_clip_00004_.mp4` | 1.5 MB | `cd9de3c1…` |
| 8 | `s007bm` | `s007bm_manju_clip_00007_.mp4` | 1.7 MB | `2b7ee541…` |
| 9 | `s004g` | `s004g_manju_clip_00010_.mp4` | 2.1 MB | `379822bc…` |
| 11 | `x001` | `x001_manju_clip_00012_.mp4` | 2.1 MB | `97da68df…` |
| 12 | `x002` | `x002_manju_clip_00013_.mp4` | 1.2 MB | `074f22c6…` |
| 13 | `x003` | `x003_manju_clip_00014_.mp4` | 1.8 MB | `cced40d2…` |
| 14 | `s006m` | `s006m_manju_clip_00006_.mp4` | 1.5 MB | `1c737777…` |
| 15 | `s012m` | `s012m_manju_clip_00019_.mp4` | 1.2 MB | `808857c3…` |
| 16 | `s008m` | `s008m_manju_clip_00008_.mp4` | 1.9 MB | `3bc5279e…` |
| 17 | `s009m` | `s009m_manju_clip_00015_.mp4` | 1.9 MB | `78230367…` |
| 18 | `s002d` | `s002d_manju_clip_00018_.mp4` | 1.5 MB | `f6e1af69…` |
| 19 | `s010m` | `s010m_manju_clip_00016_.mp4` | 1.6 MB | `a45a40d1…` |

`s003m_manju_clip_00003_.mp4` (`55a42be4…`) is the **superseded** first pass — do not cut with it.
Contact sheets `board_a.jpg` … `board_f.jpg` sit beside them, one row per shot at frames
0/30/60/90/120; `board_f` (950×1825) proves the last five clips hold.

`work/laotang_ep01/vo/` holds the voice pass — six wavs plus `VO_MANIFEST.json` (§6.5):

| File | Speaker | Length | sha256 |
|---|---|---|---|
| `vo01_sunian_vo.wav` | 苏念 VO | 3.12 s | `54a1f1e02894` |
| `vo02_sujianguo.wav` | 苏建国 | 4.40 s | `a9eed5e4ba4e` |
| `vo03_sunian_line.wav` | 苏念 | 1.92 s | `b8557952feaf` |
| `vo04_xiaoman.wav` | 小满 | 1.52 s | `0a3aed8cfe50` |
| `vo05_sunian_huoguo.wav` | 苏念 | 1.04 s | `0515e80f61ba` |
| `vo06_guyan.wav` | 顾衍 | 2.40 s | `cff33cb90f95` |

24 kHz mono PCM_16, −19…−26 dBFS, 14.4 s total. **These are the post-rerender files** (§6.5.2) —
`vo03`, `vo05` and `vo06` were re-rendered, so their lengths and hashes here differ from the
first-pass table §6.5.1 measures. Hashes were re-verified on this side after the pull, so they match
the Spark's `VO_MANIFEST.json` and the provenance entries.

### 3.1 Provenance — written, mirrored, and pinned

`~/Desktop/AIGC-Model/provenance/laotang_ep01/MODEL_PROVENANCE.json` exists: **66 entries, 156 KB** as of
14 Nov (60 picture entries, plus 6 voice entries added by the TTS render — see §6). It covers the Round 4
renders too — `manju_clip_00019_.mp4` is in it with sha256 `808857c3…`, matching the file on Windows. Each
entry carries job id, shot id, territory, prompt, model ids with SPDX + licence links + quantisation +
sha256, seed, workflow sha256, engine versions, and the output list with its own sha256 and byte count.
Rule 1 is satisfied. (`spark/provenance/ep00_*` keeps one entry each for the three handshake
episodes, same schema, even though those render folders were deleted on 15 Nov — the record outlived
the pixels.)

**It was a single copy on the Spark until 14 Nov.** `spark/provenance/` did not exist in this repo, and
`bin/restore.sh` rebuilt weights from `MANIFEST.json` only — so the operator's one-shot wipe would have
destroyed the legal defence while the clips survived in `work/laotang_ep01/`. That is now closed:

| Piece | What it does |
|---|---|
| `win/mirror_provenance.py` | pulls every `provenance/*/MODEL_PROVENANCE.json` into the repo, writes the pin, refuses to overwrite a repo copy that has *more* entries than the Spark's (that would be a stale pull over a newer file) |
| `spark/provenance/MIRROR.json` | the pin: sha256 + byte count + entry count + UTC time per file. 3 files, `laotang_ep01` = `f342b5a7…` (66 entries) |
| `bin/restore.sh --provenance-only` | after a wipe: every pinned file must exist and match its hash, every entry must carry `shot_id / territory / models / seed / workflow_sha256 / engine_version / outputs`, and every model must carry SPDX + sha256. Mismatch is a **failure**, not a warning |
| `bin/doctor.sh` §5b | the same comparison on every run, so drift is caught the moment a render adds an entry |

All four are installed and exercised — twice with synthetic drift, and then **for real**: the six-line TTS
render moved the file from 60 to 66 entries, `doctor.sh` went red on its own (`FAIL provenance mirror …
drifted`, restore non-zero), the mirror was re-run, the pin republished, and both checks went green again
with `66 entries, pinned`. **The rule is now: after any render batch, run
`python win\mirror_provenance.py`, then `bin/doctor.sh`.** The mirror is still a snapshot; the pin is what
makes a stale snapshot loud.

Note also that `doctor.sh`'s older coverage check fails only when provenance is **zero**
(`clips > 0 && prov == 0`). It prints `info assets / provenance files 116 / 3` and passes — three
episode-level files for 116 assets is normal for this layout, but read the number rather than the PASS.

---

## 4. What this session did (Round 4)

### 4.1 Found and fixed the depth-ramp defect (the one that mattered)

`depth_range()` in `win/blender_set_huoguo.py` sized the depth ramp from **camera distance**:
`far = near + max(1.6·d, 3.2)`. Correct for a wide, wrong for a close-up. At `s010`'s 0.73 m the ramp
spanned 0.36–3.56 m, so the head's own 9.6–10.1 cm of depth mapped to **6 of 255 levels** — a flat
white disc on black. A depth ControlNet given a disc renders *the disc's outline as an object*: that is
where the wooden hoop round 苏念's head, the wire across 顾衍's chest and the cables on the shop front
came from. It was never a prompt problem.

**Fix (`win/blender_depth_rerange.py`, rewritten 14 Nov):** ray-cast a grid over the frame, group hits
by object-name prefix, measure the subject's real depth span, then

```
near = z_lo − 0.15·(z_hi − z_lo)
far  = near + (z_hi − z_lo) / 0.30
```

Result: the head's own depth now occupies **~76 of 255 levels** (0.30 of the ramp, by construction), up
from 6 — on `s009` (ramp 0.583–0.903 m) and `s010` (1.042–1.378 m) alike. Both re-rolled clean on the
**first** attempt. The script renders RGBA (masks must use alpha — an RGB save leaves alpha 1.0 and
reports `cover=1.000`), hides steam, and prints `MEASURE`/`RAMP`/`CHRSTAT`/`DEPTHSTAT`/`SUBJSTAT`/
`BGSTAT`.

> **Careful with `SUBJSTAT`.** It prints `167` for a 0.30 span-frac, and 167 is *not* the subject's span:
> the script computes `(1 − (z_hi − near)/(far − near)) · 255`, which measures the gap from `z_hi` to
> `far`, i.e. the complement. The subject's own span is `(z_hi − z_lo)/(far − near) · 255` = 76. Both
> numbers are arithmetically right and the ramp is correct; only the label is wrong. Quote **6 → 76** for
> the head's span, and do not use `SUBJSTAT` as a quality gate. (Worth a one-line fix in the script the
> next time it is opened: print both, and rename the existing one `FARSTAT`.)

### 4.2 New tool: `win/blender_retarget_rig.py`

Moves **or creates** a camera, renders `<shot>_retargeted_depth.png` + control pass, appends the
placement to `work/sets/huoguo/retargets.json`, and never saves the set. Flags: `--ramp builder|hug`,
`--subject <prefix>`, `--hide <substring>`. Three placements recorded:

| Shot | New placement | Notes |
|---|---|---|
| `s011` | loc (0.30, 3.95, 1.30), target (0.30, 1.23, 1.10), 55 mm | the old aim point sat near z ≈ 4 in a 5.5 m tall frame, so a person was unreadable; dropping the aim to z 1.10 is what put 苏念 and the pot in the lower half. Ramp `builder` 1.636–6.0. |
| `s012` | loc (1.20, −5.90, 1.60), target (0.90, −3.45, **2.20**), 30 mm | raised from z 2.45; `--hide Bead` (curtain strands are surface, not structure) |
| `s002d` | loc (1.58, −3.68, 1.00), target (1.08, −4.32, 0.82), 50 mm, `--ramp hug`, `--subject Stall_Pot` | the wall behind won the "largest group" contest; a prop insert needs an explicit subject. Ramp 0.602–1.585. |

### 4.3 Five clips rendered (34 min GPU, 01:05–02:05 wall)

`s009m` 00015 (396 s) · `s010m` 00016 (416 s) · `s011m` 00017 (406 s) · `s002d` 00018 (406 s) ·
`s012m` 00019 (406 s) — 2030 s of clip time, plus keyframe re-rolls and one rejection in the same hour.
Keyframes accepted: `s010c` 00036, `s009c` 00037, `s011c` 00039, `s002e` 00041 (00040 rejected — a
punched-out hole), `s012b` 00042. `win/shots_laotang_ep01.json` is now 17 entries.

Budget from this: **~410 s per 5 s clip** on 5B, which is the number to quote, not the wall clock.

### 4.4 `bin/doctor.sh` — clean

```
BOUNDARY CLEAN — nothing leaked, nothing undeclared
```

All PASS. Two known, recorded items: `~/.nv/ComputeCache` 337 M pre-existing, `~/Desktop/AP3Model`
18 G pre-existing and not this project; one WARN — Docker data-root at `/var/lib/docker` (Oracle
images, stopped) whose wipe coverage is owed to `DELETE.md`. The run also prints
`info assets / provenance files 116 / 3` (it was 110 before the voice pass) — see §3.1 for what that
number means and does not mean.

Re-run on 14 Nov during the verification pass: identical output, so this is reproducible, not a
one-off. Re-run again after the voice pass, including after a Rule 0 failure it caught
(`app/venv-tts/bin/python3` was a symlink to `/usr/bin/python3`): `BOUNDARY CLEAN`, exit 0 (§9.13).

---

## 5. Housekeeping — done 14 Nov (kept as the checklist that was executed)

`work/story/shotlist_laotang_ep01.md` is **finished** — 19/19 marked clip-done, render queue closed,
cost closed. Two other docs are still stale:

### `versions.md`

| Line | Now says | Should say |
|---|---|---|
| 17 | "Resume at **Phase 3 (motion)**" | resume at **Phase 4 (voice)** |
| 28 | Phase 2 = "19 of 19 exist; `s010`/`s011` rejected pending rig fixes" | all 19 accepted; `s010`/`s011` re-rolled 14 Nov (`s010c` 00036, `s011c` 00039) |
| 29 | Phase 3 = "14 of 19 units rendered" | "**DONE — 19 of 19**, 18 canonical files" |
| 36 | "Blender work still outstanding is itemised in `nextblender.md` — the posed-VACE guides, the two CU re-rigs, the `s002d` stall insert…" | the CU re-rigs and the `s002d` insert are **done**; what remains is the character pass (blocked, Rule 3) and the mask/ID pass |
| 106, 368, 507 | "tighten to `near ≈ 0.75·d`, `far ≈ 2.0·d` for CUs" | the **measured-subject** rule from §4.1 — `0.75·d` was a guess from before the fix |
| 242 | "Phase 3 — Motion (IN PROGRESS — resume here)" | "DONE 14 Nov 02:05" |
| 504 | "Next actions — picture, 14 Nov" | replace with the Phase 4 handover in §6 below |
| 533–537 | "Phase 4 — Voice (not started) … **Do not start this before Phase 3 reports**" | Phase 3 has reported; Phase 4 is the current phase, and its first step is the licence gate (§6) |
| 591–597 | "Resuming Phase 3 (motion) — **the current one**" … "the set and the 8 keyframes are finished" | "Resuming Phase 4 (voice) — the current one"; 17 keyframes, 18 canonical clips |

Also missing: a **Round 4** section (the ramp diagnosis with the **6 → 76** span numbers and the
`SUBJSTAT` caveat, `retarget_rig.py`, `--hide Bead`, the `s002d` rig), and a rewrite of gotcha 11 to the
measured-subject wording.

### `nextblender.md`

- `depth_range()` must **hug the measured subject** for rigs under ~1.5 m — the `0.75·d`/`2.0·d`
  approximation is retired; point at `win/blender_depth_rerange.py` as the reference implementation.
- `retargets.json` holds three placements (`s011`, `s012`, `s002d`) that should be folded into `SHOTS`
  the next time the set is legitimately rebuilt — nobody needs a 13th/14th camera today.
- `s012` still has **no stall**; the beat is carried by the off-screen queue. Record that as a decision,
  not a to-do.
- **`s012` has three different target-z values in circulation** — 1.25 in the saved set (and line 23 of
  this file), 2.20 in `retargets.json` and the shotlist, ~2.45 in gotcha 9 of this doc. State once, in
  one place, that **2.20 is the canonical render** and 1.25 is what the saved set happens to hold.

### One more doc debt

- `AGENTS.md` names `C:\Users\yueju\Desktop\manju` as the Windows root; this repo is
  `C:\Users\admin\Desktop\manju`. The rule is right, the path is stale — an agent that follows AGENTS
  literally writes outside the boundary. Fix the path, not the rule.

The provenance discipline is now automated (§3.1), but the *habit* still has to be written down: add
"after any render batch: `python win\mirror_provenance.py`, then `bin/doctor.sh`" to `versions.md` when
you write the Round 4 section. `doctor.sh` will fail until you do, which is the point.

---

## 6. Phase 4 — voice. Done on 14 Nov, in this order

Everything below was executed and is on disk. The order matters: each gate was passed before the thing
it gated, and each install left a receipt in `app/os/installed.tsv`.

### 6.1 Licence gate — three weight rows, not four

| Row | repo | SPDX | licence link | size |
|---|---|---|---|---|
| `qwen3_tts_voicedesign_1_7b` | `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign` | Apache-2.0 | `github.com/QwenLM/Qwen3-TTS/blob/main/LICENSE` | 4.52 GB (12 files) |
| `qwen3_tts_base_1_7b` | `Qwen/Qwen3-TTS-12Hz-1.7B-Base` | Apache-2.0 | same | 4.54 GB (12 files) |
| `faster_whisper_small` | `Systran/faster-whisper-small` | MIT | `github.com/SYSTRAN/faster-whisper/blob/master/LICENSE` | 486 MB (5 files) |

Three corrections against the plan this document carried earlier:

- **The separate Tokenizer repo is redundant.** `speech_tokenizer/model.safetensors` is byte-identical
  inside all three Qwen3-TTS repos (`836b7b35…`, 682,293,092 B). Fetching a model repo whole gets the
  tokenizer with it, so there is no fourth row and no fourth download.
- **No HF repo ships a `LICENSE` file.** The licence lives in the model-card front-matter
  (`license: apache-2.0`), which is what the card reports; the manifest points `license_url` at the
  upstream GitHub LICENSE so the text is one click away and cannot be silently revised.
- **`faster-whisper-small`, not medium.** 486 MB versus 1.53 GB. ep01 has six utterances; small is
  enough for intelligibility and word timing. Swap the row if ASR quality disappoints.

### 6.2 Dependency approval — and two things that were not what the plan said

Approved: a second venv (`app/venv-tts`) with its own torch, plus the `sox` apt package, both recorded
through `bin/record-install.sh`. Installed:

```
app/venv-tts   Python 3.12.3   (5.9 GB)
  torch 2.14.1+cu130        torchaudio 2.11.1+cu130     transformers 4.57.3
  accelerate 1.12.0         qwen-tts 0.1.1              librosa 1.0.1
  soundfile 0.14.0          onnxruntime 1.32.0          einops 0.8.2   sox 1.5.0
apt: sox 14.4.2             (the binary; pysox shells out to it)
```

Two corrections, and one deliberate non-install:

- **`sox` is not `libsox-dev`.** The PyPI package is sdist-only (no wheel of any kind, pure python, builds
  fine), and it does not link against libsox — it shells out to the `sox` executable. So the correct apt
  package is **`sox`**, and headers would have been useless.
- **`torchaudio` has no 2.14 build, anywhere.** PyPI stops at 2.11.1; the cu130 index stops at 2.11.0+cu130;
  only the `test` channel has 2.11.1+cu130. Installed that with `--no-deps` against torch 2.14.1 and
  verified `import torchaudio.compliance.kaldi` succeeds — it does, on this machine, today. This matters
  more than it looks: `qwen_tts/core/__init__.py` imports the **25 Hz** tokenizer unconditionally, and
  `vq/speech_vq.py` imports both `torchaudio.compliance.kaldi` and `sox`. The 12 Hz path never calls
  either, but `import qwen_tts` fails without them — so both are load-bearing for *import*, not for
  inference. Re-test that pair after any torch upgrade.
- `flash_attention_2` was **not** built. The model prints a warning and uses the manual PyTorch path;
  a 1.7B model on GB10 does not need it. `gradio` was **not** installed (demo-only, `--no-deps`).

### 6.3 `MANIFEST.json` learned directory models

Qwen3-TTS is a directory (weights + `config.json` + `speech_tokenizer/`), not a single file like the
picture models. Each new row carries a `files[]` list with its own `sha256`, and `restore.sh` walks it:
`models/<dir>/<name>/<file>`. Single-file rows are unchanged and still restore exactly as before
(`restore.sh ae` was re-run to prove it). The Rule 2 gate now requires a 64-hex sha256 for **every** file,
so a directory model cannot slip in with an unchecked config.

### 6.4 The runner — two files, not one

| File | Runs on | Does |
|---|---|---|
| `spark/app/tts/render_lines.py` | Spark, `app/venv-tts/bin/python` | loads the model once, renders each line, writes `work/<ep>/vo/*.wav` + `VO_MANIFEST.json`, **appends provenance** (Rule 1 belongs on the machine that produced the asset) |
| `win/tts_lines.py` | Windows | validates the spec, uploads it, streams the render, pulls every wav into `work/<ep>/vo/`, re-verifies each sha256, prints the table |

The line spec is `work/story/vo_lines_laotang_ep01.json` — text, speaker, seed, instruct, window. Text is
copied character-for-character from the shotlist's audio map; the instruct text is what makes 苏念's VO and
her dialogue two presets rather than one voice.

### 6.5 What was rendered

Six utterances, four speakers, 14.4 s total, 24 kHz mono PCM_16, −19…−26 dBFS, no clipping:

| id | speaker | line | seed | rendered | slot |
|---|---|---|---|---|---|
| vo01 | 苏念 (VO) | 我妈留给我的，只有这锅汤。 | 410001 | 3.12 s | 0.0–7.5 |
| vo02 | 苏建国 | 这店，从今天起不姓你。 | 410002 | 4.40 s | 11.0–16.5 |
| vo03 | 苏念 | 锅，我拿走。 | 410001 | 1.92 s | 33.0–38.0 |
| vo04 | 小满 | 姐，今晚吃什么？ | 410004 | 1.52 s | 56.0–57.8 |
| vo05 | 苏念 | 火锅。 | 410001 | 1.04 s | 57.9–59.0 |
| vo06 | 顾衍 | 这锅汤，我找了十五年。 | 410006 | 2.40 s | 76.0–82.0 |

**The slots are shot windows, not speech lengths.** vo01 fills 3.1 s of a 7.5 s window, vo03 1.6 s of 5.0 s,
vo06 3.1 s of 6.0 s. That is a mix decision, not a render defect: either let the silence sit under the
picture (correct for a slow opening) or re-render with a slower instruct and `--overwrite`. Do not stretch
audio to fill a slot in the edit.

### 6.5.1 Measured 14 Nov (first pass) — `app/tts/measure_lines.py` -> `vo/MEASURE.json`

`faster-whisper-small` round-trip + `librosa.pyin` (floor 45 Hz, since 60 Hz clamped both a male voice
and a female line with octave errors). Speech is the loud part between lead and tail silence.

| id | speaker | speech | slot | fill | ch/s | F0 med (p10-p90) | ASR |
|---|---|---|---|---|---|---|---|
| vo01 | 苏念 | 2.94 s | 7.5 | 39% | 3.74 | 171 (51-198) | 0/11 |
| vo02 | 苏建国 | 4.12 s | 5.5 | 75% | 2.18 | 133 (50-150) | 1/9 |
| vo03 | 苏念 | 1.44 s | 5.0 | 29% | 2.77 | **279** (243-329) | 1/4 |
| vo04 | 小满 | 1.47 s | 1.8 | 82% | 4.09 | 344 (296-473) | 0/6 |
| vo05 | 苏念 | 0.68 s | 1.1 | 62% | 2.96 | **217** (163-262) | 0/2 |
| vo06 | 顾衍 | 2.92 s | 6.0 | 49% | 3.08 | **59** (53-72) | 1/9 |

**Verdict 1 — the delivery is not rushed, so the slots are the problem, not the read.** Every line sits
at or below conversational Mandarin (~4 ch/s); vo02's 2.18 is the instructed `语速慢，咬字重` and it is
the most-slot-filled line at 75%. Nothing is clipped, nothing needs stretching. Place with **offsets
inside each slot** (vo01 2.94 s in 7.5 s, vo03 1.44 s in 5.0 s, vo06 2.92 s in 6.0 s) and let the silence
carry the picture. Re-rendering slower to *fill* a window would make an already-slow read slower.

**Verdict 2 — the instruments clear intelligibility and distinctness, and fail casting on two counts.**

* Intelligible: every line differs by ≤1 character and every difference is a homophone the ASR chose
  (锅->郭, 这店->这殿, 找->招). Nothing was mispronounced.
* Distinct by pitch: 小满 344 > 苏念 171-279 > 苏建国 133 > 顾衍 59. No two speakers collide.
* **顾衍 is 59 Hz.** Probed at an 80 Hz floor he returns *no voiced frames at all*, so that is the real
  fundamental, not an octave slip. 59 Hz is a sub-bass rumble, not a quiet man of thirty — it will read
  as a slowed tape. Re-render `vo06` with an age/pitch anchor.
* **苏念 is three different women**: vo01 171, vo03 279, vo05 217 Hz. A 108 Hz spread is not delivery;
  the shotlist says the VO and her dialogue are one voice with two registers. VoiceDesign derives the
  voice from the instruct text each time and has no speaker identity, so this has to be pinned
  deliberately — either re-render vo03/vo05 against vo01's preset, or decide the registers are wanted.
* Not measurable by any of this: 苏建国's 沙哑/方言. That one still needs an ear.

One-click listen: `work/laotang_ep01/vo/audition_all.wav` (17.40 s, vo01->vo06, 0.5 s gaps).

### 6.5.2 Re-rendered 14 Nov — two casting defects, and the guard that rejected a "fix"

Three lines were re-rendered (`--only vo03,vo05,vo06 --overwrite`). `vo01`, `vo02` and `vo04` are
byte-identical to their first render, so the pre-fix table above still describes them.

| id | F0 before -> after | why | outcome |
|---|---|---|---|
| vo03 | 279 -> **208 Hz** | same woman as vo01 (171), not a second one | closer; ~3.5 semitones of register shift, accepted |
| vo05 | 217 -> **174 Hz** | same | **converged** — 3 Hz from vo01 |
| vo06 | 59 -> **75 Hz** | 59 Hz is a sub-bass artefact, not a man of thirty | intelligible and better; still low — see below |

vo03 and vo05 now share vo01's seed (410001) and carry the clause `和旁白是同一个人`. That is the
only identity lever VoiceDesign offers: it derives the voice from the instruct text and has **no
speaker state to hold**. If 苏念 must be unmistakably one person, the honest route is cloning from
vo01 with `qwen3_tts_base_1_7b` (declared, 4.54 GB, not downloaded) — not more prompt tuning.

vo06 took three attempts and **the CER guard rejected the best-sounding one**: a punchier instruct
reached 85 Hz but the ASR heard `结果他我找了15年` — 5 of 9 characters wrong. Reverting to the 75 Hz
read restored 0/9. Pitch and intelligibility moved against each other, and intelligibility won.
**75 Hz is still below a natural male voice**; that is left for an ear rather than iterated blind.

Final: `vo01` 171 / `vo02` 133 / `vo03` 208 / `vo04` 344 / `vo05` 174 / `vo06` 75 Hz; every line
≤1 character of ASR error, all homophones; fill 35–82% of its window.

**Two bugs found by doing it.** `render_lines.py --only` rewrote `VO_MANIFEST.json` from the current
run's results only, which cut the six-entry record to one while all six wavs stayed on disk — it
merges now, and `app/tts/rebuild_manifest.py` reconstructs a truncated manifest from the wavs (used
here: 6/6, every hash re-verified). `app/tts/prune_provenance.py` drops superseded provenance
entries, because `--overwrite` appends without deleting — that is how vo05 reached two.

### 6.6 Still open

1. ~~**Measure it.**~~ **Done 14 Nov** — `app/tts/measure_lines.py`, results in `MEASURE.json` and §6.5.
   Intelligibility is fine (≤1 character differs per line, every difference a homophone). The
   instruments found two casting problems that no one has heard yet — see §6.5.1.
2. **Lipsync** — only units 17 and 19 are sustained face-on dialogue, and 苏念 has no face in ep01. It is
   optional, not next by default.
3. **`qwen3_tts_base_1_7b` is declared but not downloaded** (4.54 GB). ep01 designs voices from text; Base
   is for cloning from a reference clip, which nothing in this episode needs. `bin/restore.sh
   qwen3_tts_base_1_7b` fetches it the day something does.

---

## 6.7 Assembly — Phase 5 exists as of 14 Nov (final record in §11)

`win/assemble.py` + `win/tools/ffmpeg` produce a delivery master from an EDL. The first one is
`work/laotang_ep01/cut/laotang_ep01_conform.mp4`: **90.00 s, 1080×1920, 24 fps, 2160 frames,
41.7 MB**, with captions, the 片头 title block and the per-episode AI label burned in.

**ffmpeg is repo-local, not installed.** `win/get_ffmpeg.sh` fetches a static build into
`win/tools/ffmpeg`; nothing touches PATH, Program Files or the registry, so Rule 0 holds and the
binary that made a master is the binary still sitting next to it. The build must be GPL-family:
libass (captions) and freetype/fribidi (drawtext, the Art.27 marks) are both load-bearing.

**What the assembler refuses to do** — each is a rule, not a warning:

- no clip without a provenance entry (Rule 1) — it found 19/19 by joining `shot_id` + the recorded
  output filename, which is not the on-disk name;
- no global master containing a unit whose *recorded* territory is restricted (Rule 5);
- no `--final` while `compliance.program_number` is empty — the number comes from the platform on
  review, and inventing it would be a fake regulatory mark;
- no silent duration drift: the encoded picture must match the cut within 0.25 s.

**Two bugs found by checking, both mine, both worth remembering:**

1. **Timeline ≠ in-point.** The shotlist's "In–out" column is episode time (0–90 s). I first fed
   those numbers straight to `trim` as offsets *inside* each 5 s clip, so every unit starting after
   5.04 s trimmed to zero frames and the master came out 5.04 s long — with 90 s of audio, so the
   container looked correct. `edit.json` now has `in`/`out` (timeline) separate from `src_in`
   (offset inside the clip, default 0). The post-encode picture-duration assertion exists because
   of this: audio can carry a container on its own.
2. **ASS units are not pixels.** libass lays SRT out on a 288-high canvas, so `force_style` values
   are multiplied by 1920/288 = 6.67. `MarginV=120` put the captions 800 px up the frame — I spent
   a round hunting a "missing" subtitle that was rendering in the middle of the shot.
   `Fontsize=12` (~80 px), `MarginV=20` (~133 px) now sits where a vertical drama wants it.

**Two things the conform does not fix, because they are decisions:**

- **Units longer than a clip — resolved for four of six on 14 Nov.** Units 2, 4, 10, 12, 17, 18 each
  asked for more than the 121 frames (5.0417 s) a clip holds — 6.75 s short in total against 12.54 s of
  headroom in the other thirteen. Units 2, 4, 12 and 18 were cut back to their live 121 frames and the
  freed time given to the following unit (§11.3); **units 10 and 17 still hold 1.958 s each** (3.92 s
  total). Their neighbours are at 120/121 frames, so a re-time there needs a VACE continuation or a
  shorter episode. The shotlist says "no unit needs to be longer than 5 s" — the table disagreed with
  itself, and this is where that showed.
- **No bed, no SFX.** Everywhere nobody speaks the master measures −91 dB: digital silence. The
  shotlist's audio column (pot crash, rain, curtain beads, market ambience) has no assets behind it.

---

## 7. Blockers, with the smallest thing that clears each

Assembly is done, so the live blockers are the §11.7 table. History of everything cleared before it:

| Blocker | Smallest action |
|---|---|
| 顾衍 is 75 Hz — low for a man of 30, though intelligible | **an ear decides.** 85 Hz cost 5/9 intelligibility, so this is not worth iterating blind; cloning from a reference is the only further lever (§6.5.2) |
| 苏念 vo03 sits 37 Hz above vo01 | accepted as a register shift. Exact identity needs cloning with `qwen3_tts_base_1_7b` (4.54 GB, declared, not downloaded) — VoiceDesign has no speaker state (§6.5.2) |
| vo01 / vo03 / vo06 are shorter than their slots | a mix decision, not a defect: keep the silence, or re-render with a slower `instruct` and `--overwrite` (§6.5) |
| `qwen3_tts_base_1_7b` declared but not downloaded | only needed for cloning from a reference clip; `bin/restore.sh qwen3_tts_base_1_7b` when it is |
| `torchaudio` 2.11.1 against `torch` 2.14.1 | **verified working today** (that is the only build in existence); re-test `import torchaudio.compliance.kaldi` after any torch upgrade |
| Provenance drift | **cleared** — `win/mirror_provenance.py` + `MIRROR.json`; `doctor.sh` fails on drift (§3.1). Run the mirror after each batch |
| `COMFY_MEMORY_MAX` still 44 G | not needed — TTS runs in `app/venv-tts`, which never touches ComfyUI's memory |
| Kandinsky 6.0 Pro needs a ~20 KB ComfyUI core patch | **needs approval** — not on the ep01 path, do not do it for this episode |
| Jianying not installed | **`pyJianYingDraft` is installed** (`win/venv_jianying`, 0.3.1); only the app is missing — install it pinned ≤ 5.8, then open the draft (§11.4) |
| LoRA trainer not approved | out of scope; no unit needs a LoRA |
| `versions.md` / `nextblender.md` stale | **cleared 14 Nov** — both rewritten, plus the `AGENTS.md` path and this file's §3 voice table and §11 (Phase 5) |

---

## 8. Recipes (copy-paste)

```powershell
# Spark shell, always this shape. The password is NOT kept in this file: `spark_ssh.py` reads
# SPARK_PASSWORD from the environment, and a literal here would put it in the repo permanently.
cd C:\Users\admin\Desktop\manju
$env:PYTHONIOENCODING='utf-8'
$env:SPARK_PASSWORD = Read-Host 'spark password'   # 5.1-compatible; -MaskInput on PS 7+
python win\spark_ssh.py --timeout 280 'cd ~/Desktop/AIGC-Model && source env.sh >/dev/null && <cmd>'

# boundary check — before reporting done
python win\spark_ssh.py --timeout 120 'cd ~/Desktop/AIGC-Model && source env.sh >/dev/null && bin/doctor.sh'

# provenance: after any render batch, mirror it in and re-pin, then prove it
python win\mirror_provenance.py            # pull + rewrite spark/provenance/MIRROR.json
python win\mirror_provenance.py --check    # compare only, exit 1 on drift
python win\spark_ssh.py 'cd ~/Desktop/AIGC-Model && source env.sh >/dev/null && bin/restore.sh --provenance-only'

# clips, sequential submit → poll → pull → verify
python win\batch_clips.py --only s011m,s012m

# contact sheet (runs on the Spark venv — Windows python has no PIL/ffmpeg)
python win\spark_ssh.py 'cd ~/Desktop/AIGC-Model && source env.sh >/dev/null && venv/bin/python tmp/board.py work/output/board_g.jpg s011m=work/output/manju_clip_00017_.mp4 ...'

# move/create a camera and re-render depth, never saving the set
python win\blender_retarget_rig.py --shot s011 --loc 0.3,3.95,1.3 --target 0.3,1.23,1.1 --lens 55
python win\blender_retarget_rig.py --shot s012 --loc 1.2,-5.9,1.6 --target 0.9,-3.45,2.2 --lens 30 --hide Bead
python win\blender_retarget_rig.py --shot s002d --loc 1.58,-3.68,1.0 --target 1.08,-4.32,0.82 --lens 50 --ramp hug --subject Stall_Pot

# voice (Phase 4) — driver on Windows, inference on the Spark under app/venv-tts
python win\tts_lines.py --dry-run                 # validate the spec, touch nothing
python win\tts_lines.py                           # render all six lines, pull + verify
python win\tts_lines.py --only vo01,vo03          # re-render just these
python win\tts_lines.py --only vo01 --overwrite   # force, e.g. after changing the instruct
python win\tts_lines.py --pull-only               # fetch + verify what the Spark already has
# then, always, because provenance gained entries:
python win\mirror_provenance.py

# assembly (Phase 5) — Windows only, Rule 4
python win\assemble.py --dry-run                  # check the EDL, touch nothing
python win\assemble.py --allow-hold --out work/laotang_ep01/cut/laotang_ep01_conform.mp4   # 90 s master + report
# --final is refused until compliance.program_number is real; do not invent one
win\venv_jianying\Scripts\python.exe win\build_jianying_draft.py   # 3 tracks, absolute local paths

# delivery check — container, mix, captions, draft, freeze-fills (needs no Jianying)
python win\verify_delivery.py                     # ~1 min incl. frame pairs
python win\verify_delivery.py --skip-frames       # ~1 s, text and spec only

# one weight at a time, or everything declared in the manifest
python win\spark_ssh.py --timeout 1800 'cd ~/Desktop/AIGC-Model && source env.sh >/dev/null && bin/restore.sh qwen3_tts_voicedesign_1_7b faster_whisper_small'
```

The voice path runs on the Spark because that is where the weights are, but the wavs are pulled to
`work/laotang_ep01/vo/` — assembly happens on Windows (Rule 4). `bin/restore.sh` with **no arguments**
restores every declared row, which now includes `qwen3_tts_base_1_7b` (4.54 GB, cloning only); pass ids
when you do not want that.

**PowerShell strips double quotes from a remote command.** Use quote-free commands
(`grep -m1 FREEFIELD_TOKEN= … | cut -d= -f2-`). Heredocs are unusable — write helper scripts to
`work/.btmp/*.py` and run them. `GET /jobs` (`work/.btmp/listjobs.py`) before submitting anything, so
two sessions never render the same shot twice. **`work/.btmp/` does not exist until something creates
it** — a `cp` there once failed silently and a drift test appended to the live provenance file instead.
`mkdir -p work/.btmp` first, and treat a non-zero exit from a `cp` as fatal.

---

## 9. Gotchas not to relearn

1. **Measure the subject, not the camera.** A CU depth window sized by camera distance flattens the
   subject to a disc, and the ControlNet turns the disc's edge into a hoop/wire/cable.
2. **The guide decides pose and scale; the prompt decides material, light and weather.** A pose the
   set does not contain cannot be prompted into being (proved by `s002c` and by the alley).
3. **"Largest ray-cast group" is right for a person, wrong for a prop insert** — the wall behind wins.
   Use `--subject Stall_Pot`.
4. **Surface is not structure.** Bead curtain strands and steam get hidden from depth passes; the
   builder already hides `FX_Steam`.
5. **Clay beauty carries no material,** so location continuity comes from identical anchor noun phrases
   in every prompt: "worn grey plaster alley wall", "dark painted wooden back door", "cool blue-green
   night grade".
6. **Re-posing/re-ranging never saves the set.** Assert the `.blend` sha256 (`1b927477…`) is unchanged
   after every Blender run.
7. **Keyframe timing:** ~9 s idle, 250–400 s behind a clip. Clip: 400–430 s. The queue is the cost.
8. **Two sessions once rendered the alley twice** (00021/00024/00025 vs 00026–00028). 00021/00024/00025
   are canonical.
9. **`set_huoguo_cameras.json` no longer matches** what the canonical `s012_depth_ctrl.png` was
   rendered from (target z 1.25 now vs ~2.45 then) — the parallel Blender agent re-saved the set at
   00:01:41. Trust `retargets.json` for the new placements. **2.20 is the canonical render**; 1.25 is
   just what the saved set holds.
10. Blender runs keep `BLENDER_USER_CONFIG`/`SCRIPTS` in `work\.btmp\`.
11. **`SUBJSTAT`'s "levels" number measures the gap from `z_hi` to `far`, not the subject's span.** A
    0.30 span-frac prints 167 while the subject actually spans 76 of 255. Quote 76; the ramp is fine,
    the label is not.
12. **Provenance is one file per episode, not one per asset, and it is pinned.** `restore.sh` rebuilds
    weights only; `spark/provenance/MIRROR.json` is what makes a stale mirror fail instead of look fine.
    After any batch: `win/mirror_provenance.py`, then `bin/doctor.sh` (§3.1).
13. **`python3 -m venv` creates an interpreter symlink out of the folder, and `doctor.sh` fails on it.**
    `app/venv-tts/bin/python3 -> /usr/bin/python3` is a Rule 0 violation by the letter of the rule and by
    the check. The main `venv/` does not have it because it was built with `--copies`. Either create venvs
    with `python3 -m venv --copies`, or replace that one symlink with a real copy of the interpreter
    (which is what `--copies` does) — `python` and `python3.12` stay as *relative* links to `python3`,
    which resolve inside the boundary and pass.
14. **`torchaudio` has no build matching `torch` 2.14 anywhere.** PyPI stops at 2.11.1, the cu130 index at
    2.11.0+cu130, and only the `test` channel carries 2.11.1+cu130. It was installed with `--no-deps`
    against torch 2.14.1 and `import torchaudio.compliance.kaldi` was verified — but that pairing is a
    known-unmatched pair, so re-test it after any torch upgrade instead of assuming it still holds.
15. **`qwen-tts` needs `sox` and `torchaudio` merely to *import*.** `core/__init__.py` pulls in the 25 Hz
    tokenizer unconditionally, and its `vq/speech_vq.py` imports both. The 12 Hz VoiceDesign path never
    calls them; a missing one still kills `import qwen_tts`. `sox` on PyPI is sdist-only and shells out to
    the `sox` binary, so the apt package is `sox` — not `libsox-dev`, which would have installed headers
    and no executable.
16. **Rendered speech is shorter than the shot window, and that is not a bug.** vo01 is 3.1 s inside a
    7.5 s slot. Windows in the audio map are cut lengths; silence under a slow opening is correct. If a
    line needs to be longer, change the `instruct` (slower delivery) and re-render — never time-stretch.
17. **`aformat … channel_layouts=stereo` costs 3 dB on a mono source.** Equal-power mono→stereo lands
    1/√2 in each channel, so a mix built with it ships 3 dB under the wavs it was measured from — which
    is inaudible as a defect and wrong as a delivery. Use `pan=stereo|c0=c0|c1=c0`. Found on ep01 on
    14 Nov, after the master had been signed off by every other check (§11.5).
18. **Verify the delivery, not the build log.** `python win\verify_delivery.py` is the only thing that
    checks the master, captions, wavs and draft against each other; the assembler's own report cannot
    see a 3 dB error or a mis-timed caption. Run it after any re-assembly (§11.6).
19. **Count frames, not seconds, when conforming.** A clip is 121 frames = 5.0417 s, so "5.5 s" is not a
    length any clip has. `assemble.py` used to compare `have - need` in seconds and hand `trim=duration=`
    a `%.3f` value; whether a unit got 83 or 84 frames came down to which side of a rounding edge the
    decimal fell on, and one frame of drift per unit is invisible in a 90 s file. It now rounds each unit
    to whole frames, trims 1 ms inside the last wanted frame, and reports slack as `+38fr`. The four
    holds went away by moving cut points (§11.3), not by this — this just stops the conform from
    deciding frame counts by luck.

---

## 10. First 30 minutes of the next session

1. Read this file, `AGENTS.md`, and `versions.md` §"Phase 5 — Assembly". §11 of this file is the
   latest state; §1–§10 are the record of how ep01 got here.
2. **Run the provenance check** (§3.1): `python win\mirror_provenance.py --check`, then `bin/doctor.sh`.
   The 14 Nov pin is `laotang_ep01 = f342b5a7…`, 66 entries. If anything rendered since, re-mirror before
   doing anything else — doctor will be red until you do.
3. ~~Do §5: update `versions.md` and `nextblender.md`.~~ **Done 14 Nov** — with `AGENTS.md`, `STACK.md`
   and this file. §5 is history; do not redo it.
4. **Listen — but the measurement already did most of the review.** Play
   `work/laotang_ep01/vo/audition_all.wav` (all six, 17.40 s). §6.5.1–§6.5.2 cleared intelligibility
   and distinctness, so the only things left for an ear are: does **顾衍 at 75 Hz** pass as a man of
   thirty, is **苏念's vo03 at 208 Hz** close enough to vo01's 171 Hz, and did 苏建国's 沙哑/方言 land.
   To change one: edit that line's `instruct` in
   `work/story/vo_lines_laotang_ep01.json`, then `python win\tts_lines.py --only voNN --overwrite`.
   `--overwrite` re-renders and appends a provenance entry; the old one has to be removed by hand
   (gotcha: vo05 already carries two).
5. ~~**Measure the voice, not just hear it.**~~ **Done 14 Nov** — `spark/app/tts/measure_lines.py`,
   results in §6.5.1. Re-run it only after a line is re-rendered:
   `app/venv-tts/bin/python app/tts/measure_lines.py --episode laotang_ep01` (≈40 s, ASR on CPU).
6. ~~Only then assembly.~~ **Done 14 Nov** — `win/assemble.py` produced the 90 s conform, and
   `win/build_jianying_draft.py` (repo-local `win/venv_jianying`) produced the draft. See §11. The
   remaining assembly work is a **sound pass** and the **two freeze-filled units** (10, 17), both
   decisions in §7 — not code.

---

## 11. Phase 5 — assembly, done 14 Nov (later the same day)

This section supersedes §5, §6.6, and every "assembly comes next" sentence above.

### 11.1 The master

`win/assemble.py` + repo-local `win/tools/ffmpeg` (N-128889, GPL build — libass/freetype/fribidi are
load-bearing) → `work/laotang_ep01/cut/laotang_ep01_conform.mp4`:

| | |
|---|---|
| duration | **90.00 s** (2160 frames @ 24 fps), picture and container agree |
| size | **41.7 MB**, 1080×1920 |
| sha256 | **`8710fdc0…`** — final encode, 14 Nov (after the −3 dB audio fix and the four re-timed units). Earlier: `35966a48…` pre-retime, `ffcffcb2…` pre-audio-fix |
| audio | 48 kHz stereo AAC 192k; peak **−3.7 dBFS**, mean −29.4 dBFS (see §11.5) |
| burned in | captions (SRT), 片头 title block, per-episode AI label |
| provenance join | 19/19 units matched via `shot_id` + the *recorded* output filename (not the on-disk name) |
| `final` | **false** — `compliance.program_number` is empty, so `--final` is refused by design |

The assembler's refusals are rules: no clip without provenance; no global master containing a
restricted-territory unit; no `--final` without a real program number; no encoded picture that drifts
more than 0.25 s from the cut.

### 11.2 The two defects found while building it

1. **Timeline ≠ in-point.** The shotlist's "In–out" column is episode time; feeding it to `trim` as
   an offset inside a 5.04 s clip trimmed every late unit to zero frames and produced a 5.04 s master
   that *looked* correct because 90 s of audio carried the container. `edit.json` now separates
   `in`/`out` (timeline) from `src_in` (offset inside the clip), and the post-encode duration
   assertion exists because of it.
2. **ASS units are not pixels.** libass lays out on a 288-high canvas, so `force_style` values are
   multiplied by 6.67: `MarginV=120` put captions 800 px up the frame. `Fontsize=12` (~80 px) and
   `MarginV=20` (~133 px) is where a vertical drama wants them.

### 11.3 Holds — 6.75 s down to 3.92 s, by moving four cut points

Six units asked for more than the 121 frames (5.0417 s) a clip holds. `--allow-hold` freeze-fills the
tail, but every one of the six tails still had real motion (21–39 dB between frames 0.25 s apart), and
**all six held frames contain steam** — the one thing a viewer reads instantly as a still. So the
operator re-timed four of them on 14 Nov.

The mechanism: each held unit is cut back to its live 121 frames and the freed time is given to the
**following** unit, which has unused footage. Only that one cut point moves; the episode stays 90.00 s
and no caption or VO time changes.

| Unit | Shot | was | now | following unit |
|---|---|---|---|---|
| 2 | `s011m` | 132 fr, 0.458 s frozen | **121 fr** | 3 → 83 fr (3.46 s) |
| 4 | `s003m` | 132 fr, 0.458 s frozen | **121 fr** | 5 → 95 fr (3.96 s) |
| 10 | `s001m` | 168 fr, **1.958 s frozen** | 168 fr | — none available |
| 12 | `x002` | 144 fr, 0.958 s frozen | **121 fr** | 13 → 119 fr (4.96 s) |
| 17 | `s009m` | 168 fr, **1.958 s frozen** | 168 fr | — none available |
| 18 | `s002d` | 144 fr, 0.958 s frozen | **121 fr** | 19 → 71 fr (2.96 s) |

**3.92 s of held frame remains: units 10 and 17, 47 frames each.** Their neighbours (9, 11, 16) sit at
120 of 121 frames, so there is nothing to borrow — the proper fix is a VACE continuation on the Spark
(Wan 2.2 VACE is in the stack for exactly this), or a shorter episode. Until then the holds stand.
`assemble_report.json` now records `frozen_frames` alongside `frozen_seconds`.

Re-timing means re-running `win/assemble.py` and rebuilding the draft; the four new cut points were
verified against their source clips (32–33 dB to the incoming shot, 9–12 dB to the outgoing one).

**The re-time and the frame counting are two separate fixes.** The holds existed because six units were
genuinely longer than 121 frames — no arithmetic could have made them fit. What the arithmetic *did* get
wrong was the other side of it: `assemble.py` measured unit lengths in seconds and let `trim=duration=`
round, so whether a unit came out 83 or 84 frames depended on a decimal. It now counts frames first and
trims 1 ms inside the last wanted frame — see gotcha 19.

### 11.4 The draft

`win/build_jianying_draft.py`, run with `win\venv_jianying\Scripts\python.exe` (Python 3.12,
pyJianYingDraft 0.3.1 — the Rule 3 approval, gitignored). Output:
`work/laotang_ep01/jianying_drafts/laotang_ep01/{draft_content.json,draft_meta_info.json}`.

- 3 tracks, 90.0 s, 1 video material + 6 audio materials, SRT captions imported
- picture = the conform master; the six VO wavs sit at their slot starts (§6.5)
- **every media path is absolute and local** — `C:\Users\admin\Desktop\manju\work\laotang_ep01\…` —
  which is what Rule 4 exists to guarantee

**Unverified:** Jianying is not installed on this machine, so nobody has opened the draft. Validity is
checked at the JSON level only. `plan.md` §7.5 asks the operator to pin Jianying ≤ 5.8 before trusting
the generator, because draft-schema changes between versions would break it silently.

`work/laotang_ep01/delivery/` holds a **second copy** of the master plus the SRT, `VO_MANIFEST.json`
and `assemble_report.json`. It is **gitignored on purpose** — a derived handoff bundle, not a source
of truth, because tracking it would give two `assemble_report.json` files that diverge the moment the
holds are re-timed. `cut/` is canonical; the draft references that path.

### 11.5 The −3 dB defect — the mix shipped quieter than the voice pass

Found on 14 Nov **by verifying, not by listening**. `assemble.py` converted each mono wav with
`aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo`. That conversion equal-power
spreads a mono source and lands **1/√2 = −3 dB in each channel**, so every line shipped 3 dB under the
level §6.5.1 measured: peak −6.7 dBFS, mean −32.4 dBFS.

The fix is `pan=stereo|c0=c0|c1=c0` — copy, not spread. The rebuilt master is **exact** against
`MEASURE.json` on all six lines (−19.0, −25.7, −21.0, −20.5, −20.1, −22.2 dBFS), with peak **−3.7 dBFS**,
mean −29.4 dBFS, still 90.00 s (41.7 MB in the final encode). Master sha256 **`35966a48…`** at that
point — the pre-fix master was `ffcffcb2…`; the current one is `8710fdc0…` after the §11.3 re-time.
The draft was rebuilt against it: same path, so nothing else in the draft changed.

Two lessons, both now in the checks: a level error is inaudible as a *defect* (it sounds like a quiet
mix), so it has to be measured against the wavs; and the mono→stereo conversion is the last place
anyone looks.

### 11.6 `win/verify_delivery.py` — what can be checked without Jianying

The app is not installed, so "the JSON parses" was the only evidence the delivery was coherent. This
closes that gap from the outside:

```
python win\verify_delivery.py                 # ~1 min, includes the frame checks
python win\verify_delivery.py --skip-frames   # ~1 s, text and spec only
```

| Group | What it proves |
|---|---|
| `container.*` | ffprobe truth: 90.000 s, 1080×1920, 24 fps, 2160 frames, exactly one audio stream |
| `mix.*` | per-line level against `MEASURE.json` (±1 dB), onset vs the spec window, no sound outside a declared window, peak headroom |
| `srt.*` | cue starts on the window, covers the wav, text matches the spec character for character, no overlaps |
| `draft.*` | every media path absolute and **inside the repo** (Rule 4), every file present, the video points at the canonical master, segment times and caption text equal the SRT |
| `hold.*` | the freeze-fills are frozen: frozen frame pair ≥ 45 dB, live control pair < 45 dB |

Two warnings are real and deliberately left alone:

- **`vo03` is 51% sound.** The read has a **0.79 s pause after「锅」** — measured in the wav, not the
  mix. §6.5.1's 2.29 ch/s averaged that pause in; the spoken rate is nearer 4 ch/s. Listen before
  "fixing" it: a beat there is good acting.
- **`vo05`'s caption runs 0.11 s past its slot**, because the slot is 1.10 s wide, `target_seconds`
  says 0.9 s, and the wav is 1.04 s. Bookkeeping, not a delivery defect — the caption still ends
  inside unit 13.

A check earns its place by failing: the level check is what found the −3 dB, and the PSNR pairs
separate 57.2 / 58.9 dB (frozen) from 24.1 / 12.8 dB (live control) on the two remaining holds.

### 11.7 What is left for ep01

| Item | Kind | Next action |
|---|---|---|
| **No bed, no SFX** — non-speech is −91 dB | asset work | licensed ambience/music/SFX + provenance; the shotlist's audio column (pot crash, rain, beads, market) has no files behind it |
| **Two freeze-fills** (units 10, 17 — 1.958 s each) | editorial / GPU | VACE continuation on the Spark, or cut those two units and accept an 86.08 s episode |
| **Draft unopened** | verification | install Jianying (≤5.8), open the draft, check media online |
| `--final` refused | platform gate | `compliance.program_number` after 确权 review |
| 顾衍 75 Hz / 苏念 registers / 苏建国 沙哑 | judgement | an ear on `audition_all.wav`; cloning (`qwen3_tts_base_1_7b`, not downloaded) is the only further lever |
| Lip-sync | optional | only units 17 and 19 are sustained face-on dialogue; 苏念 has no face in ep01 |
| Phase 6 characters | blocked | LoRA trainer not approved (Rule 3) |
