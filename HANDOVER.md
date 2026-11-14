# HANDOVER — 火锅店 / 《老汤》 pipeline

**Purpose.** This file is the whole state of the project, in phases, written so that a *new*
conversation or a different person can resume without re-deriving anything. Re-deriving costs
more tokens than this file costs to read.

**Read this first, then stop reading.** Do not re-read the whole repo. `AGENTS.md` is loaded
automatically by the harness; you do not need to open it.

Written 2026-11-13. Repo root: `C:\Users\admin\Desktop\manju`.

---

## Copy-paste bootstrap for a new conversation

> Read `HANDOVER.md` in `C:\Users\admin\Desktop\manju`, plus `work/sets/huoguo/README.md`.
> Phases 1–5 are DONE to a delivery master (picture, voice, conform, Jianying draft). What is left is
> judgement, not pipeline: an ear on three voices, a sound pass, and the editorial call on six
> freeze-filled units. See `newsession1.md` §11 and §7. Do not rebuild or re-render the set — it is
> finished and the user may have it open in Blender. Do not re-render a clip or a voice line without
> reading `newsession1.md` first. Follow the rules in `AGENTS.md`; anything outside the two writable
> roots is forbidden.

---

## Phase map

| Phase | Name | Status |
|---|---|---|
| 1 | Blender white-model set (8 cameras + alley + 4 CU rigs) | **DONE** |
| 2 | Keyframes via depth-ControlNet on the Spark | **DONE** — 19 of 19 exist; `s010`/`s011` re-rolled 14 Nov (`s010c` 00036, `s011c` 00039) |
| 3 | Motion — Wan 2.2 TI2V-5B clips | **DONE 14 Nov 02:05 — 19 of 19 units, 18 canonical files** (s001m serves units 3 and 10) |
| 4 | Voice / TTS | **DONE 14 Nov** — 6 utterances, measured, casting defects recorded (see "Phase 4 — Voice" below, and `newsession1.md` §6) |
| 5 | Assembly → Jianying draft (Windows only) | **DONE 14 Nov** — conform master (90.00 s) + Jianying draft in `work/laotang_ep01/jianying_drafts/laotang_ep01/`; Jianying is not installed here, so the draft has not been opened in the app yet |
| 6 | Characters (replace mannequins) | blocked: LoRA trainer not approved |
| 7 | Wipe / restore hygiene | ongoing, currently clean |

**Blender work still outstanding is itemised in `nextblender.md`** — the CU re-rigs and the `s002d`
insert are done (14 Nov); what remains is the character pass (blocked, Rule 3) and the mask/ID pass.
Read that file when the task is "build something in Blender"; this file stays the state of the pipeline.

---

## Machine facts

| Thing | Value |
|---|---|
| Windows workstation | repo root `C:\Users\admin\Desktop\manju`; Blender **5.2.3 LTS** at `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`, **EEVEE only** |
| Spark | `tdadmin@192.168.1.103`, root `~/Desktop/AIGC-Model`, password `P@ssw0rd` |
| Spark gateway | `http://192.168.1.103:8000`, bearer token = `FREEFIELD_TOKEN` in `~/Desktop/AIGC-Model/env.local` — read it over SSH, **never write it locally** |
| SSH helper | `python win/spark_ssh.py --timeout N '<cmd>'` with `$env:SPARK_PASSWORD` set |
| ComfyUI on Spark | `app/ComfyUI` @ commit `b894a86`; memory cap `COMFY_MEMORY_MAX=44G` (in `bin/up.sh`) |
| Blender on Spark | **not installed** (`which blender` empty). All Blender work is Windows-side. |
| Free disk on Spark | 1.6 TB |

### Gotchas that cost time already

1. **PowerShell strips double quotes** out of remote commands. Never send a remote command that
   relies on `"..."`. Two proven escapes: (a) avoid quotes entirely — `grep -c spdx file`;
   (b) base64 a local script and run it: `$b64=[Convert]::ToBase64String([IO.File]::ReadAllBytes("x.py")); python win\spark_ssh.py "echo '$b64' | base64 -d > ~/Desktop/AIGC-Model/tmp/x.py; cd ... && source env.sh >/dev/null && venv/bin/python tmp/x.py"`.
2. **Verify by file, not by exit code** — `set -euo pipefail` scripts wrapped in SSH return
   misleading codes. Use `grep -c`, `ls -l`, or `sha256sum`.
3. **SSH drops are normal** on long transfers. Anything long must be launched detached on the
   Spark (`bin/restore.sh` survived a socket close mid-download). Never assume a dropped SSH
   means a dead job.
4. **The gateway unloads models on lane switch.** First job on a lane pays the load time; that is
   not a performance bug.
5. **`/tmp` is forbidden.** Only genuinely system-owned entries exist there now. tmux runs on a
   socket under `$TMPDIR`.
6. **Manifest and remote config are pushed by base64** (`echo b64 | base64 -d > target`), because
   of gotcha 1. Always verify afterwards with a quote-free command.
7. **`source env.sh` before calling `tmux`.** The socket lives at `$TMPDIR/tmux-1000/default`; a
   `tmux` invocation before `env.sh` looks in `/tmp/tmux-1000`, silently fails to find the session,
   and **re-creates `/tmp/tmux-1000`** — a boundary leak caused by the attempt to fix something
   else. `work/.btmp/clean_tmux_tmp.sh` removes it with `rmdir` (never `rm -rf`), and refuses if it
   is not empty.
8. **ComfyUI is now on the LAN** (`COMFY_LISTEN` defaults to `0.0.0.0` in `bin/up.sh`, restart via
   `tmux kill-session -t manju && bin/up.sh`). `http://192.168.1.103:8188` gives the graph editor
   and the MaskEditor canvas. It also serves its output directory at
   `/view?filename=…&type=output`, which is the cheapest way to pull a generated frame or contact
   sheet to Windows. **It has no authentication** — the token on `:8000` does not cover it.
9. **Two coding agents, two different MCP config files.** OpenCode reads
   `~/.config/opencode/opencode.json` (`mcp.blender`, `type: local`, `command` as an **array**).
   Freebuff reads `~/.agents/mcp.json` (`mcpServers`, `command` as a **string** + `args`), which
   its Settings → MCP → *Add MCP server* panel writes for you. Neither agent reads the other's
   file, so configuring Blender in one does nothing for the other. The Blender side is a socket
   on `127.0.0.1:9876` from the `blender_mcp` addon (`blendermcp_server_running`), loopback only
   unless `allow_remote_connections` is enabled. Server: `uvx mcp-for-blender` (v2.2.9, addon
   1.8 = protocol 15;    server expects 16 and falls back — `uvx mcp-for-blender install-addon`
   clears the warning).
   **A third route needs no MCP config at all:** the addon's socket is plain newline-delimited
   JSON, so an agent with a terminal can talk to the *open* Blender window directly —
   `{"type": "get_scene_info"}` for state and `{"type": "execute_code", "params": {"code": "…"}}`
   for arbitrary Python. `execute_blender_code` is the MCP *tool* name, not a socket command; the
   socket answers `Unknown command type`. This was verified on 13 Nov against addon protocol 15.
   For building files, bypass the socket entirely: `blender.exe -b --factory-startup --python
   win/<builder>.py`, with `BLENDER_USER_CONFIG` and `BLENDER_USER_SCRIPTS` pointed into
   `work\.btmp\` — otherwise Blender writes prefs to `%APPDATA%\Blender Foundation`, outside the
   boundary (a headless run with those two set leaves Roaming untouched; checked).
10. **`find -newermt "-90 minutes"` is not a relative-time test.** GNU find parses that string as a
    *date*, not an offset, so it returns a hit that looks like a boundary leak and is not one — it
    cost a false alarm on 13 Nov. Use an absolute stamp and compare against the run's start:
    `find "$APPDATA/Blender Foundation" -newermt "2026-11-13 22:45:00"`, empty = clean. Before
    believing any hit, check that specific file with `stat -c '%y'`.
11. **A close-up rig with a wide depth ramp produces a flat white blob.** `depth_range()` spans
    `near…near+max(1.6·d, 3.2)`, which is right for a wide and wrong for anything under ~1.5 m: at
    0.73 m the face sits at 0.85–0.92 and has no gradient to guide on, so the model invents rings and
    wires around the head. `DEPTHSTAT std` passes anyway, because a white blob on a black background
    is high contrast. **Retired 14 Nov** — the `0.75·d`/`2.0·d` guess is superseded by the
    measured-subject rule in `win/blender_depth_rerange.py`: ray-cast the subject's real depth span,
    then `near = z_lo − 0.15·(z_hi − z_lo)`, `far = near + (z_hi − z_lo)/0.30`. This puts ~76 of
    255 levels on the subject (vs 6 before). See `newsession1.md` §4.1 and gotcha 11 there for the
    `SUBJSTAT` label caveat (it prints the complement, 167, not the span).
12. **Check `GET /jobs` before submitting.** Two sessions rendered the alley twice on 13 Nov
    (`x001`–`x003` as 00021/00024/00025 *and* 00026–00028) because neither knew the other had
    submitted. `work/.btmp/listjobs.py` lists the last jobs with shot id, status and output hash.

---

## Phase 1 — The set (DONE)

**Deliverable:** `work/sets/huoguo/`
**Builder:** `win/blender_set_huoguo.py` (edit here; never hand-edit the .blend)

**Second set, built 13 Nov:** `work/sets/houxiang/` — the 后巷 back alley, item 1 of
`nextblender.md`. Three rigs `x001`–`x003`, builder `win/blender_set_houxiang.py`, and the 旧铜锅
linked from `work/props/props_laotang.blend`. Note that `SIGHTLINE` cannot see collection
instances, so a linked prop needs the builder's `LINKCHECK` line instead.

| File | What |
|---|---|
| `huoguo_set.blend` | 362 objects, 8 cameras `CAM_s001`…`CAM_s008`, 344 meshes — the single source |
| `set_huoguo_cameras.json` | per-shot loc/target/lens **plus `depth_near_m` / `depth_far_m`** |
| `README.md` | rig table, ramp formula, failure-mode table, rig results — the engineering record |
| `sNNN_beauty.png` | clay render |
| `sNNN_depth.png` | raw depth (used for inspection/statistics) |
| `sNNN_depth_ctrl.png` | **blurred** depth — this is what actually feeds ControlNet |
| `sNNN_normal.png` | inspection only — proven *not* usable as a control signal |

### The two rules that make depth usable

- **Ramp per rig:** `near = 0.5 × d`, `far = near + max(1.6 × d, 3.2)` where `d` = camera-to-target
  distance. A single global ramp makes close-up shots flat.
- **Render depth through the Standard view transform, not AgX** — AgX compresses the near-white
  end and destroys the staircase the model needs.

### Guards built into the builder (do not remove)

- `SIGHTLINE sNNN CLEAR|BLOCKED frac=… first_hit=…` — ray-head count from camera to target.
  `BLOCKED` on s002 (`Pot_Rim` 0.856), s004 (`P_Sunian_Head` 0.973), s008 (`P_Buyer_Shoulders`
  0.979) are the subject itself and are **correct frames**, not defects.
- `DEPTHSTAT <shot> std=… OK|FLAT` — measured off the saved PNG, threshold std > 0.06. Current
  range 0.183–0.459, all OK. A `FLAT` line means the depth pass carries no information and the
  keyframe will ignore the layout.
- `CTRL <shot> radius=4` — the blur radius applied to the shipped control pass (`width / 192`).

### Commands

```powershell
# rebuild everything (renders beauty+depth+normal, rewrites ctrl passes, re-exports json)
$env:BLENDER_USER_CONFIG  = "C:\Users\admin\Desktop\manju\work\.btmp\config"
$env:BLENDER_USER_SCRIPTS = "C:\Users\admin\Desktop\manju\work\.btmp\scripts"
python win\blender_set_huoguo.py --shot-id all

# one rig
python win\blender_set_huoguo.py --shot-id s004

# regenerate only the blurred control passes (no re-render) — after changing the blur radius
python win\blender_set_huoguo.py --shot-id all --ctrl-only
```

**Caution:** the builder runs in its own headless Blender process, so it cannot disturb the user's
open session — but it *does* overwrite `huoguo_set.blend`. If the user is editing the file, ask
before rebuilding.

### What is deliberately absent

Steam, rain, crowds, signage text, tiles, food detail, tiles on walls. The set supplies
**structure**; the generator supplies **surface**. Do not "improve" the set by adding textures —
that fights the depth pass.

---

## Phase 2 — Keyframes (DONE)

**Runner:** `win/submit_keyframe.py` — uploads the control PNG, submits the workflow to the
gateway, polls, pulls the PNG, verifies sha256. This file is the template for every other
submitter.

**Recipe (measured, not guessed):**

| Parameter | Value |
|---|---|
| model | `z_image_turbo_int8_convrot.safetensors` + `Z-Image-Turbo-Fun-Controlnet-Union-2.1-lite-…-8steps` |
| text encoder / vae | `qwen_3_4b_fp8_mixed`, `ae` |
| control input | `sNNN_depth_ctrl.png` (blurred) |
| control strength | **0.85** |
| size | 768 × 1344 |
| seed | `420261113` (same seed for every shot, so frames are comparable) |
| steps / sampler | 8, `res_multistep` / `simple`, cfg 1.0 |
| wall time | **≈8.3 s per keyframe** |

**Final frames** (`work/laotang_ep01/`): `s001c`, `s002`, `s003`, **`s004d`**, `s005`, `s006`,
`s007b`, `s008`. Everything else in that folder (`s001`, `s001b`, `s004`, `s004b`, `s004c`, `s007`,
`s007n`) is a superseded test — keep for the record, don't ship.

### Wardrobe is a spec, not a prompt detail (found 13 Nov)

The first pass put 苏念 in a black sleeveless top (s004c) and a white blouse (s003) in the same
episode. The model was not wrong — the prompt left the outfit open, so it invented one per shot.
`premise_laotang.md` §Cast already defines every character's look anchor.

**`work/story/wardrobe.md`** now holds the canonical prompt clause per character plus a negative
clause (`bare shoulders, sleeveless top, tank top …`). Every keyframe and clip prompt must carry the
clause for whichever character is legible in frame. s004d is the reference implementation:
*plain dark apron over a worn oatmeal knit sweater* — and the sleeves also cover the arm-to-torso
seam, so the armpit wedges disappear with the wardrobe fix.

**Correction, 13 Nov — the clause said `sleeves down` and the model never obeyed it.** `s003b`,
`s004d` and `s004g` were generated against that wording and all three came back with the cuffs
bunched at the forearm. Consistent across generations and rigs, so the wording was the defect, not
the samples; it now reads *sleeves pushed up to the forearm, cuffs bunched*. A clause the model
overrides is worse than no clause — it teaches you to trust the text instead of checking the frame.

**The apron stays on.** `s004g` was prompted to untie it and instead shows her steadying it at the
waist, which is the better outcome: the next four units put her in the alley and at the street stall,
still in the apron. The shot list was corrected to match, rather than re-rolling the picture to fit
a beat that was written by hand.

All eight honoured the depth layout. That is Phase 2's pass criterion, and it passed.

### Failure modes — cause was the *guide*, not the model

| Symptom | Cause | Fix |
|---|---|---|
| white halo arc above every head | razor-sharp near-white silhouette edge read as a separate object | blur control pass 4 px |
| black wedge at the armpit | proxy arm cylinder merely **tangent** to torso → hairline sliver of far background | arm radius 0.055 at x ±0.178 so it bites the torso |
| ceiling as a black void | ceiling is nearest geometry, clips to pure white, model reads it as unlit sky | tilt the rig down so ceiling isn't a large area of frame |

### Two findings worth not re-testing

- **Normal maps are not a substitute for depth.** Tried on s007: the model used the normals
  loosely and rebuilt the shot as a doorway view. Feed depth.
- **Blur is not cosmetic.** Blurred@0.85 fixed both halo and layout. Sharp@0.85 → halos.
  Blurred@0.72 → layout drift.

---

## Phase 3 — Motion (DONE 14 Nov 02:05)

**Goal:** prove the room stays consistent while the camera moves, then decide 5B vs A14B.

### State of the weights

All three **downloaded and sha256-verified** (13 Nov):

| Weight | Size | State |
|---|---|---|
| `wan2.2_ti2v_5B_fp16.safetensors` | 10.00 GB | verified |
| `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | 6.74 GB | verified |
| `wan2.2_vae.safetensors` | 1.41 GB | verified |

**Stalled downloads are the normal failure, not the exception.** `hf_hub_download` has no
aggressive idle timeout, so a dropped connection leaves the process alive and frozen at a fixed byte
count. Diagnose it by running `du -sb tmp/hf_restore` twice ~20 s apart: identical, and the process
still in `pgrep`, means hung. Recovery is `work/.btmp/restart_restore.sh`, which kills the old
process (bracket-trick patterns so it doesn't kill itself), relaunches detached and resumes — no
bytes are lost, because the `.incomplete` file is kept. Log: `logs/restore.log`.

### Node graph (settled — taken from ComfyUI's official `image_to_video_wan22_5B.json`)

```
UNETLoader(wan2.2_ti2v_5B_fp16, default) → ModelSamplingSD3(shift 8.0)
CLIPLoader(umt5_xxl_fp8_e4m3fn_scaled, type="wan", device="default")
VAELoader(wan2.2_vae)
CLIPTextEncode positive / negative
LoadImage(first frame) → Wan22ImageToVideoLatent(vae, width, height, length, batch_size, start_image)
KSampler(model, seed, steps=30, cfg=5.0, sampler=uni_pc, scheduler=simple, denoise=1.0)
VAEDecode → CreateVideo(fps=24) → SaveVideo(filename_prefix="manju_clip", format="mp4")
```

Verified against live `object_info`: `Wan22ImageToVideoLatent` required = `vae, width, height,
length, batch_size`, optional `start_image`; `CreateVideo` required = `images, fps`; `SaveVideo`
required = `video, filename_prefix, format`. `SaveVideo` emits through `ui.PreviewVideo`, which the
gateway already collects (it scans `images | videos | gifs | audio`).

**Open discrepancy, unresolved:** ComfyUI's template uses `shift 8.0 / 30 steps`; the Wan repo's own
`wan_ti2v_5B.py` uses `sample_shift 5.0 / sample_steps 50 / sample_guide_scale 5.0 / fps 24 /
frame_num 121`. Start with the ComfyUI values (they are what the repackaged weights are exercised
with), and only sweep the Wan-repo values if motion quality disappoints.

### Target

704 × 1280 (portrait 720p; both divisible by the 16×16×4 VAE), `length=121` = 5.0 s @ 24 fps,
lane `wan-i2v` (lanes are free-form strings — no gateway edit needed).

**Memory:** 5B fp16 (10 GB) + umt5 fp8 (6.7 GB) fits inside the 44 G cap. A14B does not — raising
`COMFY_MEMORY_MAX` is a decision, not a tweak.

### First clip — result

`s001m` from `s001c`: **121 frames, 704×1280, 24 fps, 405 s** on the GB10 (≈3.35 s/frame at
30 steps). Output `work/laotang_ep01/s001m_manju_clip_00001_.mp4` (1.56 MB), contact sheet
`s001m_contact.jpg`.

**Verdict: the room holds.** Across all five sampled frames the round tables, hotplate pots, red
enamel stools, pendant lamps, pass-through window, wall signage and the waiter's position are
stable; only the camera moves (a slow push-in) and the steam drifts. No furniture swimming, no
walls rearranging, no cut-like jumps. Phase 3's pass criterion is met on the establishing wide.

### Batch result — 8 clips, 13 Nov 22:23–23:05

`win/batch_clips.py` ran the seven remaining rigs sequentially. Reported **6/7 ok**; it was
actually **7/7** — see the s007bm note.

| Shot | Wall | Furniture held | Verdict |
|---|---|---|---|
| s001m | 405 s | yes | establishing wide, camera + steam only |
| s002m | 400 s | yes | pot, chilli broth, red stools, pendant lamps, wall sign all stable; slow tilt up |
| s003m | 419 s | yes | two-shot holds; **wardrobe is pre-fix** — she is in a light top, no dark apron |
| s004em | 418 s | yes | apron + oatmeal sweater correct; pass-through and bowl stacks stable; steam crosses the face at 60–120 |
| s005m | 416 s | yes | window frame and table hold; the city lights behind re-shuffle between frames — fine alone, breaks a cut between two takes of it |
| s006m | 418 s | yes | shutter slats, stall table, stools, lamp hold; subject slides rightward although the prompt asked for a static camera |
| s007bm | **137 s → client died** | yes | room holds through the dolly; **background diners mutate** — a seated group changes size and a white-sleeved arm enters at the right edge by frame 120 |
| s008m | 696 s | yes | bowl lift reads correctly; shutter slat pattern drifts; 282 s of that wall time was queueing behind the failed poll |

**s007bm did not fail.** `submit_clip.py` lost the connection at 137 s (`WinError 10060`) and
exited, but the job ran to completion server-side and wrote `manju_clip_00007_.mp4` at 14:58.
Recovered by `GET /jobs/f4607af8e1684dd6/file/0` → `s007bm_manju_clip_00007_.mp4`
(1,761,602 B, sha256 `2b7ee541…`). **No re-render was needed.**

Two tooling lessons, both now in `submit_clip.py`:

- Polling retries on `OSError` up to `--max-poll-errors` (default 120 ≈ 10 min) instead of dying
  on the first socket hiccup, and the failure message says the job may still be renderable.
- The output download retries three times before giving up.

**Per-shot pass criterion is met on every rig so far: no furniture swam.** The remaining defects
are content, not structure — so the lever is the guide or the prompt, never the sampler.

### Round 2 — 13 Nov 23:05–00:20: five clips, five keyframes, three rejected guides

| Shot | What changed | Result |
|---|---|---|
| `s003m` | new keyframe `s003b` (00017) carrying both wardrobe clauses | `…_00009_.mp4`, 1,663,547 B, sha `3a7ae56b…`, 401 s. Verified on a contact sheet: wardrobe right in all five sampled frames, room holds. He crosses the floor to her side instead of the push-in the prompt asked for — the model moved the actor. Accepted: it serves the line better. |
| `s004g` | new keyframe (00019) from the existing `s004` rig | `…_00010_.mp4`, 2,253,876 B, sha `379822bc…`, 411 s. The apron does **not** come off; she steadies it at the waist and looks away. Accepted — see the wardrobe correction below. |
| `s002c` | first attempt | **Rejected.** Pot stayed upright on its burner, broth spilled around its base: a good picture of the wrong action. |
| `s002c` | posed guide, second attempt | keyframe `00020` (251 s, sha `63c596a1…`): pot lying on its side, mouth to camera, broth pouring across the table. Clip `…_00011_.mp4`, 2,694,597 B, sha `39d7dda9…`, 416 s — the pot settles, the spill keeps spreading, table and stools hold. |
| `x001` | alley wide, `houxiang` rig | keyframe `00021` (208 s, sha `1a03c1e3…`): rain, lit back door, copper pot at the kerb. |
| `x002` | first pass | **Rejected.** Copper pot framed against brick with a red bin and a golden grade — a different alley from `x001`. |
| `x002b` | re-roll with material anchors | keyframe `00024` (8.7 s, sha `61078d9e…`): grey plaster wall, wooden door up the alley, cool grade. Accepted. |
| `x003` | first pass | **Rejected.** Metal-framed glass door with signage; `x001` has a wooden door. |
| `x003b` | re-roll with material anchors | keyframe `00025` (8.7 s, sha `5553d587…`): 苏建国 in the lit wooden doorway, her shoulder in silhouette. Accepted. |

The three alley clips went into `batch_clips.py --only x001,x002,x003` afterwards. `s002c`'s clip
board shows the pot holding its pose for all 121 frames — the first shot in the film whose *pose*
came from geometry the builder did not originally contain.

### Round 3 — 14 Nov 00:10–01:00: the alley lands, the CU rigs do not

| Item | Result |
|---|---|
| alley clips | `x001` 00012 (421 s, `97da68df…`), `x002` 00013 (421 s, `074f22c6…`), `x003` 00014 (421 s, `cced40d2…`). All three hold: walls, door, rain, bin bags, the pot. |
| `s009b` | 00035, accepted. First pass 00033 cast 顾衍 at ~50 while `s005m` shows him at ~30 — a casting break in the reveal shot, fixed by restoring *lean young man of 30, clean-shaven, smooth unlined face*. |
| `s010` | 00034, **rejected**. A beige ring around her head and flat panels beside her cheeks — the model filling in structure the depth guide did not have. |
| `s011` | 00031, **rejected**. The model painted a copper alembic still in a bright daytime kitchen; no pass-through, no night. |
| `s012` | 00032, usable as a shop-front insert but the rig aims at z = 2.45 m, so the door sits in the bottom third under a quarter-frame of blank wall, and the stall the beat asked for is absent. |

**The CU rigs defeat their own depth ramp.** `depth_range()` uses `far = near + max(1.6·d, 3.2)`.
At `s009`'s 0.73 m subject distance that is 0.36–3.56 m, so a head at 0.6–0.85 m lands between 0.85
and 0.92 on an 8-bit ramp — a flat white blob. The background is the only thing with structure, and
the model, faced with a featureless blob, invents a ring, a hoop or a wire around the face. It did
that twice, in two different prompts, which is what makes it a rig defect rather than bad luck.

Rule to add to `depth_range()` (**superseded 14 Nov** — see `win/blender_depth_rerange.py` and
`newsession1.md` §4.1 for the measured-subject rule): the old guess was `near ≈ 0.75·d`,
`far ≈ 2.0·d` for rigs under ~1.5 m. The correct version ray-casts the subject's real depth span and
sets `near = z_lo − 0.15·(z_hi − z_lo)`, `far = near + (z_hi − z_lo)/0.30`, which puts ~76 of 255
levels on the subject instead of 6. Wide rigs keep the existing formula.

`DEPTHSTAT std` does not catch this — a flat white subject against a black background has a healthy
standard deviation. The check that would catch it is *the spread of values inside the subject's
silhouette*, and it does not exist yet.

**Two sessions submitted the same alley shots at the same time** (`x001`–`x003` as 00021/00024/00025
and again as 00026–00028). Nothing broke, but it cost six keyframes' worth of GPU for three useful
frames. Before submitting, check `GET /jobs` for the shot id — `win/listjobs` does not exist, so the
one-liner is in `work/.btmp/listjobs.py`.

### The depth guide decides pose, and a prompt cannot overrule it

`s002c` was a clean test of the question the whole pipeline rests on. Same depth pass as `s002m`,
only the prompt changed to "tipped over on its side", and the keyframe came back **upright with the
broth spilled around it**. The model kept the guide's silhouette and repainted the surface. Depth
carries place, scale and pose; text carries material, light and liquid. When a shot needs a different
pose, the geometry has to change — no wording is a substitute.

`win/blender_pose_s002c.py` is the pattern, and it generalises to any prop in any set:

- opens the set, transforms only the named parts, renders beauty + depth + blurred control for one
  shot, and **never saves the set** — it asserts the set's sha256 is unchanged and exits non-zero if
  it is not;
- rotates the pot 80° about world X through its own centre, settles it by measuring the world
  bounding box of the posed parts, then nudges it 0.10 m toward camera so it is off the burner;
- prints the posed bbox and its `world_to_camera_view` position, so "the pot left the frame" is a
  line of output rather than a discovery in the PNG.

Both bugs in the first attempt were arithmetic, not art: parenting the parts to an empty and settling
from the empty's matrix put the pot outside the frustum, and `bound_box` corners are in local space,
so they must be multiplied by the *object's* matrix, not the parent's.

The script also rebuilds the depth override material, because **`huoguo_set.blend` contains no
`OV_Depth`/`OV_Normal`** — they had no users when it was saved and were purged. That is the same trap
`blender_set_template.py` fixed with `use_fake_user`, and the set predates the fix. Any guide
regenerated from the saved file has to build the override itself; a fresh set build gets it in memory
and feels fine until you reload the file.

### Clay beauty carries no material, so a location is only as consistent as its prompt

The alley (`work/sets/houxiang/`, delivered 13 Nov 23:22) exposed the mirror image of the pose
lesson. The set is clay: the door is a box, the wall is a plane. Every material in the finished
frame is invented per shot. `x001` came back with a dark wooden back door in a grey plaster alley;
`x002` and `x003` from the same set came back with brick, a red bin, a metal-framed glass door and
signage — three shots of one alley that do not match.

The fix is not geometry, it is wording: the anchor phrases are now copied verbatim into every
prompt for the location — *worn grey plaster alley wall*, *dark painted wooden back door*, *narrow
Chongqing back alley at night, in light rain* — plus the same colour direction, *cool blue-green
night grade*. Both re-rolls (`x002b`, `x003b`) match `x001` on the first try.

So the rule is symmetric and worth stating once:

| Question | Lever |
|---|---|
| where, how big, which way the object is facing | depth guide (geometry) |
| what it is made of, what colour the light is, what the weather is | prompt, and only prompt |

Reusing identical noun phrases across shots of a location is the cheapest continuity tool in the
pipeline. A character reference image would be better, and is what a LoRA buys (Phase 6).

### The 90 s structure is written down

`work/story/shotlist_laotang_ep01.md` — 19 five-second units (the 5.04 s model cap), mapped to beats,
lines, audio and the Blender item that unblocks each. Counts live in that file, not here, because they
change faster than this document.

Judge future clips the same way — extract a contact sheet rather than watching:

```powershell
# on the Spark: decode with the venv's PyAV (already a ComfyUI dependency) and write a 5-frame sheet
$b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes("work\.btmp\contact_sheet.py"))
python win\spark_ssh.py "echo '$b64' | base64 -d > ~/Desktop/AIGC-Model/tmp/contact_sheet.py; cd ~/Desktop/AIGC-Model && source env.sh >/dev/null && venv/bin/python tmp/contact_sheet.py work/output/manju_clip_00001_.mp4 work/output/s001m_contact.jpg"
# then pull it over ComfyUI's own HTTP server (it serves its output dir)
Invoke-WebRequest "http://192.168.1.103:8188/view?filename=s001m_contact.jpg&type=output" -OutFile work\.btmp\s001m_contact.jpg
```

### Using ComfyUI from the browser (canvas / MaskEditor)

`work/comfy_workflows/manju_inpaint.json` is pushed to the Spark at
`app/ComfyUI/user/default/workflows/`, so it appears in the UI's **Workflows** sidebar as
`manju_inpaint`. It does: LoadImage → VAEEncodeForInpaint → Z-Image Turbo → SaveImage, denoise 0.62.

### The four workspaces (all live on the Spark)

| File | Lane | Graph |
|---|---|---|
| `manju_keyframe_control` | Z-Image + depth ControlNet | UNET → QwenImageDiffsynthControlnet(0.85) → ModelSamplingAuraFlow → KSampler(8 steps, cfg 1.0) |
| `manju_inpaint` | Z-Image masked | LoadImage MASK → VAEEncodeForInpaint → KSampler(12 steps, denoise 0.62) |
| `manju_i2v` | Wan 2.2 5B | LoadImage → Wan22ImageToVideoLatent(704×1280×121) → KSampler(30 steps, cfg 5.0, uni_pc) → SaveWEBM(vp9, 24 fps) |
| `manju_t2v` | Wan 2.2 5B | same as `manju_i2v` with no start image — look tests only |

`manju_t2v` is **derived** from `manju_i2v` by `win/validate_workflow.py`, never hand-edited, so the
two cannot drift. That same script validates every workflow against the live `/object_info`
contract — node types, link slot indices, link types, required non-widget inputs — before anything
is pushed. Run it after any workflow edit:

```powershell
python win\validate_workflow.py
```

Push the whole directory as one gzipped blob (four files exceed the command-line limit; base64 of a
tar avoids it). Pull a generated video back the same way as the contact sheet, via
`/view?filename=…&type=output`.

Mask workflow: right-click the image in **Load Image** → *Open in MaskEditor* → paint the area to
change (white = repaint) → **Save to node** → Run. The prompt describes only what should appear
inside the mask.

**Governance:** running from the UI bypasses the gateway, so the job is **not** written to
`queue.db` and **not** recorded in provenance. UI runs are for experiments, masks and look
development. Anything destined for a master goes through `win/submit_keyframe.py` /
`win/submit_clip.py` (Rule 1).

Note: `?workflow=<name>.json` in the URL does **not** reliably open a workflow when the app is
still booting — it races with session restore. Open it from the Workflows sidebar instead. The two
console 404s on load are the optional `user.css` lookups and are harmless.

### Batch driver

`win/batch_clips.py` runs every shot in `win/shots_laotang_ep01.json` (per-shot prompt + first
frame) through `submit_clip.py`, one at a time, continuing past failures and reporting a summary.
Sequential is correct: one GPU, and the gateway assigns per lane, so parallel submits only reorder
the queue.

```powershell
$raw = python win\spark_ssh.py "grep -m1 '^FREEFIELD_TOKEN=' ~/Desktop/AIGC-Model/env.local | cut -d= -f2-"
$env:FREEFIELD_TOKEN = ($raw -join '').Trim()
python win\batch_clips.py --dry-run          # check wiring first
python win\batch_clips.py                    # 7 clips, ~7 min each
python win\batch_clips.py --only s004em      # a single re-roll
```

### Next actions — picture, 14 Nov (all completed 14 Nov)

1. **Fix the two CU depth ramps** (`s009`, `s010`): **done** — `win/blender_depth_rerange.py`
   (measured subject, 6 → 76 levels); both re-rolled clean on the first attempt (`s009c` 00037,
   `s010c` 00036). `s011`/`s012`/`s002d` re-rigged via `win/blender_retarget_rig.py`.
2. **Re-rig `s011`** — **done** via `win/blender_retarget_rig.py --loc 0.30,3.95,1.30 --target
   0.30,1.23,1.10 --lens 55`. The failure mode was real: 3.07 m back at 35 mm put a person at 1/6
   frame height and the model invented a laboratory still. Clip `00017`.
3. **`s012`** — **done** at target z **2.20** (not 1.25, which is only what the saved set holds; not
   2.45). `--hide Bead`. Clip `00019`. **No stall, by decision** — the beat is carried by the
   off-screen queue; do not add one to satisfy a checklist.
4. **`s002d`** — **done**: stall-side low rig, `--ramp hug --subject Stall_Pot` (the wall behind won
   the "largest group" contest). Clip `00018`.
5. **Then five clips** — **rendered 14 Nov 01:05–02:05**, 2030 s of clip time (~410 s per 5 s clip):
   `s009m` 00015, `s010m` 00016, `s011m` 00017, `s002d` 00018, `s012m` 00019. Picture complete at
   19 units / 90 s, 18 canonical files.

Do not start a re-roll without checking `GET /jobs` first (gotcha 12) — the Blender agent submits to
the same gateway. This still applies; "done" is not "frozen".

### Pass/fail criterion

Watch the **furniture**, not the faces: tables, stools, pendant lamps, door curtain, kitchen pass
must hold their positions across all 121 frames. If they swim, the next lever is per-frame depth
control (Wan VACE, another large download) — not a prompt rewrite. Report per-shot results, then ask
whether to raise the memory cap for A14B or stay on 5B.

---

## Phase 4 — Voice (DONE 14 Nov)

Qwen3-TTS VoiceDesign rendered all six utterances of the episode; `qwen3_tts_base_1_7b`
(cloning) and `latentsync_1_6` (lip-sync) are **declared in `MANIFEST.json` but not downloaded** —
nothing in ep01 needs either. Full record: `newsession1.md` §6.

| Piece | State |
|---|---|
| `qwen3_tts_voicedesign_1_7b` 4.52 GB, `faster_whisper_small` 486 MB | downloaded, Apache-2.0 / MIT, rows gated in `MANIFEST.json` |
| `app/venv-tts` | Python 3.12.3, torch 2.14.1+cu130, qwen-tts 0.1.1, sox, torchaudio 2.11.1+cu130 (the only build that exists) |
| render | `spark/app/tts/render_lines.py` ← `win/tts_lines.py`; 6 wavs in `work/laotang_ep01/vo/`, 24 kHz mono PCM_16, −19…−26 dBFS |
| measure | `app/tts/measure_lines.py` → `vo/MEASURE.json`; ASR ≤1 character of error per line, all homophones |
| casting fixes | vo03 279→208 Hz, vo05 217→174 Hz (share 苏念's seed/preset); vo06 59→75 Hz |

**What is left is an ear, not a pipeline.** Play `work/laotang_ep01/vo/audition_all.wav` (17.40 s,
vo01→vo06). 顾衍 at 75 Hz is intelligible but low for a man of thirty — 85 Hz cost 5/9 ASR
characters, so it is not worth iterating blind. 苏念's vo03 sits 37 Hz above vo01 (a register
shift, accepted); exact identity needs cloning from vo01 with `qwen3_tts_base_1_7b`, not more
prompt tuning. 苏建国's 沙哑/方言 is not measurable at all.

**Lip-sync is optional, not next by default** — only units 17 and 19 are sustained face-on
dialogue, and 苏念 has no face in ep01.

## Phase 5 — Assembly (DONE 14 Nov — draft delivered, unverified in Jianying)

`win/assemble.py` + repo-local `win/tools/ffmpeg` already produced the first delivery master:
`work/laotang_ep01/cut/laotang_ep01_conform.mp4` — 90.00 s, 1080×1920, 24 fps, 2160 frames,
40.6 MB, with captions, 片头 title block and per-episode AI label burned in. ffmpeg is repo-local
(not installed, PATH untouched) and must be GPL-family (libass/freetype/fribidi load-bearing).

The assembler refuses (rules, not warnings): no clip without provenance (19/19 joined by shot_id +
recorded output filename), no global master containing a restricted-territory unit, no `--final`
while `compliance.program_number` is empty, and no silent duration drift (encoded picture must match
the cut within 0.25 s). Two open decisions, both creative: (a) six units are longer than a 5.04 s
clip (2, 4, 10, 12, 17, 18 — 6.75 s short total, 12.54 s headroom elsewhere) — `--allow-hold`
freeze-fills the tail, or re-time the cut; (b) no bed/SFX, so non-speech measures −91 dB (digital
silence) — the shotlist's SFX column has no assets behind it.

**Done 14 Nov:** repo-local venv created at `win/venv_jianying` (Python 3.12, pyJianYingDraft 0.3.1,
recorded as a Rule 3 approval; the venv is gitignored). Draft generated by
`win/build_jianying_draft.py` at `work/laotang_ep01/jianying_drafts/laotang_ep01/` — picture track =
the conform master, six VO wavs at their slot starts, SRT captions imported. Verified in the JSON:
3 tracks, 90.0 s, 1 video + 6 audio materials, and **every media path absolute and local**
(`C:\Users\admin\Desktop\manju\work\laotang_ep01\…`), which is the Rule 4 requirement.

| Path | What it is |
|---|---|
| `work/laotang_ep01/cut/laotang_ep01_conform.mp4` | **canonical** master — the draft references this one |
| `work/laotang_ep01/cut/assemble_report.json` | durations, holds, ffmpeg build, `final: false` |
| `work/laotang_ep01/delivery/` | a second copy of the master plus `laotang_ep01.srt`, `VO_MANIFEST.json`, `assemble_report.json` — **gitignored**, derived from `cut/` + `vo/`, never a source of truth |

**Two things the draft cannot prove on its own.** (1) **Jianying is not installed on this
machine**, so the draft has never been opened — validity is checked at the JSON level only, and
`plan.md` §7.5 still asks the operator to pin the Jianying version (≤5.8) before trusting the
generator. (2) The freeze-fills are baked into the picture track, so changing them means re-running
`win/assemble.py` and rebuilding the draft, not editing inside Jianying.

**Verified 14 Nov — and one defect found by verifying.** `win\verify_delivery.py` checks the master,
the captions, the six wavs and the draft against each other: ffprobe for the container, per-line level
against `MEASURE.json`, caption text and timing against the spec, absolute in-repo paths in the draft,
and the six freeze-fills by PSNR. It found the mix shipping **3 dB quiet** —
`aformat=…channel_layouts=stereo` equal-power-spreads a mono wav, landing 1/√2 per channel.
`pan=stereo|c0=c0|c1=c0` fixed it, the master was rebuilt, and the dialogue now matches the wavs
exactly (−19.0 … −22.2 dBFS per line, peak −3.7 dBFS). **Run it after any re-assembly; it needs no
Jianying.**

## Phase 6 — Characters (blocked)

`work/characters/` holds three MPFB previews (`lead1_mpfb_turnaround.png`,
`lead1_mpfb_bust_preview.png`, `lead1_baked_albedo.png`). The mannequins in the set are deliberate
proxies. A character LoRA trainer is **not approved** (Rule 3) — ask the operator before installing
anything. Replacing mannequins needs no rework of the set or the rigs.

## Phase 7 — Wipe / restore hygiene (ongoing)

- `bin/doctor.sh` must print **BOUNDARY CLEAN** before any "done" report. Last run: clean.
- `spark/models/MANIFEST.json` — **11 rows, 51.52 GB declared, 37.34 GB downloaded**; 9 Apache-2.0,
  1 MIT (`faster_whisper_small`), 1 OpenRAIL++ (`latentsync_1_6`). Declared only:
  `qwen3_tts_base_1_7b` (4.54 GB, cloning) and `latentsync_1_6` (9.64 GB, lip-sync).
- Any system install goes through `bin/record-install.sh` with a receipt in `app/os/installed.tsv`.
- `bin/restore.sh` rebuilds the folder from the manifest after a wipe; it is also the resume tool
  for interrupted downloads.

---

## Do not re-derive these (already proven)

| Claim | How it was proven |
|---|---|
| White model + proxies carry structure into depth guides | 8/8 rigs honoured the layout |
| Depth must be blurred before ControlNet | halo vs no halo at identical strength |
| Normal maps ≠ depth control | s007n returned a doorway view |
| AgX breaks the depth ramp | flat/compressed depth until switched to Standard |
| 8 keyframes ≈ 70 s total | measured 8.3 s each |
| Blender runs on Windows only; Spark is GPU-only | `which blender` empty on Spark |
| **mono→stereo `aformat` costs 3 dB** | the rebuilt master matches `MEASURE.json` per line only after switching to `pan=stereo\|c0=c0\|c1=c0` |
| Nothing in the project was downloaded as an image | every PNG is Blender-rendered or Z-Image-generated |

## Blockers and their smallest unblocks

| Blocker | Smallest unblock |
|---|---|
| **No bed, no SFX** — non-speech measures −91 dB | a licensed ambience/SFX pass (music + pot crash, rain, bead curtain, market), each with provenance |
| **Six units freeze-filled** (2, 4, 10, 12, 17, 18 — 6.75 s total) | editorial call: accept the holds, or re-time the cut and re-run `win/assemble.py` |
| **Draft unverified in Jianying** (not installed here) | operator opens it; pin Jianying ≤5.8 per `plan.md` §7.5 |
| `--final` refused while `compliance.program_number` is empty | the number comes from platform review; inventing one is a fake regulatory mark |
| 顾衍 voice is 75 Hz — intelligible, low for a man of 30 | an ear decides; cloning, not more prompt tuning (85 Hz cost 5/9 ASR characters) |
| A14B can't fit 44 G | operator decision to raise `COMFY_MEMORY_MAX` (not needed — picture is done on 5B) |
| Character LoRA trainer not approved | operator approval, then manifest + record-install |
| Kandinsky 6.0 Pro needs a 20 KB ComfyUI core patch | operator approval (not on the ep01 path) |
| SSH key auth not installed (`~/.ssh` is outside the boundary) | operator exception for `~/.ssh` |

---

## Per-phase resume prompts

Paste the one that matches where you are. Each is written to be the *entire* first message of a new
conversation — no other context needed.

**Resuming Phase 5 (assembly) — the current one**

> Read `C:\Users\admin\Desktop\manju\HANDOVER.md`, section "Phase 5 — Assembly", and
> `C:\Users\admin\Desktop\manju\newsession1.md` §11 and §7. Phases 1–5 are done: the 90 s conform
> master is at `work/laotang_ep01/cut/laotang_ep01_conform.mp4` and the Jianying draft at
> `work/laotang_ep01/jianying_drafts/laotang_ep01/`. Do not re-render clips or voice. The three open
> decisions are listed in §7 of `newsession1.md` — a sound/SFX pass, the six freeze-filled units, and
> whether the draft opens in Jianying (not installed here). Ask which of the three to take before
> touching anything.

**Resuming Phase 3 (motion) — historical, do not re-run**

> Read `C:\Users\admin\Desktop\manju\HANDOVER.md`, section "Phase 3 — Motion". This phase is
> **complete** — 19 of 19 units, 18 canonical clips. Read it only to understand how a clip was made;
> do not submit a clip. If a re-roll is genuinely needed, check `GET /jobs` first (gotcha 12) and
> read `newsession1.md` §4.1 on the depth ramp before re-rendering any guide.

**Resuming Phase 4 (voice) — historical, only the ear remains**

> Read `C:\Users\admin\Desktop\manju\HANDOVER.md`, section "Phase 4 — Voice", and
> `newsession1.md` §6.5.1–§6.5.2. Weights are downloaded and six wavs are rendered and measured;
> do not re-render unless a line sounds wrong. What is left is judgement: play
> `work/laotang_ep01/vo/audition_all.wav` and decide on 顾衍 (75 Hz), 苏念's two registers, and
> 苏建国's 沙哑/方言. To change one line: edit its `instruct` in
> `work/story/vo_lines_laotang_ep01.json`, then `python win\tts_lines.py --only voNN --overwrite`.

**Resuming Phase 6 (characters)**

> Read `C:\Users\admin\Desktop\manju\HANDOVER.md`, section "Phase 6 — Characters". A LoRA trainer is
> not approved — do not install one. The mannequins in `work/sets/huoguo/huoguo_set.blend` are the
> placeholders to replace.

**Resuming Phase 7 (hygiene) only**

> Read `C:\Users\admin\Desktop\manju\HANDOVER.md`, section "Phase 7 — Wipe / restore hygiene". Run
> `bin/doctor.sh` on the Spark and report its output verbatim; fix anything non-empty rather than
> noting it.

---

## Keeping the next conversation cheap

1. Read this file and `work/sets/huoguo/README.md`. Nothing else, unless a phase says so.
2. Never dump image files unless the user asks to see one — each one is a large, expensive token
   block. Check dimensions/statistics with a script instead.
3. Read `win/submit_keyframe.py` or `win/submit_clip.py` before writing another driver; they are the
   canonical pattern for submit → poll → pull → verify.
4. Prefer running one probe script over a chain of shell one-liners; the quoting rules above make
   long SSH one-liners fail more often than they succeed.
5. When a phase finishes, **update this file** — replace the status in the phase map and append what
   was learned. This document is the project's memory.

11. **"Byte-identical passes" is not a guard.** Two identical alley builds differ in
`_beauty`/`_depth`/`_normal` bytes; only `_depth_ctrl` reproduces exactly, and disabling output
dither makes no difference — it is the renderer's sampling. Byte-comparing re-rendered passes fails
for correct code and broken code alike, so it proves nothing in either direction. Prove a file was
not rewritten with mtime, reserve sha256 for `*_depth_ctrl.png`, and use a perceptual diff for
cross-build equivalence. A set file's sha256 assertion is still valid: those are opened, never
re-rendered.
