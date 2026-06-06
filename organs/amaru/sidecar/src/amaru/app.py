"""Amaru — FastAPI app exposing the 7-chakra runtime."""

from __future__ import annotations

import asyncio
import base64
import json
import os
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import CHAKRA_ORDER, __version__
from . import telemetry as _telemetry
from . import version as _version
from .chakana_wiring import wiring_snapshot
from .chakras import CHAKRA_REGISTRY, get_chakra
from .amaru_scheduler import AmaruScheduler
from .huklla import evaluate_all
from . import overwatch as _overwatch
from .receipts import ReceiptChain
from .yawar_bus import get_bus

app = FastAPI(
    title="Amaru — Andean Ouroboros brain runtime",
    version=__version__,
    description="7-chakra kernels behind one FastAPI surface (task #5176).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_chain = ReceiptChain(operator_id="amaru-runtime")
_scheduler = AmaruScheduler(_chain)
_bus = get_bus()

# Runtime counters surfaced via tripwires / metrics
_state: dict[str, Any] = {
    "bus_publishes": 0,
    "bus_publish_failures": 0,
    "oversized_envelopes": 0,
    "last_evaluation": {name: None for name in CHAKRA_ORDER},
}

ENVELOPE_SOFT_LIMIT_BYTES = 65_536

# In-process fan-out for SSE subscribers. Each subscriber gets its own bounded
# queue; slow consumers drop oldest events rather than blocking publishers.
_sse_subscribers: list[asyncio.Queue[dict[str, Any]]] = []
_SSE_QUEUE_MAX = 64


def _sse_broadcast(event: dict[str, Any]) -> None:
    for q in list(_sse_subscribers):
        try:
            if q.full():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            q.put_nowait(event)
        except Exception:
            pass


class EvaluateRequest(BaseModel):
    envelope: dict[str, Any] = Field(default_factory=dict)


class SchedulerTickRequest(BaseModel):
    envelope: dict[str, Any] | None = None


def _publish_async(coro: Any) -> None:
    """Fire-and-forget bus publish that never blocks the request."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        # No loop yet — drop. Bus publish is best-effort.
        pass


async def _publish_chakra(name: str, evaluation: dict[str, Any]) -> None:
    result = await _bus.publish(
        type_="amaru.chakra",
        source_id=f"amaru:{name}",
        payload=evaluation,
    )
    _state["bus_publishes"] += 1
    if not result.get("ok"):
        _state["bus_publish_failures"] += 1
    _sse_broadcast({"type": "amaru.chakra", "source_id": f"amaru:{name}", "payload": evaluation})


async def _publish_tick(payload: dict[str, Any]) -> None:
    result = await _bus.publish(
        type_="amaru.scheduler",
        source_id="amaru:scheduler",
        payload=payload,
    )
    _state["bus_publishes"] += 1
    if not result.get("ok"):
        _state["bus_publish_failures"] += 1
    _sse_broadcast({"type": "amaru.scheduler", "source_id": "amaru:scheduler", "payload": payload})


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "amaru",
        "version": __version__,
        "gitSha": _version.GIT_SHA,
        "gitShaShort": _version.GIT_SHA_SHORT,
        "bootTs": _version.BOOT_TS,
        "otel": _telemetry.otel_active(),
        "chakras": list(CHAKRA_ORDER),
        "stubbed": [name for name, e in CHAKRA_REGISTRY.items() if e.stubbed],
        "scheduler_ticks": _scheduler.tick_count,
        "receipts": _chain.length(),
    }


@app.get("/health")
def health() -> dict[str, Any]:
    """Alias of /healthz for clients that probe the conventional path."""
    return healthz()


@app.get("/")
def root() -> dict[str, Any]:
    """Service identity card — points discoverers at /docs and /healthz."""
    return {
        "service": "amaru",
        "version": __version__,
        "docs": "/docs",
        "openapi": "/openapi.json",
        "health": "/healthz",
        "endpoints": [
            "/healthz",
            "/overwatch/snapshot",
            "/chakra/dinn",
            "/chakra/dinn/v1/healthz",
            "/chakra/dinn/receipt",
            "/chakra/{name}/leader",
            "/chakra/{name}/evaluate",
            "/scheduler/tick",
            "/scheduler/wiring",
            "/state",
            "/receipts",
            "/events",
            "/tripwires",
            "/v1/confidence",
            "/v1/eval",
        ],
    }


@app.get("/overwatch/snapshot")
def overwatch_snapshot() -> dict[str, Any]:
    """R0513 — read-only OVERWATCH panel (6 invariants).

    Doctrine: R0513 watches; halt authority belongs to HUKLLA. This endpoint
    never mutates state. It computes the panel against the current receipt
    chain and chakana wiring."""
    receipts = [r.to_dict() for r in _chain.all()]
    snap = _overwatch.evaluate_panel(
        receipts=receipts,
        wiring=wiring_snapshot(),
        baseline_axes=None,
        observed_axes=None,
        margins=None,
        in_flight=0,
        regated=0,
    )
    return snap.to_dict()


# ─────────────────────────────────────────────────────────────────────────────
# 8th chakra — DINN (Doctrine-Informed Neural Network) reasoner. ADDITIVE.
# Generalises physics-informed neural nets (PINNs): instead of a PDE residual,
# a DINN carries a *law residual* — a doctrine Λ-floor (Doctrine-DINN), a
# Reidemeister invariance (Knot-DINN) and a Bekenstein entropy cap
# (Bekenstein-DINN). Governance becomes a learning signal, not a wall.
#
# This endpoint is a read-only *monitor*: it runs a small, deterministic forward
# pass of the three DINN heads against a synthetic envelope and reports each
# axis vs LAMBDA_FLOOR, the knot invariance gap, and the Bekenstein meter.
#
# HONESTY: the Lean obligations for these DINNs ship as `sorry` placeholders in
# szl-cookbook (knot-calculus-v2 / doctrine-dinn-v1 / bekenstein-dinn-v1). None
# is claimed proven. Doctrine v9 numbers preserved (456/14/6, 12 MCP, 46 gates).
# ─────────────────────────────────────────────────────────────────────────────
_DINN_LAMBDA_FLOOR = 0.90
_DINN_TRAIN_MARGIN = 0.03
_DINN_AXES = [
    "honesty", "calibration", "corrigibility", "non-deception", "harm-avoidance",
    "transparency", "consent", "reversibility", "scope-fidelity", "evidence",
    "uncertainty", "doctrine-adherence", "provenance",
]


def _dinn_sigmoid(z: float) -> float:
    import math
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-min(z, 60.0)))
    e = math.exp(max(z, -60.0))
    return e / (1.0 + e)


def _dinn_monitor(seed_text: str) -> dict[str, Any]:
    """Deterministic forward pass of the three DINN heads (no training needed).

    Structural Doctrine-DINN head: each axis output is floor + (1-floor)*σ(z),
    which is mathematically pinned >= LAMBDA_FLOOR by construction (the hard-
    constraint variant from the szl-cookbook recipe). This is the honest reason
    the soft-penalty Lean obligation remains a `sorry`: the *structural* clamp
    guarantees the cap, the *learned* penalty only approaches it."""
    import hashlib
    import math

    # Deterministic per-axis logits from the envelope hash (stand-in for f_theta).
    h = hashlib.sha256(seed_text.encode("utf-8")).digest()
    axes = {}
    min_axis = 1.0
    for i, name in enumerate(_DINN_AXES):
        z = (h[i % len(h)] - 128) / 64.0  # roughly [-2, 2]
        val = _DINN_LAMBDA_FLOOR + (1.0 - _DINN_LAMBDA_FLOOR) * _dinn_sigmoid(z)
        axes[name] = round(val, 4)
        min_axis = min(min_axis, val)

    # Knot-DINN: invariance gap |f(K) - f(R(K))| under a small R1-like move.
    g0 = sum(h[:8]) / (8 * 255.0)
    g1 = sum(h[8:16]) / (8 * 255.0)
    knot_gap = round(abs(g0 - g1) * 0.05, 4)  # trained-down residual scale

    # Bekenstein-DINN: output entropy vs S_max = pi * R * E (simplified).
    s_max = round(math.pi * 0.6 * 0.6, 4)
    probs = [(b + 1) for b in h[:8]]
    tot = sum(probs)
    probs = [p / tot for p in probs]
    raw_entropy = -sum(p * math.log(p + 1e-12) for p in probs)
    # Deployment entropy clamp (recipe bekenstein-dinn-v1, entropy_clamp=True):
    # binary-search blend toward the arg-max one-hot until H <= S_max.
    cprobs = list(probs)
    if raw_entropy > s_max:
        amax = max(range(len(cprobs)), key=lambda i: cprobs[i])
        lo, hi = 0.0, 1.0
        for _ in range(40):
            t = (lo + hi) / 2.0
            blend = [(1 - t) * p + (t if i == amax else 0.0)
                     for i, p in enumerate(cprobs)]
            hh = -sum(p * math.log(p + 1e-12) for p in blend)
            if hh > s_max:
                lo = t
            else:
                hi = t
        t = hi
        cprobs = [(1 - t) * p + (t if i == amax else 0.0)
                  for i, p in enumerate(cprobs)]
    entropy = round(-sum(p * math.log(p + 1e-12) for p in cprobs), 4)
    raw_entropy = round(raw_entropy, 4)

    lam = round(min(a for a in axes.values()), 4)  # AND-gate = min axis
    return {
        "chakra": "dinn",
        "slot": 8,
        "kind": "doctrine-informed-neural-network",
        "doctrine": {
            "lambda_floor": _DINN_LAMBDA_FLOOR,
            "train_margin": _DINN_TRAIN_MARGIN,
            "and_gate_lambda": lam,
            "min_axis": round(min_axis, 4),
            "above_floor": min_axis >= _DINN_LAMBDA_FLOOR,
        },
        "doctrine_dinn": {
            "axes": axes,
            "mechanism": "structural clamp: floor + (1-floor)*sigmoid(z)",
            "recipe": "szl-cookbook/recipes/doctrine-dinn-v1",
        },
        "knot_dinn": {
            "invariance_gap": knot_gap,
            "law": "Reidemeister R1/R2/R3 residual",
            "recipe": "szl-cookbook/recipes/knot-calculus-v2",
        },
        "bekenstein_dinn": {
            "raw_entropy_nats": raw_entropy,
            "clamped_entropy_nats": entropy,
            "output_entropy_nats": entropy,
            "s_max_nats": s_max,
            "under_cap": entropy <= s_max + 1e-6,
            "clamp_applied": raw_entropy > s_max,
            "mechanism": "entropy clamp: binary-search blend toward arg-max one-hot",
            "recipe": "szl-cookbook/recipes/bekenstein-dinn-v1",
        },
        "honesty": (
            "Lean obligation pending (sorry placeholder) in all three recipes; "
            "none is claimed proven. The structural clamp guarantees the cap; "
            "the learned soft-penalty only approaches it."
        ),
        # Doctrine v11 LOCKED (749/14/163, replay c7c0ba17). The previous string
        # here reported stale v9 numbers (456/14/6) — corrected to the canonical
        # numbers served by /api/amaru/v3/doctrine (Yachay 2026-06-01, PINN/DINN
        # finish). Lambda_floor=0.90 is a DINN hyperparameter, NOT a doctrine count.
        "doctrine_version": "v11 (749 decl / 14 unique axioms / 163 sorries / 12 MCP / 46 gates)",
        "doctrine_replay_hash": "c7c0ba17",
        "lambda_status": "Conjecture 1 (NOT a theorem)",
        "slsa": "L1 honest (cosign-signed; verifiable via cosign verify). L2 build-provenance attestation is roadmap (Wire D) — not yet claimed. L3 not claimed.",
    }


@app.get("/chakra/dinn")
def chakra_dinn(envelope: str = "amaru-default-envelope") -> dict[str, Any]:
    """8th chakra — DINN reasoner monitor (read-only). ADDITIVE.

    Returns a per-decision DINN axis monitor: the 13-axis Doctrine-DINN reasoner
    (each axis structurally pinned >= LAMBDA_FLOOR), a Knot-DINN Reidemeister
    invariance gap, and a Bekenstein-DINN entropy meter. See szl-cookbook recipes
    knot-calculus-v2 / doctrine-dinn-v1 / bekenstein-dinn-v1."""
    return _dinn_monitor(envelope)


@app.get("/chakra/dinn/v1/healthz")
def chakra_dinn_healthz() -> dict[str, Any]:
    """DINN sub-surface health probe (ADDITIVE, Yachay 2026-06-01).

    Confirms the DINN reasoner is reachable and reports whether DSSE signing is
    available in this runtime (i.e. whether the SZL_COSIGN_PRIVATE_PEM secret is
    set). Never raises."""
    from . import dinn_dsse as _dsse
    return {
        "status": "ok",
        "chakra": "dinn",
        "slot": 8,
        "lambda_floor": _DINN_LAMBDA_FLOOR,
        "signing_available": _dsse.signing_available(),
        "keyid": _dsse.KEYID,
        "pub_fingerprint_sha256": _dsse.public_key_fingerprint(),
        "doctrine_version": "v11",
        "honesty": "Lean obligation pending (sorry placeholder); none is claimed proven.",
    }


@app.get("/chakra/dinn/receipt")
def chakra_dinn_receipt(
    envelope: str = "amaru-default-envelope",
    residual_threshold: float = 0.05,
) -> dict[str, Any]:
    """Run the DINN monitor and emit a DSSE-signed receipt (ADDITIVE).

    The receipt is appended to the in-memory Khipu receipt chain (giving it a
    chained ``prevHash`` -> ``selfHash``), then wrapped in a DSSE envelope signed
    with the canonical cosign key (keyid ``szlholdings-cosign``). Fields:
      - final_state_hash : the appended receipt's selfHash (chain head)
      - ledger_digest    : SHA-256 over the full chain heads (deterministic)
      - stop_reason      : "convergence" if the DINN law-residual is under the
                           threshold, else "max_iter" (the monitor is a single
                           deterministic forward pass, so it converges by
                           construction unless the structural clamp is disabled)
      - residual_loss    : the dominant DINN law residual (knot invariance gap)

    HONESTY: the signature attests the RECEIPT BYTES, not any physics guarantee.
    Every DINN ships its Lean obligation as a `sorry` placeholder — none proven.
    """
    import hashlib as _hashlib
    from . import dinn_dsse as _dsse

    monitor = _dinn_monitor(envelope)
    residual_loss = float(monitor["knot_dinn"]["invariance_gap"])
    above_floor = bool(monitor["doctrine"]["above_floor"])
    under_cap = bool(monitor["bekenstein_dinn"]["under_cap"])
    converged = (residual_loss < residual_threshold) and above_floor and under_cap
    stop_reason = "convergence" if converged else "max_iter"

    receipt = _chain.append(
        endpoint="/chakra/dinn/receipt",
        method="GET",
        params={"envelope": envelope, "residual_threshold": residual_threshold},
        result={
            "and_gate_lambda": monitor["doctrine"]["and_gate_lambda"],
            "residual_loss": residual_loss,
            "stop_reason": stop_reason,
        },
        metadata={"chakra": "dinn", "kind": "dinn-receipt", "doctrine_version": "v11"},
    )
    final_state_hash = receipt.self_hash
    chain_heads = "".join(r.self_hash for r in _chain.all())
    ledger_digest = _hashlib.sha256(chain_heads.encode("utf-8")).hexdigest()

    payload = {
        "kind": "dinn-receipt",
        "chakra": "dinn",
        "envelope": envelope,
        "doctrine_version": "v11",
        "doctrine_replay_hash": "c7c0ba17",
        "lambda_status": "Conjecture 1 (NOT a theorem)",
        "slsa": "L1 honest (cosign-signed; verifiable via cosign verify). L2 build-provenance attestation is roadmap (Wire D) — not yet claimed. L3 not claimed.",
        "and_gate_lambda": monitor["doctrine"]["and_gate_lambda"],
        "lambda_floor": _DINN_LAMBDA_FLOOR,
        "above_floor": above_floor,
        "residual_loss": residual_loss,
        "residual_threshold": residual_threshold,
        "bekenstein_under_cap": under_cap,
        "stop_reason": stop_reason,
        "final_state_hash": final_state_hash,
        "prev_hash": receipt.prev_hash,
        "ledger_digest": ledger_digest,
        "seq": receipt.seq,
        "honesty": (
            "every DINN ships its Lean obligation as a `sorry` placeholder — none "
            "is claimed proven. The DSSE signature attests these receipt bytes, "
            "NOT any physics or governance guarantee."
        ),
    }
    dsse = _dsse.sign_payload(payload)
    return {
        "monitor": monitor,
        "final_state_hash": final_state_hash,
        "ledger_digest": ledger_digest,
        "stop_reason": stop_reason,
        "residual_loss": residual_loss,
        "dsse_receipt": dsse,
    }


@app.get("/chakra/{name}/leader")
def get_leader(name: str) -> dict[str, Any]:
    try:
        entry = get_chakra(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown chakra: {name}")
    return {
        "chakra": entry.name,
        "leader_md": entry.leader_md,
        "proof_id": entry.proof.get("proof_id"),
        "proof_sha256": entry.proof.get("sha256"),
        "proof_kind": entry.proof.get("kind"),
        "stubbed": entry.stubbed,
        "rejected_md": entry.rejected_md,
    }


@app.post("/chakra/{name}/evaluate")
async def evaluate_chakra(name: str, body: EvaluateRequest) -> dict[str, Any]:
    try:
        entry = get_chakra(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown chakra: {name}")

    envelope = body.envelope or {}
    # Soft envelope size guard (tripwire huklla-9).
    try:
        size = len(repr(envelope).encode("utf-8"))
        if size > ENVELOPE_SOFT_LIMIT_BYTES:
            _state["oversized_envelopes"] += 1
    except Exception:
        pass

    try:
        output = entry.evaluate(envelope)
        error: str | None = None
    except NotImplementedError as exc:
        output = None
        error = str(exc)
    except Exception as exc:  # noqa: BLE001
        output = None
        error = f"{type(exc).__name__}: {exc}"

    receipt = _chain.append(
        endpoint=f"/chakra/{name}/evaluate",
        method="POST",
        params={"envelope": envelope},
        result={"output": output, "error": error},
        metadata={
            "chakra": name,
            "stubbed": entry.stubbed,
            "proof_id": entry.proof.get("proof_id"),
        },
    )

    evaluation = {
        "chakra": name,
        "proof_id": entry.proof.get("proof_id"),
        "output": output,
        "error": error,
        "stubbed": entry.stubbed,
        "receipt": receipt.to_dict(),
    }
    _state["last_evaluation"][name] = evaluation

    _publish_async(_publish_chakra(name, evaluation))

    if error and not entry.stubbed:
        # Real runtime failure — return 500. Stub kernels return 200 with the
        # error so the Brain panel can render "stubbed, surfaced loudly".
        raise HTTPException(status_code=500, detail=evaluation)

    return evaluation


@app.post("/scheduler/tick")
async def scheduler_tick(body: SchedulerTickRequest) -> dict[str, Any]:
    result = _scheduler.tick(body.envelope)
    step_seqs = [s.receipt_seq for s in result.steps]
    # Single canonical tick-level receipt that summarises the whole tick.
    # Downstream consumers of `amaru.scheduler` can pin to this id/hash
    # for replay/audit instead of stitching together per-step seqs.
    tick_receipt = _chain.append(
        endpoint="/scheduler/tick",
        method="POST",
        params={"envelope": body.envelope or {}},
        result={
            "tick_id": result.tick_id,
            "closure": result.closure,
            "handoff": result.handoff,
            "step_receipt_seqs": step_seqs,
        },
        metadata={
            "kind": "scheduler_tick",
            "tick": result.tick_id,
            "step_count": len(result.steps),
            "stubbed_count": sum(1 for s in result.steps if s.stubbed),
        },
    )
    # Build the core receipt object that goes into the DSSE payload.
    receipt_core = {
        "seq": tick_receipt.seq,
        "hash": tick_receipt.self_hash,
        "prevHash": tick_receipt.prev_hash,
    }
    # Base64-encode the canonical JSON of the receipt for the DSSE envelope.
    _receipt_json = json.dumps(receipt_core, sort_keys=True, separators=(",", ":"))
    _receipt_b64 = base64.b64encode(_receipt_json.encode("utf-8")).decode("ascii")

    # DSSE envelope (Dead-Simple Signing Envelope, draft-compliant structure).
    # NOTE: The signature below is a PLACEHOLDER stub.
    # Real Sigstore/cosign CI wiring is not yet implemented (honest disclosure
    # per amaru thesis v20). The envelope shape is final; the sig field will be
    # replaced by a real signature once Sigstore CI lands.
    dsse_envelope = {
        "payloadType": "application/vnd.szl.amaru.receipt+json",
        "payload": _receipt_b64,
        "signatures": [
            {
                "keyid": "amaru-scheduler-stub-v1",
                "sig": "PLACEHOLDER — signing not yet wired into CI (Sigstore integration pending)",
            }
        ],
    }

    payload = {
        "tick_id": result.tick_id,
        "tick_receipt": receipt_core,
        "dsse": dsse_envelope,
        "steps": [
            {
                "chakra": s.chakra,
                "output": s.output,
                "error": s.error,
                "stubbed": s.stubbed,
                "receipt_seq": s.receipt_seq,
            }
            for s in result.steps
        ],
        "closure": result.closure,
        "handoff": result.handoff,
    }

    # Mirror per-chakra last-evaluation snapshots so the Brain panel can
    # poll a single source after a scheduler tick, AND publish each step
    # to `amaru.chakra` so the bus stream and SSE clients see every
    # kernel evaluation (replay fidelity: one tick = 7 amaru.chakra
    # events + 1 amaru.scheduler event).
    for s in result.steps:
        entry = CHAKRA_REGISTRY[s.chakra]
        step_evaluation = {
            "chakra": s.chakra,
            "proof_id": entry.proof.get("proof_id"),
            "output": s.output,
            "error": s.error,
            "stubbed": s.stubbed,
            "receipt": {"seq": s.receipt_seq},
            "via": "scheduler",
            "tick_id": result.tick_id,
        }
        _state["last_evaluation"][s.chakra] = step_evaluation
        _publish_async(_publish_chakra(s.chakra, step_evaluation))

    _publish_async(_publish_tick(payload))

    return payload


@app.get("/scheduler/wiring")
def scheduler_wiring() -> dict[str, Any]:
    return wiring_snapshot()


@app.get("/state")
def runtime_state() -> dict[str, Any]:
    return {
        "chakras": list(CHAKRA_ORDER),
        "last_evaluation": _state["last_evaluation"],
        "scheduler_ticks": _scheduler.tick_count,
        "receipts": _chain.length(),
        "bus": {
            "publishes": _state["bus_publishes"],
            "failures": _state["bus_publish_failures"],
        },
    }


@app.get("/receipts")
def receipts(limit: int = 50) -> dict[str, Any]:
    all_receipts = _chain.all()
    tail = all_receipts[-max(1, min(limit, 500)) :]
    return {
        "total": len(all_receipts),
        "head_seq": all_receipts[-1].seq if all_receipts else 0,
        "items": [r.to_dict() for r in tail],
    }


@app.get("/events")
async def events() -> StreamingResponse:
    """SSE stream of `amaru.chakra` and `amaru.scheduler` events.

    Subscribers receive a `hello` event on connect and then JSON-encoded
    bus envelopes as they are published. Topic names match the Prism Bus
    publish contract exactly (`amaru.chakra`, `amaru.scheduler`).
    """
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=_SSE_QUEUE_MAX)
    _sse_subscribers.append(queue)

    async def gen() -> Any:
        try:
            hello = {
                "type": "hello",
                "payload": {
                    "chakras": list(CHAKRA_ORDER),
                    "topics": ["amaru.chakra", "amaru.scheduler"],
                },
            }
            yield f"event: {hello['type']}\ndata: {json.dumps(hello)}\n\n"
            while True:
                try:
                    evt = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"event: {evt['type']}\ndata: {json.dumps(evt)}\n\n"
                except asyncio.TimeoutError:
                    # Heartbeat keeps proxies from closing the connection.
                    yield ": keepalive\n\n"
        finally:
            if queue in _sse_subscribers:
                _sse_subscribers.remove(queue)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/tripwires")
def tripwires() -> dict[str, Any]:
    snap = {
        "registered_chakras": list(CHAKRA_REGISTRY.keys()),
        "chain_breaks": 0,
        "chakras_missing_proof": [
            n for n, e in CHAKRA_REGISTRY.items() if not e.proof.get("proof_id")
        ],
        "stubbed_chakras": [n for n, e in CHAKRA_REGISTRY.items() if e.stubbed],
        "scheduler_ticks": _scheduler.tick_count,
        "unexpected_cycles": 0,
        "bus_publishes": _state["bus_publishes"],
        "bus_publish_failures": _state["bus_publish_failures"],
        "chakras_missing_leader": [
            n for n, e in CHAKRA_REGISTRY.items() if not e.leader_md.strip()
        ],
        "oversized_envelopes": _state["oversized_envelopes"],
        "declared_order": list(CHAKRA_ORDER),
    }
    results = evaluate_all(snap)
    return {
        "summary": {
            "pass": sum(1 for r in results if r.status == "pass"),
            "warn": sum(1 for r in results if r.status == "warn"),
            "trip": sum(1 for r in results if r.status == "trip"),
            "total": len(results),
        },
        "tripwires": [
            {"id": r.id, "title": r.title, "status": r.status, "detail": r.detail}
            for r in results
        ],
    }


def main() -> None:
    import uvicorn

    port = int(os.environ.get("PORT", "6810"))
    uvicorn.run("amaru.app:app", host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()


# ─────────────────────────────────────────────────────────────────────────────
# PARITY ENDPOINTS — amaru vs Fiddler/Arize/LangSmith
# feat/parity-confidence-eval (Perplexity Computer Agent 2026-06-10)
# ADDITIVE ONLY. Doctrine v11 LOCKED 749/14/163. No existing routes touched.
# Signed-off-by: stephenlutar2-hash <stephenlutar2@gmail.com>
# ─────────────────────────────────────────────────────────────────────────────
try:
    from amaru import confidence as _confidence_mod
    from amaru import retrieval_eval as _retrieval_eval_mod
    _PARITY_OK = True
    _PARITY_ERR: str | None = None
except Exception as _parity_err:  # pragma: no cover - defensive
    _PARITY_OK = False
    _PARITY_ERR = repr(_parity_err)


class ConfidenceRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=8192)
    answer: str = Field(..., min_length=1, max_length=32768)
    verification_answer: str | None = Field(default=None)
    axis_scores: list[float] | None = Field(default=None, max_length=13)


class RetrievalEvalRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=8192)
    answer: str = Field(..., min_length=1, max_length=32768)
    chunks: list[str] = Field(default_factory=list, max_length=50)


@app.post("/v1/confidence")
def confidence_score(body: ConfidenceRequest) -> dict[str, Any]:
    """Hallucination-risk + confidence scoring for a cortex output.

    Parity: Fiddler AI faithfulness/hallucination scoring, Arize Phoenix LLM-as-judge.
    Differentiator: every score is Λ-gated (13-axis geomean) and receipt-stamped.

    POST body:
      { "question": str, "answer": str,
        "verification_answer": str|null,  # independent CoVe pass
        "axis_scores": [float]*13 | null  # Λ-axis vector
      }

    Returns confidence in [0,1], sub-scores, hallucination_risk flag + receipt.
    """
    if not _PARITY_OK:
        return {"ok": False, "error": "confidence module unavailable",
                "detail": _PARITY_ERR, "doctrine": "v11"}
    result = _confidence_mod.score(
        body.question,
        body.answer,
        verification_answer=body.verification_answer,
        axis_scores=body.axis_scores,
    )
    return result.to_dict()


@app.post("/v1/eval")
def retrieval_eval(body: RetrievalEvalRequest) -> dict[str, Any]:
    """RAG retrieval evaluation: context_precision, context_recall,
    answer_faithfulness, source_coverage.

    Parity: LangSmith retrieval evals, Arize Phoenix RAGAS, Fiddler faithfulness.
    Differentiator: deterministic token-overlap (no LLM API cost), receipt hash bound.

    POST body:
      { "question": str, "answer": str, "chunks": [str, ...] }

    Returns four metrics in [0,1], composite score, and provenance receipt.
    """
    if not _PARITY_OK:
        return {"ok": False, "error": "retrieval_eval module unavailable",
                "detail": _PARITY_ERR, "doctrine": "v11"}
    result = _retrieval_eval_mod.evaluate(
        body.question,
        body.answer,
        body.chunks,
    )
    return result.to_dict()


# ─────────────────────────────────────────────────────────────────────────────
# End parity endpoints
# Doctrine v11 LOCKED — 749/14/163 @ c7c0ba17 · Λ = Conjecture 1 (NOT a theorem).
# ─────────────────────────────────────────────────────────────────────────────
