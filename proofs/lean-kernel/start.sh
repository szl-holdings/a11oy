#!/usr/bin/env bash
set -e
export PATH="/root/.elan/bin:${PATH}"
echo "[start] toolchain: $(cat ${LUTAR_REPO:-/opt/lutar-lean}/lean-toolchain 2>/dev/null)"
echo "[start] lean: $(lean --version 2>/dev/null || echo missing)"
# Launch FastAPI (uvicorn) on 8000; nginx proxies 7860 -> 8000.
cd /opt/app
uvicorn server:app --host 127.0.0.1 --port 8000 --workers 1 &
sleep 2
echo "[start] starting nginx on 7860"
nginx -g 'daemon off;'
