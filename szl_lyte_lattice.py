# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 — LYTE lattice BIND hologram on a-11-oy.com.
"""
szl_lyte_lattice.py — BIND_AS_A11OY_PACKAGE status surface.

Cites szl-holdings/lyte-lattice @ 9db7f25. Not a second flagship.
Not a production certificate of a-11-oy.com.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List, Optional

_ORGAN_NAME = "LYTE lattice"
_KHIPU_ORGAN = "lyte-lattice"
_RECEIPT_TYPE = "SZL.LyteLattice.Status.v1"
_BIND = "BIND_AS_A11OY_PACKAGE"
_ORDER = "AO-2026-08-29-001"
_SOURCE = "https://github.com/szl-holdings/lyte-lattice"
_SOURCE_SHA = "9db7f25c99f22faf0806ea9bdc2773f54a06dbbd"
_FACTORY = "https://github.com/szl-holdings/a11oy-factory"
_LYTE_WINDOW = "https://github.com/szl-holdings/lyte-services"
_HUB_SPACE = "https://huggingface.co/spaces/SZLHOLDINGS/lyte-lattice"
_PRODUCT = "https://a-11-oy.com"
_PROOF = "https://a11oy.net"
_LOCKED_PROVEN = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
_KERNEL_COMMIT = "c7c0ba17"

_FRONTIERS: List[Dict[str, str]] = [
    {"n": "lyte", "title": "Lyte", "cited": "owner-admitted design-partner cell", "honesty": "STRUCTURAL-ONLY"},
    {"n": "N1", "title": "Serve", "cited": "vLLM / SGLang / Ollama / TensorRT-LLM", "honesty": "LIVE hologram"},
    {"n": "N2", "title": "Graph", "cited": "LangGraph agent orchestration", "honesty": "LIVE hologram"},
    {"n": "N3", "title": "Guard", "cited": "Llama Guard prompt/response safeguard", "honesty": "LIVE hologram"},
    {"n": "N4", "title": "Mosaic", "cited": "MosaicML / Databricks own-data mosaic", "honesty": "LIVE hologram"},
    {"n": "N5", "title": "Lattice", "cited": "immune-lattice SENTRA / YAWAR overlay", "honesty": "LIVE hologram"},
    {"n": "N6", "title": "Cover", "cited": "Guidewire P&C core", "honesty": "LIVE hologram"},
    {"n": "N7", "title": "Quant", "cited": "QuantConnect LEAN backtest", "honesty": "LIVE hologram"},
    {"n": "N8", "title": "Title", "cited": "Zillow / public records", "honesty": "LIVE hologram · occupancy UNAVAILABLE"},
    {"n": "N9", "title": "Retrieve", "cited": "LlamaIndex / Haystack / Letta", "honesty": "LIVE hologram"},
    {"n": "N10", "title": "Observe", "cited": "Phoenix / LangSmith / Langfuse / DeepEval", "honesty": "LIVE hologram"},
    {"n": "N11", "title": "Tune", "cited": "Unsloth LoRA / QLoRA", "honesty": "LIVE hologram"},
    {"n": "N12", "title": "Schema", "cited": "Outlines / Instructor constrained generation", "honesty": "LIVE hologram"},
    {"n": "N13", "title": "Energy", "cited": "RAPL / NVML joule channel", "honesty": "LIVE probe · joule UNAVAILABLE unless RAPL reads"},
    {"n": "N14", "title": "Tool", "cited": "Anthropic MCP", "honesty": "LIVE hologram"},
    {"n": "N15", "title": "Memory", "cited": "Mem0 / Zep Graphiti", "honesty": "LIVE hologram"},
    {"n": "N16", "title": "Eval", "cited": "RAGAS / HELM / LMSYS Arena", "honesty": "LIVE hologram"},
    {"n": "N17", "title": "Mesh", "cited": "NVIDIA Dynamo / Ray Serve / llm-d", "honesty": "LIVE hologram · GPU UNAVAILABLE"},
    {"n": "N18", "title": "Route", "cited": "LiteLLM / OpenRouter / RouteLLM", "honesty": "LIVE hologram"},
    {"n": "N19", "title": "Cache", "cited": "LMCache / Mooncake / GPTCache", "honesty": "LIVE hologram"},
    {"n": "N20", "title": "Voice", "cited": "LiveKit / Cartesia / Deepgram", "honesty": "LIVE hologram · no audio bytes"},
    {"n": "N21", "title": "Sandbox", "cited": "Daytona / E2B", "honesty": "LIVE hologram · AST whitelist"},
    {"n": "N22", "title": "Identity", "cited": "SPIFFE / SPIRE / Astrix NHI", "honesty": "LIVE hologram · unsigned"},
    {"n": "N23", "title": "Rails", "cited": "NVIDIA NeMo Guardrails", "honesty": "LIVE hologram · not Llama Guard"},
    {"n": "N24", "title": "Browser", "cited": "Playwright / Stagehand / Browserbase", "honesty": "LIVE hologram · plan only"},
    {"n": "N25", "title": "Policy", "cited": "AWS Cedar / Open Policy Agent", "honesty": "LIVE hologram"},
    {"n": "N26", "title": "Inference", "cited": "szl-command-lab NVML/RAPL wrap", "honesty": "REPORTED · never a fabricated joule"},
    {"n": "N27", "title": "Train", "cited": "szl-forge Unsloth QLoRA; szl-gpu-bridge", "honesty": "UNAVAILABLE · NEVER_DISPATCH"},
]

_WAVES = [
    {"id": "W1", "name": "Core path", "cells": ["N1", "N2", "N3", "N4", "N5", "N6", "N7", "N8", "N9"], "admitted": 9, "blocked": 0},
    {"id": "W2", "name": "Observe + shape", "cells": ["N10", "N11", "N12", "N13", "N14", "N15", "N16", "N17", "N18"], "admitted": 9, "blocked": 0},
    {"id": "W3", "name": "Plane edge", "cells": ["N19", "N20", "N21", "N22", "N23", "N24", "N25", "N26", "N27"], "admitted": 8, "blocked": 1},
]


def _unsigned_receipt(payload: Dict[str, Any]) -> Dict[str, Any]:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha3_256(blob).hexdigest()
    return {
        "receipt_type": _RECEIPT_TYPE,
        "organ": _KHIPU_ORGAN,
        "digest": digest,
        "alg": "sha3_256",
        "signature": None,
        "signed": False,
        "kind": "UNSIGNED-honest",
        "proven_trust": False,
        "note": "Hash-linked only. Not Cosign. Not DSSE. proven_trust stays false.",
    }


def _khipu_receipt(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        import szl_khipu  # type: ignore

        dag = szl_khipu.get_dag(_KHIPU_ORGAN, ns="a11oy")
        r = dag.emit("lyte-lattice.status", payload)
        signed = bool(r.get("signature"))
        return {
            "receipt_type": _RECEIPT_TYPE,
            "organ": _KHIPU_ORGAN,
            "ns": "a11oy",
            "seq": r.get("seq"),
            "digest": r.get("digest"),
            "prev": r.get("prev"),
            "payload_digest": r.get("payload_digest"),
            "signature": r.get("signature"),
            "signed": signed,
            "kind": "UNSIGNED-honest" if not signed else "HASH-LINKED",
            "proven_trust": False,
            "chain_verified": r.get("chain_verified"),
            "chain_depth": dag.depth(),
            "head_digest": dag.head(),
        }
    except Exception:
        return None


def healthz() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "lyte-lattice",
        "organ": _ORGAN_NAME,
        "bind": _BIND,
        "certified": False,
        "proven_trust": False,
        "hub_running": False,
        "source": _SOURCE,
        "sha": _SOURCE_SHA,
    }


def status() -> Dict[str, Any]:
    honesty = {
        "bind": _BIND,
        "order": _ORDER,
        "certified": False,
        "product_certificate": False,
        "second_flagship": False,
        "lyte": "STRUCTURAL-ONLY",
        "organs": "LIVE hologram (cited GitHub console). Not a local GPU cluster.",
        "energy_joule": "UNAVAILABLE unless RAPL energy_uj is actually read. Watts are not joules.",
        "occupancy": "UNAVAILABLE. Not MLS.",
        "receipts": "UNSIGNED-honest",
        "proven_trust": False,
        "hub_running": "UNAVAILABLE — Immune HF_TOKEN readback required. Not fabricated LIVE.",
        "lambda": "Conjecture 1 (advisory, never a theorem, never green)",
        "khipu": "Conjecture 2",
        "factory": "bind, not a second flagship",
        "never": "a11oy.com",
        "cite_the_leader": True,
        "rehost_cited_code": False,
        "fabricated_live": False,
    }
    payload: Dict[str, Any] = {
        "ok": True,
        "service": "lyte-lattice",
        "organ": _ORGAN_NAME,
        "state": "BIND",
        "state_note": (
            "BIND hologram cited from GitHub. Not a flagship. Not a production "
            "certificate of a-11-oy.com. Hub RUNNING is UNAVAILABLE until Immune "
            "readback. Organs are LIVE holograms in the cited console, not this tab. "
            "W1–W3 sealed on Alloy State Fabric against origin packets."
        ),
        "bind": _BIND,
        "order": _ORDER,
        "source": {
            "url": _SOURCE,
            "sha": _SOURCE_SHA,
            "evidence_class": "REPORTED",
            "canonical": True,
            "packets": [
                "packets/alloy-state-fabric-w1.json",
                "packets/alloy-state-fabric-w2.json",
                "packets/alloy-state-fabric-w3.json",
            ],
        },
        "hub": {
            "url": _HUB_SPACE,
            "running": False,
            "state": "UNAVAILABLE",
            "evidence_class": "UNAVAILABLE",
            "note": "Hugging Face is the artifact registry, not the front door. RUNNING only after Immune readback.",
        },
        "factory": {"url": _FACTORY, "role": "Decision Cell Compiler", "bind": True, "flagship": False},
        "lyte_window": {"url": _LYTE_WINDOW, "honesty": "STRUCTURAL-ONLY", "admitted": True},
        "product": {"url": _PRODUCT, "path": "/lyte", "certified": False},
        "proof": {"url": _PROOF},
        "waves": _WAVES,
        "frontiers": _FRONTIERS,
        "locked_proven": {
            "set": _LOCKED_PROVEN,
            "count": len(_LOCKED_PROVEN),
            "kernel_commit": _KERNEL_COMMIT,
            "note": "EXACTLY 8 locked-proven. This bind adds nothing.",
        },
        "honesty": honesty,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    receipt_body = {
        "receipt_type": _RECEIPT_TYPE,
        "organ": _ORGAN_NAME,
        "state": "BIND",
        "sha": _SOURCE_SHA,
        "certified": False,
        "proven_trust": False,
        "hub_running": False,
        "energy_joule": "UNAVAILABLE",
        "occupancy": "UNAVAILABLE",
    }
    payload["khipu_receipt"] = _khipu_receipt(receipt_body) or _unsigned_receipt(receipt_body)
    return payload


def register(app, ns: str = "a11oy") -> Dict[str, Any]:
    from fastapi.responses import JSONResponse

    prefixes = [f"/api/{ns}/v1/lyte", "/v1/lyte"]
    routes: List[str] = []
    try:
        from starlette.routing import Route

        def _health(_r=None):
            return JSONResponse(healthz())

        def _status(_r=None):
            return JSONResponse(status())

        for p in prefixes:
            app.router.routes.insert(0, Route(f"{p}/healthz", _health, methods=["GET"]))
            app.router.routes.insert(0, Route(f"{p}/status", _status, methods=["GET"]))
            routes.extend([f"{p}/healthz", f"{p}/status"])
    except Exception:
        async def _h_health():
            return JSONResponse(healthz())

        async def _h_status():
            return JSONResponse(status())

        for p in prefixes:
            app.add_api_route(f"{p}/healthz", _h_health, methods=["GET"], include_in_schema=True)
            app.add_api_route(f"{p}/status", _h_status, methods=["GET"], include_in_schema=True)
            routes.extend([f"{p}/healthz", f"{p}/status"])

    print(
        f"[{ns}] szl_lyte_lattice routes registered "
        f"(BIND hologram, {len(routes)} routes, not a flagship, not certified)",
        flush=True,
    )
    return {"ok": True, "ns": ns, "organ": _ORGAN_NAME, "bind": _BIND, "certified": False, "routes": routes}


def _selftest() -> Dict[str, Any]:
    h = healthz()
    s = status()
    assert h["ok"] is True and h["certified"] is False and h["hub_running"] is False
    assert s["state"] == "BIND"
    assert s["honesty"]["certified"] is False
    assert s["honesty"]["proven_trust"] is False
    assert s["honesty"]["lyte"] == "STRUCTURAL-ONLY"
    assert "UNAVAILABLE" in s["honesty"]["energy_joule"]
    assert s["honesty"]["occupancy"].startswith("UNAVAILABLE")
    assert s["hub"]["running"] is False
    assert s["hub"]["state"] == "UNAVAILABLE"
    assert s["source"]["sha"] == _SOURCE_SHA
    assert len(s["frontiers"]) == 28
    assert s["frontiers"][0]["honesty"] == "STRUCTURAL-ONLY"
    assert s["frontiers"][-1]["n"] == "N27"
    assert len(s["waves"]) == 3
    served = json.dumps(s).lower()
    assert "a11oy.com" in s["honesty"]["never"]
    assert s["product"]["certified"] is False
    assert s["khipu_receipt"]["proven_trust"] is False
    assert s["khipu_receipt"].get("signed") is False or s["khipu_receipt"]["kind"] in (
        "UNSIGNED-honest",
        "HASH-LINKED",
    )
    assert s["state"] != "LIVE"
    assert s["state"] != "RUNNING"
    _ = served
    return {"ok": True, "state": s["state"], "sha": s["source"]["sha"], "frontiers": len(s["frontiers"])}


if __name__ == "__main__":
    print(json.dumps(_selftest(), indent=2))
