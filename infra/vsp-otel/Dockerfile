# vsp-otel — Λ-signed OpenTelemetry collector exporter shim
# Layer 4 of the SZL 7-layer architecture. SLSA L1+L2 target.
#
# Per-file COPY only (SZL Doctrine v11 §build). No `COPY . .`.
FROM python:3.12-slim AS base

# Non-root runtime user.
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin vsp

WORKDIR /app

# --- dependency layer (cached) -------------------------------------------------
COPY collector/requirements.txt /app/collector/requirements.txt
RUN pip install --no-cache-dir -r /app/collector/requirements.txt

# --- application layer (per-file COPY, doctrine §build) ------------------------
COPY collector/__init__.py    /app/collector/__init__.py
COPY collector/app.py         /app/collector/app.py
COPY collector/lambda_gate.py /app/collector/lambda_gate.py
COPY collector/dsse.py        /app/collector/dsse.py
COPY collector/stats.py       /app/collector/stats.py

ENV LAMBDA_FLOOR=0.90 \
    VSP_SIGN_MODE=auto \
    PORT=4318 \
    PYTHONUNBUFFERED=1

EXPOSE 4318
USER vsp

# OTLP/HTTP receiver on :4318/v1/traces ; /healthz ; /metrics
HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"4318\")}/healthz')" || exit 1

ENTRYPOINT ["uvicorn", "collector.app:app", "--host", "0.0.0.0", "--port", "4318"]
