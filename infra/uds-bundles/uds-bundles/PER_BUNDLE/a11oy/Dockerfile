# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# a11oy UDS runtime image. Derived from the live HF Space Dockerfile pattern at
# szl-cookbook/recipes/_hf_surfaces/_live/a11oy/. ADDITIVE: this is a k8s/Zarf
# build target; it does NOT modify the HF Space. Note (PURIQ charter gotcha):
# the upstream Space uses explicit per-file COPY (not `COPY . .`), so any new
# root .py needs its own COPY line — preserved here.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

# Minimal real dependency surface (FastAPI + uvicorn). Pinned for reproducible airgap builds.
RUN pip install --no-cache-dir "fastapi==0.111.0" "uvicorn[standard]==0.30.1"

# Explicit per-file COPY (matches live Space convention — see PURIQ charter a11oy gotcha)
COPY serve.py ./serve.py

EXPOSE 8080

# Non-root for UDS Core / Pepr restricted PSS admission
RUN useradd -u 65532 -m a11oy
USER 65532

HEALTHCHECK --interval=15s --timeout=3s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/api/a11oy/healthz').status==200 else 1)"

CMD ["uvicorn", "serve:app", "--host", "0.0.0.0", "--port", "8080"]
