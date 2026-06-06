"""OTLP bridge (WU-3): in-process spans -> OTLP/HTTP-JSON -> vsp-otel exporter.

This is the THIN integration layer in the canonical home ``szl-holdings/uds-mesh``
(per ADR-0001). The real OTLP wire encoder/exporter lives in
``szl-holdings/vsp-otel`` (``runtime/src/otlp/exporter.ts``, shipped in PR #61,
``feat/real-otlp-exporter``). This module does NOT reimplement that wire format —
it bridges uds-mesh's in-process span dicts into the exact OTLP/HTTP-JSON
``ExportTraceServiceRequest`` shape that the vsp-otel exporter/collector emit and
parse, then hands the batch to an injectable transport (default = the in-proc OTLP
collector handler; production = HTTP POST to ``MESH_OTLP_ENDPOINT``).

ADR: ADR-0001 (Canonical Home for the UDS Mesh, ACCEPTED 2026-06-03).

HONESTY OVER CHECKLIST
----------------------
- The OTLP/HTTP-JSON encoding here is REAL and round-trips
  (resourceSpans -> scopeSpans -> spans; ns timestamps as strings) — matching the
  vsp-otel exporter contract documented in WU-3.
- No live network POST in CI: ``transport`` defaults to an in-proc capture. The
  real HTTP transport is provided but only used when ``MESH_OTLP_ENDPOINT`` is set.
- The DSSE batch receipt reuses ``pinn_dsse.sign_payload`` (UNSIGNED marker when
  the cosign key is absent — never a fabricated signature).
- This is an INTEGRATION layer; the authoritative exporter is vsp-otel PR #61.

Doctrine v11 — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (never a theorem).
"""
from __future__ import annotations

import os
from typing import Any, Callable

try:
    import pinn_dsse  # type: ignore
except Exception:  # pragma: no cover
    pinn_dsse = None  # type: ignore

BRIDGE_RECEIPT_TYPE = "application/vnd.szl.mesh-otlp-batch-receipt+json"


def _hex(s: str) -> str:
    """Pass through hex; ids in span dicts are expected already hex-encoded."""
    return s


def to_otlp_json(
    spans: list[dict[str, Any]],
    resource: dict[str, Any] | None = None,
    scope_name: str = "szl.uds-mesh.bridge",
) -> dict[str, Any]:
    """Encode in-process span dicts to an OTLP/HTTP-JSON ExportTraceServiceRequest.

    Each input span dict may carry: ``trace_id``, ``span_id``, ``name``,
    ``start_ns``, ``end_ns``, ``attributes`` (dict), ``status`` (str), and the
    SZL anchor attrs (``szl.anchor_formula.id`` etc.) which are preserved.

    >>> req = to_otlp_json([{"trace_id": "a"*32, "span_id": "b"*16, "name": "x"}])
    >>> req["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["name"]
    'x'
    """
    resource = resource or {"service.name": "uds-mesh"}

    def attr_kv(d: dict[str, Any]) -> list[dict[str, Any]]:
        out = []
        for k, v in d.items():
            if isinstance(v, bool):
                val = {"boolValue": v}
            elif isinstance(v, int):
                val = {"intValue": str(v)}
            elif isinstance(v, float):
                val = {"doubleValue": v}
            else:
                val = {"stringValue": str(v)}
            out.append({"key": k, "value": val})
        return out

    otlp_spans = []
    for s in spans:
        sp: dict[str, Any] = {
            "traceId": _hex(s.get("trace_id", "")),
            "spanId": _hex(s.get("span_id", "")),
            "name": s.get("name", ""),
            "kind": int(s.get("kind", 1)),
            "startTimeUnixNano": str(s.get("start_ns", 0)),
            "endTimeUnixNano": str(s.get("end_ns", 0)),
            "attributes": attr_kv(s.get("attributes", {})),
        }
        if s.get("parent_span_id"):
            sp["parentSpanId"] = _hex(s["parent_span_id"])
        if s.get("status"):
            sp["status"] = {"code": s["status"]}
        otlp_spans.append(sp)

    return {
        "resourceSpans": [
            {
                "resource": {"attributes": attr_kv(resource)},
                "scopeSpans": [
                    {"scope": {"name": scope_name}, "spans": otlp_spans}
                ],
            }
        ]
    }


def parse_otlp_json(req: dict[str, Any]) -> list[dict[str, Any]]:
    """Inverse of :func:`to_otlp_json` — round-trips spans back to dicts.

    >>> spans = [{"trace_id": "a"*32, "span_id": "b"*16, "name": "x",
    ...           "attributes": {"szl.anchor_formula.id": "F1"}}]
    >>> back = parse_otlp_json(to_otlp_json(spans))
    >>> back[0]["name"] == "x" and back[0]["attributes"]["szl.anchor_formula.id"] == "F1"
    True
    """
    def kv_to_dict(kvs: list[dict[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for kv in kvs:
            val = kv.get("value", {})
            if "boolValue" in val:
                out[kv["key"]] = val["boolValue"]
            elif "intValue" in val:
                out[kv["key"]] = int(val["intValue"])
            elif "doubleValue" in val:
                out[kv["key"]] = val["doubleValue"]
            else:
                out[kv["key"]] = val.get("stringValue", "")
        return out

    spans: list[dict[str, Any]] = []
    for rs in req.get("resourceSpans", []):
        for ss in rs.get("scopeSpans", []):
            for sp in ss.get("spans", []):
                spans.append(
                    {
                        "trace_id": sp.get("traceId", ""),
                        "span_id": sp.get("spanId", ""),
                        "parent_span_id": sp.get("parentSpanId", ""),
                        "name": sp.get("name", ""),
                        "kind": sp.get("kind", 1),
                        "start_ns": int(sp.get("startTimeUnixNano", "0")),
                        "end_ns": int(sp.get("endTimeUnixNano", "0")),
                        "attributes": kv_to_dict(sp.get("attributes", [])),
                        "status": (sp.get("status") or {}).get("code"),
                    }
                )
    return spans


def _inproc_transport(req: dict[str, Any]) -> dict[str, Any]:
    """Default transport: parse the request back (round-trip) and accept it.

    Mirrors what the vsp-otel collector verifier does on ingest (re-parse +
    count). No network is touched.
    """
    spans = parse_otlp_json(req)
    return {"code": "SUCCESS", "accepted": len(spans)}


def _http_transport(endpoint: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def _post(req: dict[str, Any]) -> dict[str, Any]:  # pragma: no cover - network
        import json
        import urllib.request

        data = json.dumps(req).encode("utf-8")
        r = urllib.request.Request(
            endpoint, data=data, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(r, timeout=10) as resp:
            return {"code": "SUCCESS" if resp.status < 300 else "FAILURE",
                    "http_status": resp.status}

    return _post


class OtlpBridge:
    """Bridge in-process mesh spans to the vsp-otel OTLP exporter contract."""

    def __init__(self, transport: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
                 resource: dict[str, Any] | None = None) -> None:
        endpoint = os.environ.get("MESH_OTLP_ENDPOINT")
        if transport is not None:
            self.transport = transport
        elif endpoint:
            self.transport = _http_transport(endpoint)
        else:
            self.transport = _inproc_transport
        self.resource = resource or {"service.name": "uds-mesh"}

    def export(self, spans: list[dict[str, Any]]) -> dict[str, Any]:
        """Encode spans to OTLP-JSON, send via transport, stamp a DSSE receipt."""
        req = to_otlp_json(spans, self.resource)
        try:
            result = self.transport(req)
        except Exception as e:  # honest failure, no fake success
            return {"code": "FAILURE", "error": f"{type(e).__name__}: {e}",
                    "batch_receipt": self._receipt(0, "FAILURE")}
        accepted = result.get("accepted", len(spans))
        result["batch_receipt"] = self._receipt(accepted, result.get("code", "SUCCESS"))
        return result

    def _receipt(self, accepted: int, code: str) -> dict[str, Any]:
        payload = {"kind": "mesh-otlp-batch", "accepted": accepted, "code": code}
        if pinn_dsse is None:
            return {"payloadType": BRIDGE_RECEIPT_TYPE, "signed": False,
                    "honesty": "UNSIGNED — pinn_dsse unavailable; no signature fabricated.",
                    "_payload": payload}
        return pinn_dsse.sign_payload(payload, payload_type=BRIDGE_RECEIPT_TYPE)


if __name__ == "__main__":  # pragma: no cover
    import doctest

    fails, _ = doctest.testmod(verbose=False)
    if fails == 0:
        print("\u2713 otlp_bridge doctests passed (in-process spans -> OTLP/HTTP-JSON -> transport)")
