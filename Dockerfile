# syntax=docker/dockerfile:1
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
#
# a11oy HF Docker Space — RESET build (Brand Orchestration Layer at /).
#
# RESET 2026-05-31 (Yachay CTO): a11oy is NOT a /console/ admin panel.
# Per Replit .replit-artifact/artifact.toml: BASE_PATH="/", serve="static" from dist/public,
# rewrite /* -> /index.html (SPA history fallback). The React SPA IS the Brand
# Orchestration Layer; its HomePage (Vessels-DNA / investor-facing landing) renders at /.
#
# Serves:
#   /            — SPA front door (Brand Orchestration Layer landing)
#   /assets/*    — SPA JS/CSS chunks (vite base="/")
#   /boardroom, /investor-demo, /sovereign, /fabric, /nexus, /command, ... — SPA routes (history fallback)
#   /api/a11oy/* — a11oy serve endpoints (health, gates, reason, policy/evaluate, proxy)
#
# HF Space requirement: listen on PORT 7860.

# ---------------------------------------------------------------------------
# OWNED KHIPU CPU RUNTIME: use the official universal manylinux wheel.
# No source-build toolchain or compile intermediates enter either
# the builder or the published runtime. The exact release asset is
# pinned by SHA-256 and verified for size plus glibc linkage.
ARG A11OY_REQUIRE_LOCAL_LLM=1
FROM python:3.12-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf AS llama-build-1
ARG LLAMA_CPP_WHEEL=llama_cpp_python-0.3.35-py3-none-manylinux2014_x86_64.manylinux_2_17_x86_64.whl
COPY scripts/fetch_owned_khipu_wheel.py /tmp/fetch_owned_khipu_wheel.py
RUN python3 /tmp/fetch_owned_khipu_wheel.py && rm /tmp/fetch_owned_khipu_wheel.py
