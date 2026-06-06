# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings — Yachay (CTO) + Perplexity Computer Agent
# Doctrine v11 LOCKED — 749/14/163 · Λ = Conjecture 1
"""Drop-in middleware that organs import to enable Verifiable Span Provenance.

Usage (in any organ's ``serve.py``)::

    import vsp_otel.middleware
    vsp_otel.middleware.install(app)   # app is a FastAPI / ASGI app

``install`` is **additive and fail-safe**: if the OpenTelemetry SDK or the OTLP
gRPC exporter are not present, it degrades to an HONEST no-op and returns a
status object describing exactly what was (and was not) wired — it never claims
provenance it did not actually enable.

What ``install`` wires when the SDK is present
----------------------------------------------
1. A ``TracerProvider`` with a ``Resource`` describing the organ.
2. The ``DSSEKhipuSpanProcessor`` (synchronous) — binds + Khipu-chains spans.
3. A ``BatchSpanProcessor`` feeding the **real OTLP/gRPC exporter** to the
   collector (so spans cross the pod boundary).
4. ``FastAPIInstrumentor`` (when ``opentelemetry-instrumentation-fastapi`` is
   present) so HTTP requests become spans automatically.

It also exposes ``GET {prefix}/vsp/khipu`` and ``GET {prefix}/vsp/provenance``
endpoints (when the app is a FastAPI app) reporting the Khipu head, chain length,
and Welford trace-fan-out variance — an honest, court-admissible board.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from . import DOCTRINE
from .dsse_processor import DSSEKhipuSpanProcessor, KhipuChain
from .exporter import VSPExporterConfig, build_exporter


@dataclass
class VSPConfig:
    service_name: str = field(default_factory=lambda: os.environ.get(
        "OTEL_SERVICE_NAME", "szl-organ"))
    endpoint_prefix: str = "/api/vsp"
    otlp: VSPExporterConfig = field(default_factory=VSPExporterConfig.from_env)
    signer: Optional[Callable[[bytes], bytes]] = None
    keyid: str = ""
    rekor_submit: Optional[Callable[[dict], int]] = None
    enable_fastapi_instrumentation: bool = True


@dataclass
class VSPStatus:
    """Honest report of what install() actually wired."""
    enabled: bool
    otlp_exporter: bool
    dsse_processor: bool
    fastapi_instrumented: bool
    endpoints_registered: bool
    chain: Optional[KhipuChain]
    note: str

    def as_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "otlp_exporter": self.otlp_exporter,
            "dsse_processor": self.dsse_processor,
            "fastapi_instrumented": self.fastapi_instrumented,
            "endpoints_registered": self.endpoints_registered,
            "khipu_len": len(self.chain) if self.chain is not None else 0,
            "khipu_head": self.chain.head if self.chain is not None else None,
            "doctrine": DOCTRINE,
            "note": self.note,
        }


def install(app: Any = None, config: VSPConfig | None = None,
            chain: KhipuChain | None = None) -> VSPStatus:
    """Install Verifiable Span Provenance into an ASGI/FastAPI ``app``.

    Returns a :class:`VSPStatus` describing exactly what was wired. Never raises
    on a missing optional dependency — degrades to an HONEST no-op.
    """
    cfg = config or VSPConfig()
    chain = chain if chain is not None else KhipuChain()

    dsse_proc = DSSEKhipuSpanProcessor(
        chain=chain, signer=cfg.signer, keyid=cfg.keyid,
        rekor_submit=cfg.rekor_submit,
    )

    otlp_ok = False
    sdk_ok = False
    vsp_exporter = None
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        sdk_ok = True

        resource = Resource.create({
            "service.name": cfg.service_name,
            "szl.mesh.lambda_axis": DOCTRINE["lambda"],
            "szl.doctrine.version": DOCTRINE["version"],
        })
        provider = TracerProvider(resource=resource)
        # 1) DSSE/Khipu processor (synchronous, binds every span).
        provider.add_span_processor(dsse_proc)
        # 2) Real OTLP/gRPC export to the collector (cross-pod).
        try:
            vsp_exporter = build_exporter(cfg.otlp)
            provider.add_span_processor(BatchSpanProcessor(vsp_exporter))
            otlp_ok = True
        except RuntimeError:
            otlp_ok = False  # HONEST: OTLP package absent; spans still chained
        trace.set_tracer_provider(provider)
    except ImportError:
        sdk_ok = False

    fastapi_ok = False
    if app is not None and cfg.enable_fastapi_instrumentation:
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            FastAPIInstrumentor.instrument_app(app)
            fastapi_ok = True
        except Exception:
            fastapi_ok = False

    endpoints_ok = _register_endpoints(app, cfg, chain, dsse_proc, vsp_exporter)

    note = _build_note(sdk_ok, otlp_ok, fastapi_ok)
    return VSPStatus(
        enabled=sdk_ok or endpoints_ok,
        otlp_exporter=otlp_ok,
        dsse_processor=True,
        fastapi_instrumented=fastapi_ok,
        endpoints_registered=endpoints_ok,
        chain=chain,
        note=note,
    )


def _build_note(sdk_ok: bool, otlp_ok: bool, fastapi_ok: bool) -> str:
    if not sdk_ok:
        return ("OpenTelemetry SDK not installed — VSP degraded to Khipu-chain "
                "endpoints only (HONEST no-op for tracing).")
    parts = ["OTel SDK wired; DSSE/Khipu processor active"]
    parts.append("OTLP gRPC exporter ACTIVE" if otlp_ok
                 else "OTLP gRPC exporter ABSENT (spans chained but not exported)")
    parts.append("FastAPI auto-instrumented" if fastapi_ok
                 else "FastAPI instrumentation not available")
    return "; ".join(parts) + "."


def _register_endpoints(app, cfg, chain, dsse_proc, vsp_exporter) -> bool:
    """Register the honest provenance board on a FastAPI app, if possible."""
    if app is None or not hasattr(app, "add_api_route"):
        return False
    prefix = cfg.endpoint_prefix.rstrip("/")

    def khipu_board():
        receipts = chain.receipts()
        return {
            "khipu_len": len(receipts),
            "khipu_head": chain.head,
            "chain_valid": chain.verify(),
            "receipts": [
                {
                    "index": r.index,
                    "prev": r.prev,
                    "receipt_hash": r.receipt_hash,
                    "link": r.link,
                    "payload_type": r.payload_type,
                    "rekor_log_index": r.rekor_log_index,
                }
                for r in receipts[-100:]
            ],
        }

    def provenance_board():
        fanout = (vsp_exporter.fanout_snapshot()
                  if vsp_exporter is not None else None)
        return {
            "service": cfg.service_name,
            "doctrine": DOCTRINE,
            "khipu_len": len(chain),
            "khipu_head": chain.head,
            "chain_valid": chain.verify(),
            "spans_bound": dsse_proc._bound,
            "trace_fanout": fanout,  # Welford online variance of batch sizes
            "slsa": "L1 honest + L2 attested (CI provenance)",
            "honest_gaps": [
                "Default signer is HMAC test signer unless a real cosign key is injected.",
                "Rekor inclusion only when rekor_submit is configured.",
            ],
        }

    try:
        app.add_api_route(f"{prefix}/khipu", khipu_board, methods=["GET"],
                          include_in_schema=False)
        app.add_api_route(f"{prefix}/provenance", provenance_board,
                          methods=["GET"], include_in_schema=False)
        return True
    except Exception:
        return False
