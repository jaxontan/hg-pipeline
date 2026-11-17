#!/bin/bash
set -uo pipefail
ROOT="$HOME/Desktop/AIGC-PP2"
{
  echo ""
  echo "---"
  echo ""
  echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) — README.md"
  echo ""
  echo "Wrote README.md (539 lines) as the project entry point: what the project is, the stack"
  echo "(GB10 / CUDA 13.0 / torch 2.14.1+cu130 / ComfyUI 0.45.0 / the two venvs), the verified"
  echo "model table with licences, the excluded models and why, all 7 lanes described node by node"
  echo "with settings and measured cost, the measured comparison + season budget, known limits,"
  echo "operations and the uninstall path."
  echo ""
  echo "Also corrected two stale statements in AIGC-PP2_PLAN.md: hard rule 6 still claimed"
  echo "127.0.0.1-only (now documents the switchable COMFY_BIND), and section 3 still listed"
  echo "--use-sage-attention as required (it raises sm121 and was removed)."
} >> "$ROOT/SETUP_LOG.md"
echo "SETUP_LOG.md: $(wc -l < "$ROOT/SETUP_LOG.md") lines"
ls -1 "$ROOT"/*.md
