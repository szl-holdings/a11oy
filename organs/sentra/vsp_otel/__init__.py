# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""vsp-otel — VSP cross-pod OpenTelemetry middleware (real Python implementation).

Vendored per-file COPY into each organ (a11oy, amaru, sentra, killinchu, rosie)
so cross-pod W3C traceparent propagation + OTLP/gRPC spans are uniform mesh-wide.

Doctrine v11 LOCKED 749/14/163 @ c7c0ba17 · Λ = Conjecture 1.
"""
from .middleware import install, make_traceparent, parse_traceparent  # noqa: F401

__version__ = "0.1.0"
__all__ = ["install", "make_traceparent", "parse_traceparent"]
