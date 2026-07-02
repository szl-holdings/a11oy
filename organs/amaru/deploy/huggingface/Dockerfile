FROM python:3.12-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf AS backend

WORKDIR /app
COPY sidecar/ ./sidecar/
RUN pip install --no-cache-dir ./sidecar

FROM node:22-slim@sha256:813a7480f28fdadac1f7f5c824bcdad435b5bc1322a5968bbbdef8d058f9dff4 AS frontend

WORKDIR /build
COPY web/package.json web/package-lock.json* ./
RUN npm ci --ignore-scripts
COPY web/ ./
RUN npm run build

FROM python:3.12-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf

WORKDIR /app

COPY --from=backend /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=backend /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY sidecar/src/amaru /app/amaru
COPY --from=frontend /build/dist /app/static

# Operator console SPA — self-contained, no build step
COPY static_console/ /app/console/

COPY deploy/huggingface/serve.py /app/serve.py

# Run as a non-root user (uid 1000) for hardened (e.g. IL5) runtimes.
RUN addgroup --system --gid 1000 amaru \
 && adduser  --system --uid 1000 --gid 1000 amaru \
 && chown -R amaru:amaru /app
USER 1000:1000

ENV PORT=7860
EXPOSE 7860

LABEL org.opencontainers.image.source="https://github.com/szl-holdings/amaru" \
      org.opencontainers.image.licenses="LicenseRef-SZL-Proprietary" \
      org.opencontainers.image.title="amaru" \
      org.opencontainers.image.description="Amaru full-stack image: FastAPI sidecar API plus built static frontend + operator console, served on :7860." \
      org.opencontainers.image.vendor="SZL Holdings"

CMD ["python", "serve.py"]
