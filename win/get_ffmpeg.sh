#!/usr/bin/env bash
# Fetch a static ffmpeg into win/tools/ — repo-local, no PATH change, no admin.
#
# Rule 0: the binary lives inside the folder. Nothing is written to Program
# Files, %LOCALAPPDATA% or PATH, so the folder stays self-describing and the
# version that made a master is the version that is still here.
#
# Gyan's "essentials" build is the smallest one that still carries libass
# (hard subs) and freetype/fribidi (drawtext) — both are mandatory: the
# 片头 programme number and the per-episode AI label are drawtext, the
# captions are libass.
set -euo pipefail
cd "$(dirname "$0")/.."

URL="https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
DEST="win/tools"
ZIP="$DEST/ffmpeg.zip"

mkdir -p "$DEST"
if [ -x "$DEST/ffmpeg/bin/ffmpeg.exe" ]; then
  echo "already installed: $("$DEST/ffmpeg/bin/ffmpeg.exe" -hide_banner -version | head -1)"
  exit 0
fi

echo "downloading $URL"
# -C - resumes: this mirror is slow from here and has been cut off before.
curl -L -C - --retry 5 --retry-delay 3 -o "$ZIP" "$URL"

unzip -q -o "$ZIP" -d "$DEST"
inner=$(find "$DEST" -maxdepth 1 -type d -name 'ffmpeg-*' | head -1)
[ -n "$inner" ] || { echo "no ffmpeg-* directory in $ZIP" >&2; exit 1; }
rm -rf "$DEST/ffmpeg"
mv "$inner" "$DEST/ffmpeg"
rm -f "$ZIP"

echo "installed: $("$DEST/ffmpeg/bin/ffmpeg.exe" -hide_banner -version | head -1)"
echo "filters we depend on:"
"$DEST/ffmpeg/bin/ffmpeg.exe" -hide_banner -filters 2>/dev/null \
  | grep -E ' (subtitles|drawtext) ' || {
    echo "  MISSING subtitles/drawtext — this build cannot make a compliant master" >&2; exit 1; }
