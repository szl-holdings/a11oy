# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 — five-space operator BIND hologram on a-11-oy.com.
"""
szl_five_space.py — BIND_AS_A11OY_PACKAGE status surface.

Five named spaces: Command · Loop · Queue · Memory · Ledger.
This module is the in-tree bind, not a second flagship and not a dump of a
Vite hologram onto serve.py. The tab at /five-space is a 0-CDN hologram.
Receipts sealed here are UNSIGNED-honest and browser-local SAMPLE.
They are not the lasting RECORD. RECORD lives on a11oy.net/five-space/.

Honesty (Doctrine v11 LOCKED):
  - Operator is STRUCTURAL-ONLY (named spaces, local compile).
  - Receipts are UNSIGNED-honest. proven_trust stays false.
  - Energy joule stays UNAVAILABLE. No RAPL/NVML is read here.
  - Λ = Conjecture 1. Locked-8 untouched.
  - sovereign=false on this surface.
  - a-11-oy.com is not certified by this bind.
  - This tab does not replace /console.
  - This module never fabricates LIVE, RUNNING, or PASS.

Endpoints (dual-registered under /api/{ns}/v1/five-space/* and /v1/five-space/*):
  GET /healthz  — process liveness + bind identity.
  GET /status   — deterministic honest roll-up. No network. No fabricated LIVE.

Stdlib + optional szl_khipu. Additive; try/except-guarded by the caller.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_ORGAN_NAME = "Five-space operator"
_KHIPU_ORGAN = "five-space-operator"
_RECEIPT_TYPE = "SZL.FiveSpace.Status.v1"
_BIND = "BIND_AS_A11OY_PACKAGE"
_ORDER = "AO-2026-08-29-002"
_SOURCE = "https://github.com/szl-holdings/a11oy"
_SOURCE_PATH = "szl_five_space.py"
_PRODUCT = "https://a-11-oy.com"
_PROOF = "https://a11oy.net"
_PROOF_RECORD = "https://a11oy.net/five-space/"
_LOCKED_PROVEN = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
_KERNEL_COMMIT = "c7c0ba17"


def _module_sha() -> str:
    """MEASURED hash of this bind module. Not a product certificate."""
    try:
        blob = Path(__file__).read_bytes()
    except Exception:
        blob = b"szl_five_space.py"
    return hashlib.sha3_256(blob).hexdigest()


# Named spaces. Honesty is parsed from this table and never upgraded.
_SPACES: List[Dict[str, str]] = [
    {
        "id": "command",
        "title": "Command",
        "duty": "Estate, origin lock, advisory Λ. Never executes.",
        "honesty": "STRUCTURAL-ONLY",
    },
    {
        "id": "loop",
        "title": "Loop",
        "duty": "Compile frontier ideas from selected projects. SAMPLE in this tab.",
        "honesty": "SAMPLE",
    },
    {
        "id": "queue",
        "title": "Queue",
        "duty": "Admit is a named human act. Deny by default.",
        "honesty": "STRUCTURAL-ONLY",
    },
    {
        "id": "memory",
        "title": "Memory",
        "duty": "WORKING / EPISODIC writable. DOCTRINE deny-by-default. STALE is a state.",
        "honesty": "STRUCTURAL-ONLY",
    },
    {
        "id": "ledger",
        "title": "Ledger",
        "duty": "Hash-chain every state change. UNSIGNED-honest. Not the a11oy.net RECORD.",
        "honesty": "UNSIGNED-honest",
    },
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
        r = dag.emit("five-space.status", payload)
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
        "service": "five-space-operator",
        "organ": _ORGAN_NAME,
        "bind": _BIND,
        "certified": False,
        "proven_trust": False,
        "sovereign": False,
        "hub_running": False,
        "source": _SOURCE,
        "path": _SOURCE_PATH,
        "sha": _module_sha(),
    }


def status() -> Dict[str, Any]:
    honesty = {
        "bind": _BIND,
        "order": _ORDER,
        "certified": False,
        "product_certificate": False,
        "second_flagship": False,
        "replaces_console": False,
        "operator": "STRUCTURAL-ONLY",
        "loop": "SAMPLE (browser-local compile). Not a production receipt.",
        "energy_joule": "UNAVAILABLE. This bind does not read RAPL or NVML.",
        "receipts": "UNSIGNED-honest",
        "record": "Lasting RECORD is a11oy.net/five-space/. This tab is not the record.",
        "proven_trust": False,
        "sovereign": False,
        "lambda": "Conjecture 1 (advisory, never a theorem, never green)",
        "khipu": "Conjecture 2",
        "never": "a11oy.com",
        "cite_the_leader": True,
        "rehost_cited_code": False,
        "fabricated_live": False,
        "vite_dump": False,
    }
    payload: Dict[str, Any] = {
        "ok": True,
        "service": "five-space-operator",
        "organ": _ORGAN_NAME,
        "state": "BIND",
        "state_note": (
            "BIND hologram of the five-space operator. Not a flagship. "
            "Not a production certificate of a-11-oy.com. Does not replace /console. "
            "Loop compiles SAMPLE ideas in this tab. Lasting RECORD is a11oy.net."
        ),
        "bind": _BIND,
        "order": _ORDER,
        "source": {
            "url": _SOURCE,
            "path": _SOURCE_PATH,
            "sha": _module_sha(),
            "evidence_class": "STRUCTURAL-ONLY",
            "canonical": True,
        },
        "product": {
            "url": _PRODUCT,
            "path": "/five-space",
            "certified": False,
            "replaces_console": False,
        },
        "proof": {"url": _PROOF, "record": _PROOF_RECORD},
        "spaces": _SPACES,
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
        "sha": payload["source"]["sha"],
        "certified": False,
        "proven_trust": False,
        "sovereign": False,
        "energy_joule": "UNAVAILABLE",
    }
    payload["khipu_receipt"] = _khipu_receipt(receipt_body) or _unsigned_receipt(receipt_body)
    return payload


def register(app, ns: str = "a11oy") -> Dict[str, Any]:
    from fastapi.responses import JSONResponse

    prefixes = [f"/api/{ns}/v1/five-space", "/v1/five-space"]
    routes: List[str] = []
    try:
        from starlette.routing import Route

        def _health(_r=None):  # noqa: ANN001
            return JSONResponse(healthz())

        def _status(_r=None):  # noqa: ANN001
            return JSONResponse(status())

        for p in prefixes:
            app.router.routes.insert(0, Route(f"{p}/healthz", _health, methods=["GET"]))
            app.router.routes.insert(0, Route(f"{p}/status", _status, methods=["GET"]))
            routes.extend([f"{p}/healthz", f"{p}/status"])
    except Exception:
        async def _h_health():  # noqa: ANN202
            return JSONResponse(healthz())

        async def _h_status():  # noqa: ANN202
            return JSONResponse(status())

        for p in prefixes:
            app.add_api_route(f"{p}/healthz", _h_health, methods=["GET"], include_in_schema=True)
            app.add_api_route(f"{p}/status", _h_status, methods=["GET"], include_in_schema=True)
            routes.extend([f"{p}/healthz", f"{p}/status"])

    print(
        f"[{ns}] szl_five_space routes registered "
        f"(BIND hologram, {len(routes)} routes, not a flagship, not certified, not /console)",
        flush=True,
    )
    return {
        "ok": True,
        "ns": ns,
        "organ": _ORGAN_NAME,
        "bind": _BIND,
        "certified": False,
        "sovereign": False,
        "routes": routes,
    }


def _selftest() -> Dict[str, Any]:
    h = healthz()
    s = status()
    assert h["ok"] is True and h["certified"] is False and h["hub_running"] is False
    assert h["sovereign"] is False
    assert s["state"] == "BIND"
    assert s["honesty"]["certified"] is False
    assert s["honesty"]["proven_trust"] is False
    assert s["honesty"]["sovereign"] is False
    assert s["honesty"]["operator"] == "STRUCTURAL-ONLY"
    assert s["honesty"]["replaces_console"] is False
    assert s["honesty"]["vite_dump"] is False
    assert "UNAVAILABLE" in s["honesty"]["energy_joule"]
    assert s["product"]["certified"] is False
    assert s["product"]["path"] == "/five-space"
    assert s["product"]["replaces_console"] is False
    assert s["proof"]["record"] == _PROOF_RECORD
    assert [sp["id"] for sp in s["spaces"]] == ["command", "loop", "queue", "memory", "ledger"]
    assert s["spaces"][0]["honesty"] == "STRUCTURAL-ONLY"
    assert s["spaces"][1]["honesty"] == "SAMPLE"
    assert s["spaces"][4]["honesty"] == "UNSIGNED-honest"
    assert "a11oy.com" in s["honesty"]["never"]
    assert s["khipu_receipt"]["proven_trust"] is False
    assert s["khipu_receipt"].get("signed") is False or s["khipu_receipt"]["kind"] in (
        "UNSIGNED-honest",
        "HASH-LINKED",
    )
    assert s["state"] != "LIVE"
    assert s["state"] != "RUNNING"
    assert s["locked_proven"]["count"] == 8
    return {
        "ok": True,
        "state": s["state"],
        "sha": s["source"]["sha"],
        "spaces": len(s["spaces"]),
    }


if __name__ == "__main__":
    print(json.dumps(_selftest(), indent=2))
