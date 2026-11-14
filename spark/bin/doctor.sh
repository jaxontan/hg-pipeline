#!/usr/bin/env bash
# doctor.sh — proves Rule 0. Run before every batch and before reporting any task "done".
#
#   bin/doctor.sh            # check only
#   bin/doctor.sh --strict   # treat WARN as failure (use before a master build)
#
# Exit 0 = boundary clean. Exit 1 = a leak exists and must be fixed, not noted.
#
# Note: env.sh redirects HOME *inside* the folder, so leak checks must look at
# MANJU_REAL_HOME, not $HOME. Checking $HOME would always pass and prove nothing.

set -uo pipefail

REAL="${MANJU_REAL_HOME:-/home/$(id -un)}"
AIGC="${AIGC:-${MANJU_REAL_HOME:-$HOME}/Desktop/AIGC-Model}"
STRICT=0
[ "${1:-}" = "--strict" ] && STRICT=1

FAIL=0
WARN=0

pass() { printf '  \033[32mPASS\033[0m  %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m  %-32s %s\n' "$1" "$2"; FAIL=1; }
warn() { printf '  \033[33mWARN\033[0m  %-32s %s\n' "$1" "$2"; WARN=1; }
info() { printf '  info  %-32s %s\n' "$1" "$2"; }

echo "doctor.sh — boundary check for $AIGC"
echo "            real home: $REAL"
echo

# ---- 0. the folder itself -------------------------------------------------
[ -d "$AIGC" ] && pass "folder exists" || fail "folder exists" "missing: $AIGC"
[ -w "$AIGC" ] && pass "folder writable" || fail "folder writable" "permission denied"

avail=$(df -Pk "$AIGC" 2>/dev/null | awk 'NR==2{printf "%.0f", $4/1048576}')
[ "${avail:-0}" -ge 50 ] && pass "free space" "${avail} GiB" \
                         || fail "free space" "only ${avail:-?} GiB — models need headroom"

# the single most important assertion: HOME really is inside the boundary
case "${HOME:-/nonexistent}" in
  "$AIGC"/*) pass "HOME redirected inside" "HOME=$HOME" ;;
  *)         fail "HOME redirected inside" "HOME=${HOME:-unset} — source env.sh first" ;;
esac
[ -n "${MANJU_BOUNDARY:-}" ] && pass "env.sh sourced" || fail "env.sh sourced" "MANJU_BOUNDARY unset"

# permission: isolation anyone can read past is not isolation
perms=$(stat -c '%a' "$AIGC" 2>/dev/null)
case "$perms" in
  700|750|770) pass "folder mode" "$perms" ;;
  *) warn "folder mode" "$perms — group/other access on a multi-user host" ;;
esac

echo
# ---- 1. known cache leak sites (in the REAL home) ------------------------
# A cache site is only OUR leak if it gained files after the baseline was pinned.
# Anything older predates this project (e.g. ~/.nv/ComputeCache from the imaged
# NVIDIA toolchain, 14 Sep) and failing on it would train everyone to ignore FAIL.
ANCHOR="$AIGC/app/os/apt.baseline.tsv"

check_dir() {  # name, path
  local name="$1" path="$2"
  [ -e "$path" ] || { pass "$name"; return; }
  find "$path" -mindepth 1 -print -quit 2>/dev/null | grep -q . || { pass "$name"; return; }
  if [ -f "$ANCHOR" ]; then
    local grew
    grew=$(find "$path" -mindepth 1 -newer "$ANCHOR" 2>/dev/null | head -3)
    if [ -n "$grew" ]; then
      fail "$name" "written after baseline: $(printf '%s ' $grew)"
    else
      info "$name" "$(du -sh "$path" 2>/dev/null | cut -f1) pre-existing, untouched"
    fi
  else
    fail "$name" "non-empty: $path (baseline not pinned — cannot tell old from new)"
  fi
}
check_dir "~/.cache/huggingface"  "$REAL/.cache/huggingface"
check_dir "~/.cache/torch"        "$REAL/.cache/torch"
check_dir "~/.cache/pip"          "$REAL/.cache/pip"
check_dir "~/.cache/uv"           "$REAL/.cache/uv"
check_dir "~/.cache/comfy"        "$REAL/.cache/comfy"
check_dir "~/.ollama"             "$REAL/.ollama"
check_dir "~/.local/share/uv"     "$REAL/.local/share/uv"
check_dir "~/.config/blender"     "$REAL/.config/blender"
check_dir "~/.nv/ComputeCache"    "$REAL/.nv/ComputeCache"

# Pre-existing operator content, not ours. Reported so it is never a surprise, never failed.
if [ -d "$REAL/Desktop/AP3Model" ]; then
  info "~/Desktop/AP3Model" "$(du -sh "$REAL/Desktop/AP3Model" 2>/dev/null | cut -f1) pre-existing, not this project"
fi

echo
# ---- 2. /tmp -------------------------------------------------------------
stray=$(find /tmp -maxdepth 2 -user "$(id -un)" 2>/dev/null | grep -v '/tmp/perf-[0-9]*\.map$' | head -5)
[ -z "$stray" ] && pass "/tmp clean" || fail "/tmp clean" "$(echo "$stray" | tr '\n' ' ')"
perf=$(find /tmp -maxdepth 1 -name 'perf-*.map' -user "$(id -un)" 2>/dev/null | wc -l)
if [ "$perf" -gt 0 ]; then
  warn "/tmp/perf-*.map" "$perf file(s) — torch writes these regardless of TMPDIR; recorded in DELETE.md"
fi
case "${TMPDIR:-}" in "$AIGC"/*) pass "TMPDIR inside boundary" ;; *) fail "TMPDIR inside boundary" "TMPDIR=${TMPDIR:-unset}" ;; esac

echo
# ---- 3. docker (allowed, but must be a declared exception) ---------------
if command -v docker >/dev/null 2>&1; then
  running=$(docker ps -q 2>/dev/null | wc -l)
  if [ "$running" -eq 0 ]; then
    warn "docker data-root" "present at /var/lib/docker (Oracle images, stopped) — wipe coverage owed to DELETE.md"
  else
    fail "docker containers running" "$running running — they hold unified memory; stop with: docker stop \$(docker ps -q)"
  fi
else
  pass "docker absent"
fi

echo
# ---- 4. symlinks crossing the boundary -----------------------------------
escaped=""
while IFS= read -r l; do
  tgt=$(readlink -f "$l" 2>/dev/null) || continue
  case "$tgt" in "$AIGC"/*) ;; *) escaped="$escaped $l->$tgt" ;; esac
done < <(find "$AIGC" -maxdepth 5 -type l 2>/dev/null)
[ -z "$escaped" ] && pass "no outward symlinks" || fail "no outward symlinks" "$escaped"

echo
# ---- 5. provenance coverage ---------------------------------------------
clips=$(find "$AIGC/work" -type f \( -name '*.mp4' -o -name '*.mov' -o -name '*.wav' -o -name '*.png' \) 2>/dev/null | wc -l)
prov=$(find "$AIGC/provenance" -name 'MODEL_PROVENANCE.json' 2>/dev/null | wc -l)
info "assets / provenance files" "$clips / $prov"
if [ "$clips" -gt 0 ] && [ "$prov" -eq 0 ]; then
  fail "provenance coverage" "assets exist with no provenance — assembly will refuse"
else
  pass "provenance coverage"
fi

# ---- 5b. provenance mirror pin -------------------------------------------
# provenance/ is produced here and mirrored to the repo by win/mirror_provenance.py, which
# writes MIRROR.json. A hash mismatch means this copy gained entries after the last mirror:
# the repo is behind, and the wipe would keep the stale one. Fail, do not warn.
pin="$AIGC/provenance/MIRROR.json"
if [ -f "$pin" ]; then
  if drift=$(python3 - "$AIGC" "$pin" <<'PY' 2>&1
import hashlib, json, sys
from pathlib import Path
aigc, pin = Path(sys.argv[1]), Path(sys.argv[2])
pinned = json.loads(pin.read_text(encoding="utf-8")).get("files", {})
bad = []
for rel, meta in sorted(pinned.items()):
    path = aigc / "provenance" / rel
    if not path.is_file():
        bad.append(f"{rel} missing")
        continue
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != meta["sha256"]:
        bad.append(f"{rel} drifted")
for path in sorted((aigc / "provenance").glob("*/MODEL_PROVENANCE.json")):
    rel = f"{path.parent.name}/{path.name}"
    if rel not in pinned:
        bad.append(f"{rel} unpinned")
print("; ".join(bad) if bad else f"{len(pinned)} file(s) match the pin")
sys.exit(1 if bad else 0)
PY
  ); then
    pass "provenance mirror" "$drift"
  else
    fail "provenance mirror" "$drift — run win/mirror_provenance.py on Windows"
  fi
else
  warn "provenance mirror" "no MIRROR.json — run win/mirror_provenance.py"
fi

echo
# ---- 6. weights are declared --------------------------------------------
w=$(find "$AIGC/models" -type f \( -name '*.safetensors' -o -name '*.gguf' -o -name '*.pth' -o -name '*.ckpt' \) 2>/dev/null | wc -l)
if [ "$w" -eq 0 ]; then
  info "weights declared" "no weights on disk yet (MANIFEST still required before the first download)"
elif [ -f "$AIGC/models/MANIFEST.json" ]; then
  d=$(grep -c '"sha256"' "$AIGC/models/MANIFEST.json" 2>/dev/null || echo 0)
  [ "$d" -ge "$w" ] && pass "every weight in MANIFEST" "$w weights, $d declared" \
                    || fail "every weight in MANIFEST" "$w weights, only $d declared"
else
  fail "models/MANIFEST.json" "missing — Rule 2 violated: $w undeclared weight file(s)"
fi

echo
# ---- 7. undeclared system installs --------------------------------------
OS="$AIGC/app/os"
if [ -s "$OS/apt.baseline.tsv" ]; then
  declared=$({ cut -f3 "$OS/installed.tsv" 2>/dev/null | tr ',' '\n';
               cat "$OS/apt.authorized.txt" 2>/dev/null; } | sed 's/:.*//' | sort -u)
  added=$(comm -13 <(cut -f1 "$OS/apt.baseline.tsv" | sed 's/:.*//' | sort -u) \
                   <(cut -f1 "$OS/apt.all.tsv" 2>/dev/null | sed 's/:.*//' | sort -u) 2>/dev/null)
  undeclared=""
  for p in $added; do
    printf '%s\n' "$declared" | grep -qx "$p" || undeclared="$undeclared $p"
  done
  n_added=$(printf '%s\n' "${added:-}" | grep -c . || true)
  if [ -z "$undeclared" ]; then pass "apt delta declared" "$n_added since baseline"
  else fail "apt delta declared" "undeclared:${undeclared}"; fi

  if [ -s "$OS/pip-user.txt" ]; then
    newpi=$(comm -13 <(sed 's/[=<>].*//' "$OS/pip.user.baseline.txt" 2>/dev/null | sort -u) \
                     <(sed 's/[=<>].*//' "$OS/pip-user.txt" | sort -u) 2>/dev/null)
    upi=""
    for p in $newpi; do printf '%s\n' "$declared" | grep -qx "$p" || upi="$upi $p"; done
    [ -z "$upi" ] && pass "pip --user delta declared" || fail "pip --user delta declared" "undeclared:${upi}"
  fi

  binlist=$(find /usr/local/bin -maxdepth 1 -type f 2>/dev/null | sed 's|.*/||')
  ubin=""
  for b in $binlist; do printf '%s\n' "$declared" | grep -qx "$b" || ubin="$ubin $b"; done
  [ -z "$ubin" ] && pass "/usr/local/bin declared" || warn "/usr/local/bin not in ledger" "${ubin:-none}"
else
  info "apt baseline" "not pinned yet — run: bin/record-install.sh snapshot"
fi

echo
if [ "$FAIL" -eq 0 ]; then
  if [ "$WARN" -eq 1 ] && [ "$STRICT" -eq 1 ]; then
    echo "BOUNDARY CLEAN but WARNINGS PRESENT — --strict treats them as failures"
    exit 1
  fi
  echo "BOUNDARY CLEAN — nothing leaked, nothing undeclared"
  [ "$WARN" -eq 1 ] && echo "(warnings above are known and recorded in DELETE.md)"
else
  echo "BOUNDARY VIOLATED — fix the FAIL lines before continuing"
fi
exit "$FAIL"
