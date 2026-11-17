#!/bin/bash
set -uo pipefail
ROOT="$HOME/Desktop/AIGC-PP2"
mkdir -p "$ROOT/assets/input" "$ROOT/assets/audio" "$ROOT/cache/pip" "$ROOT/tmp"

echo "=== prepare smoke assets ==="
cp -f "$ROOT/outputs/smoketest/klein_00001_.png" "$ROOT/assets/input/smoke_ref.png"
cp -f "$ROOT/outputs/smoketest/wan5b_00001_.mp4" "$ROOT/assets/input/smoke_drive.mp4"
ls -lh "$ROOT/assets/input/"

echo
echo "=== what does ComfyUI see as video options? ==="
curl -s --max-time 20 http://127.0.0.1:9090/object_info/LoadVideo \
 | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['LoadVideo']['input']['required']['file'][0])"
echo "=== images ==="
curl -s --max-time 20 http://127.0.0.1:9090/object_info/LoadImage \
 | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['LoadImage']['input']['required']['image'][0][:12])"
