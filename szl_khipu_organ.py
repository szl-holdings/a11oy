# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 — SZL KHIPU product organ on a-11-oy.com.
"""
szl_khipu_organ.py — KHIPU product organ (stdlib).

Canonical kernel source is github.com/szl-holdings/szl-khipu. This module
does not rehost Qwen, Mixtral, SGLang, FlashAttention, SageAttention,
FlexAttention, or vLLM. Duals: Ari = GreenLight, Kay Pacha = Anatomy.

Honesty (Doctrine v11 LOCKED):
  - CUDA UNAVAILABLE. Energy UNAVAILABLE. proven_trust stays false.
  - Λ = Conjecture 1 OPEN. Never a theorem. Never green.
  - 1.5B / QLoRA RESEARCH, not trained here.
  - FIFO kernel Hub cards (GreenLight / Anatomy / Chaski) stay 401.
  - GET /khipu HTML is exact. /khipu/{hash} stays the receipt API.
  - Receipts are UNSIGNED-honest unless szl_khipu (DAG) signs.

Endpoints (under /api/{ns}/v1/khipu-organ/* only — never /api/{ns}/v1/khipu/*,
which is the receipt DAG: organs, chain, verify, intoto, CPU-lab pin, chat):
  GET  /healthz /status
  POST /lambda /greenlight /anatomy /prefix /route

Stdlib + optional szl_khipu DAG. Additive; try/except-guarded by the caller.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from typing import Any, Dict, List, Optional

_ORGAN_NAME = "KHIPU"
_KHIPU_ORGAN = "khipu"
_RECEIPT_TYPE = "SZL.KhipuOrgan.Status.v1"
_SOURCE = "https://github.com/szl-holdings/szl-khipu"
_HUB_SPACE = "https://huggingface.co/spaces/SZLHOLDINGS/szl-khipu"
_PRODUCT = "https://a-11-oy.com/khipu"
_PROOF = "https://a11oy.net/khipu/"
_LOCKED_PROVEN = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
_KERNEL_COMMIT = "c7c0ba17"
_YUYAY = [
    "moralGrounding",
    "measurabilityHonesty",
    "empiricalGrounding",
    "logicalConsistency",
    "sourceTransparency",
    "reproducibility",
    "licenseHygiene",
    "scopeDiscipline",
    "claimCalibration",
    "evalAwareness",
    "deceptionKeywords",
    "conflictingDirectives",
    "reversalDirective",
]
_FLOORS = [0.95, 0.95, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9]
_ORGANS = [
    {"id": "heart", "name": "HEART", "quechua": "YUYAY", "role": "13-axis conjunctive critique — advisory Λ"},
    {"id": "circulatory", "name": "CIRCULATORY", "quechua": "YAWAR", "role": "append-only receipt bus"},
    {"id": "brain", "name": "BRAIN", "quechua": "YACHAY", "role": "read-only reasoning cortex"},
    {"id": "nervous", "name": "NERVOUS", "quechua": "OTel", "role": "telemetry spine — energy UNAVAILABLE"},
    {"id": "skeleton", "name": "SKELETON", "quechua": "Khipu", "role": "locked-8 formula spine"},
]
_CUTS = [
    {"cut": "PrefixWitness", "job": "radix-prefix KV digest", "not": "not SGLang"},
    {"cut": "RouteWitness", "job": "expert-assignment digest", "not": "not Mixtral"},
    {"cut": "TileReceipt", "job": "schedule receipt", "not": "not Dao .cu"},
    {"cut": "ScoreMod", "job": "score modification", "not": "not FlexAttention"},
    {"cut": "BlockWitness", "job": "block KV witness", "not": "not vLLM"},
    {"cut": "YARQA", "job": "canal attention", "not": "not SageAttention · not CUDA"},
]
_PREFIX_STEMS = ("NAV", "NAV ABSTAIN", "YUYAY", "YUYAY WILLAY ARI")


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
        r = dag.emit("khipu-organ.status", payload)
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


def _honesty() -> Dict[str, Any]:
    return {
        "proven_trust": False,
        "energy": "UNAVAILABLE",
        "cuda": "UNAVAILABLE",
        "conjecture_1": "OPEN",
        "lambda": "advisory, never a theorem, never green",
        "research_1_5b": "RESEARCH, not trained here",
        "fifo_hub_cards": "GreenLight / Anatomy / Chaski stay 401 — not minted here",
        "never": "a11oy.com",
        "rehost_cited_code": False,
        "fabricated_joule": False,
    }


def healthz() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "khipu-organ",
        "organ": _ORGAN_NAME,
        "certified": False,
        "proven_trust": False,
        "cuda": "UNAVAILABLE",
        "energy": "UNAVAILABLE",
        "conjecture_1": "OPEN",
        "source": _SOURCE,
        "product": _PRODUCT,
        "proof": _PROOF,
    }


def status() -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "ok": True,
        "service": "khipu-organ",
        "organ": _ORGAN_NAME,
        "state": "ORGAN",
        "state_note": (
            "Product organ for SZL KHIPU. Duals Ari=GreenLight, Kay Pacha=Anatomy. "
            "Original cuts only. CUDA UNAVAILABLE. Energy UNAVAILABLE. "
            "Conjecture 1 OPEN. proven_trust false."
        ),
        "source": {"url": _SOURCE, "canonical": True, "evidence_class": "REPORTED"},
        "hub": {
            "url": _HUB_SPACE,
            "running": False,
            "state": "LOCATION_ONLY",
            "note": "Hugging Face is the artifact registry, not the front door.",
        },
        "product": {"url": _PRODUCT, "path": "/khipu", "certified": False},
        "proof": {"url": _PROOF},
        "origins": {
            "product": "https://a-11-oy.com",
            "proof": "https://a11oy.net",
            "note": "Two public origins only: a-11-oy.com and a11oy.net. Never a11oy.com.",
        },
        "duals": {"Ari": "GreenLight", "Kay Pacha": "Anatomy"},
        "cuts": _CUTS,
        "nanos": [
            "TinyKhipu-Nano",
            "ReceiptAgent-Nano",
            "Moons-Nano",
            "MiniEmbed-Nano",
        ],
        "training_receipt_seed": 20260721,
        "locked_proven": {
            "set": _LOCKED_PROVEN,
            "count": len(_LOCKED_PROVEN),
            "kernel_commit": _KERNEL_COMMIT,
            "note": "EXACTLY 8 locked-proven. This organ adds nothing.",
        },
        "honesty": _honesty(),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    receipt_body = {
        "receipt_type": _RECEIPT_TYPE,
        "organ": _ORGAN_NAME,
        "certified": False,
        "proven_trust": False,
        "energy": "UNAVAILABLE",
        "cuda": "UNAVAILABLE",
        "conjecture_1": "OPEN",
    }
    payload["khipu_receipt"] = _khipu_receipt(receipt_body) or _unsigned_receipt(receipt_body)
    return payload


def lambda_gate(axes: Optional[List[float]] = None) -> Dict[str, Any]:
    xs = list(axes) if axes is not None else list(_FLOORS)
    if len(xs) != 13:
        return {
            "ok": False,
            "blocked": True,
            "value": 0.0,
            "reason": "expected 13 Yuyay axes",
            **_honesty(),
        }
    if any((not math.isfinite(v)) or v <= 0 for v in xs):
        return {
            "ok": True,
            "blocked": True,
            "value": 0.0,
            "axes": dict(zip(_YUYAY, xs)),
            "reason": "zero-routed",
            "advisory": True,
            **_honesty(),
        }
    w = 1.0 / 13.0
    log = sum(w * math.log(v) for v in xs)
    value = math.exp(log)
    if not math.isfinite(value):
        value = 0.0
    return {
        "ok": True,
        "blocked": value == 0,
        "value": value,
        "axes": dict(zip(_YUYAY, xs)),
        "reason": (
            "zero-routed"
            if value == 0
            else "advisory pass — uniqueness remains Conjecture 1 OPEN"
        ),
        "advisory": True,
        **_honesty(),
    }


def greenlight(
    paint_sorry: int = 0,
    claim_proven: int = 0,
    stamp_joule: int = 0,
) -> Dict[str, Any]:
    checks = [
        {
            "id": "sorry",
            "ok": paint_sorry != 1,
            "detail": (
                "BLOCKED · a sorry cannot be painted green"
                if paint_sorry == 1
                else "sorry stays sorry · locked-8 is 8, not 21"
            ),
        },
        {
            "id": "conjecture1",
            "ok": claim_proven != 1,
            "detail": (
                "BLOCKED · proven_trust cannot be true while Λ is Conjecture 1"
                if claim_proven == 1
                else "proven_trust locked false · uniqueness OPEN"
            ),
        },
        {
            "id": "energy",
            "ok": stamp_joule != 1,
            "detail": (
                "BLOCKED · fabricated joule · energy UNAVAILABLE"
                if stamp_joule == 1
                else "energy UNAVAILABLE · never a fabricated joule"
            ),
        },
    ]
    blocked = any(not c["ok"] for c in checks)
    return {
        "dual": "Ari",
        "painted": sum(1 for c in checks if not c["ok"]),
        "blocked": 1 if blocked else 0,
        "greenlit": 0 if blocked else 1,
        "provenTrust": False,
        "checks": checks,
        "reason": (
            next(c["detail"] for c in checks if not c["ok"])
            if blocked
            else "GREEN-LIGHT · LIVE bound · proven_trust false · energy UNAVAILABLE"
        ),
        **_honesty(),
    }


def anatomy(zero_heart: bool = False, fabricate_joule: bool = False) -> Dict[str, Any]:
    organs = []
    for spec in _ORGANS:
        down = False
        detail = spec["role"]
        if spec["id"] == "heart" and zero_heart:
            down = True
            detail = "DOWN · HEART/YUYAY zeroed"
        if fabricate_joule:
            down = True
            detail = "DOWN · fabricated joule · energy UNAVAILABLE"
        organs.append({**spec, "status": "DOWN" if down else "LIVE", "detail": detail})
    blocked = any(o["status"] == "DOWN" for o in organs)
    return {
        "dual": "Kay Pacha",
        "blocked": blocked,
        "liveCount": sum(1 for o in organs if o["status"] == "LIVE"),
        "organs": organs,
        "reason": (
            "body BLOCKED"
            if blocked
            else "body LIVE · proven_trust false · energy UNAVAILABLE"
        ),
        **_honesty(),
    }


def _djb2(s: str) -> str:
    h = 5381
    for ch in s:
        h = ((h << 5) + h + ord(ch)) & 0xFFFFFFFF
    return f"{h:08x}"


def prefix_witness(hijack: int = 0) -> Dict[str, Any]:
    nodes = []
    for stem in _PREFIX_STEMS:
        kv = f"kv:7:{stem}"
        nodes.append({"prefix": stem, "kv": kv, "digest": _djb2(kv)})
    claimed = "|".join(n["digest"] for n in nodes)
    if hijack == 1:
        nodes[0] = {**nodes[0], "kv": nodes[0]["kv"] + "#POISON"}
    now = "|".join(_djb2(n["kv"]) for n in nodes)
    hold = 1 if now == claimed and hijack != 1 else 0
    return {
        "hold": hold,
        "broken": 0 if hold else 1,
        "hijack": 1 if hijack == 1 else 0,
        "reason": (
            "PrefixWitness HOLDS · radix digest matches · not SGLang · no tokens/s claim"
            if hold
            else "PrefixWitness BROKEN · cached KV mutated after digest · fail closed"
        ),
        **_honesty(),
    }


def _mulberry32(seed: int):
    a = seed & 0xFFFFFFFF

    def rng() -> float:
        nonlocal a
        a = (a + 0x6D2B79F5) & 0xFFFFFFFF
        t = a
        t = (t ^ (t >> 15)) & 0xFFFFFFFF
        t = (t * ((t | 1) & 0xFFFFFFFF)) & 0xFFFFFFFF
        t = (t ^ ((t + ((t * ((t ^ (t >> 7)) & 0xFFFFFFFF)) & 0xFFFFFFFF)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        t = (t ^ (t >> 14)) & 0xFFFFFFFF
        return t / 4294967296.0

    return rng


def route_witness(tamper: int = 0) -> Dict[str, Any]:
    rng = _mulberry32(7)
    n, e = 8, 4
    assignment = []
    for _ in range(n):
        row = [rng() for _ in range(e)]
        assignment.append(max(range(e), key=lambda i: row[i]))
    digest = _djb2(",".join(str(x) for x in assignment))
    routed = list(assignment)
    if tamper == 1:
        routed[0] = (routed[0] + 1) % e
    now = _djb2(",".join(str(x) for x in routed))
    hold = 1 if now == digest and tamper != 1 else 0
    return {
        "hold": hold,
        "broken": 0 if hold else 1,
        "assignment": routed,
        "reason": (
            "RouteWitness HOLDS · assignment digest matches · not Mixtral · no tokens/s claim"
            if hold
            else "RouteWitness BROKEN · expert swapped after routing · fail closed"
        ),
        **_honesty(),
    }


def register(app, ns: str = "a11oy") -> Dict[str, Any]:
    from fastapi.responses import JSONResponse

    prefixes = [f"/api/{ns}/v1/khipu-organ"]
    routes: List[str] = []

    async def _body(request):
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        return payload

    async def _lambda(request):
        payload = await _body(request)
        axes = payload.get("axes")
        return JSONResponse(lambda_gate(axes if isinstance(axes, list) else None))

    async def _green(request):
        payload = await _body(request)
        return JSONResponse(
            greenlight(
                paint_sorry=int(bool(payload.get("paint_sorry"))),
                claim_proven=int(bool(payload.get("claim_proven"))),
                stamp_joule=int(bool(payload.get("stamp_joule"))),
            )
        )

    async def _anatomy(request):
        payload = await _body(request)
        return JSONResponse(
            anatomy(
                zero_heart=bool(payload.get("zero_heart")),
                fabricate_joule=bool(payload.get("fabricate_joule")),
            )
        )

    async def _prefix(request):
        payload = await _body(request)
        return JSONResponse(prefix_witness(hijack=int(bool(payload.get("hijack")))))

    async def _route(request):
        payload = await _body(request)
        return JSONResponse(route_witness(tamper=int(bool(payload.get("tamper")))))

    async def _h_health():
        return JSONResponse(healthz())

    async def _h_status():
        return JSONResponse(status())

    for p in prefixes:
        # add_api_route only. Do not steal the receipt DAG at /api/{ns}/v1/khipu/*.
        app.add_api_route(f"{p}/healthz", _h_health, methods=["GET"], include_in_schema=True)
        app.add_api_route(f"{p}/status", _h_status, methods=["GET"], include_in_schema=True)
        app.add_api_route(f"{p}/lambda", _lambda, methods=["POST"], include_in_schema=True)
        app.add_api_route(f"{p}/greenlight", _green, methods=["POST"], include_in_schema=True)
        app.add_api_route(f"{p}/anatomy", _anatomy, methods=["POST"], include_in_schema=True)
        app.add_api_route(f"{p}/prefix", _prefix, methods=["POST"], include_in_schema=True)
        app.add_api_route(f"{p}/route", _route, methods=["POST"], include_in_schema=True)
        routes.extend(
            [
                f"{p}/healthz",
                f"{p}/status",
                f"{p}/lambda",
                f"{p}/greenlight",
                f"{p}/anatomy",
                f"{p}/prefix",
                f"{p}/route",
            ]
        )

    print(
        f"[{ns}] szl_khipu_organ routes registered "
        f"(product organ, {len(routes)} routes, GET /khipu HTML is exact, CUDA UNAVAILABLE)",
        flush=True,
    )
    return {"ok": True, "ns": ns, "organ": _ORGAN_NAME, "certified": False, "routes": routes}


def _selftest() -> Dict[str, Any]:
    h = healthz()
    s = status()
    g = lambda_gate()
    z = lambda_gate([0.0] + _FLOORS[1:])
    gl = greenlight()
    sorry = greenlight(paint_sorry=1)
    an = anatomy()
    dead = anatomy(zero_heart=True)
    px = prefix_witness()
    hij = prefix_witness(hijack=1)
    rt = route_witness()
    sw = route_witness(tamper=1)
    assert h["ok"] is True and h["certified"] is False and h["proven_trust"] is False
    assert s["honesty"]["proven_trust"] is False
    assert s["honesty"]["energy"] == "UNAVAILABLE"
    assert s["duals"]["Ari"] == "GreenLight"
    assert g["blocked"] is False and g["advisory"] is True
    assert z["blocked"] is True and z["value"] == 0.0
    assert gl["greenlit"] == 1 and sorry["blocked"] == 1
    assert an["blocked"] is False and dead["blocked"] is True
    assert px["hold"] == 1 and hij["broken"] == 1
    assert rt["hold"] == 1 and sw["broken"] == 1
    blob = json.dumps(s).lower()
    assert "qwen" not in blob or "not qwen" in blob or "never" in blob
    return {"ok": True, "organ": _ORGAN_NAME}


if __name__ == "__main__":
    print(json.dumps(_selftest(), indent=2))
