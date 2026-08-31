# syntax=docker/dockerfile:1
# SPDX-License-Identifier: Apache-2.0
FROM python:3.12-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf

ARG VERSION=""
ARG REVISION=""
ARG BUILD_DATE=""
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SZL_ORO_ENV=production \
    SZL_ORO_DB_PATH=/data/oro.sqlite \
    SZL_ORO_SIGNING_KEY_PATH=/run/secrets/oro_ed25519 \
    SZL_ORO_SIGNING_KEY_ID=oro-production-v1 \
    A11OY_VERSION=${VERSION} \
    A11OY_GIT_SHA=${REVISION} \
    A11OY_BUILD_DATE=${BUILD_DATE}
LABEL org.opencontainers.image.title="A11oy ORO Control Plane" \
      org.opencontainers.image.version=${VERSION} \
      org.opencontainers.image.revision=${REVISION} \
      org.opencontainers.image.created=${BUILD_DATE} \
      org.opencontainers.image.licenses="Apache-2.0"

WORKDIR /app
RUN pip install --no-cache-dir \
      "fastapi==0.137.1" \
      "uvicorn[standard]==0.49.0" \
      "starlette==1.3.1" \
      "cryptography==50.0.0" && \
    groupadd --gid 10001 oro && \
    useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin oro && \
    install -d -m 0700 -o oro -g oro /data

COPY --chown=10001:10001 oro/ ./oro/
COPY --chown=10001:10001 schemas/oro/ ./schemas/oro/

USER 10001:10001
EXPOSE 7860
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import json,urllib.request; d=json.load(urllib.request.urlopen('http://127.0.0.1:7860/api/a11oy/v1/oro/healthz',timeout=3)); assert d['alive'] is True"

CMD ["python", "-m", "uvicorn", "oro.api:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1"]
