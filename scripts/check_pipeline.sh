#!/bin/bash
set -uo pipefail
ROOT="$HOME/Desktop/AIGC-PP2"
cd "$ROOT" || exit 1
. "$ROOT/env.sh"

echo "=== config parses ==="
python - <<'PY'
import json
cfg = json.load(open("pipeline/config.json"))
print("lanes:", ", ".join(cfg["lanes"]))
print("ok")
PY

echo
echo "=== import check ==="
python -c "import pipeline.cli, pipeline.graphs, pipeline.comfy, pipeline.manifest, pipeline.assemble; print('imports ok')"

echo
echo "=== health ==="
python -m pipeline.cli health

echo
echo "=== lanes ==="
python -m pipeline.cli lanes

echo
echo "=== export workflows ==="
python -m pipeline.cli export-workflows
ls -1 "$ROOT/workflows"
