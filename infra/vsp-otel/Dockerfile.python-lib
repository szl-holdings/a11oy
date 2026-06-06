# SPDX-License-Identifier: Apache-2.0
# vsp-otel — Verifiable Span Provenance via OpenTelemetry (Python layer)
# Doctrine v11 LOCKED — 749/14/163 · Λ = Conjecture 1
# Per-file COPY only — this Dockerfile NEVER uses `COPY . .` (SZL doctrine).
# Minimal image: slim base, no build toolchain in the final layer.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 1) Dependencies first (better layer caching). Pinned to the OTLP gRPC stack.
RUN pip install --no-cache-dir \
    "opentelemetry-api>=1.25.0" \
    "opentelemetry-sdk>=1.25.0" \
    "opentelemetry-exporter-otlp-proto-grpc>=1.25.0"

# 2) Package metadata (explicit per-file COPY — no `COPY . .`).
COPY pyproject.toml ./pyproject.toml
COPY src/vsp_otel/README.md ./README.md

# 3) Source — explicit per-file COPY of every module.
COPY src/vsp_otel/__init__.py        ./src/vsp_otel/__init__.py
COPY src/vsp_otel/exporter.py        ./src/vsp_otel/exporter.py
COPY src/vsp_otel/dsse_processor.py  ./src/vsp_otel/dsse_processor.py
COPY src/vsp_otel/middleware.py      ./src/vsp_otel/middleware.py

# 4) Install the package itself (no deps — already installed above).
RUN pip install --no-cache-dir --no-deps -e .

# Smoke check that the package imports cleanly at build time (honest gate).
RUN python -c "import vsp_otel; print('vsp_otel', vsp_otel.__version__, vsp_otel.DOCTRINE['lambda'])"

# Default: print the doctrine/provenance banner. There is no long-running server
# here — vsp_otel is a *library* organs import; the collector runs separately
# (see deploy/otel-collector-config.yaml).
CMD ["python", "-c", "import vsp_otel, json; print(json.dumps(vsp_otel.DOCTRINE, indent=2))"]
