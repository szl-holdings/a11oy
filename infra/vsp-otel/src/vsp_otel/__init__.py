# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings — Yachay (CTO) + Perplexity Computer Agent
# Doctrine v11 LOCKED — 749 declarations / 14 unique axioms / 163 sorries
# Λ = Conjecture 1 (NEVER a theorem)
"""vsp_otel — Verifiable Span Provenance via OpenTelemetry.

This is the *operational* OTel layer for the SZL mesh. It closes the honest gap
left by a11oy's in-process span exporter:

  * a11oy / vsp-otel (TypeScript runtime) emit Λ-signed spans **in-process only** —
    there is no real OTLP wire export and no cross-pod broker.
  * ``vsp_otel`` (this Python package) provides a **real OTLP/gRPC exporter** wired
    to an OpenTelemetry Collector, a **DSSE-aware span processor** that binds every
    span into the Khipu receipt chain, and a **drop-in middleware** so any organ
    (FastAPI app) can turn on Verifiable Span Provenance with one call.

Public API
----------
    install(app, **kw)            -> install VSP into a FastAPI/ASGI app
    build_exporter(endpoint, ...) -> a configured OTLP gRPC SpanExporter
    DSSEKhipuSpanProcessor        -> SpanProcessor that DSSE-binds + Khipu-chains spans
    KhipuChain                    -> in-memory append-only Khipu receipt chain

Honest gaps are declared in README.md and ARCH.md — read them.
"""

from __future__ import annotations

__version__ = "0.1.0"

# Doctrine constants (single source of truth, re-exported for tests/diagnostics).
DOCTRINE = {
    "version": "v11",
    "declarations": 749,
    "axioms_unique": 14,
    "sorries_total": 163,
    "lambda": "Conjecture 1",  # NEVER a theorem
    "replay_hash": "c7c0ba17",
}

# SZL OTel semantic-convention attribute keys (the contract organs rely on).
ATTR_RECEIPT_HASH = "szl.mesh.receipt_hash"
ATTR_REKOR_LOG_INDEX = "szl.mesh.rekor_log_index"
ATTR_DSSE_PAYLOAD_TYPE = "szl.mesh.dsse_payload_type"
ATTR_KHIPU_PREV = "szl.mesh.khipu_prev"
ATTR_KHIPU_INDEX = "szl.mesh.khipu_index"
ATTR_LAMBDA_AXIS = "szl.mesh.lambda_axis"

from .exporter import build_exporter, VSPExporterConfig  # noqa: E402
from .dsse_processor import (  # noqa: E402
    DSSEKhipuSpanProcessor,
    KhipuChain,
    KhipuReceipt,
    dsse_pae,
    dsse_envelope,
)
from .middleware import install, VSPConfig  # noqa: E402

__all__ = [
    "__version__",
    "DOCTRINE",
    "ATTR_RECEIPT_HASH",
    "ATTR_REKOR_LOG_INDEX",
    "ATTR_DSSE_PAYLOAD_TYPE",
    "ATTR_KHIPU_PREV",
    "ATTR_KHIPU_INDEX",
    "ATTR_LAMBDA_AXIS",
    "build_exporter",
    "VSPExporterConfig",
    "DSSEKhipuSpanProcessor",
    "KhipuChain",
    "KhipuReceipt",
    "dsse_pae",
    "dsse_envelope",
    "install",
    "VSPConfig",
]
