# 《老汤》ep01 — 90-second shot list

Written 2026-11-13, after the 8-clip batch. Supersedes "8 clips" as the unit of work: a 90 s episode
is **19 five-second units**, because Wan 2.2 TI2V-5B caps at 121 frames = 5.04 s @ 24 fps. There is no
longer-shot option on this model, so pacing is done by trimming inside the units at the cut.

- **Target:** 90 s, 9:16, 红果 cadence — reversal at 20 s, reversal at 45 s, reveal at 78 s, freeze at 88 s.
- **Raw material:** 19 × 5.04 s = 95.8 s, trimmed ~6 % at the cut. No unit needs to be longer than 5 s.
- **Territory:** every shot `both`. No engine with a territorial exclusion is used in this story.
- **Wardrobe:** every prompt carries the clause from `wardrobe.md` for each legible character.
- **Existing vs new:** **19 of 19 units have a finished clip** (last five landed 14 Nov 01:05–02:05).
  18 canonical files (`s001m` serves two units; `s003m_00003` is the superseded first pass).
- **CU depth ramp — found 14 Nov 00:30, fixed 00:50.** `depth_range()` sizes the ramp from camera
  distance (`far = near + max(1.6·d, 3.2)`), which is right for a wide and wrong for a close-up. On
  `s010` the head occupies **6 of 255 levels** — a flat white disc on black — and a depth ControlNet
  given a disc renders the disc's outline as an object: a wooden hoop round 苏念's head, a wire across
  顾衍's chest, cables across the shop front. The fix measures the character's own depth span by
  ray-casting a grid and sets `near = z_lo − 0.15·(z_hi−z_lo)`, `far = near + (z_hi−z_lo)/0.30`:
  76 → **167 of 255 levels**. Both CUs re-rolled clean on the first attempt. `win/blender_depth_rerange.py`.
- **Parallel duplication, 13 Nov:** the alley was submitted **twice at the same time** — `x001`
  00021 / `x002b` 00024 / `x003b` 00025 from one session, and `x001`–`x003` 00026–00028 from
  another. The 00024/00025 re-rolls carry the wall/door anchoring that keeps the three frames in
  one alley; the 00026–00028 pass was prompted without those anchors. **Treat 00021/00024/00025 as
  canonical** and compare before shipping anything.

## The list

| # | In–out | Beat | Shot | Rig | Source | What we see | Audio |
|---|---|---|---|---|---|---|---|
| 1 | 0.0–2.5 | 1 | `s002m` | s002 | **clip done** | pot close-up, steam rising, red stools behind | VO 苏念: 「我妈留给我的，只有这锅汤。」 |
| 2 | 2.5–8.0 | 1 | `s011m` | s011 (aim z 1.10, 55 mm) | **clip done** | through the pass-through: 苏念 carrying the pot toward camera, shelf and bowls framing her | VO ends; kitchen clatter |
| 3 | 8.0–11.0 | 2 | `s001m` | s001 | **clip done** | wide from the door: she stops, he steps into her path | room noise drops |
| 4 | 11.0–16.5 | 2 | `s003m` | s003 | **clip re-rolled 13 Nov** | two-shot, he leans over the table | 苏建国: 「这店，从今天起不姓你。」 |
| 5 | 16.5–20.0 | 2 | `s002c` | **s002 variant** | **clip done** | low on the pot as it goes over, broth across the table | pot crash, gasps |
| 6 | 20.0–24.0 | 3 | `s005m` | s005 | **clip done** | 顾衍 at the window, looks up, does not move | silence, steam |
| 7 | 24.0–29.0 | 3 | `s004em` | s004 | **clip done** | 苏念's face, eyes lifting, pass-through behind | her breath |
| 8 | 29.0–33.0 | 3 | `s007bm` | s007 | **clip done** | reverse wide: the room frozen, diners not eating | a stool scrapes |
| 9 | 33.0–38.0 | 4 | `s004g` | **s004 variant** | **clip done** | she steadies the apron at her waist, looks away, no argument | 苏念: 「锅，我拿走。」 |
| 10 | 38.0–45.0 | 4 | `s001m` | s001 | **reuse** | wide: she walks out through the beaded curtain, apron still on | curtain beads, door |
| 11 | 45.0–50.0 | 5 | `x001` | x001 (alley) | **clip done** | alley wide: she walks out of the lit back door, the copper pot at the kerb | rain starts |
| 12 | 50.0–56.0 | 5 | `x002` | x002 (alley) | **clip done** | low: the old copper pot in the rubbish, dented, rain running off it | metal scrape |
| 13 | 56.0–60.0 | 5 | `x003` | x003 (alley) | **clip done** | over her shoulder: 苏建国 framed in the lit door, watching her go | 小满 (off-screen): 「姐，今晚吃什么？」 苏念: 「火锅。」 |
| 14 | 60.0–65.0 | 6 | `s006m` | s006 | **clip done** | street stall: folding table, one pot, steam in the lamp light | market ambience |
| 15 | 65.0–70.0 | 6 | `s012m` | s012 (target z 2.20) | **clip done** | the old shop front at night, lights on, red stools out front | a queue murmurs off-screen |
| 16 | 70.0–75.0 | 6 | `s008m` | s008 | **clip done** | first customer sits: 顾衍, no coat, no expression | stool, bowl set down |
| 17 | 75.0–82.0 | 7 | `s009m` | s009 (new rig) | **clip done** | tight CU: spoon to his mouth, he stops, sets it down | 顾衍: 「这锅汤，我找了十五年。」 |
| 18 | 82.0–88.0 | 7 | `s002d` | **`s002d` new — street stall, low** | **clip done** | insert: the copper pot, steam, the dent catching the lamp | steam, rain |
| 19 | 88.0–90.0 | 8 | `s010m` | s010 (new rig) | **clip done** | tight CU 苏念, still, eyes wet, no reaction | silence → episode card |

## Render queue — closed 14 Nov 02:05

Every unit has a clip. What follows is the order it was built in, and what each stage taught, because
the sequence is the argument for how the remaining units got their guides.

**Wave 0 — done 13 Nov (existing rigs)**

| Shot | Depth guide | Prompt note | Result |
|---|---|---|---|
| `s002c` | `s002c_depth_ctrl.png` (posed) | pot lying on its side, mouth to camera, broth across the table | 00020; needed a **posed guide** — the upright-pot pass produced an upright pot with the broth spilled around it |
| `s004g` | `s004_depth_ctrl.png` | she steadies the apron at the waist | 00019 + clip 00010; the apron does not come off and does not need to |

`win/blender_pose_s002c.py` re-poses the pot without touching `huoguo_set.blend`; the set's hash is
asserted unchanged. Lesson for every remaining shot: **the guide decides pose, the prompt decides
surface.** A pose the set does not contain cannot be prompted into being.

**Wave 1 — rigs built 13 Nov, all four resolved 14 Nov.** Rigs `s009`–`s012` passed SIGHTLINE /
DEPTHSTAT but sat too close for their depth ramp — that is the defect described at the top of this
file. `win/blender_retarget_rig.py` moved the two wide rigs and re-rendered every guide with the
measured-subject ramp.

| Shot | Verdict |
|---|---|
| `s009` | **done** — keyframe `s009c` (00037), clip `s009m` (00015, 396 s). Hugged ramp 0.583–0.903 m, subject 167/255 levels, no wire across the chest. 00033 had cast him at ~50 against a 30-year-old; 00035 fixed the age, 00037 fixed the ramp. |
| `s010` | **done** — keyframe `s010c` (00036), clip `s010m` (00016, 416 s). Hugged ramp 1.042–1.378 m, subject 167/255 levels; the beige hoop did not reappear on the first re-roll. |
| `s011` | **done** — re-aimed from z ≈ 4 (a 5.5 m tall frame, person unreadable) to **(0.30, 1.23, 1.10) at 55 mm**, camera left at (0.30, 3.95, 1.30). Keyframe `s011c` (00039) carries one pot with 苏建国 behind her; clip `s011m` (00017, 406 s, sha `a6ce369c…`). The alembic still and the daytime kitchen were consequences of the unreadable framing, not of the prompt. |
| `s012` | **done** — target z raised 2.45 → **2.20**, `Bead` curtain hidden for the depth pass (surface, not structure). Keyframe `s012b` (00042), clip `s012m` (00019, 406 s, sha `808857c3…`). The overhead cables stay in frame: a Chongqing street with cables is plausible, and the shop front, stools and night grade all read. Still **no stall** — the beat is carried by the queue heard off-screen. |

**Wave 2 — the alley, unblocked and rendered 13 Nov**

| Shot | Guide | Result |
|---|---|---|
| `x001` | `x001_depth_ctrl.png` | 00021 — alley wide, rain, door light, copper pot at the kerb. Clip `…_00012_.mp4` (421 s, sha `97da68df…`): she walks to camera, walls and pot hold. |
| `x002` | `x002_depth_ctrl.png` | **re-rolled** as `x002b` (00024): the first pass put the pot in a brick niche with a red bin and a golden grade — a different alley from `x001`. Anchoring the wall as *worn grey plaster* and the door as *dark painted wood* fixed both. Clip `…_00013_.mp4` (421 s, sha `074f22c6…`): rain, reflections, pot holds. |
| `x003` | `x003_depth_ctrl.png` | **re-rolled** as `x003b` (00025): the first pass painted a metal-framed glass door with signage, contradicting `x001`'s wooden door. Same anchoring fix. Clip `…_00014_.mp4` (421 s, sha `cced40d2…`): 苏建国 stays in the doorway, she turns her head. |
| `s002d` | `s002d_depth_ctrl.png` | **rig built 13 Nov night; shot 14 Nov.** Own camera at the stall, low, 50 mm, at (1.58, −3.68, 1.00) aiming at (1.08, −4.32, 0.82) and framed on `Stall_Pot` only — the ray-cast "largest group" is the wall behind, which is right for a person and wrong for a prop insert. Ramp `hug` 0.602–1.585 m. Keyframe 00041 (copper hotpot, no hole; 00040 rejected for a punched-out hole), clip `s002d` (00018, 406 s, sha `f6e1af69…`). |

## Cost

- Keyframe: ~9 s each when the queue is free, up to ~250 s behind a clip.
- Clip: 400–430 s each on the GB10. **Zero clips left** — the last five (`s009m`, `s010m`, `s011m`,
  `s002d`, `s012m`) took 25 min of GPU on 14 Nov 01:05–02:05.
- Blender work left: **none for picture.** The three variant rigs live in
  `work/sets/huoguo/retargets.json` for if a re-roll is ever needed; nothing has to be re-rendered.

The whole episode's picture cost ~2 h 30 min of GPU across two evenings.

**Contact sheets:** `board_a` … `board_f.jpg` in `work/laotang_ep01/` hold one row per shot at frames
0/30/60/90/120. `board_f` verifies the last five clips (950×1825, 5 rows × 5 frames).

## What is deliberately not in this list

- No crowd shots. The queue is heard, not shown, until ep40 (premise).
- No second location beyond the alley and the street strip.
- No shot needing a character LoRA. Every face here is the generator's, held by wardrobe and depth only.
- No 10-second takes. The model cannot make one.
- **小满 has no face in ep01.** Her line is off-screen over unit 13. The alley rig frames an adult
  proxy in the lit doorway (that is 苏建国, per the builder's own note), so there is nowhere to put a
  12-year-old without re-rigging — and a voice-only entrance is a legitimate 红果 hook.

## Audio map (for Phase 4)

| Time | Character | Line |
|---|---|---|
| 0.0–7.5 | 苏念 VO | 「我妈留给我的，只有这锅汤。」 |
| 11.0–16.5 | 苏建国 | 「这店，从今天起不姓你。」 |
| 33.0–38.0 | 苏念 | 「锅，我拿走。」 |
| 56.0–59.0 | 小满 / 苏念 | 「姐，今晚吃什么？」 / 「火锅。」 |
| 76.0–82.0 | 顾衍 | 「这锅汤，我找了十五年。」 |

Five lines, four speakers. 苏念's VO and her dialogue are the same voice but different delivery —
VoiceDesign should produce them as two presets, not one.
