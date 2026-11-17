# PIPELINE.md — the AIGC-PP2 ComfyUI pipeline

Everything here runs against ComfyUI on `127.0.0.1:9090`. No file lives outside `$ROOT`.

```
~/Desktop/AIGC-PP2/
├── pipeline/            ← this layer (config, graphs, client, CLI)
├── workflows/           ← exported API graphs, one per lane (generated, do not hand-edit)
├── projects/<name>/     ← manifest.jsonl + shots.json + finished episode
├── assets/input/        ← media ComfyUI can read (refs, driving clips, speech wavs)
├── assets/audio/        ← Qwen3-TTS output
├── outputs/<project>/<lane>/<name>_00001_.mp4|png
└── models/              ← 115 GB, read-only from the pipeline's point of view
```

## Quick start

```bash
cd ~/Desktop/AIGC-PP2
. ./env.sh

venv/bin/python -m pipeline.cli health     # is the server up?
venv/bin/python -m pipeline.cli lanes      # every lane + measured cost
```

## Lanes

| Lane | Engine | Resolution | ~Time | Use for |
|---|---|---|---|---|
| `image_fast` | Z-Image-Turbo | 832×1216 | 9 s | keyframes, backgrounds, props |
| `image_character` | FLUX.2-Klein-4B | 896×1152 | 6 s | character sheets, multi-ref |
| `video_ltx_preview` | LTX-2.5 single pass | 512×768, 97f | 50 s | animatics, blocking |
| `video_ltx_final` | LTX-2.5 two-pass | 1024×1536, 97f | 125 s | **final shots** |
| `video_wan_t2v` | Wan2.2 TI2V 5B | 704×1280, 121f | 455 s | draft / I2V fallback |
| `video_s2v` | Wan2.2 S2V 14B + LoRA | 480×832, audio-length | 130 s | dialogue / lip-sync |
| `video_animate` | Wan2.2 Animate 14B | 480×832, 49f | 376 s | motion transfer (real footage only) |

LTX lanes generate their own audio; that is the cheapest ambience source.

## Commands

```bash
# still
venv/bin/python -m pipeline.cli image --lane image_fast \
  --prompt "1980年代县城老街，黄昏，穿中山装的中年男人背影" --out man_01

# video (final quality)
venv/bin/python -m pipeline.cli video --lane video_ltx_final --project ep01 \
  --prompt "Photoreal cinematic: ..." --out shot_001

# voice (runs in venv-tts automatically)
venv/bin/python -m pipeline.cli voice --out line_01 \
  --text "老陈，这搪瓷缸子跟了你二十年了。" \
  --instruct "中年男性，沙哑低沉，语速缓慢，带北方口音"

# dialogue: lip-sync a still to that line; length is derived from the wav
venv/bin/python -m pipeline.cli dialogue --project ep01 --out shot_002 \
  --prompt "A middle-aged man in a navy Mao suit speaks to camera beside a street lamp" \
  --audio assets/audio/line_01.wav --ref outputs/ep01/video_ltx_final/shot_001_00001_.mp4
```

`--ref` for `dialogue` must be an image; extract a frame first:

```bash
ffmpeg -y -ss 2 -i outputs/ep01/video_ltx_final/shot_001_00001_.mp4 -frames:v 1 assets/input/ref_001.png
```

## Assembly

```bash
cat > projects/ep01/shots.json <<'JSON'
[{"file": "outputs/ep01/video_ltx_final/shot_001_00001_.mp4"},
 {"file": "outputs/ep01/video_s2v/shot_002_00001_.mp4"}]
JSON
venv/bin/python -m pipeline.cli assemble --shots projects/ep01/shots.json \
  --out projects/ep01/ep01.mp4
```

Every clip is normalised to 1080×1920 / 24 fps / H.264 + AAC before concatenation, so mixed
engines and resolutions join cleanly.

## Reproducibility

Each run appends one line to `projects/<name>/manifest.jsonl`:

```json
{"ts": "...", "lane": "video_ltx_final", "prompt": "...", "params": {...},
 "graph_hash": "3f1a...", "files": ["ep01/video_ltx_final/shot_001_00001_.mp4"], "elapsed_s": 125.1}
```

`graph_hash` is a SHA-256 of the exact submitted graph, so any take can be replayed or diffed
against a later change in defaults.

## Exported workflows

```bash
venv/bin/python -m pipeline.cli export-workflows      # write workflows/<lane>.api.json
venv/bin/python -m pipeline.cli describe              # every lane, as text
venv/bin/python -m pipeline.cli describe --lane video_ltx_final
```

Writes `workflows/<lane>.api.json` — the same graphs the CLI submits, for inspection, diffing,
or submission by any other client. Regenerate after editing `pipeline/config.json`.

`describe` prints each lane as a numbered node list plus its wiring (`#24 SamplerCustomAdvanced.latent_image <- #19 LTXVConcatAVLatent`), which is the fastest way to read a graph without a browser.

To open an exported graph in the ComfyUI UI, drag the `.json` onto the canvas (or
Workflow → Open). The frontend recognises API-format JSON and rebuilds the node graph from it; the
layout is auto-arranged, so it is for inspection, not for hand-editing. Copy the files to your
desktop first — they live on the Linux host:

```powershell
scp tdadmin@192.168.1.103:"~/Desktop/AIGC-PP2/workflows/*.api.json" C:\Users\admin\Desktop\AIGC-PP2\workflows\
```

## Accessing the UI

ComfyUI listens on `0.0.0.0:9090` (set 2026-11-16 at your request), so the web UI is at:

```
http://192.168.1.103:9090
```

Change the bind without editing the launcher:

```bash
pkill -f 'ComfyUI/main.py'
COMFY_BIND=127.0.0.1 bash ~/Desktop/AIGC-PP2/start_comfy.sh   # localhost only
COMFY_BIND=0.0.0.0   bash ~/Desktop/AIGC-PP2/start_comfy.sh   # LAN (default)
```

**The server has no authentication and custom nodes execute arbitrary Python.** While it is on
`0.0.0.0`, anyone who can reach 192.168.1.103:9090 can run code as `tdadmin`. That is acceptable on
a trusted home LAN; do not leave it bound this way on a shared or public network. The alternative,
which needs no exposure at all, is an SSH tunnel from your desktop:

```powershell
ssh -N -L 9090:127.0.0.1:9090 tdadmin@192.168.1.103   # then open http://127.0.0.1:9090
```

## Rules baked in

- The CLI talks to `127.0.0.1` regardless of the bind, so pipeline runs never depend on LAN exposure.
- Media that ComfyUI must read is copied into `assets/input` (`ensure_input`), never referenced
  from outside.
- `dialogue` computes frame count from the wav (`4k+1` frames at 16 fps) so audio and video
  never drift.
- Failed runs raise `ComfyError` with the server's `execution_error` payload and record nothing
  in the manifest.

## Keyframe-first production (added 2026-11-17)

The lanes above generate from text. The three lanes below take images too, and `produce` chains
them into an episode. The method is described in `workflows/PRODUCTION_WORKFLOW.md`; this is the
command reference.

| Lane | Engine | Output | Use for |
|---|---|---|---|
| `image_ref` | FLUX.2-Klein-4B + reference latents | 1088×1920 | keyframes that keep a character and a location |
| `video_ltx_i2v` | LTX-2.5 two-pass from a keyframe | 1088×1920, 24 fps | every shot without lip-sync |
| `video_ltx_talk` | LTX-2.5 two-pass from a keyframe + wav | 1088×1920, audio-length | dialogue |

```bash
# keyframe: references are "image 1", "image 2", … in the order given
venv/bin/python -m pipeline.cli image --ref assets/input/demo/char_chen_default.png \
  --ref assets/input/demo/loc_street_dusk.png --prompt "…" --out key_01

# keyframe -> shot (--length in frames, 8k+1)
venv/bin/python -m pipeline.cli video --lane video_ltx_i2v --image key_01.png --prompt "…" --out s01

# keyframe + voice line -> lip-synced shot; the wav is padded (0.25 s lead-in, tail to the
# 8k+1 frame grid) and the original audio is muxed back
venv/bin/python -m pipeline.cli talk --image key_01.png --audio assets/audio/line_01.wav \
  --prompt "…" --out s02
```

### `produce` — run an episode

```bash
venv/bin/python -m pipeline.cli produce --show demo --stage assets
venv/bin/python -m pipeline.cli produce --show demo --episode ep00 --stage keyframes,sheet
venv/bin/python -m pipeline.cli produce --show demo --episode ep00 --stage voice,animatic
venv/bin/python -m pipeline.cli produce --show demo --episode ep00 --stage video,assemble
venv/bin/python -m pipeline.cli produce --show demo --episode ep00 --stage all
venv/bin/python -m pipeline.cli produce --show demo --episode ep00              # status
```

| Flag | Effect |
|---|---|
| `--stage` | `assets`, `keyframes`, `sheet`, `voice`, `animatic`, `video`, `assemble`, comma-separated, or `all`. Default: `status`. |
| `--only S03,S07` | Restrict to those shots (for `assets`: character or location ids). |
| `--force` | Regenerate even when the output exists. Without it every stage resumes. |

Inputs: `projects/<show>/bible.json` and `projects/<show>/episodes/<ep>.json`
(templates in `workflows/templates/`). Where things land:

```
assets/input/<show>/char_<id>_<wardrobe>.png   face + body sheet (reference for keyframes)
assets/input/<show>/loc_<id>.png               location plate
assets/audio/<show>/<ep>_<shot>.wav            voice lines
outputs/<show>/image_ref/<ep>_<shot>_k<n>_*.png        keyframes   (n = key_take)
outputs/<show>/video_ltx_{i2v,talk}/<ep>_<shot>_t<n>_*.mp4   shots  (n = take)
projects/<show>/<ep>/<ep>_keyframes.jpg        contact sheet
projects/<show>/<ep>/<ep>_animatic.mp4         stills + voice
projects/<show>/<ep>/<ep>.mp4, <ep>.srt, shots.json
```

Rerolls are data, not commands: set `"key_take": 2` or `"take": 2` on a shot and rerun the
stage. The seed is `seed + take − 1`; earlier takes stay on disk.

### `assemble` finishing flags

`--fit cover` (fill 9:16, crop overflow) · `--burn-subs` (each shot's `text`, phrase by phrase)
· `--loudnorm` (−16 LUFS) · `--label "…"` (small top-left notice). A shot entry may carry
`"voice": "x.wav"` to mix a voice-over on top of the clip's own sound. Without flags the
assembler behaves exactly as before.

### `voice --batch`

`venv-tts/bin/python -m pipeline.voice --batch jobs.json --model-dir models/tts` generates many
lines in one model load (`[{"text", "instruct", "out"}, …]`). `produce --stage voice` uses it.
