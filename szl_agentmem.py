"""
szl_agentmem.py — SZL AGENTMEM: a Λ-gated, governed, energy-aware agent-memory
recall surface with a signed-receipt-per-recall design.

This is an SZL cross-axis SYNTHESIS surface: it combines three real, cited strands
that no published system ships together —

  (1) AGENT MEMORY — hierarchical / self-organising long-term memory for LLM agents
      (MemGPT, A-MEM, Mem0, DSPy), recall over a persistent memory store;
  (2) Λ-GATING — the SZL restraint advisory (Λ = Conjecture 1, gray, NEVER green),
      applied as a per-recall TRUST GATE over what an agent is allowed to act on;
  (3) THE RECEIPT CHAIN — a signed-receipt-PER-RECALL design so every act of
      remembering is auditable (receipt-on-WRITE, never on a read).

  GET  /api/<ns>/v1/frontier/agentmem?seed=&n_memories=&query_k=&horizon=

The endpoint returns a MODELED/CONJECTURE model of governed agent-memory recall:
a deterministic, seeded memory store is queried; the top-k recalls pass through a
Λ-advisory trust gate and a memory-consistency check; and the response DESCRIBES
(does not mint) the signed receipt each recall would emit on a real WRITE.

Returned JSON (top-level `label`, metrics nested under `payload` — the agentmem
surface reads the label at top level OR payload.label, metrics from payload)
----------------------------------------------------------------------------
  label                       : "MODELED" (the recall/consistency arithmetic is a
                                deterministic simulation; the SZL synthesis is
                                additionally flagged CONJECTURE inside payload).
  payload.n_memories          : size of the modeled persistent memory store
  payload.query_k             : top-k memories retrieved for the query
  payload.horizon             : staleness horizon (age beyond which a memory is stale)
  payload.recalled[]          : per-recall {id, relevance, salience, age_steps,
                                consistent, lambda_advisory, admitted}
  payload.consistency         : {checked, consistent, conflicts, consistency_rate}
  payload.lambda_gate         : {status, value, bounds, admits, gated_out, trust,
                                trust_cap} — Λ advisory (Conjecture 1, gray)
  payload.receipt_design      : signed-receipt-per-recall DESIGN (CONJECTURE),
                                incl. an UNSIGNED content-hash preview (signed:false)
  payload.parts_labeled       : which parts are MODELED vs CONJECTURE
  payload.honest_note         : plain-language honesty disclaimer
  payload.citations           : dict of citable sources (verbatim, never claimed as ours)
  payload.computed_at         : ISO-8601 UTC timestamp

HONEST STATUS
  MODELED — the memory store, relevance/salience scores, age model, and the
    memory-consistency check are a deterministic seeded simulation. relevance,
    consistency_rate, admits/gated_out, and trust are genuinely COMPUTED from the
    modeled store, reported not fabricated. It does NOT run a trained retriever,
    an embedding model, or any of the cited agent-memory systems.
  CONJECTURE — the SZL SYNTHESIS is unproven and labeled as such: (a) Λ as a
    per-recall trust gate is the SZL restraint advisory Λ = Conjecture 1 (gray,
    NEVER green), not a theorem; (b) the signed-receipt-per-recall chain is a
    DESIGN — no receipt is minted here (receipt-on-WRITE, never on a GET), so the
    response only DESCRIBES the receipt and shows an UNSIGNED content-hash preview.

DOCTRINE v11
  Nothing here is in the locked-8 (adds 0). Λ = Conjecture 1 (gray, never green).
  Trust is capped at 0.97 and is never 1.0. No fabricated data. Pure stdlib.
  Deterministic with seed. 0 runtime CDN. RECEIPT-ON-WRITE, NOT ON-READ: this GET
  signs nothing and appends to no provenance chain — it computes a plain content
  hash as a clearly-UNSIGNED design preview.

CITATIONS (clean-room; none claimed as SZL's own; verified to resolve 2026-07-07):
  MemGPT: Towards LLMs as Operating Systems (virtual context / memory tiers):
    Packer et al. 2023, arXiv:2310.08560   https://arxiv.org/abs/2310.08560
  A-MEM: Agentic Memory for LLM Agents (self-organising agent memory, 2025):
    Xu et al. 2025, arXiv:2502.12110       https://arxiv.org/abs/2502.12110
  Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory
  (LoCoMo memory-consistency comparison, 2025):
    Chhikara et al. 2025, arXiv:2504.19413 https://arxiv.org/abs/2504.19413
  DSPy: Compiling Declarative LM Calls into Self-Improving Pipelines:
    Khattab et al. 2023, arXiv:2310.03714  https://arxiv.org/abs/2310.03714
"""
import hashlib
from datetime import datetime, timezone

from starlette.routing import Route
from starlette.responses import JSONResponse

CITATIONS = {
    "MemGPT: Towards LLMs as Operating Systems — Packer et al. 2023 arXiv:2310.08560": "https://arxiv.org/abs/2310.08560",
    "A-MEM: Agentic Memory for LLM Agents — Xu et al. 2025 arXiv:2502.12110": "https://arxiv.org/abs/2502.12110",
    "Mem0: Production-Ready AI Agents with Scalable Long-Term Memory — Chhikara et al. 2025 arXiv:2504.19413": "https://arxiv.org/abs/2504.19413",
    "DSPy: Compiling Declarative LM Calls into Self-Improving Pipelines — Khattab et al. 2023 arXiv:2310.03714": "https://arxiv.org/abs/2310.03714",
}

# MODELED recall / gate hyperparameters (reported verbatim; not trained).
_LAMBDA_MIN = 0.02          # Λ advisory lower bound (gray floor)
_LAMBDA_MAX = 0.94          # Λ advisory upper bound (NEVER 1.0 — Conjecture 1)
_LAMBDA_ADMIT = 0.55        # advisory admit threshold (a recall is admitted above it)
_TRUST_CAP = 0.97           # doctrine hard cap on trust (never green / never 1.0)
_CONFLICT_EVERY = 7         # every Nth planted memory is a modeled stale/conflict item
_RECALL_CAP = 64            # max recalled entries returned (matches surface stream cap)


def _u01(seed, i, salt=0):
    """Deterministic uniform in [0,1) from (seed, i, salt) via two LCG rounds."""
    s = ((i + 1) * 2654435761 + seed * 40503 + salt * 2246822519) & 0xFFFFFFFF
    s = (1664525 * s + 1013904223) & 0xFFFFFFFF
    s = (1664525 * s + 1013904223) & 0xFFFFFFFF
    return s / 4294967295.0


def _recall(seed=42, n_memories=256, query_k=16, horizon=128):
    """Deterministic governed-recall simulation over a seeded memory store.

    Each memory item i has: a MODELED relevance-to-query score, a salience
    (write-time importance), an age in steps, and a consistency flag (a fraction
    are planted stale/conflicting). The top-`query_k` by relevance are recalled;
    each recall gets a Λ advisory in [_LAMBDA_MIN,_LAMBDA_MAX] derived from its
    relevance and consistency, and is ADMITTED iff its advisory clears the admit
    threshold AND it is consistent. The gate is ADVISORY (gray), never a hard
    green; overall trust is capped at _TRUST_CAP.
    """
    n_memories = max(1, n_memories)
    query_k = max(1, min(query_k, n_memories))
    horizon = max(1, horizon)

    # Build the modeled store: (id, relevance, salience, age, consistent).
    store = []
    for i in range(n_memories):
        relevance = _u01(seed, i, salt=1)                 # relevance to the query
        salience = 0.2 + 0.8 * _u01(seed, i, salt=2)      # write-time importance
        age = int(_u01(seed, i, salt=3) * (2 * horizon))  # age in steps
        # Planted inconsistency: some memories are stale (age > horizon) or a
        # deterministically-planted conflict — modeled, not fabricated.
        stale = age > horizon
        planted_conflict = (i % _CONFLICT_EVERY == 0)
        consistent = not (stale or planted_conflict)
        store.append({
            "id": i,
            "relevance": relevance,
            "salience": salience,
            "age_steps": age,
            "consistent": consistent,
        })

    # Recall: top-k by relevance (ties broken by id for determinism).
    ranked = sorted(store, key=lambda m: (-m["relevance"], m["id"]))
    top = ranked[:query_k]

    recalled = []
    admits = 0
    gated_out = 0
    consistent_n = 0
    lam_sum = 0.0
    for m in top:
        rel = m["relevance"]
        cons = m["consistent"]
        if cons:
            consistent_n += 1
        # Λ advisory: rises with relevance, penalised if inconsistent; bounded so
        # it is NEVER 1.0 (Λ = Conjecture 1, gray). This is the SZL synthesis part.
        base = _LAMBDA_MIN + (_LAMBDA_MAX - _LAMBDA_MIN) * rel
        if not cons:
            base *= 0.5
        lam = round(min(_LAMBDA_MAX, max(_LAMBDA_MIN, base)), 6)
        lam_sum += lam
        admitted = bool(lam >= _LAMBDA_ADMIT and cons)
        if admitted:
            admits += 1
        else:
            gated_out += 1
        recalled.append({
            "id": m["id"],
            "relevance": round(rel, 6),
            "salience": round(m["salience"], 6),
            "age_steps": m["age_steps"],
            "consistent": cons,
            "lambda_advisory": lam,
            "admitted": admitted,
        })

    checked = len(top)
    conflicts = checked - consistent_n
    consistency_rate = round(consistent_n / checked, 6) if checked else 0.0
    mean_lambda = round(lam_sum / checked, 6) if checked else 0.0

    # Overall trust: rises with consistency and mean Λ advisory, HARD-CAPPED at
    # _TRUST_CAP so it is never green / never 1.0 (doctrine v11).
    trust_raw = 0.5 * consistency_rate + 0.5 * (mean_lambda / _LAMBDA_MAX if _LAMBDA_MAX else 0.0)
    trust = round(min(_TRUST_CAP, trust_raw), 6)

    return {
        "n_memories": n_memories,
        "query_k": query_k,
        "horizon": horizon,
        "recalled": recalled[:_RECALL_CAP],
        "consistency": {
            "checked": checked,
            "consistent": consistent_n,
            "conflicts": conflicts,
            "consistency_rate": consistency_rate,
        },
        "lambda_gate": {
            "status": "Λ = Conjecture 1 (advisory, gray — NEVER green, not a theorem)",
            "admit_threshold": _LAMBDA_ADMIT,
            "mean_lambda_advisory": mean_lambda,
            "bounds": {"min": _LAMBDA_MIN, "max": _LAMBDA_MAX},
            "admits": admits,
            "gated_out": gated_out,
            "trust": trust,
            "trust_cap": _TRUST_CAP,
        },
    }


def _receipt_design(payload, seed):
    """Describe the signed-receipt-PER-RECALL chain (CONJECTURE synthesis).

    RECEIPT-ON-WRITE, NOT ON-READ: this GET mints NOTHING and appends to no
    provenance chain. To make the design concrete without violating that, we
    compute a plain SHA3-256 content hash of the recall payload and return it as
    a clearly-UNSIGNED design PREVIEW (signed:false). A real deployment would
    emit one signed Khipu receipt per recall WRITE, binding the query, the
    recalled ids, the Λ-gate verdict, the consistency result, and the energy
    label into the hash-chained receipt DAG — none of which happens on this read.
    """
    gate = payload["lambda_gate"]
    cons = payload["consistency"]
    canonical = "|".join([
        f"seed={seed}",
        f"k={payload['query_k']}",
        "ids=" + ",".join(str(r["id"]) for r in payload["recalled"]),
        f"admits={gate['admits']}",
        f"gated_out={gate['gated_out']}",
        f"consistency_rate={cons['consistency_rate']}",
        f"trust={gate['trust']}",
    ])
    preview_digest = hashlib.sha3_256(canonical.encode("utf-8")).hexdigest()
    return {
        "kind": "signed-receipt-per-recall (SZL synthesis — CONJECTURE, design-only)",
        "binds": [
            "query + recalled memory ids",
            "Λ-gate verdict (admits / gated_out; Λ = Conjecture 1, gray)",
            "memory-consistency result (consistency_rate, conflicts)",
            "energy label of the recall op (MEASURED/MODELED/SAMPLE — not fabricated)",
        ],
        "chain": "one hash-linked Khipu receipt per recall WRITE (Conjecture 2: "
                 "integrity real; BFT/consensus is the conjecture)",
        "signature": "DSSE_PLACEHOLDER (cosign founder-gated) — NOT applied here",
        "signed": False,
        "minted_on_this_get": False,
        "receipt_preview_digest": preview_digest,
        "preview_digest_alg": "SHA3-256 over a canonical recall summary (UNSIGNED preview only)",
        "doctrine": "RECEIPT-ON-WRITE, NOT ON-READ — a GET signs nothing and grows no chain.",
        "verify_when_minted": "/api/a11oy/v1/khipu/verify/{digest}",
    }


def _ii(req, key, default):
    try:
        return int(float(req.query_params.get(key, default)))
    except Exception:
        return default


def _h_agentmem(req):
    seed       = _ii(req, "seed", 42)
    n_memories = max(8, min(_ii(req, "n_memories", 256), 4096))
    query_k    = max(1, min(_ii(req, "query_k", 16), 256))
    horizon    = max(1, min(_ii(req, "horizon", 128), 4096))

    p = _recall(seed=seed, n_memories=n_memories, query_k=query_k, horizon=horizon)
    p["receipt_design"] = _receipt_design(p, seed)
    p.update({
        "label": "MODELED",
        "model": "Λ-gated governed agent-memory recall with signed-receipt-per-recall design",
        "seed": seed,
        "parts_labeled": {
            "MODELED": [
                "memory store (relevance / salience / age simulation)",
                "top-k recall ranking",
                "memory-consistency check (consistency_rate, conflicts)",
                "trust (computed from consistency + mean Λ, hard-capped at 0.97)",
            ],
            "CONJECTURE": [
                "Λ as a per-recall trust gate (Λ = Conjecture 1, gray — never green)",
                "signed-receipt-per-recall chain (design-only; nothing minted on a GET)",
                "the governed-agent-memory synthesis as a whole (unshipped combination)",
            ],
        },
        "honest_note": (
            "MODELED + CONJECTURE. The memory store, relevance/salience/age model, "
            "and the memory-consistency check are a deterministic seeded simulation; "
            "relevance, consistency_rate, admits/gated_out and trust are genuinely "
            "computed, reported not fabricated. It does NOT run a trained retriever, "
            "an embedding model, or any cited agent-memory system. The SZL SYNTHESIS "
            "is CONJECTURE: Λ as a per-recall trust gate is the restraint advisory "
            "Λ = Conjecture 1 (gray, NEVER green, not a theorem), and the "
            "signed-receipt-per-recall chain is a DESIGN — no receipt is minted here "
            "(RECEIPT-ON-WRITE, never on a GET); the receipt_preview_digest is a "
            "plain UNSIGNED content hash, not a signature. Trust is capped at 0.97 "
            "and is never 1.0. Cites MemGPT (arXiv:2310.08560), A-MEM "
            "(arXiv:2502.12110), Mem0 (arXiv:2504.19413), DSPy (arXiv:2310.03714). "
            "SZL claims NONE of these methods as its own. Nothing here is in the locked-8."
        ),
        "citations": CITATIONS,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    })
    # Surface reads label at top level OR payload.label, metrics from payload.
    return JSONResponse({"label": "MODELED", "payload": p})


def register(app, ns: str = "a11oy"):
    """Wire /api/<ns>/v1/frontier/agentmem onto app. Additive, try/except-guarded."""
    base = f"/api/{ns}/v1/frontier"
    handlers = [(f"{base}/agentmem", _h_agentmem)]
    add_api_route = getattr(app, "add_api_route", None)
    for path, fn in handlers:
        if callable(add_api_route):
            app.add_api_route(path, fn, methods=["GET"])
        else:
            app.router.routes.append(Route(path, fn))
    return [p for p, _ in handlers]


if __name__ == "__main__":
    p = _recall(seed=42, n_memories=256, query_k=16, horizon=128)
    p["receipt_design"] = _receipt_design(p, 42)
    g = p["lambda_gate"]
    c = p["consistency"]
    assert 0.0 <= g["trust"] <= _TRUST_CAP, "trust must be capped at 0.97"
    assert g["bounds"]["max"] < 1.0, "Λ advisory must never reach 1.0 (Conjecture 1)"
    assert p["receipt_design"]["signed"] is False, "no signing on a read path"
    assert p["receipt_design"]["minted_on_this_get"] is False
    assert g["admits"] + g["gated_out"] == c["checked"]
    print("checked:", c["checked"], "consistent:", c["consistent"], "conflicts:", c["conflicts"])
    print("consistency_rate:", c["consistency_rate"], "mean_lambda:", g["mean_lambda_advisory"])
    print("admits:", g["admits"], "gated_out:", g["gated_out"], "trust:", g["trust"], "(cap", _TRUST_CAP, ")")
    print("lambda_status:", g["status"])
    print("receipt signed:", p["receipt_design"]["signed"], "preview_digest:", p["receipt_design"]["receipt_preview_digest"][:16], "...")
    print("label: MODELED (synthesis parts CONJECTURE)")
