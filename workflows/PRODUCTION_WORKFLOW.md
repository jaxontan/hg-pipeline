# 红果漫剧 production workflow

How an episode gets made on this machine, from IP bible to a finished 1080×1920 file.
Everything below was run on the DGX on 2026-11-17; the numbers are measured, not estimated.

The original seven lanes generate each shot from text alone, so a character is re-invented in
every shot. This workflow changes one thing and everything else follows from it:

> **Every shot starts from a keyframe, and every keyframe is conditioned on the character
> sheet and the location plate.** Text decides what happens; images decide who and where.

```
 bible.json ──► ASSETS ──► KEYFRAMES ──► VOICE ──► ANIMATIC ──► VIDEO ──► ASSEMBLE ──► ep.mp4
 episode.json    Klein      Klein+refs    Qwen3-TTS  ffmpeg       LTX-2.5    ffmpeg
                 Z-Image                                           i2v / talk
        gate ①: approve cast     gate ②: contact sheet     gate ③: animatic     gate ④: takes
```

One command runs any stage, and every stage skips what already exists:

```bash
cd ~/Desktop/AIGC-PP2 && . ./env.sh
venv/bin/python -m pipeline.cli produce --show demo --episode ep00 --stage all
venv/bin/python -m pipeline.cli produce --show demo --episode ep00            # status table
```

---

## 1. Who does what

| Role | Owns | File / output | Lane |
|---|---|---|---|
| **IP / showrunner** | look, cast, wardrobe, voices, locations | `projects/<show>/bible.json` | — |
| **Casting & art** | character sheets, location plates | `assets/input/<show>/char_*.png`, `loc_*.png` | `image_character`, `image_ref`, `image_fast` |
| **Screenwriter** | beats, lines, hook and cliffhanger | `episodes/<ep>.json` → `dialogue`, `note` | — |
| **Director** | what each shot shows and what moves | `action`, `motion`, `duration`, `key_from` | — |
| **Camera** | size, angle, lens, move, light | `size`, `angle`, `lens`, `move`, `light` | `image_ref` (framing) + `video_ltx_i2v` (movement) |
| **Actors** | performance, lip-sync | keyframe + voice line | `video_ltx_talk` |
| **Sound** | voices, ambience | `voice`, `emotion`, `sound` | Qwen3-TTS, LTX native audio |
| **Editor** | cut, subtitles, loudness, label | `shots.json`, `<ep>.mp4`, `<ep>.srt` | `assemble` |

In practice the writer, director and camera are whoever edits the episode JSON — you, or Claude
Code working from a script. The pipeline's job is to make that file the single source of truth.

---

## 2. The lanes this workflow adds

| Lane | What it does | Output | Measured |
|---|---|---|---|
| `image_ref` | FLUX.2-Klein with reference images chained through `ReferenceLatent`. Sheet + plate in, keyframe out. | 1088×1920 still | **18–21 s** |
| `video_ltx_i2v` | LTX-2.5 two-pass, keyframe pinned as frame 0 in both passes. Makes its own ambience. | 1088×1920, 24 fps | **129 s (2 s shot) · 180–192 s (3 s) · 241–246 s (4 s)** |
| `video_ltx_talk` | Same graph, plus the voice wav encoded by the audio VAE and frozen with a zero noise mask, so the picture is generated *to* the speech. | 1088×1920, audio-length | **240 s (4.0 s line) · 297 s (4.7 s, incl. model swap)** |

`video_ltx_talk` is the default for dialogue, ahead of Wan S2V. It is the same model and the same resolution as
every other shot, so dialogue no longer looks softer than the shots around it (the README's
"480×832 is soft" limit), and it needs no frame-extraction step. S2V is kept as a per-shot
fallback, and the demo needed it once — see §5.

Graphs: `workflows/image_ref.api.json`, `video_ltx_i2v.api.json`, `video_ltx_talk.api.json`
— drag onto the ComfyUI canvas to inspect. Wiring follows the bundled `video_ltx2_5_i2v`,
`video_ltx2_3_ia2v` and `image_flux2_klein_image_edit_4b_distilled` templates.

---

## 3. Stage by stage

### Stage 0 — write the bible (`projects/<show>/bible.json`)

Start from `workflows/templates/bible.json`.

| Field | Why it matters |
|---|---|
| `style.look` | Prepended to every keyframe. One sentence; this is the show's grade. |
| `style.video` | Appended to every video prompt. State what the world *is* ("1983 period setting"). Writing "no cars" did not keep cars out, and at CFG 1.0 the negative prompt is inert. |
| `characters.<id>.appearance` | Age, build, face, hair. Used once, to cast the face. |
| `characters.<id>.wardrobe` | Named outfits. Each one gets its own sheet; a shot picks one with `"wardrobe": {"chen": "funeral"}`. |
| `characters.<id>.noun` / `token` | How prompts refer to them: `noun` in keyframes ("the man from image 1"), `token` in video ("the middle-aged man in the navy Mao suit"). Keep `token` visual — the video model has never heard the character's name. |
| `characters.<id>.voice` | The fixed half of the TTS description. A shot's `emotion` is appended to it. |
| `locations.<id>.prompt` / `short` | `prompt` generates the plate; `short` reminds the keyframe what to keep. |
| `finish` | `burn_subtitles`, `loudnorm`, `label` (on-screen AI-content notice). |

### Stage 1 — assets (gate ①: approve the cast)

```bash
venv/bin/python -m pipeline.cli produce --show demo --stage assets
```

Per character and wardrobe: a face portrait is cast from text, a full-length body is generated
*from that face*, and the two are joined into one sheet. Per location: one empty plate.
Results land in `assets/input/<show>/`.

**Look at every sheet before going on.** Everything downstream inherits these faces. To recast,
change the character's `seed` (or its description) and rerun with `--force --only chen`.
To use your own art instead, save it under the same filename — the stage never overwrites an
existing file without `--force`.

### Stage 2 — shot list (`projects/<show>/episodes/<ep>.json`)

Start from `workflows/templates/episode.json`. One object per shot:

| Field | Meaning |
|---|---|
| `id` | Unique, in cut order (`S01`…). |
| `characters`, `location` | Ids from the bible. They become the keyframe's reference images. |
| `size`, `angle`, `lens` | Framing — see the camera table below. |
| `action` | What the **first frame** shows. Write `{chen}` where the character is named. |
| `motion` | What **changes** during the shot. Defaults to `action`. |
| `move` | Camera movement. |
| `light`, `sound` | One phrase each. `sound` becomes LTX's ambience on non-dialogue shots. |
| `dialogue` | `{who, text, emotion, acting}` → lip-sync shot, length set by the line. Add `"vo": true` for a line heard over a shot of something else. |
| `duration` | Seconds, for shots without lip-sync (default 4). |
| `key_from` | Reuse another shot's keyframe — for a reaction that continues the same setup. |
| `talk_lane` | `"video_s2v"` sends this dialogue shot through Wan S2V instead of LTX (see §5, painted captions). |
| `take`, `key_take`, `seed` | Reroll handles (see stage 5). |

#### Camera language

Use a code or write your own phrase; unknown values pass through verbatim.

| `size` | Use it for |
|---|---|
| `ELS` `LS` | Where are we; exits and entrances. Rare — a phone screen punishes wide shots. |
| `MS` `MCU` | The default. Most dialogue. |
| `CU` `ECU` | Hooks, reversals, decisions. The money shots. |
| `TWO` `OTS` | Confrontation; who has the power in the room. |
| `INSERT` | The prop, the letter, the hand — a cheap way to buy rhythm. |
| `POV` | Discovery. |

| `angle` | `eye` · `low` (power) · `high` (defeat) · `top` · `dutch` (unease) · `profile` · `back` |
|---|---|

| `move` | Reads as |
|---|---|
| `static` | Default. Lets the face do the work. |
| `push_in` | Pressure rising; the standard move on a line that matters. |
| `crash_zoom` | Shock. The 反转 beat. Keep the shot to ~2 s. |
| `pull_out` | Reveal, or abandonment. |
| `pan_left` `pan_right` `tilt_up` `tilt_down` | Redirecting attention. |
| `track_left` `track_right` `follow` `lead` | Walking and talking. |
| `orbit` `crane_up` | Scale; openings and endings. |
| `handheld` `rack_focus` | Instability; shifting attention inside one frame. |

#### 红果 short-drama craft rules the shot list should obey

These are editorial conventions of the format, not pipeline constraints:

1. **Open on conflict.** The first shot is a face and a line, not an establishing shot.
   The viewer decides in about three seconds.
2. **One beat per shot, 2–5 s.** A line longer than ~14 characters is two shots or a rewrite.
3. **A turn every 15–20 s**, and one real reversal per episode.
4. **End on an unanswered question.** The last shot is the reason to tap the next episode.
5. **Faces in the upper two thirds.** The bottom fifth and the right edge belong to the app's
   caption and buttons; subtitles here sit just above that zone.
6. **Dialogue carries the plot; pictures carry the emotion.** If the sound were off, the
   subtitles alone should tell the story.

### Stage 3 — keyframes (gate ②: the contact sheet)

```bash
venv/bin/python -m pipeline.cli produce --show demo --episode ep00 --stage keyframes,sheet
```

One still per shot, each conditioned on the sheets of the characters in it and the plate of its
location. `sheet` writes `projects/<show>/<ep>/<ep>_keyframes.jpg` — every shot on one page.

Judge three things there, because they are cheap to fix now and expensive later: is it the
same person in every frame, does the framing match the shot size, do consecutive shots cut
(eyelines, screen direction, light). Reroll one shot by setting `"key_take": 2` on it and
rerunning the stage.

### Stage 4 — voice and animatic (gate ③: does the cut work?)

```bash
venv/bin/python -m pipeline.cli produce --show demo --episode ep00 --stage voice,animatic
```

All lines are generated in one model load. `animatic` cuts the stills to the voice at real shot
lengths into `<ep>_animatic.mp4` — a few seconds of CPU. Watch it with sound: pacing, line
readings and the cliffhanger are all judgeable here, before any video is rendered.
Redo a line by editing `emotion`/`text` and rerunning `--stage voice --only S04 --force`.

### Stage 5 — video (gate ④: takes)

```bash
venv/bin/python -m pipeline.cli produce --show demo --episode ep00 --stage video
```

Shots with a `dialogue` go to `video_ltx_talk`; everything else, including voice-over shots, to
`video_ltx_i2v`. Both use the same model, so the whole stage runs without a model swap.

A bad take is rerolled, not edited: set `"take": 2` on the shot (seed + 1) and rerun. The old
take stays on disk; the episode uses whichever number the JSON names.

### Stage 6 — assemble

```bash
venv/bin/python -m pipeline.cli produce --show demo --episode ep00 --stage assemble
```

Every clip is cover-cropped to 1080×1920 / 24 fps, voice-overs are mixed over their shot's
ambience, subtitles are burned in phrase by phrase (≤ 14 characters on screen at a time),
audio is normalised to −16 LUFS, and the AI-content label is drawn top-left.
Outputs: `projects/<show>/<ep>/<ep>.mp4`, `<ep>.srt`, `shots.json`.

---

## 4. Single-shot commands

The runner is built from these; use them directly for experiments.

```bash
# keyframe from references (the prompt calls them image 1, image 2 …)
venv/bin/python -m pipeline.cli image --ref assets/input/demo/char_chen_default.png \
  --ref assets/input/demo/loc_street_dusk.png --out key_test \
  --prompt "Photoreal film still, medium close-up. The man from image 1 stands in the street from image 2 …"

# keyframe -> shot
venv/bin/python -m pipeline.cli video --lane video_ltx_i2v --image key.png --length 97 \
  --prompt "He lowers the mug and looks down the street. The camera slowly pushes in." --out s01

# keyframe + line -> lip-synced shot (length comes from the wav)
venv/bin/python -m pipeline.cli talk --image key.png --audio assets/audio/line_01.wav \
  --prompt "The man speaks in Mandarin Chinese, lips in sync, calm and restrained." --out s02

# finishing flags on the plain assembler
venv/bin/python -m pipeline.cli assemble --shots shots.json --out ep.mp4 \
  --fit cover --burn-subs --loudnorm --label "内容由AI生成"
```

---

## 5. Measured cost

The demo episode (`workflows/templates/`, 6 shots, 20.9 s finished) on this machine:

| Stage | What ran | Time |
|---|---|---|
| assets | 2 faces, 2 bodies, 1 plate | 52 s |
| keyframes | 5 stills at 1088×1920, two references each | 97 s (18–21 s each) |
| sheet | contact sheet | 1 s |
| voice | 3 lines, one model load | 52 s |
| animatic | stills + voice | 5 s |
| video | 4 × i2v, 2 × talk at 1088×1920 | 21.4 min |
| assemble | crop, subtitles, loudness, label | under 1 min |

| Shot length | Frames | `video_ltx_i2v` | `video_ltx_talk` |
|---|---|---|---|
| 2.0 s | 49 | 129 s | — |
| 3.0 s | 73 | 180–192 s | — |
| 4.0 s | 97 | 241–246 s | 240 s |
| 4.7 s | 113 | — | 297 s (first shot after a model swap) |

That is about **60× realtime** for finished 1088×1920 video, against the 31× the README
measured for text-only 1024×1536. The keyframe-first lanes cost roughly twice as much per second
and buy a stable cast, native 9:16 and full-resolution lip-sync. Everything before the video
stage is under four minutes per episode, which is why the gates sit there.

Budget from these numbers, one take per shot: a 2.5-minute episode is about **2.5 h** of video
rendering; 30 episodes (75 min) about **76 h**. Plan on 1.5× for rerolls. The README's season
budget (§7) predates these lanes and is lower than this.

### The defect to watch for: captions painted into dialogue shots

`video_ltx_talk` sometimes draws its own garbled Chinese captions into the picture. In the demo
it happened on **one dialogue shot in all four takes** (S04) and on the other dialogue shot in
neither of two takes (S01). What was tried on S04, and failed:

| Attempt | Result |
|---|---|
| Reroll with a new seed | captions again |
| Dialogue prompt without "in Mandarin Chinese" | captions again |
| New keyframe (`key_take: 2`) | captions again |
| Video CFG 2.5 + negative "subtitles, captions, on-screen text" | captions again, harsher skin, 362 s instead of 250 s — rejected |

The cause is not established. What works is the escape hatch: put
`"talk_lane": "video_s2v"` on the shot and it is lip-synced by Wan S2V from the same keyframe
and wav instead (151 s). That take is 480×832 upscaled, so it is softer and the mouth moves
less, but it never draws text. The demo's S04 is cut that way.

**Check every `talk` take for painted text before assembling** — the burned-in subtitle sits
right below where the fake one appears, so it is easy to miss in a thumbnail.

---

## 6. What is still open

| Limit | Effect | Next step |
|---|---|---|
| **Voice timbre is re-designed per line.** Qwen3-TTS *VoiceDesign* builds a voice from the description each time; the same description gives a similar voice, not an identical one. | A character's voice can drift between lines, more so when `emotion` changes. | Download `Qwen3-TTS-12Hz-1.7B-Base` (Apache-2.0) and clone each character's voice from one approved VoiceDesign clip. The donor is synthetic, so no licence question arises. |
| Identity comes from one reference pass. | Good within a scene; extreme angles and profile shots drift most. | Add a profile view to the sheet; for the lead, train a Klein LoRA on ~20 approved keyframes. |
| Two characters in one frame. | Works, but faces can blend when both are small. | Prefer `OTS` and alternating singles — also the format's convention. |
| **LTX paints captions into some dialogue shots.** | One of the demo's two dialogue shots, every take. | Per-shot `talk_lane: video_s2v` fallback today; root cause still to find (candidates: the frozen-audio conditioning, close frontal framing). |
| `static` is not fully static on dialogue shots. | The camera still creeps in during a line. | Untested: pin the keyframe as a last-frame guide too (`LTXVAddGuide`). |
| Lip-sync was checked on stills, not scored. | A take can be loose on fast lines. | Watch dialogue takes with sound; try `"modality_scale": 3.0` in the `video_ltx_talk` lane (one extra forward pass per step). |
| No music or sound-design bed. | Episodes are voice + per-shot ambience only. | Needs licensed music or a local music model; not solved here. |
| Period and text errors (modern cars, garbled signage). | Occasional. | Era rules in `style.video`; fix at the keyframe stage, where rerolls cost seconds. |

Before publishing, confirm the platform's current rules yourself: the AI-generated-content
label wording and placement, and the filing/licence requirements for 微短剧 on 红果. The
pipeline draws whatever `finish.label` says; it does not know what the platform requires.
