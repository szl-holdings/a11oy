# SZL Immune v0.1 — source-backed, dependency-free Node image.
# Build context: spaces/immune
FROM node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293

WORKDIR /app

# Canonical source and generated OpenAPI contract. Legacy dist/ remains in Git history
# as deployment evidence, but this image never executes that opaque bundle.
COPY package.json ./package.json
COPY openapi.json ./openapi.json
COPY src ./src
RUN mkdir -p /app/data/immune

RUN chmod -R a+rwX /app/data && chown -R 1000:1000 /app

ENV NODE_ENV=production \
    PORT=7860

EXPOSE 7860

USER 1000

CMD ["node", "src/server/immune-server.mjs"]
