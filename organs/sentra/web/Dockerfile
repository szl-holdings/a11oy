# syntax=docker/dockerfile:1
# Multi-stage build for the Sentra web app (@workspace/sentra).
#
# Workspace layout (pnpm-workspace.yaml): web, runtime/*, stubs/*
# The web app is a Vite SPA; `vite build` emits to web/dist (base path /sentra/).
#
# NOTE: web/package.json depends on two packages published to the private
# @szl-holdings GitHub Packages registry (@szl-holdings/a11oy-policy,
# @szl-holdings/a11oy-receipt-substrate). `pnpm install` therefore requires
# NODE_AUTH_TOKEN (a secret available in CI, not in local/sandbox builds).
# Pass it as a BuildKit secret:  --secret id=npmrc,src=$HOME/.npmrc
#
# Build context is the repo ROOT (pnpm needs the whole workspace):
#   docker build -f web/Dockerfile -t sentra-web .
#
# Per-file COPY (Doctrine v11 — no COPY . .)
FROM node:22-alpine@sha256:16e22a550f3863206a3f701448c45f7912c6896a62de43add43bb9c86130c3e2 AS base
WORKDIR /app
RUN apk add --no-cache libc6-compat
RUN corepack enable pnpm

# ---- deps: install full workspace (cached on lockfile + manifests) ----
FROM base AS deps
ENV CI=true
# Workspace root files
COPY package.json ./
COPY pnpm-lock.yaml ./
COPY pnpm-workspace.yaml ./
COPY biome.json ./
COPY .npmrc ./
# Web app sources
COPY web/ ./web/
# Runtime packages (workspace members)
COPY runtime/ ./runtime/
# Stubs (workspace members)
COPY stubs/ ./stubs/
RUN --mount=type=secret,id=npmrc,target=/root/.npmrc \
    pnpm install --frozen-lockfile --ignore-scripts

# ---- builder: build the web SPA ----
FROM base AS builder
ENV NODE_ENV=production
COPY --from=deps /app ./
RUN pnpm --filter @workspace/sentra run build

# ---- runner: static nginx, non-root ----
FROM nginx:alpine@sha256:54f2a904c251d5a34adf545a72d32515a15e08418dae0266e23be2e18c66fefa AS runner
COPY --from=builder /app/web/dist /usr/share/nginx/html
RUN printf 'server {\n  listen 8080;\n  root /usr/share/nginx/html;\n  index index.html;\n  location / { try_files $uri $uri/ /index.html; }\n}\n' > /etc/nginx/conf.d/default.conf \
    && sed -i 's|pid\s*/run/nginx.pid;|pid /tmp/nginx.pid;|' /etc/nginx/nginx.conf \
    && sed -i '/^user /d' /etc/nginx/nginx.conf \
    && chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/log/nginx /etc/nginx/conf.d \
    && chmod -R 755 /usr/share/nginx/html
EXPOSE 8080
LABEL org.opencontainers.image.source="https://github.com/szl-holdings/sentra"
LABEL org.opencontainers.image.description="Sentra — Cyber Resilience Command (web console)"
LABEL org.opencontainers.image.licenses="LicenseRef-SZL-Proprietary"
USER nginx
CMD ["nginx", "-g", "daemon off;"]
