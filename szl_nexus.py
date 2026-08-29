# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 — NEXUS analog workstation BIND hologram on a-11-oy.com.
"""
szl_nexus.py — BIND_AS_A11OY_PACKAGE status surface.

This module cites [szl-holdings/nexus](https://github.com/szl-holdings/nexus)
@ bf7765c. It does not rehost Loihi, BrainScaleS, or THAT silicon. It does not
open a fourth flagship. It does not add nexus.a-11-oy.com (no second HF custom
domain). Energy joule stays UNAVAILABLE. Hub Space SZLHOLDINGS/nexus is private
and is not a public product origin.

Honesty (Doctrine v11 LOCKED):
  - NEXUS is SOFTWARE. Analog physics runs in the cited GitHub console.
  - Six modules only: Grid, Scope, Tape, Patch, Seq, Voice. HOLO is a CRT mode.
  - Five organs: YACHAY, YUYAY, YAWAR, OTel, KHIPU. WILLAY is a second-brain
    gate, not a sixth organ and not a seventh module.
  - Energy joule stays UNAVAILABLE unless RAPL energy_uj is actually read.
  - Hub RUNNING stays UNAVAILABLE (Space is private; no fabricated LIVE).
  - Receipts are UNSIGNED-honest. proven_trust stays false.
  - a-11-oy.com is not certified by this bind.
  - Λ = Conjecture 1. Locked-8 untouched.
  - Product host is a-11-oy.com/nexus. Proof host is a11oy.net (location only).
  - Never a11oy.com.

Endpoints (dual-registered under /api/{ns}/v1/nexus/* and /v1/nexus/*):
  GET /healthz  — process liveness + bind identity.
  GET /status   — deterministic honest roll-up. No network. No fabricated LIVE.

Stdlib + optional szl_khipu. Additive; try/except-guarded by the caller.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List, Optional

_ORGAN_NAME = "NEXUS analog workstation"
_KHIPU_ORGAN = "nexus"
_RECEIPT_TYPE = "SZL.Nexus.Status.v1"
_BIND = "BIND_AS_A11OY_PACKAGE"
_ORDER = "AO-2026-08-29-002"
_SOURCE = "https://github.com/szl-holdings/nexus"
_SOURCE_SHA = "bf7765ce1ff47102e3c9eefcd3b9c77368a009e4"
_FACTORY = "https://github.com/szl-holdings/a11oy-factory"
_HUB_SPACE = "https://huggingface.co/spaces/SZLHOLDINGS/nexus"
_PRODUCT = "https://a-11-oy.com"
_PROOF = "https://a11oy.net"
_LOCKED_PROVEN = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
_KERNEL_COMMIT = "c7c0ba17"

# Cite the job. Do not clone the chip. Do not add a seventh module.
_FRONTIERS: List[Dict[str, str]] = [
    {"n": "analog", "title": "Analog computer", "cited": "SOFTWARE workstation in cited GitHub", "honesty": "SOFTWARE · not a physical chip"},
    {"n": "M1", "title": "Grid", "cited": "coefficient field / analog bank", "honesty": "SOFTWARE"},
    {"n": "M2", "title": "Scope", "cited": "phosphor CRT + HOLO mode", "honesty": "SOFTWARE · HOLO is a CRT mode"},
    {"n": "M3", "title": "Tape", "cited": "loop / capture deck", "honesty": "SOFTWARE"},
    {"n": "M4", "title": "Patch", "cited": "analog jack / hybrid IC", "honesty": "SOFTWARE"},
    {"n": "M5", "title": "Seq", "cited": "sequencer samples correlator (ADC)", "honesty": "SOFTWARE"},
    {"n": "M6", "title": "Voice", "cited": "Web Audio voice, not a seventh module", "honesty": "SOFTWARE"},
    {"n": "HOLO", "title": "CRT hologram", "cited": "WILLAY reconstruct on Scope", "honesty": "mode, not a module"},
    {"n": "O1", "title": "YACHAY", "cited": "AdEx cognition organ", "honesty": "SOFTWARE · organ 1/5"},
    {"n": "O2", "title": "YUYAY", "cited": "pacemaker If current", "honesty": "SOFTWARE · organ 2/5"},
    {"n": "O3", "title": "YAWAR", "cited": "traveling-wave organ", "honesty": "SOFTWARE · organ 3/5"},
    {"n": "O4", "title": "OTel", "cited": "optical write (3-factor STDP eligibility)", "honesty": "SOFTWARE · organ 4/5"},
    {"n": "O5", "title": "KHIPU", "cited": "bound / leak", "honesty": "SOFTWARE · organ 5/5"},
    {"n": "2BRN", "title": "WILLAY", "cited": "holographic second-brain gate on STP/STDP", "honesty": "gate, not a sixth organ"},
    {"n": "AdEx", "title": "AdEx Euler", "cited": "Brette & Gerstner 2005 (cite, do not clone silicon)", "honesty": "SOFTWARE"},
    {"n": "CORR", "title": "Correlator", "cited": "leaky product of X×Y (analog-correlator job)", "honesty": "SOFTWARE"},
    {"n": "SCH", "title": "Schmitt", "cited": "hysteresis clock for S&H", "honesty": "SOFTWARE"},
    {"n": "HYB", "title": "Hybrid IC", "cited": "sequencer samples correlator; REP accent loads analog IC", "honesty": "SOFTWARE"},
    {"n": "E", "title": "Energy", "cited": "RAPL / NVML joule channel", "honesty": "UNAVAILABLE unless RAPL reads"},
    {"n": "HUB", "title": "Hub Space", "cited": "SZLHOLDINGS/nexus", "honesty": "UNAVAILABLE · Hub Space private"},
]


def _unsigned_receipt(payload: Dict[str, Any]) -> Dict[str, Any]:
    """UNSIGNED-honest hash. Not Cosign. proven_trust stays false."""
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
        r = dag.emit("nexus.status", payload)
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
        "service": "nexus",
        "organ": _ORGAN_NAME,
        "bind": _BIND,
        "certified": False,
        "proven_trust": False,
        "hub_running": False,
        "hub_public": False,
        "source": _SOURCE,
        "sha": _SOURCE_SHA,
        "modules": ["grid", "scope", "tape", "patch", "seq", "voice"],
        "organs": ["YACHAY", "YUYAY", "YAWAR", "OTel", "KHIPU"],
        "willay": "second-brain gate, not a sixth organ",
        "energy_joule": "UNAVAILABLE",
    }


def status() -> Dict[str, Any]:
    honesty = {
        "bind": _BIND,
        "order": _ORDER,
        "certified": False,
        "product_certificate": False,
        "second_flagship": False,
        "fourth_flagship": False,
        "nexus": "SOFTWARE",
        "modules": "exactly six (Grid, Scope, Tape, Patch, Seq, Voice). HOLO is a CRT mode.",
        "organs": "exactly five (YACHAY, YUYAY, YAWAR, OTel, KHIPU). WILLAY is a gate.",
        "energy_joule": "UNAVAILABLE unless RAPL energy_uj is actually read. Watts are not joules.",
        "hub": "PRIVATE. RUNNING UNAVAILABLE. Not a public product origin.",
        "subdomain": "nexus.a-11-oy.com must not be added (no second HF custom domain).",
        "receipts": "UNSIGNED-honest",
        "proven_trust": False,
        "lambda": "Conjecture 1 (advisory, never a theorem, never green)",
        "khipu": "Conjecture 2",
        "factory": "bind, not a second flagship",
        "never": "a11oy.com",
        "cite_the_leader": True,
        "rehost_cited_chips": False,
        "fabricated_live": False,
        "physical_loihi": False,
        "physical_brainscales": False,
    }
    payload: Dict[str, Any] = {
        "ok": True,
        "service": "nexus",
        "organ": _ORGAN_NAME,
        "state": "BIND",
        "state_note": (
            "BIND hologram cited from GitHub. Not a flagship. Not a production "
            "certificate of a-11-oy.com. Hub Space is private; RUNNING is UNAVAILABLE. "
            "Six modules. Five organs. WILLAY is a second-brain gate. Energy UNAVAILABLE."
        ),
        "bind": _BIND,
        "order": _ORDER,
        "source": {
            "url": _SOURCE,
            "sha": _SOURCE_SHA,
            "evidence_class": "REPORTED",
            "canonical": True,
        },
        "hub": {
            "url": _HUB_SPACE,
            "running": False,
            "public": False,
            "state": "UNAVAILABLE",
            "evidence_class": "UNAVAILABLE",
            "note": "Hugging Face is the artifact registry, not the front door. Space is private. Do not 307 visitors onto a 401/404 origin.",
        },
        "factory": {"url": _FACTORY, "role": "Decision Cell Compiler", "bind": True, "flagship": False},
        "product": {"url": _PRODUCT, "path": "/nexus", "certified": False},
        "proof": {"url": _PROOF, "role": "location-only RECORD. Not a product host."},
        "modules": ["grid", "scope", "tape", "patch", "seq", "voice"],
        "organs": ["YACHAY", "YUYAY", "YAWAR", "OTel", "KHIPU"],
        "willay": {"role": "holographic second-brain gate", "organ": False, "module": False},
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
        "hub_public": False,
        "energy_joule": "UNAVAILABLE",
        "modules": 6,
        "organs": 5,
    }
    payload["khipu_receipt"] = _khipu_receipt(receipt_body) or _unsigned_receipt(receipt_body)
    return payload


def register(app, ns: str = "a11oy") -> Dict[str, Any]:
    from fastapi.responses import JSONResponse

    prefixes = [f"/api/{ns}/v1/nexus", "/v1/nexus"]
    routes: List[str] = []
    try:
        from starlette.routing import Route

        def _health(_r=None):  # noqa: ANN001
            return JSONResponse(healthz())

        def _status(_r=None):  # noqa: ANN001
            return JSONResponse(status())

        for p in prefixes:
            app.router.routes.insert(0, Route(f"{p}/healthz", _health, methods=["GET", "HEAD"]))
            app.router.routes.insert(0, Route(f"{p}/status", _status, methods=["GET", "HEAD"]))
            routes.extend([f"{p}/healthz", f"{p}/status"])
    except Exception:
        async def _h_health():  # noqa: ANN202
            return JSONResponse(healthz())

        async def _h_status():  # noqa: ANN202
            return JSONResponse(status())

        for p in prefixes:
            app.add_api_route(f"{p}/healthz", _h_health, methods=["GET", "HEAD"], include_in_schema=True)
            app.add_api_route(f"{p}/status", _h_status, methods=["GET", "HEAD"], include_in_schema=True)
            routes.extend([f"{p}/healthz", f"{p}/status"])

    print(
        f"[{ns}] szl_nexus routes registered "
        f"(BIND hologram, {len(routes)} routes, not a flagship, not certified, hub private)",
        flush=True,
    )
    return {"ok": True, "ns": ns, "organ": _ORGAN_NAME, "bind": _BIND, "certified": False, "routes": routes}


def _selftest() -> Dict[str, Any]:
    h = healthz()
    s = status()
    assert h["ok"] is True and h["certified"] is False and h["hub_running"] is False
    assert h["hub_public"] is False
    assert h["energy_joule"] == "UNAVAILABLE"
    assert h["modules"] == ["grid", "scope", "tape", "patch", "seq", "voice"]
    assert len(h["organs"]) == 5
    assert s["state"] == "BIND"
    assert s["honesty"]["certified"] is False
    assert s["honesty"]["proven_trust"] is False
    assert s["honesty"]["fourth_flagship"] is False
    assert s["honesty"]["nexus"] == "SOFTWARE"
    assert "UNAVAILABLE" in s["honesty"]["energy_joule"]
    assert s["hub"]["running"] is False
    assert s["hub"]["public"] is False
    assert s["hub"]["state"] == "UNAVAILABLE"
    assert s["source"]["sha"] == _SOURCE_SHA
    assert len(s["frontiers"]) == 20
    assert s["product"]["path"] == "/nexus"
    assert s["product"]["certified"] is False
    assert "a11oy.com" in s["honesty"]["never"]
    assert s["khipu_receipt"]["proven_trust"] is False
    assert s["state"] != "LIVE"
    assert s["state"] != "RUNNING"
    dumped = json.dumps(s)
    assert "nexus.a-11-oy.com" in dumped  # forbidden, disclosed as must-not-add
    assert "Loihi" not in dumped or s["honesty"]["physical_loihi"] is False
    return {"ok": True, "state": s["state"], "sha": s["source"]["sha"], "frontiers": len(s["frontiers"])}


if __name__ == "__main__":
    print(json.dumps(_selftest(), indent=2))
