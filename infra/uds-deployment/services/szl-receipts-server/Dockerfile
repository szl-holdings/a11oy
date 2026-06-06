# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# OCI image for the SZL receipts server. Replaces the ConfigMap-mounted source
# on a stock python:3.12-slim with a built, self-contained image (PhD Systems
# Scope 6 fix). Behavior is preserved from the prior inline server; the only
# additions are Ed25519 signing, canonical DSSE PAE, chain rehydration, and
# OTLP spans (see server.py header).

FROM python:3.12-slim

# OCI image metadata.
LABEL org.opencontainers.image.title="szl-receipts-server" \
      org.opencontainers.image.description="SZL governance receipts server (Ed25519, DSSE, OTLP)" \
      org.opencontainers.image.source="https://github.com/szl-holdings/szl-uds-deployment" \
      org.opencontainers.image.licenses="Apache-2.0"

# Install Python dependencies first for layer caching.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

# Application code.
WORKDIR /app
COPY server.py /app/server.py

# Non-root user (uid/gid 65532 = "nonroot", matches the chart securityContext).
RUN groupadd --gid 65532 nonroot \
 && useradd --uid 65532 --gid 65532 --no-create-home --shell /usr/sbin/nologin nonroot \
 && mkdir -p /data/receipts \
 && chown -R 65532:65532 /data/receipts /app
USER 65532:65532

# Default store path matches the chart's SZL_RECEIPT_STORE.
ENV SZL_RECEIPT_STORE=/data/receipts \
    SZL_PORT=8080

EXPOSE 8080

# Healthcheck against /healthz (alias of /health in server.py).
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python3 -c "import urllib.request,os,sys; \
    p=os.environ.get('SZL_PORT','8080'); \
    sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{p}/healthz',timeout=2).status==200 else 1)"

ENTRYPOINT ["python3", "/app/server.py"]
