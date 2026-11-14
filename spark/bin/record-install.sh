#!/usr/bin/env bash
# record-install.sh — the only sanctioned way to change the machine outside the folder.
#
#   bin/record-install.sh apt install -y tmux
#   bin/record-install.sh pip install --user uv
#   bin/record-install.sh snap install blender --classic
#   bin/record-install.sh run "curl -LsSf https://astral.sh/uv/install.sh | sh"
#   bin/record-install.sh snapshot          # regenerate full machine inventory
#   bin/record-install.sh ledger            # show what has been installed since baseline
#
# Rationale: system-wide packages are allowed, but the folder must remain enough to
# (a) rebuild this machine exactly and (b) script the one-shot wipe. A package nobody
# recorded breaks both. doctor.sh fails on undeclared installs.

set -uo pipefail
AIGC="${AIGC:-$HOME/Desktop/AIGC-Model}"
OS="$AIGC/app/os"
LEDGER="$OS/installed.tsv"
mkdir -p "$OS"
[ -f "$LEDGER" ] || printf 'date\tlayer\titem\tversion\tcommand\treversible\n' > "$LEDGER"

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }

snapshot() {
  dpkg --get-selections 2>/dev/null | awk '{print $1"\t"$2}' > "$OS/apt.all.tsv"
  apt list --installed 2>/dev/null | tail -n +2 | cut -d/ -f1 | sort > "$OS/apt.versions.txt"
  pip list --user --format=freeze 2>/dev/null > "$OS/pip-user.txt"
  pip list --format=freeze 2>/dev/null > "$OS/pip-system.txt"
  { command -v snap >/dev/null && snap list 2>/dev/null; } > "$OS/snap.txt"
  { ls -1 /usr/local/bin 2>/dev/null; } > "$OS/usr-local-bin.txt"
  nvidia-smi --query-gpu=driver_version,cuda_version --format=csv,noheader 2>/dev/null > "$OS/gpu-driver.txt"
  lsb_release -ds > "$OS/os-release.txt" 2>/dev/null || head -3 /etc/os-release > "$OS/os-release.txt"
  uname -m > "$OS/arch.txt"
  uv --version > "$OS/uv-version.txt" 2>/dev/null
  echo "snapshot written to $OS/"
}

# The first snapshot becomes the baseline of a pristine machine. Never overwrite it —
# the wipe diff is computed against this file.
if [ "${1:-}" = "snapshot" ]; then
  [ -f "$OS/apt.baseline.tsv" ] || cp /dev/null "$OS/apt.baseline.tsv"
  if [ ! -s "$OS/apt.baseline.tsv" ]; then
    snapshot && cp "$OS/apt.all.tsv" "$OS/apt.baseline.tsv" && cp "$OS/pip-user.txt" "$OS/pip.user.baseline.txt" 2>/dev/null
    echo "baseline pinned. Do not delete $OS/apt.baseline.tsv — the wipe script depends on it."
  else
    snapshot && echo "baseline already pinned: $OS/apt.baseline.tsv"
  fi
  exit 0
fi

if [ "${1:-}" = "ledger" ]; then
  column -t -s $'\t' "$LEDGER"
  echo
  echo "-- apt delta since baseline --"
  comm -13 <(cut -f1 "$OS/apt.baseline.tsv" 2>/dev/null | sort) \
           <(cut -f1 "$OS/apt.all.tsv" 2>/dev/null | sort) 2>/dev/null
  exit 0
fi

# ---- run + receipt -------------------------------------------------------
layer="${1:-run}"; shift || true
[ "$layer" = "run" ] && { cmd_str="$*"; } || { cmd_str="$layer $*"; }

# Non-interactive sudo. There is no tty under automation, so:
#   SUDO_ASKPASS=<helper> bin/record-install.sh apt install -y foo   → sudo -A
# Without it, plain sudo (interactive session). Never store the password here.
SUDO="sudo"
if [ -n "${SUDO_ASKPASS:-}" ]; then SUDO="sudo -A"; fi

echo ">> $cmd_str"
if [ "$layer" = "apt" ] || [ "$layer" = "apt-get" ]; then
  [ -f "$OS/apt.all.tsv" ] && cut -f1 "$OS/apt.all.tsv" | sort -u > "$OS/.apt.before" || : > "$OS/.apt.before"
fi
case "$layer" in
  apt|apt-get) $SUDO apt-get "$@" ; rc=$? ;;
  snap)        $SUDO snap "$@" ; rc=$? ;;
  systemctl)   $SUDO systemctl "$@" ; rc=$? ;;
  pip)         python3 -m pip "$@" ; rc=$? ;;
  sudo)        $SUDO "$@" ; rc=$? ;;
  *)           bash -c "$*" ; rc=$? ;;
esac

if [ $rc -ne 0 ]; then
  rm -f "$OS/.apt.before"
  echo "!! command failed ($rc) — nothing recorded" >&2
  exit $rc
fi

# What changed? Record the concrete items, not just the command.
item=""; ver=""
case "$layer" in
  apt|apt-get) item=$(echo "$*" | tr ' ' '\n' | grep -v '^-' | grep -v '^install$' | paste -sd, -)
               ver=$(dpkg-query -W -f='${Version}\n' $(echo "$item" | tr ',' ' ') 2>/dev/null | paste -sd';' -) ;;
  pip)   item=$(echo "$*" | tr ' ' '\n' | grep -v '^-' | grep -v '^install$' | paste -sd, -)
         ver=$(python3 -m pip show "$(echo "$item" | cut -d, -f1)" 2>/dev/null | awk '/^Version:/{print $2}') ;;
  snap)  item="$*"; ver=$(snap list 2>/dev/null | awk 'NR==2{print $2}') ;;
  *)     item="$cmd_str"; ver="n/a" ;;
esac
printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$(ts)" "$layer" "${item:-unknown}" "${ver:-unknown}" \
  "$(echo "$cmd_str" | tr '\t' ' ')" "y" >> "$LEDGER"

snapshot >/dev/null
if { [ "$layer" = "apt" ] || [ "$layer" = "apt-get" ]; } && [ -f "$OS/.apt.before" ]; then
  { [ -f "$OS/apt.authorized.txt" ] && cat "$OS/apt.authorized.txt";
    comm -13 "$OS/.apt.before" <(cut -f1 "$OS/apt.all.tsv" | sort -u); } | sort -u > "$OS/.apt.auth.tmp"
  mv "$OS/.apt.auth.tmp" "$OS/apt.authorized.txt"
  rm -f "$OS/.apt.before"
fi
echo "receipt recorded → $LEDGER"
echo "reminder: anything you installed is now part of DELETE.md's wipe set."
