#!/bin/bash
set -uo pipefail
ROOT="$HOME/Desktop/AIGC-PP2"
cd "$ROOT" || exit 1
F=$("$ROOT/venv/bin/python" -c 'import comfyui_frontend_package, os; print(os.path.dirname(comfyui_frontend_package.__file__))')
echo "frontend package: $F"
ls "$F"
echo "--- static:"
ls "$F/static" 2>/dev/null | head -5
echo "--- api-format support markers:"
grep -rlo 'loadApiJson' "$F/static" 2>/dev/null | head -3
grep -rho 'API format[^"]\{0,40\}' "$F/static" 2>/dev/null | sort -u | head -5
