"""rosie.console — operator-console backend handlers + observability.

This package brings the operator-console handlers that the live Gradio Space
drives (Receipt Verifier, Span Explorer, Mesh Query) into the repository as a
plain, importable, testable Python library — independent of Gradio. The same
functions can back the Gradio UI, the TypeScript API, or a CLI.

Modules:
  receipt_verifier — DSSE/PAE v1 HMAC-SHA-256 envelope verification.
  spans            — span fixture generation + filtering (Span Explorer).
  mesh             — per-component mesh health aggregation (mesh query).
  version          — build identity for /healthz (git SHA + boot timestamp).
  telemetry        — structured JSON logging + optional OpenTelemetry spans.
  health           — /healthz payload + stdlib HTTP server.

SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

__all__ = [
    "receipt_verifier",
    "spans",
    "mesh",
    "version",
    "telemetry",
    "health",
]
