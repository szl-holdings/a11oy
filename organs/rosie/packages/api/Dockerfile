# syntax=docker/dockerfile:1.7
# rosie-api — multi-stage, non-root, Node 20 alpine.
# Final image target ~80 MB. EXPOSE 8080. HEALTHCHECK against /v1/health.

# ── deps: install production dependencies only ───────────────────────────────
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev --no-audit --no-fund

# ── runtime: copy source + prod deps, run as non-root ────────────────────────
FROM node:20-alpine AS runtime
WORKDIR /app

# Build metadata injected at image build time.
ARG GIT_COMMIT=dev
ARG APP_VERSION=1.0.0
ENV NODE_ENV=production \
    PORT=8080 \
    GIT_COMMIT=${GIT_COMMIT} \
    APP_VERSION=${APP_VERSION}

# Production deps from the deps stage; source is run directly via Node's native
# TypeScript stripping (no build artifact, no extra toolchain in the image).
COPY --from=deps /app/node_modules ./node_modules
COPY package.json ./
COPY src ./src

# Drop privileges to the built-in unprivileged `node` user.
USER node

EXPOSE 8080

# Liveness: the container is healthy iff /v1/health answers 200.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:'+(process.env.PORT||8080)+'/v1/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

# Minimal permissions: no --allow-* / no broad flags; only the TS strip flag.
CMD ["node", "--experimental-strip-types", "src/index.ts"]
