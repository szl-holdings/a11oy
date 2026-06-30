# IMMUNE investor demo — self-contained image.
# Build context = this deploy/ directory. Run build-standalone.sh FIRST to produce ./dist.
#
#   bash build-standalone.sh
#   docker build -t immune-demo .
#   docker run --rm -p 7860:7860 immune-demo
#
# The server bundle has all node deps inlined, so no npm install is needed at image
# build time — the image stays small.
FROM node:20-alpine

WORKDIR /app

# Self-contained server bundle, the vite-built SPA, and the REAL receipt/evidence chain.
COPY dist/immune-server.js ./immune-server.js
COPY dist/public ./public
COPY dist/data ./data

# Hugging Face Spaces runs the container as a non-root user (UID 1000); the immune
# ledger appends to ./data/immune, so that path must be writable by that user.
RUN chmod -R a+rwX /app/data && chown -R 1000:1000 /app

ENV NODE_ENV=production \
    PORT=7860

EXPOSE 7860

USER 1000

CMD ["node", "immune-server.js"]
