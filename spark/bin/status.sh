#!/usr/bin/env bash
# status.sh — read-only. What is the machine doing right now?
# Safe to run at any time; writes nothing, changes nothing.

set -uo pipefail
AIGC="${AIGC:-${MANJU_REAL_HOME:-$HOME}/Desktop/AIGC-Model}"

hr() { printf '%s\n' "------------------------------------------------------------"; }

echo "manju status · $(date '+%Y-%m-%d %H:%M:%S %Z')"
hr

# ---- GPU ------------------------------------------------------------------
echo "GPU"
nvidia-smi --query-gpu=name,driver_version,pstate,temperature.gpu,clocks.sm,clocks.max.sm,power.draw \
           --format=csv,noheader 2>/dev/null | sed 's/^/  /'
if command -v nvidia-smi >/dev/null 2>&1; then
  procs=$(nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader 2>/dev/null)
  if [ -n "$procs" ]; then printf '  compute procs:\n'; printf '%s\n' "$procs" | sed 's/^/    /'
  else echo "  compute procs: none"; fi
fi
hr

# ---- memory (unified: GPU and CPU share this pool) ------------------------
echo "MEMORY (unified pool — GPU allocations count here)"
free -m | awk 'NR==1 || NR==2 {print "  "$0}'
avail_kb=$(awk '/MemAvailable/{print $2}' /proc/meminfo)
avail_g=$(( avail_kb / 1048576 ))
if   [ "$avail_g" -lt 8 ];  then echo "  >> LOW (${avail_g} GiB). Start nothing heavy."
elif [ "$avail_g" -lt 25 ]; then echo "  >> ${avail_g} GiB free — one job at a time."
else echo "  >> ${avail_g} GiB free — plenty."
fi
echo "  swap: $(free -m | awk 'NR==3{print $3" MiB used of "$2" MiB"}')"
hr

# ---- disk -----------------------------------------------------------------
echo "DISK"
df -h "$AIGC" 2>/dev/null | awk 'NR==2{printf "  %s  used %s of %s (%s)  free %s\n",$6,$3,$2,$5,$4}'
du -sh "$AIGC"/* 2>/dev/null | sort -h | tail -6 | sed 's/^/  /'
hr

# ---- processes ------------------------------------------------------------
echo "SERVICES"
found=0
for pat in 'ComfyUI/main.py' 'comfy-api-proxy' 'gateway.py' 'llama-server'; do
  pids=$(pgrep -f "$pat" 2>/dev/null | tr '\n' ' ')
  if [ -n "$pids" ]; then echo "  $pat: up (pid $pids)"; found=1; fi
done
[ "$found" -eq 0 ] && echo "  none running"
if command -v docker >/dev/null 2>&1; then
  d=$(docker ps --format '{{.Names}} ({{.Status}})' 2>/dev/null)
  echo "  docker: ${d:-none running}"
fi
hr

# ---- ports ----------------------------------------------------------------
echo "LISTENING"
ss -tln 2>/dev/null | awk 'NR>1{print $4}' | sed 's/.*://' | sort -un | tr '\n' ' ' | sed 's/^/  /'
echo
hr

# ---- queue / last job (only if the control plane exists) ------------------
if [ -f "$AIGC/app/queue.db" ]; then
  echo "QUEUE"
  python3 - "$AIGC/app/queue.db" <<'PY' 2>/dev/null | sed 's/^/  /'
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
try:
    for row in c.execute("select status, count(*) from jobs group by status"):
        print(f"{row[0]:<10} {row[1]}")
except Exception as e:
    print("queue unreadable:", e)
PY
  hr
fi

echo "boundary: $AIGC"
