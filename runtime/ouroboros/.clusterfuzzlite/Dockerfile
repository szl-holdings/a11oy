FROM gcr.io/oss-fuzz-base/base-builder-javascript@sha256:c0de2235c73edc0d02f6f6cb36c6e326d892ec16caf1b5f715083ad09fccdacd

# Install Node.js (match .node-version in repo root)
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g pnpm \
    && rm -rf /var/lib/apt/lists/*

# Copy repo into the builder image
COPY . $SRC/ouroboros

WORKDIR $SRC/ouroboros

# Copy build script
COPY .clusterfuzzlite/build.sh $SRC/
