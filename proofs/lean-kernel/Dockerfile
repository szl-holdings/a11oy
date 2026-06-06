# SZLHOLDINGS/lean-kernel — live Lean/Lake verification kernel
# Ubuntu 24.04 + elan + Lean v4.13.0 + Mathlib v4.13.0 + nginx + FastAPI
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/root/.elan/bin:${PATH}"
ENV ELAN_BIN="/root/.elan/bin"
ENV LUTAR_REPO="/opt/lutar-lean"

RUN apt-get update && apt-get install -y --no-install-recommends \
      git curl ca-certificates nginx python3 python3-pip python3-venv \
      build-essential \
    && rm -rf /var/lib/apt/lists/*

# --- elan (Lean toolchain manager), SHA-pinned to the same commit CI uses ---
RUN ELAN_SHA=3d5138e1526a569a23901b8ee559032793cf445e \
    && EXPECTED=4bacca9502cb89736fe63d2685abc2947cfbf34dc87673504f1bb4c43eda9264 \
    && curl -sSfL "https://raw.githubusercontent.com/leanprover/elan/$ELAN_SHA/elan-init.sh" -o /tmp/elan-init.sh \
    && echo "$EXPECTED  /tmp/elan-init.sh" | sha256sum -c \
    && sh /tmp/elan-init.sh -y --default-toolchain none \
    && rm /tmp/elan-init.sh

# --- clone lutar-lean at pinned main; install the v4.13.0 toolchain ---
RUN git clone --depth 1 https://github.com/szl-holdings/lutar-lean.git ${LUTAR_REPO} \
    && cd ${LUTAR_REPO} \
    && cat lean-toolchain \
    && lake --version

# --- warm Mathlib cache (best-effort; build still works without) ---
# The repo ships a pinned lake-manifest.json, so we DO NOT run `lake update`
# (which could move deps off the pinned revs). `lake exe cache get` pulls the
# prebuilt Mathlib oleans for the pinned revs so the on-demand `lake build` is
# fast. If the cache is unavailable the kernel still serves; the build endpoint
# reports the honest failure rather than faking green.
RUN cd ${LUTAR_REPO} \
    && (lake exe cache get || echo "WARN: mathlib cache fetch incomplete; build will compile from source on demand")

# --- python service deps ---
COPY requirements.txt /opt/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /opt/requirements.txt

# --- app + data + nginx ---
COPY app/ /opt/app/
COPY data/ /opt/app/data/
COPY nginx.conf /etc/nginx/sites-available/default
COPY start.sh /opt/start.sh
RUN chmod +x /opt/start.sh

EXPOSE 7860
CMD ["/opt/start.sh"]
