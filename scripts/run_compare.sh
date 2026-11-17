#!/bin/bash
# Quality comparison: same beat through LTX 2-pass, Wan T2V 5B, and Wan Animate v1.
set -uo pipefail
ROOT="$HOME/Desktop/AIGC-PP2"
cd "$ROOT" || exit 1
. "$ROOT/env.sh"
LOG="$ROOT/logs/compare.log"
: > "$LOG"
mkdir -p "$ROOT/outputs/compare"

echo "=== $(date -u) start ===" | tee -a "$LOG"

# reference frame for Animate: a real scene frame, not the settei sheet
ffmpeg -y -loglevel error -ss 2.0 -i "$ROOT/outputs/smoketest/ltx_00001_.mp4" \
       -frames:v 1 "$ROOT/assets/input/ltx_scene_ref.png"
echo "ref extracted: $(ls -lh "$ROOT/assets/input/ltx_scene_ref.png" | awk '{print $5}')" | tee -a "$LOG"

echo "" | tee -a "$LOG"
echo "########## 1/3  LTX-2.5 two-pass ##########" | tee -a "$LOG"
python -u scripts/ltx_2pass.py 2>&1 | tee -a "$LOG"

echo "" | tee -a "$LOG"
echo "########## 2/3  Wan2.2 TI2V 5B ##########" | tee -a "$LOG"
python -u scripts/wan_t2v.py 2>&1 | tee -a "$LOG"

echo "" | tee -a "$LOG"
echo "########## 3/3  Wan2.2 Animate 14B (scene ref) ##########" | tee -a "$LOG"
python -u scripts/smoke_animate.py ltx_scene_ref.png smoke_drive.mp4 2>&1 | tee -a "$LOG"

echo "" | tee -a "$LOG"
echo "=== $(date -u) done ===" | tee -a "$LOG"
ls -lh "$ROOT/outputs/compare" "$ROOT/outputs/smoketest"/*.mp4 2>/dev/null | tee -a "$LOG"
