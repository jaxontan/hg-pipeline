#!/bin/bash
# End-to-end verification of the pipeline layer, using only the CLI.
set -uo pipefail
ROOT="$HOME/Desktop/AIGC-PP2"
cd "$ROOT" || exit 1
. "$ROOT/env.sh"
P="$ROOT/venv/bin/python"

PROMPT="Photoreal cinematic: 1970s Chinese county-town street at dusk, a middle-aged man in a navy Mao suit walks toward camera with a white enamel mug, cyclist behind, warm street lamp, wet cobbles, 35mm grain"

echo "########## 1/5 image ##########"
$P -m pipeline.cli --project verify image --lane image_fast \
  --prompt "1980年代县城老街，黄昏，穿藏蓝中山装的中年男人，二维动画赛璐璐风格，竖构图" \
  --out keyframe_01

echo
echo "########## 2/5 video (LTX two-pass) ##########"
$P -m pipeline.cli --project verify video --lane video_ltx_final \
  --prompt "$PROMPT" --out shot_001

echo
echo "########## 3/5 voice ##########"
$P -m pipeline.cli --project verify voice --out line_01 \
  --text "老陈，这搪瓷缸子跟了你二十年了，扔了怪可惜的。" \
  --instruct "中年男性，沙哑低沉的嗓音，说话缓慢，带一点北方口音，情绪克制而疲惫"

echo
echo "########## 4/5 dialogue (length auto from wav) ##########"
VID=$(ls -t "$ROOT"/outputs/verify/video_ltx_final/*.mp4 | head -1)
ffmpeg -y -loglevel error -ss 2 -i "$VID" -frames:v 1 "$ROOT/assets/input/ref_verify.png"
$P -m pipeline.cli --project verify dialogue --lane video_s2v \
  --prompt "A middle-aged Chinese man in a navy Mao suit speaks to the camera on a small-town street at dusk, natural lip movement, 1980s county town, low-saturation film look" \
  --audio "$ROOT/assets/audio/line_01.wav" --ref "$ROOT/assets/input/ref_verify.png" \
  --out shot_002

echo
echo "########## 5/5 assemble ##########"
mkdir -p "$ROOT/projects/verify"
python3 - "$ROOT" <<'PY'
import glob, json, os, sys
root = sys.argv[1]
shots = sorted(glob.glob(os.path.join(root, "outputs/verify/video_*/*.mp4")),
               key=os.path.getmtime)
# keep one per lane, ordered: ltx first, then s2v
ltx = [s for s in shots if "video_ltx_final" in s]
s2v = [s for s in shots if "video_s2v" in s]
files = ltx[-1:] + s2v[-1:]
out = [{"file": f} for f in files]
p = os.path.join(root, "projects/verify/shots.json")
json.dump(out, open(p, "w"), indent=1)
print("shots.json:", [os.path.relpath(f, root) for f in files])
PY
$P -m pipeline.cli --project verify assemble \
  --shots "$ROOT/projects/verify/shots.json" --out "$ROOT/projects/verify/verify.mp4"

echo
echo "########## results ##########"
find "$ROOT/outputs/verify" -type f -printf '%10s  %p\n' | sort -k2
echo "--- manifest"
cat "$ROOT/projects/verify/manifest.jsonl" | python3 -c "
import sys, json
for line in sys.stdin:
    d = json.loads(line)
    print(f\"{d['lane']:<16} {d['elapsed_s']:>6.1f}s  {d['graph_hash']}  {d['files']}\")
"
echo "--- episode"
ffprobe -v error -show_entries format=duration,size:stream=codec_type,width,height,r_frame_rate -of default=nw=1 "$ROOT/projects/verify/verify.mp4"
