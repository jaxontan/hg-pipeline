# NEXT BLENDER — what still has to be built

Written 2026-11-13. Companion to `HANDOVER.md`; read that first for machine facts, then this.

**Scope of this file:** only *Blender files*. Not ComfyUI graphs, not weights, not the cut.
Every item here is a `.blend` plus a builder script, because the project rule is that a `.blend`
is generated, never hand-edited — a hand-edited set cannot be rebuilt after the Spark wipe and
cannot be reproduced when a rig needs re-rendering in six weeks.

**Cost model:** a set costs authoring + checking time, not render time. One EEVEE pass at
768 × 1344 is seconds. The expensive part is the `SIGHTLINE` / `DEPTHSTAT` loop and the one
keyframe you render to prove the new guide is actually followed.

**These run on Windows, in parallel with the Spark.** The 7-clip batch does not compete for the
Blender process — different machine. Build while it renders.

---

## What already exists (verified on disk today)

| File | Size | Role | State |
|---|---|---|---|
| `work/sets/huoguo/huoguo_set.blend` | 443,810 B | 火锅店 interior + street strip, **12 rigs**, 366 objects | **FROZEN 13 Nov 00:01**, sha256 `1b9274777296f1ad…` — s009 target 1.00 m, s011 45 mm at 1.38 m, s012 target z **1.25 in the saved set (canonical render uses 2.20 via `retargets.json`)**. Do not rebuild while guides are in flight. |
| `work/sets/huoguo/huoguo_set_pre_rigs.blend` | 473,074 B | the 8-rig build, copied before that rewrite | **rollback point**, sha256 `9296cc0e…` |
| `work/characters/lead1_mpfb_bust.blend` | 4.7 MB | 苏念 bust preview, MPFB | **test only** — no turntable, not posed, not the other three leads |
| `work/ep00_p3_previz/s001_previz.blend` | 130 KB | the original single-shot smoke test | **superseded**, keep as record |
| `win/blender_set_huoguo.py` | 36 KB | builder for the set above | the pattern to copy |
| `work/sets/_template/set_template.blend` | 100,209 B | item 7 scaffold, 1 self-test rig `t000` | **done 13 Nov 22:52**, sha256 `7e8385f7…a0e7ed` |
| `win/blender_set_template.py` | — | builder for the template above | done — copy this for a new set |
| `work/props/props_laotang.blend` | 168,434 B | item 3 library: 5 props, 1 merged mesh each | **done 13 Nov**, sha256 `ef8b72b6…1c41a2f9` |
| `win/blender_props_laotang.py` | — | builder for the prop library | done |
| `work/sets/houxiang/houxiang_set.blend` | 236,054 B | item 1 alley, 3 rigs `x001`–`x003`, 105 objects | **done 13 Nov**, sha256 `c095b24d…` (x003 re-rendered with 小满) |
| `win/blender_set_houxiang.py` | — | builder for the alley | done |
| `win/blender_previz.py` | 7.5 KB | first previz script | superseded |

So: **two real sets, one template, one prop library, one character test, one dead previz.** Only
item 5 has no file at all; 4 and 6 are edits to files that exist; 1, 2, 3 and 7 are done.

---

## P0 — ep01 cannot be finished without these

### 1. 后巷 back alley — the third location — **DONE 13 Nov**

**File:** `work/sets/houxiang/houxiang_set.blend`
**Builder:** `win/blender_set_houxiang.py` (copy the huoguo builder; same guards, same conventions)
**Output:** `x001…x003` rigs, `sNNN_`→`xNNN_` passes, `set_houxiang_cameras.json`

`premise_laotang.md` names three set pieces and says "no location moves": the interior, the
street strip, **the back alley**. The interior and street strip are in `huoguo_set.blend`. The
alley does not exist anywhere — and it is where beat 5 happens, where the pot is picked out of
the rubbish, and where ep02 opens ("that pot's queue is longer than the old shop's").

| Rig | Intent | Why it needs its own frame |
|---|---|---|
| x001 | wide, 苏念 out the back door, pot at the kerb | establishes the alley in one frame; needs the shop's back wall at one end to tie it to the interior |
| x002 | low, close on the pot in the rubbish | **the 捡锅 beat** — the title object's introduction; the frame has to read as *discarded*, not *placed* |
| x003 | over-shoulder back at the shop door | ep02/03 returns; 苏建国 framed in the doorway, lit from inside |

Build notes that are not optional:

- 2.4 m wide, 11 m long, walls 3.2 m — narrow enough that a 24 mm at 1.6 m sees both walls, so
  the depth pass has near-left/near-right anchors. A wide alley renders flat.
- Back door of the shop **must** be the same 1.30 × 2.10 m opening as the front door in
  `huoguo_set.blend`, or the two sets will not cut together.
- Rubbish: 3 bin bags, a crate, a broken stool, a stack of cardboard. These are *depth anchors*,
  not decoration — without them the lower third of every alley frame is one grey plane and
  ControlNet gets nothing.
- Wet-patch geometry is **not** modelled. Rain, reflections and puddles are the video model's job,
  same division of labour as the street strip.
- No signage text, no neon.

**Acceptance:** `SIGHTLINE` clear or blocked-by-subject only; `DEPTHSTAT std > 0.06` on all three;
one keyframe at strength 0.85, blurred control, that holds the alley walls and the bin bags.

**Result, 13 Nov.** `houxiang_set.blend` 210,786 B, sha256 `5871402…89660`, 96 objects,
collections `SET/FURN/PROPS/FX/PROXY`, 12 passes. Geometry as specified: 2.40 m wide × 11.00 m
long, walls 3.20 m, back door **1.30 × 2.10** — the same opening as the front door in
`huoguo_set.blend`, so the two sets cut together.

| Rig | SIGHTLINE | DEPTHSTAT | depth ramp |
|---|---|---|---|
| `x001` | BLOCKED 0.978 `P_Shu_Torso` | 0.363 OK | 3.17 – 13.33 m |
| `x002` | CLEAR — guard blind, see below | 0.232 OK | 0.67 – 3.87 m |
| `x003` | BLOCKED 0.950 `P_Shu_Torso` | 0.241 OK | 1.53 – 6.43 m |

Both `BLOCKED` lines are 苏建国 *in the doorway*, at 95–98 % of the way to the target: the subject,
not a defect. That is the x003 frame by definition, and it is also true of x001, which frames him
through the same door.

**The pot is linked, not copied** — `//..\..\props\props_laotang.blend`, resolved and present at
load. `LINKCHECK` puts it at uv (0.74, 0.27) in x001 and (0.50, 0.49) in x002: in frame for both
shots that need it, behind the camera in x003 as intended.

**Gotcha that cost a cycle — `scene.ray_cast` cannot see collection instances.** x002 aims straight
at the linked pot and still reported `SIGHTLINE CLEAR`; a depsgraph dump proved the instance was
there at (-0.62, 6.55, 0.0), projecting to frame centre. So `SIGHTLINE` only ever tests the set's
own geometry and **every linked prop is invisible to it**. The builder now prints a note to that
effect and adds `LINKCHECK <rig> pot_uv=… in_frame=…` as the prop guard. Never read a `CLEAR` as
"the prop is in shot".

Two smaller traps: `bpy.ops.file.make_paths_relative()` needs the .blend to already have a path, so
the order is save → relative → save; and there is only **one** 苏念 in the file, at (-0.40, 5.05)
facing the door — x001 sees her back mid-alley and x003 is over that same shoulder. A second copy
facing the other way put two of the same character in one frame.

**小满 was missing from the guide — fixed 13 Nov.** x003 is the shot she exists for
(「姐，今晚吃什么？」), and no prompt can conjure a person the depth pass does not contain. A 1.40 m
proxy now stands at (0.40, 4.30) and renders in **x003 only**, so the x001/x002 guides did not move
(a claim since retired as meaningless — see the guard note at the end of this file). The first
placement, x = −0.42, projected *inside* the frame at uv 0.79 —
and sat directly behind 苏念. **In frame is not visible.** The guard now ray-casts to her head as
well: `CHILDCHECK x003 uv=(0.20,0.51) in_frame=True visible=True first_hit=P_Xiaoman_Head`. x001
keeps her out deliberately — she runs in by the *end* of that unit, so a t=0 guide must not hold her.

**Consequence: x003's keyframe is stale.** `00025` and `00028` were both rendered from the guide
that had no child in it. x003 needs one re-render before its clip.

**Not done:** the acceptance's keyframe at strength 0.85 is closed by execution elsewhere — `s002c`
ran at the 0.85 default through `win/blender_pose_s002c.py`. This build submitted none.

---

### 2. Rig extension on the existing set — `s009`–`s012` — **DONE 13 Nov 23:31**

**File:** the same `work/sets/huoguo/huoguo_set.blend`
**Script:** add four entries to `SHOTS` in `win/blender_set_huoguo.py`, then
`python win\blender_set_huoguo.py --shot-id s009,s010,s011,s012`

The eight rigs cover beats 1–7 *as beats*, but two of ep01's eight beats name a frame the set
cannot currently make, and ep02–03 need two more:

| Rig | Frame | Gap it closes |
|---|---|---|
| `s009` | **tight CU, 顾衍 tasting one spoonful then setting it down** — 85 mm | beat 7 is specified as "tight CU"; `s008` is a 24 mm two-shot. The episode's reveal line happens in a frame that does not exist. |
| `s010` | **tight CU, 苏念's face, freeze** — 85 mm | beat 8 is "freeze on 苏念's face". `s004` is a 50 mm with the pass-through behind her — too much room for a cliffhanger. |
| `s011` | **through the pass-through, 苏念 carrying the pot toward camera** — 35 mm | beat 1 is "interior, pass-through". `s002` is the pot, low, *front* of house. The pass rig looks the other way. |
| `s012` | **shop front from the street at night** — 30 mm | ep02's queue and ep03's 打脸 both open on the frontage. `s001` looks *in through* the door; nothing looks *at* the shop. |

**Caution — read this before running it.** The builder reconstructs the whole scene from the
script on every invocation; `--shot-id` only filters *which passes render*. So adding a rig and
running `--shot-id s009` will **rewrite `huoguo_set.blend`**. The eight existing PNGs are not
touched, but the `.blend` on disk is replaced. If the user has unsaved changes in their open
Blender window, ask first, or duplicate the file to `huoguo_set_pre_rigs.blend` before the run.
The `.blend1` backup will rotate at that moment — the 22:23 build becomes the fallback, which is
the right one.

**Result, 13 Nov 23:31.** Rebuilt with 12 rigs — 431,882 B, sha256 `98b0b81b…ef67`. Checked against
the pre-rigs copy before trusting it: `362 objects / 344 meshes / 8 cameras` →
`366 objects / 344 meshes / 12 cameras`. Exactly +4 cameras, nothing else touched. The file got
41 KB *smaller*, which looks alarming and is only the fresh rebuild's layout — the object and mesh
counts are identical. Rollback: `huoguo_set_pre_rigs.blend`, 473,074 B, sha256 `9296cc0e…`.

| Rig | SIGHTLINE | DEPTHSTAT | lens / camera–target |
|---|---|---|---|
| `s009` | BLOCKED 0.825 `P_Buyer_Head` | 0.317 OK | 85 mm / 0.73 m |
| `s010` | BLOCKED 0.921 `P_Sunian_Head` | 0.331 OK | 85 mm / 1.15 m |
| `s011` | CLEAR | 0.444 OK | 35 mm / 3.07 m |
| `s012` | BLOCKED 0.949 `FrontWall_Over` | 0.435 OK | 30 mm / 2.61 m |

Both close-ups are blocked by the subject's own head and `s012` by the frontage header — those are
the frames, not obstructions. The eight shipped rigs' PNGs were untouched (mtimes still 19:35–19:37).

**Keyframes rendered for all four** — 8.7–8.9 s each, sha256 verified on pull: `s009`→00029,
`s010`→00030, `s011`→00031, `s012`→00032. Submitted by the new `win/batch_keyframes.py` +
`win/shots_laotang_ep01_keyframes.json`, which in the same run rendered `x001`–`x003`
(00026–00028). **All 9 outstanding keyframes now exist; only `s002d` is left.**

Caveat recorded the same evening: the alley was submitted **twice in parallel**, and `x002`/`x003`
were also re-rolled as `x002b` (00024) / `x003b` (00025) with wall-and-door anchoring. Those
re-rolls are canonical; 00026–00028 did not carry the anchoring.

---

### 3. The copper pot, as a library prop — **DONE 13 Nov**

**File:** `work/props/props_laotang.blend`
**Builder:** `win/blender_props_laotang.py`
**Use:** linked into `houxiang` and `huoguo`, never copied

The series is named after this object. Right now the "pot" in the set is `Stall_Pot`, a plain
copper cylinder (`cyl 0.150 × 0.115`), and the hero pot is the 鸳鸯锅 with a divider — which is a
*different* pot, the one 苏建国 keeps. The 旧铜锅 that 苏念 picks out of the rubbish and that
顾衍 recognises is not modelled at all, in any rig, at any angle.

| Object | Detail |
|---|---|
| `Prop_Tongguo` | 0.19 m radius, one ear handle, dented rim (real dent geometry, 4 shallow facets), tarnished — a *separate* mesh from the 鸳鸯锅 so the depth pass distinguishes them |
| `Prop_Tongguo_Lid` | separate, slightly ajar — 顾衍 lifts it in ep03 |
| `Prop_Sign_Cardboard` | 0.55 × 0.40 m folded board, two flaps, no text (text is the generator's job; a modelled glyph fights the depth pass) |
| `Prop_Bowl_White` | the bowl 顾衍 sets down; needed as a *held* object in `s009` |
| `Prop_Chopsticks_Rest` | one pair + rest, for `s009`/`s010` |

**Why a library and not more cylinders in the set builder:** the pot has to appear in the alley,
on the stall, and later in the old shop — three files, one object, one hash. Copy-pasting
geometry into three builders is how the pot ends up two different sizes by episode 4.

**Acceptance:** each prop renders its own isolated turnaround (`prop_<name>_turn.png`, 8 views)
so a keyframe prompt can be checked against a consistent silhouette; the pot's depth pass shows
the ear handle and the dent as shape, not as a smooth cylinder.

**Result, 13 Nov.** `props_laotang.blend` 168,434 B, sha256 `ef8b72b6…1c41a2f9`, 5 collections,
5 merged meshes, overrides `OV_Depth`/`OV_Normal` inside the file. Real `dimensions`, not intent:

| Object | dims (m) | verts | note |
|---|---|---|---|
| `Prop_Tongguo` | 0.384 × 0.373 × 0.155 | 608 | x exceeds y by 11 mm — the facets pulled the ±Y wall in |
| `Prop_Tongguo_Lid` | 0.416 × 0.420 × 0.071 | 1394 | authored ajar in *pot space*, origin at the pot's base |
| `Prop_Sign_Cardboard` | 0.515 × 0.078 × 0.400 | 24 | 0.550 m flat stock, both wings folded to +Y |
| `Prop_Bowl_White` | 0.121 × 0.121 × 0.053 | 544 | |
| `Prop_Chopsticks_Rest` | 0.235 × 0.033 × 0.017 | 112 | |

Sheets, 2048 × 1024, 8 azimuths in a 4 × 2 grid, orthographic, **object rotated and camera
fixed** so the lighting is identical in all eight cells — two views differing only in shading
would read as two different silhouettes:
`prop_tongguo_turn.png` · `prop_tongguo_turn_depth.png` (the pot only) · `prop_tongguo_lid_turn.png`
· `prop_sign_cardboard_turn.png` · `prop_bowl_white_turn.png` · `prop_chopsticks_rest_turn.png`

Guards on the pot's depth sheet: `DEPTHSTAT Prop_Tongguo std=0.454 OK` and
`DENTCHK view0_vs_view4 max=0.776 frac_changed=0.0090 ASYMMETRIC` — opposite views differ over
0.9 % of the frame, which is the ear handle plus the facets. The facets are also measurable in the
bounding box: 0.384 wide against 0.373 deep.

**Pot space.** Pot and lid share one origin — the pot's base centre on the floor, both meshes at
world (0, 0, 0). The lid is authored tilted against that rim, so linking it at the pot's location
reproduces the ajar pose with no extra transform, and every other prop also sits base-at-z=0.

**Three traps paid for here, all silent:**

1. `obj.matrix_world` is the *last evaluated* matrix. Assigning to it in the same tick as
   `obj.scale = size` discards that scale — the sign's two flaps became unit cubes and the board
   measured 1.351 m instead of 0.550 m. 1.351 is exactly a 1 m cube rotated 28°, which is how it
   was spotted. `pivot_rotate()` now bakes from the `loc`/`rot_euler`/`scale` properties and
   rewrites mesh data; never from `matrix_world`.
2. Bake each part's own transform before `join()` — joining parts that carry different
   non-uniform object scales can bake shear into the result. `harvest()` applies transforms per
   part first.
3. A whole-image mean is the wrong test for a small feature. The first `DENTCHK` compared view 0
   with view 4 and returned 0.0057 — a correct number on a correct pot, because the background is
   identical in both frames. It now counts changed pixels (`> 0.05`: 0.0090 of the frame) and
   reports the max delta (0.776).

---

## P1 — the levers the next phase will actually need

### 4. Posed guide variants — the VACE prerequisite

**Not a new file.** A mode in the existing builder: `--pose <shot> <pose>` writing
`sNNN_depth_ctrl_p2.png` / `_p3.png`.

Every depth guide shipped so far is the pose at **t = 0**. Wan therefore invents all motion,
which is why `s001m` held the furniture (camera-only move) and why a clip with a *person*
moving is the real test. If any batch clip drifts, the documented fix is per-frame structural
control (VACE), and VACE needs a guide per keyframe, not one.

Per shot: 3 poses (start / mid / end) at the extremes the prompt asks for — 顾衍 leaning in
(`s003`), 苏念 lifting her eyes (`s004`), the bowl coming up (`s008`). The mannequins are
already rigged enough to rotate a limb; no mocap, no new dependency.

**Acceptance:** a 3-guide set for one shot renders and is *visibly different* frame to frame
(`DEPTHSTAT` std in the same band, but the mean changes) — if the three guides are
indistinguishable, the pose did not take and VACE gets nothing.

### 5. Character turntables — 4 files, one per lead

**Files:** `work/characters/lead1_sunian_turntable.blend`, `lead2_guyan_`, `lead3_shujianguo_`,
`lead4_xiaoman_`
**Builder:** `win/blender_character_turntable.py`

`lead1_mpfb_bust.blend` is a bust preview from the P3 smoke test: one lead, no turntable, no
neutral light rig, not the wardrobe. For LoRA training and for `sameface` checks you need the
same thing four times, built identically, or the training set is inconsistent before training
starts.

One file contains: neutral grey studio, 3-point light rig, camera ring of 8 views at 85 mm,
the character posed at the wardrobe clause from `work/story/wardrobe.md` (apron over sweater /
dark shirt sleeves rolled / shiny short-sleeve shirt + chain / school uniform + backpack), one
render set per lead at 768 × 1344 plus 1024 × 1024 head crops.

**Blocked on nothing.** Building the files needs only MPFB, already used. *Training* is still
blocked (Rule 3, no LoRA trainer approved) — do not install one to satisfy this item.

### 6. Mask/ID pass — makes the wardrobe fix systematic

**Not a new file.** `--mask-only` mode in `blender_set_huoguo.py`, rendering
`sNNN_id_<Object>.png` (flat white on black, one per proxy and hero prop, Standard transform).

Today the shirt is fixed by hand-painting a mask in the ComfyUI MaskEditor, once, per shot. The
same bug appears in any shot where 苏念 is legible — that is most of the episode. An ID pass
gives a pixel-exact mask for `P_Sunian` in all eight rigs at once, for free, and it is derived
from the same geometry that produced the depth pass, so it is always in register.

**Acceptance:** `s004_id_P_Sunian.png` covers the torso and arms and nothing else; feeding it to
`manju_inpaint` at denoise 0.62 changes the shirt and leaves the face untouched.

### 7. Set template — stop the bugs from recurring — **DONE 13 Nov 22:52**

**File:** `work/sets/_template/set_template.blend` + `win/blender_set_template.py`
**Sha256:** `7e8385f73cd6c72a3b1f5c30dbad58eaf92cb04296227decfb4728e172a0e7ed` · 100,209 B
**Build:** `python win\blender_set_template.py --shot-id t000`

A scaffold that carries the decisions already paid for: Standard view transform for guide
passes, AgX for beauty, 768 × 1344, the collection names (`SET`, `FURN`, `PROPS`, `FX`,
`PROXY`), the material-override depth/normal setup, the per-rig ramp function, and the three
guards. New sets are copied from it instead of from a builder that has drifted.

Self-test (`t000`, 48 samples) — a scaffold that merely *looks* right would fail here:

```
SIGHTLINE t000 CLEAR frac=1.000 first_hit=-
TEMPLATE  guide_vt=Standard beauty_vt=AgX res=768x1344 samples=48 ctrl_radius=4
          collections=SET,FURN,PROPS,FX,PROXY overrides=OV_Depth,OV_Normal rigs=1
DEPTH     t000 near=1.64 far=6.88
DEPTHSTAT t000 std=0.138 OK
CTRL      t000 radius=4
```

Reopened headless, the saved file reports
`vt=AgX res=768x1344 colls=SET,FURN,PROPS,FX,PROXY ov=OV_Depth,OV_Normal ramp=1.64-6.88
cams=CAM_t000`, so the overrides and the baked ramp survive the round trip. Passes on disk:
`t000_beauty.png` 889,852 B · `t000_depth.png` 468,924 B · `t000_depth_ctrl.png` 82,540 B ·
`t000_normal.png` 730,117 B · `set_template_cameras.json` 563 B.

**Trap found while building it:** a datablock with zero users is purged when the `.blend` is
saved. `OV_Depth`/`OV_Normal` are only ever *view-layer overrides*, so they have no object
users — the first build wrote a file containing no overrides at all, while rendering correctly in
the same session. Both now set `use_fake_user = True`. Any new material that is only an override
needs the same, or the next set silently re-invents it.

**How a new set starts from it:** copy the file, delete the `Probe_*` objects, replace `SHOTS` in
a copy of the builder. Keep the guard block — it is the only thing that says the guide is flat
before the keyframe does.

---

## P2 — optional, defensible, not on the critical path

| File | What | Why it is not P0/P1 |
|---|---|---|
| `work/cuts/laotang_ep01_animatic.blend` | Blender VSE timeline: 8 clips + slate + timecode, for judging pacing | review tool only. The deliverable is a **Jianying draft on Windows** (Rule 4); a Blender VSE cut is not shippable and must never be mistaken for one |
| `work/sets/huoguo/huoguo_wall_dressing.blend` | 2 framed panels + a menu board for the bare back wall (README known gap 3) | only when a shot needs a specific wall. A generic panel is the generator's job |
| `work/sets/houxiang/houxiang_night.blend` | lit variant of the alley for ep02 | same geometry, different lights — a *variant*, not a build. Do it only after x001–x003 pass |

---

## What is deliberately **not** on this list

| Not doing | Reason |
|---|---|
| New sets for ep02–03 | premise: "Everything in ep02–03 uses the same three set pieces. No new builds." The alley is the only missing piece, and it is ep01. |
| Textures, materials, PBR | the set supplies structure; the generator supplies surface. Adding texture fights the depth pass (README, proven). |
| Steam, rain, crowds, puddles, signage text | all five are cheaper for the video model to invent, and none survive a depth pass. |
| Sculpting / UV / Geometry-Nodes workspaces | 11 Blender workspaces exist; the work uses Layout, Rendering and Scripting. New tabs are new places to be lost. |
| A rigged, animated character in the set | the pipeline drives motion with Wan + (later, if needed) VACE from posed guides. A full animation rig is a month of work that the generator out-performs on screen. |
| Blender on the Spark | not installed, and should not be: Blender is Windows-side by design (Rule 4). |
| Rebuilding `huoguo_set.blend` from scratch | it is finished and correct. Only the *additive* rig pass in item 2 touches it. |

---

## Order of work

1. **Set template** (item 7) — 10 min, prevents the two most expensive guide bugs in everything after it. **Done 13 Nov.**
2. **Copper pot library** (item 3) — the alley cannot be posed without the object it is about. **Done 13 Nov.**
3. **Back alley** (item 1) — the only blocking build for ep01. **Done 13 Nov** (keyframe still to render).
4. **Rig extension `s009`–`s012`** (item 2) — after the batch finishes, so the `.blend` rewrite is not competing with anything. **Done 13 Nov.**
5. **Mask/ID pass** (item 6) — immediately after, because it retro-fixes wardrobe across all 8 rigs cheaply.
6. **Posed guides** (item 4) — only if a batch clip drifts, or when VACE is approved.
7. **Character turntables** (item 5) — whenever the LoRA approval lands; the files can be built before it.

---

## Checklist to paste into a new conversation

> Read `C:\Users\admin\Desktop\manju\nextblender.md` and the "Do not re-derive" table in
> `HANDOVER.md`. Build in the order listed at the bottom of `nextblender.md`. Every `.blend` is
> produced by a script in `win/` — never hand-edit one. Reuse `win/blender_set_huoguo.py` as the
> pattern for a new set: per-rig depth ramp, Standard view transform for guide passes, blurred
> control pass, `SIGHTLINE` and `DEPTHSTAT` guards, `--ctrl-only`. Do not rebuild
> `huoguo_set.blend` wholesale; the only change to it is the additive `s009`–`s012` rig pass, and
> ask the user before that run because it rewrites the file.

## Guard retired, 13 Nov — "byte-identical passes"

Two identical builds of the alley produce different bytes for `_beauty`, `_depth` and `_normal`;
the blurred `_depth_ctrl` pass is byte-stable. Turning Blender's output dither off changed nothing,
so it is the renderer's sampling, not quantisation. Consequence: "the existing PNGs are
byte-identical" **passes for the wrong reason** — the files are untouched, not reproducible — and it
fails the moment anything re-renders, for correct code as readily as broken code. That is the same
failure as a guard that reports a value it did not read.

Guards that survive:

* `sha256` — only on `*_depth_ctrl.png`, the pass actually submitted as the guide.
* "nothing was written" — mtime, or a hash compared **without** re-rendering.
* cross-build equivalence — a perceptual diff, never a hash.

Retired from this file and `HANDOVER.md`: every "byte-identical passes" claim.

## s002d — copper-pot insert, variant route (13 Nov)

`win/blender_pose_s002d.py` — opens the frozen `huoguo_set.blend`, links `Prop_Tongguo` from the
prop library, builds `CAM_s002d` in memory, renders three passes, **saves nothing** (`set:
UNCHANGED` asserted, non-zero exit if it moves). No 13th camera in the canonical file, so the
s006/s008 guides cannot be disturbed by it.

Result: camera az=+36°, dz=0.27, distance fitted to 1.74 m on the projected corners (50 mm);
`DEPTHSTAT s002d std=0.329 OK`; passes `s002d_beauty.png` 831,575 B, `s002d_depth.png` 120,819 B,
`s002d_depth_ctrl.png` 146,919 B.

Three real bugs, all found by guards rather than by eye:

1. **The camera was 0.075 m inside `P_Buyer_Torso`.** A uniformly *white* depth pass means the
   nearest surface is at the ramp's near plane everywhere — a missing instance renders as
   background, not as a near-plane wash. The one-ray test named the defect in a line; a stripped
   repro would have found nothing. Same class as s009/s010: a customer standing at the stall.
   The camera is now chosen by scanning azimuths for a clear line.
2. **`objects.new(name, collection)` is invalid** — a collection instance is an *empty* with
   `instance_type = "COLLECTION"`. The first run died on it.
3. **`"Tongguo"` as a substring matched `Prop_Tongguo_Lid`**, and the lid rendered `DEPTHSTAT
   0.415 OK` — a plausible-looking pass of the wrong object. Exact collection name now, and
   `DEPTHSTAT FLAT` raises instead of printing.

Also learned here: `hide_render` does not remove an object from the depsgraph `ray_cast` reads, so
the hidden `Stall_Pot` stand-in looked like an obstruction at exactly the pot's distance. Clearing
on it is correct; the linked pot occupies the same space.

Not verified: the dent reads only as a wobble on the near rim at this distance. If the insert needs
the dent *legible*, the prop wants another ~8° of yaw and the lamp brought closer — a pose change,
not a framing one.

---

## Updates — 14 Nov (Round 4)

### `depth_range()` — measured subject, not camera distance

The old formula `far = near + max(1.6·d, 3.2)` sized the ramp from **camera distance**. At `s010`'s 0.73 m the head's own 9.6–10.1 cm of depth mapped to **6 of 255 levels** — a flat white disc, and the ControlNet turned the disc's edge into a hoop/wire/cable. That was never a prompt problem.

Reference implementation: **`win/blender_depth_rerange.py`**. It ray-casts a grid over the frame, groups hits by object-name prefix, measures the subject's real depth span, then

```
near = z_lo − 0.15·(z_hi − z_lo)
far  = near + (z_hi − z_lo) / 0.30
```

Result: the head's own depth now occupies **~76 of 255 levels** (up from 6), on `s009` (ramp 0.583–0.903 m) and `s010` (1.042–1.378 m) alike. Both re-rolled clean on the **first** attempt.

The `0.75·d` / `2.0·d` approximation that `HANDOVER.md` carried is **retired** — it was a guess from before the fix. Use the measured-subject rule instead.

**Caveat — `SUBJSTAT` is mislabelled.** It prints `167` for a 0.30 span-frac, but 167 is the *complement* (gap from `z_hi` to `far`), not the subject's span. The subject spans `(z_hi − z_lo)/(far − near)·255` = 76. Quote **6 → 76** for the head's span; do not use `SUBJSTAT` as a quality gate. Fix next time the script is opened: print both, rename the existing one `FARSTAT`.

### Three placements recorded in `work/sets/huoguo/retargets.json` (never saved the set)

| Shot | New placement | Notes |
|---|---|---|
| `s011` | loc (0.30, 3.95, 1.30), target (0.30, 1.23, 1.10), 55 mm | old aim point sat near z ≈ 4 in a 5.5 m tall frame, so a person was unreadable; dropping the aim to z 1.10 put 苏念 and the pot in the lower half. Ramp `builder` 1.636–6.0. |
| `s012` | loc (1.20, −5.90, 1.60), target (0.90, −3.45, **2.20**), 30 mm | raised from z 2.45; `--hide Bead` (curtain strands are surface, not structure) |
| `s002d` | loc (1.58, −3.68, 1.00), target (1.08, −4.32, 0.82), 50 mm, `--ramp hug`, `--subject Stall_Pot` | the wall behind won the "largest group" contest; a prop insert needs an explicit subject. Ramp 0.602–1.585. |

Fold these into `SHOTS` the next time the set is legitimately rebuilt — nobody needs a 13th/14th camera today.

### `s012` — no stall, by decision

`s012` still has **no stall**. The beat is carried by the off-screen queue. Recorded as a decision, not a to-do. Do not add a stall to satisfy a checklist.

### `s012` target-z — canonical value

Three values are in circulation: **1.25** in the saved set (and `set_huoguo_cameras.json`), **2.20** in `retargets.json` and the shotlist, and ~2.45 in older notes. **2.20 is the canonical render** (that is what `s012m` / `s012b` were produced from). 1.25 is just what the saved set happens to hold.

### Provenance habit (now automated)

After any render batch: `python win/mirror_provenance.py`, then `bin/doctor.sh`. `doctor.sh` fails on drift until you do — that is the point. See `newsession1.md` §3.1.
