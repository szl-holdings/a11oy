# syntax=docker/dockerfile:1.7
#
# a11oy — multi-stage container build.
#
# a11oy is a TypeScript policy / receipt substrate. It is a library plus a
# CLI (receipt-substrate) that can also run an HTTP server. ENTRYPOINT
# dispatches to the bundled CLI or, when given the `serve` subcommand, boots
# the HTTP server (/healthz, /readyz, /v1/ledger, /v1/verify,
# /v1/policy/evaluate) that the Kubernetes probes target. The doctrine packages
# (@a11oy/core, @a11oy/connection) are compiled to dist/ and importable by
# downstream Node tooling.
#
# Build:  docker build -t a11oy:seriesa-test .
# Run:    docker run --rm a11oy:seriesa-test --version
#         docker run --rm a11oy:seriesa-test --help
#         docker run --rm -p 8080:8080 a11oy:seriesa-test serve --port 8080
#
# Authored for SZL Holdings. Signed-off per repository DCO.

# ---------------------------------------------------------------------------
# Stage 1 — builder: install workspace deps and compile the doctrine packages.
# ---------------------------------------------------------------------------
FROM node:22-alpine AS builder

# Enable Corepack-managed pnpm pinned to the version used in CI/local dev.
RUN corepack enable && corepack prepare pnpm@11.5.0 --activate

WORKDIR /app

# pnpm's deps-status guard re-runs `pnpm install` before `run` scripts; the
# extracted showcase repo references some workspace packages that live in the
# parent monorepo, so we disable that guard for in-image builds. The frozen
# lockfile install below is still authoritative for what gets installed.
ENV PNPM_CONFIG_VERIFY_DEPS_BEFORE_RUN=false
# Native-dep build scripts (esbuild/unrs-resolver) are not needed to compile the
# doctrine TS packages; pnpm v11 otherwise exits non-zero on "ignored builds".
ENV PNPM_CONFIG_STRICT_DEP_BUILDS=false
# pnpm refuses to purge node_modules without a TTY unless CI is set.
ENV CI=true

# Copy only the manifests + lockfile first to maximise layer caching.
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json ./
COPY packages/a11oy-knowledge/package.json packages/a11oy-knowledge/package.json
COPY packages/qec-integrity/package.json   packages/qec-integrity/package.json
COPY artifacts/a11oy-uds/package.json       artifacts/a11oy-uds/package.json
COPY web/packages/a11oy-core/package.json       web/packages/a11oy-core/package.json
COPY web/packages/a11oy-connection/package.json web/packages/a11oy-connection/package.json

RUN pnpm install --frozen-lockfile

# Copy the rest of the source and build the doctrine packages to dist/.
COPY . .
RUN pnpm run build:doctrine

# Prune to a production-only node_modules for the runtime stage. The doctrine
# packages carry essentially no runtime deps, so this drops the TypeScript /
# jest toolchain (node_modules ~142M -> ~0.3M).
RUN pnpm prune --prod

# ---------------------------------------------------------------------------
# Stage 2 — runtime: minimal Alpine, non-root, CLI entrypoint.
# ---------------------------------------------------------------------------
FROM node:22-alpine AS runtime

ENV NODE_ENV=production

WORKDIR /app

# Create a non-root user (uid 1000) to satisfy hardened (e.g. IL5) runtimes.
RUN addgroup -g 1000 -S a11oy \
 && adduser  -u 1000 -S a11oy -G a11oy

# Copy production node_modules and the built / source artifacts the CLI needs.
COPY --from=builder --chown=a11oy:a11oy /app/node_modules ./node_modules
COPY --from=builder --chown=a11oy:a11oy /app/package.json ./package.json
COPY --from=builder --chown=a11oy:a11oy /app/packages ./packages
COPY --from=builder --chown=a11oy:a11oy /app/web/packages/a11oy-core/dist       ./web/packages/a11oy-core/dist
COPY --from=builder --chown=a11oy:a11oy /app/web/packages/a11oy-connection/dist ./web/packages/a11oy-connection/dist
COPY --from=builder --chown=a11oy:a11oy /app/docker-entrypoint.sh ./docker-entrypoint.sh

RUN chmod +x ./docker-entrypoint.sh

USER 1000:1000

# OCI image metadata. VERSION is overridable at build time:
#   docker build --build-arg VERSION=1.0.0-alpha ...
ARG VERSION=1.0.0
LABEL org.opencontainers.image.source="https://github.com/szl-holdings/a11oy" \
      org.opencontainers.image.licenses="LicenseRef-SZL-Proprietary" \
      org.opencontainers.image.title="a11oy" \
      org.opencontainers.image.description="Governed policy / receipt substrate: Layer 6 formula gates, receipt chaining, and doctrine runtime (CLI plus `serve` HTTP mode)." \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.vendor="SZL Holdings"

# Default port for serve mode; the k8s probes target /healthz on this port.
EXPOSE 8080
ENV A11OY_PORT=8080

# HEALTHCHECK probes the serve-mode /healthz endpoint. It is a no-op for plain
# CLI invocations (which exit immediately), and gives orchestrators a real
# liveness signal when the container is run as `serve`.
HEALTHCHECK --interval=20s --timeout=3s --start-period=5s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:'+(process.env.A11OY_PORT||8080)+'/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

ENTRYPOINT ["./docker-entrypoint.sh"]
# Default to CLI help. Long-running deployments override this with `serve`
# (see deploy/manifests/a11oy-deployment.yaml).
CMD ["--help"]
