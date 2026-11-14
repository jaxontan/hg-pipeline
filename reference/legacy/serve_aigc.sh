#!/bin/bash
set -e
. "/home/tdadmin/Desktop/AIGC-Model/env.sh"
export FREEFIELD_TOKEN="j4HNuplMBwe2jMXxVE2ZYTwPgqwmEsojbq_TxvlaLtw"
export COMFYUI_URL="http://127.0.0.1:8188"
export PROXY_URL="http://127.0.0.1:8189"
export GATEWAY_PORT="8000"
export EPHEMERAL_DIR="$AIGC/ephemeral_io"

rm -rf "$AIGC/ephemeral_io/input"/* "$AIGC/ephemeral_io/output"/* "$AIGC/ephemeral_io/temp"/* 2>/dev/null || true

cd "$AIGC/comfy"
setsid nohup "$AIGC/venv/bin/python" "$AIGC/comfy/main.py" \
    --listen 127.0.0.1 --port 8188 --disable-auto-launch \
    --extra-model-paths-config "$AIGC/comfy/extra_model_paths.yaml" \
    --input-directory "$AIGC/ephemeral_io/input" \
    --output-directory "$AIGC/ephemeral_io/output" \
    --temp-directory "$AIGC/ephemeral_io/temp" \
    > "$AIGC/logs/comfyui.log" 2>&1 < /dev/null &

for i in $(seq 1 120); do
    if curl -s http://127.0.0.1:8188/system_stats >/dev/null; then
        break
    fi
    sleep 1
done
curl -s http://127.0.0.1:8188/system_stats >/dev/null || (cat "$AIGC/logs/comfyui.log" | tail -n 30 && exit 1)

setsid nohup "$AIGC/venv/bin/comfy-api-proxy" \
    --comfyui http://127.0.0.1:8188 --port 8189 \
    --comfyui-base-dir "$AIGC/comfy" \
    > "$AIGC/logs/proxy.log" 2>&1 < /dev/null &

for i in $(seq 1 60); do
    if ss -tln | grep -q ":8189 "; then
        break
    fi
    sleep 1
done

setsid nohup "$AIGC/venv/bin/python" "$AIGC/gateway.py" \
    > "$AIGC/logs/gateway.log" 2>&1 < /dev/null &

for i in $(seq 1 30); do
    if curl -s http://127.0.0.1:8000/health | grep -q '"ok": true'; then
        break
    fi
    sleep 1
done
curl -s http://127.0.0.1:8000/health
echo ""
