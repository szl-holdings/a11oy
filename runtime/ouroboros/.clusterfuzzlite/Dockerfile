FROM gcr.io/oss-fuzz-base/base-builder-javascript@sha256:c0de2235c73edc0d02f6f6cb36c6e326d892ec16caf1b5f715083ad09fccdacd

# Install Node.js (match .node-version in repo root: 20)
# Pinned release archive + committed SHA-256 (SCPIN-CURL-1). Checksum copied from
# https://nodejs.org/dist/v20.20.2/SHASUMS256.txt (node-v20.20.2-linux-x64.tar.gz).
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates \
    && test "$(dpkg --print-architecture)" = "amd64" \
    && curl -fsSLo /tmp/node.tar.gz https://nodejs.org/dist/v20.20.2/node-v20.20.2-linux-x64.tar.gz \
    && echo "19e56f0825510207dd904f087fe52faa0a4eb6b2aab5f0ea7a33830d04888b8b  /tmp/node.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/node.tar.gz -C /usr/local --strip-components=1 --no-same-owner \
    && rm -f /tmp/node.tar.gz \
    && node --version | grep -Fx 'v20.20.2' \
    && npm install -g pnpm \
    && rm -rf /var/lib/apt/lists/*

# Copy repo into the builder image
COPY . $SRC/ouroboros

WORKDIR $SRC/ouroboros

# Copy build script
COPY .clusterfuzzlite/build.sh $SRC/
