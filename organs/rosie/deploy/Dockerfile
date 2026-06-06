# rosie.Dockerfile — BLUEPRINT (operator console)
#
# Builds the image referenced by the rosie skeleton:
#   deploy/zarf.yaml -> components[0].images[0]: ghcr.io/szl-holdings/rosie:v0.3.1
#   deploy/manifests/rosie-deployment.yaml -> container image (same ref)
#
# ── RESOLVED 2026-06-02 (historical note — was: BLOCKER) ─────────────────────
# The rosie GIT repo is a TypeScript/Python LIBRARY (src/qec, src/replay,
# src/topology + khipu-receipt.ts). It has NO app.py, NO Dockerfile, NO chart.
# package.json `build` is `tsc --noEmit` (type-check only — produces NO artifact).
#
# The actual operator console (Gradio, ~28.7 kB app.py, 6 tabs:
# Span Explorer / Receipt Verifier / Mesh Health / Doctrine Sweep / Live Formulas /
# About) lives ONLY on the Hugging Face Space SZLHOLDINGS/rosie-operator-console
# (requirements: gradio>=5.9.1, pydantic>=2.7.0; HTTP 200 on 2026-05-30).
#
# RESOLUTION: app.py + requirements.txt were vendored from the HF Space into the
#    repo root in a prior commit. The two COPY lines below now reference the repo
#    root paths directly (build context: repo root). The deploy/app/ vendor path
#    the Dockerfile originally expected never existed.
#
# Verified: /app.py (sha 395c9c45) + /requirements.txt (sha c84fd53d) both
#    present at repo root as of 2026-06-02.
# ──────────────────────────────────────────────────────────────────────────────
#
# Build context: repo root. File layout (vendored at repo root):
#   app.py            (from HF Space app.py)
#   requirements.txt  (from HF Space requirements.txt: gradio>=5.9.1, pydantic>=2.7.0)
#
# Gradio listens on 7860 by default. The skeleton manifest below uses
# GRADIO_SERVER_PORT=8080 so it matches a containerPort: 8080 service convention
# shared with the other modules. Gradio reads GRADIO_SERVER_NAME / GRADIO_SERVER_PORT.

FROM python:3.12-slim

# Non-root runtime (HF Spaces convention; keeps parity with the live Space)
RUN useradd -m -u 1000 rosie
WORKDIR /home/rosie/app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./app.py

ENV GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=8080 \
    PYTHONUNBUFFERED=1

USER rosie
EXPOSE 8080
CMD ["python", "app.py"]
