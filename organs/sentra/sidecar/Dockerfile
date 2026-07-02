# syntax=docker/dockerfile:1
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# Dockerfile for the sentra verdict sidecar service.
#
# This is a SEPARATE image from the root Dockerfile (PR #99) which builds
# the Vite/nginx web SPA. This image builds the Python FastAPI service that
# exposes POST /v1/verdict and POST /v1/inspect to the a11oy mesh-router.
#
# Build:
#   docker build -f sidecar/Dockerfile -t sentra-sidecar \
#     --build-arg VERSION=$(git describe --tags --always) \
#     --build-arg REVISION=$(git rev-parse HEAD) \
#     --build-arg BUILD_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ) .
#
# Run:
#   docker run -p 8091:8091 sentra-sidecar
#
# Environment variables:
#   SENTRA_SIDECAR_HOST       (default: 0.0.0.0)
#   SENTRA_SIDECAR_PORT       (default: 8091)
#   SENTRA_SIDECAR_LOG_LEVEL  (default: info)
#
# The image does NOT depend on the web SPA Dockerfile (PR #99) and does not
# duplicate it. They build separate containers that may run side-by-side.

ARG VERSION=0.0.0-dev
ARG REVISION=unknown
ARG BUILD_DATE=unknown

# ---- builder: install Python deps ----
FROM python:3.12-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf AS builder

WORKDIR /app

# Copy only the requirements so the layer is cached on lockfile changes.
COPY sidecar/requirements.txt ./sidecar/requirements.txt

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r sidecar/requirements.txt

# ---- runner: minimal runtime image ----
FROM python:3.12-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf AS runner

ARG VERSION
ARG REVISION
ARG BUILD_DATE

WORKDIR /app

# Non-root user for least-privilege execution.
RUN addgroup --system sentra && adduser --system --ingroup sentra sentra

# Copy installed packages from builder.
COPY --from=builder /usr/local/lib /usr/local/lib
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy only the source files the service needs.
COPY sidecar/ ./sidecar/
COPY src/sentra_immune.py ./src/sentra_immune.py

ENV SENTRA_SIDECAR_HOST=0.0.0.0 \
    SENTRA_SIDECAR_PORT=8091 \
    SENTRA_SIDECAR_LOG_LEVEL=info \
    SENTRA_VERSION=${VERSION} \
    SENTRA_GIT_SHA=${REVISION} \
    SENTRA_BUILD_DATE=${BUILD_DATE}

EXPOSE 8091

LABEL org.opencontainers.image.source="https://github.com/szl-holdings/sentra"
LABEL org.opencontainers.image.description="sentra verdict sidecar — POST /v1/verdict HTTP service"
LABEL org.opencontainers.image.licenses="LicenseRef-SZL-Proprietary"
LABEL org.opencontainers.image.version="${VERSION}"
LABEL org.opencontainers.image.revision="${REVISION}"
LABEL org.opencontainers.image.created="${BUILD_DATE}"

USER sentra

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python - <<'EOF'
import urllib.request, sys
try:
    r = urllib.request.urlopen("http://localhost:8091/healthz", timeout=3)
    sys.exit(0 if r.status == 200 else 1)
except Exception:
    sys.exit(1)
EOF

CMD ["python", "-m", "uvicorn", "sidecar.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8091", \
     "--log-level", "info"]
