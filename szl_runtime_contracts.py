# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Stephen P. Lutar Jr. / SZL Holdings
"""Bounded runtime contracts for the a11oy service layer.

Taxonomy home: services/ (runtime health, identity, and observability posture).

The four read-only endpoints deliberately answer different questions:

* ``/api/livez`` proves only that this Python process can answer a request.
* ``/api/readyz`` re-walks the configured Khipu chain and folds in the existing
  boot-preflight signal.  Missing or non-durable chain state fails closed.
* ``/api/build-info`` emits only observable, allowlisted build metadata.
* ``/api/<ns>/v1/otel/status`` separates in-process propagation, exporter
  configuration, and fresh collector delivery evidence.

GETs never mint receipts, sign data, contact an upstream, or write to disk.
"""

import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional


_STARTED_MONOTONIC = time.monotonic()
_SHA_RE = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")
_VERSION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+\-]{0,63}\Z")
_ENV_SHA_NAMES = (
    "A11OY_GIT_SHA",
    "SZL_GIT_SHA",
    "SPACE_COMMIT_SHA",
    "GITHUB_SHA",
    "VERCEL_GIT_COMMIT_SHA",
    "SOURCE_VERSION",
    "GIT_COMMIT",
)
_ENV_VERSION_NAMES = ("A11OY_VERSION", "APP_VERSION", "RELEASE_VERSION")
_DURABLE_BACKENDS = {"sqlite", "json", "postgres", "postgresql", "lmdb"}
_FRESH_COLLECTOR_EVIDENCE_S = 120.0
_SPA_HISTORY_PREFIXES = ("/a11oy",)
_SPA_HISTORY_EXACT_PATHS = frozenset({"/holographic"})
_SPA_FALLBACK_HEADER = "X-SZL-Route-State"
_SPA_FALLBACK_VALUE = "SPA_FALLBACK"
_PRESERVED_RESPONSE_HEADERS = (
    "Content-Security-Policy",
    "Referrer-Policy",
    "Server",
    "Strict-Transport-Security",
    "X-Content-Type-Options",
    "X-RateLimit-Limit",
    "X-RateLimit-Policy",
    "X-RateLimit-Remaining",
    "X-RateLimit-Reset",
    "X-Span-Id",
    "X-Trace-Id",
)
