"""
szl_lgmi.py — SZL LGMI: Λ-Governed Mechanistic Interpretability. A per-circuit
Λ-advisory TRUST GATE (the szl-lambda-gate aggregator) laid over sparse-feature /
circuit ATTRIBUTION, with a signed-attribution-receipt-per-write design.

This is an SZL cross-axis SYNTHESIS: mechanistic interpretability publishes rich
methods for FINDING features and circuits (sparse autoencoders, attribution/ablation
patching, automated circuit discovery), but ships NO governance layer that decides,
under an explicit advisory trust bound, WHICH attributed circuits a downstream claim
is allowed to rely on. LGMI ties the real interpretability field leaders to the SZL
Λ-gate aggregator (szl-lambda-gate) — Λ = Conjecture 1 (gray, NEVER green) — plus a
signed-attribution-receipt-PER-WRITE chain so every "this feature explains that
behaviour" claim is auditable.

  GET  /api/<ns>/v1/frontier/lgmi?seed=&n_features=&n_circuits=&sparsity=

The endpoint returns a MODELED/CONJECTURE model of governed interpretability: a
deterministic, seeded population of sparse FEATURES (each with an activation
frequency and a monosemanticity score) is composed into CIRCUITS carrying an
attribution effect; each circuit passes a Λ-advisory trust gate and a
faithfulness/sufficiency consistency check; and the response DESCRIBES (does not
mint) the signed attribution receipt each admitted-claim WRITE would emit.

Returned JSON (top-level `label`, metrics nested under `payload`)
----------------------------------------------------------------------------
  label                       : "MODELED"
  payload.n_features          : number of modeled sparse features
  payload.n_circuits          : number of composed circuits scored
  payload.sparsity            : target L0 sparsity of the SAE decomposition (frac)
  payload.features[]          : {id, activation_freq, monosemanticity, dead}
  payload.circuits[]          : {id, feature_ids, attribution, faithfulness,
                                sufficiency, consistent, lambda_advisory, admitted}
  payload.attribution         : {circuits, admitted, gated_out, mean_attribution,
                                mean_faithfulness, consistency_rate, dead_feature_rate}
  payload.lambda_gate         : {status, admit_threshold, mean_lambda_advisory,
                                bounds, admits, gated_out, trust, trust_cap} — Λ
                                advisory (Conjecture 1, gray)
  payload.receipt_design      : signed-attribution-receipt-per-write DESIGN
                                (CONJECTURE), incl. an UNSIGNED content-hash preview
  payload.parts_labeled       : which parts are MODELED vs CONJECTURE
  payload.honest_note         : plain-language honesty disclaimer
  payload.citations           : dict of citable sources (verbatim, never claimed as ours)
  payload.computed_at         : ISO-8601 UTC timestamp

HONEST STATUS
  MODELED — the sparse-feature population, monosemanticity/activation-frequency
    simulation, circuit composition, attribution effect, and faithfulness /
    sufficiency checks are a deterministic seeded simulation. Attribution,
    faithfulness, consistency_rate, admits/gated_out and trust are genuinely COMPUTED
    from the modeled decomposition, reported not fabricated. It does NOT train a real
    sparse autoencoder, run attribution/ablation patching on a real model, execute
    automated circuit discovery, or reproduce any cited system's results.
  CONJECTURE — the SZL SYNTHESIS is unproven and labeled as such: (a) Λ as a
    per-circuit trust gate is the szl-lambda-gate advisory Λ = Conjecture 1 (gray,
    NEVER green), not a theorem; (b) the signed-attribution-receipt-per-write chain is
    a DESIGN — no receipt is minted here (receipt-on-WRITE, never on a GET); (c) the
    interpretability + Λ-governance + signed-receipt COMBINATION as one surface is the
    SZL-original synthesis (unshipped combination).

DOCTRINE v11
  Nothing here is in the locked-8 (adds 0). Λ = Conjecture 1 (gray, never green).
  Trust is capped at 0.97 and is never 1.0. No fabricated data. Pure stdlib.
  Deterministic with seed. 0 runtime CDN. RECEIPT-ON-WRITE, NOT ON-READ.

CITATIONS (clean-room; none claimed as SZL's own; verified to resolve 2026-07-07):
  Towards Monosemanticity: Decomposing Language Models With Dictionary Learning
    (SAE features): Bricken et al. 2023, Transformer Circuits
    https://transformer-circuits.pub/2023/monosemantic-features
  Sparse Autoencoders Find Highly Interpretable Features in Language Models:
    Cunningham et al. 2023, arXiv:2309.08600   https://arxiv.org/abs/2309.08600
  Jumping Ahead: Improving Reconstruction Fidelity with JumpReLU Sparse
    Autoencoders: Rajamanoharan et al. 2024, arXiv:2407.14435
    https://arxiv.org/abs/2407.14435
  Towards Automated Circuit Discovery for Mechanistic Interpretability (ACDC):
    Conmy et al. 2023, arXiv:2304.14997   https://arxiv.org/abs/2304.14997
  Interpretability in the Wild: a Circuit for Indirect Object Identification (IOI):
    Wang et al. 2022, arXiv:2211.00593   https://arxiv.org/abs/2211.00593
  Attribution Patching / AtP*: Efficient Localization of LLM Behaviour:
    Kramár et al. 2024, arXiv:2403.00745   https://arxiv.org/abs/2403.00745
"""
import hashlib
from datetime import datetime, timezone

from starlette.requests import Request
from starlette.routing import Route
from starlette.responses import JSONResponse

CITATIONS = {
    "Towards Monosemanticity: Dictionary Learning SAE features — Bricken et al. 2023 (Transformer Circuits)": "https://transformer-circuits.pub/2023/monosemantic-features",
    "Sparse Autoencoders Find Highly Interpretable Features — Cunningham et al. 2023 arXiv:2309.08600": "https://arxiv.org/abs/2309.08600",
    "Jumping Ahead: JumpReLU Sparse Autoencoders — Rajamanoharan et al. 2024 arXiv:2407.14435": "https://arxiv.org/abs/2407.14435",
    "Towards Automated Circuit Discovery (ACDC) — Conmy et al. 2023 arXiv:2304.14997": "https://arxiv.org/abs/2304.14997",
    "Interpretability in the Wild: IOI Circuit — Wang et al. 2022 arXiv:2211.00593": "https://arxiv.org/abs/2211.00593",
    "Attribution Patching / AtP* — Kramár et al. 2024 arXiv:2403.00745": "https://arxiv.org/abs/2403.00745",
}

# MODELED interpretability / gate hyperparameters (reported verbatim; not trained).
_LAMBDA_MIN = 0.02          # Λ advisory lower bound (gray floor)
_LAMBDA_MAX = 0.94          # Λ advisory upper bound (NEVER 1.0 — Conjecture 1)
_LAMBDA_ADMIT = 0.55        # advisory admit threshold (a circuit is admitted above it)
_TRUST_CAP = 0.97           # doctrine hard cap on trust (never green / never 1.0)
_DEAD_EVERY = 9             # every Nth feature is a modeled dead/degenerate latent
_CONFLICT_EVERY = 7         # every Nth circuit is a modeled low-faithfulness item
_FEATURE_CAP = 128          # max feature entries returned
_CIRCUIT_CAP = 96           # max circuit entries returned (matches surface stream cap)


def _u01(seed, i, salt=0):
    """Deterministic uniform in [0,1) from (seed, i, salt) via two LCG rounds."""
    s = ((i + 1) * 2654435761 + seed * 40503 + salt * 2246822519) & 0xFFFFFFFF
    s = (1664525 * s + 1013904223) & 0xFFFFFFFF
    s = (1664525 * s + 1013904223) & 0xFFFFFFFF
    return s / 4294967295.0


def _decompose(seed=42, n_features=64, n_circuits=48, sparsity=0.08):
    """Deterministic Λ-governed mechanistic-interpretability simulation.

    A dictionary of `n_features` sparse latents is modeled, each with an activation
    frequency and a monosemanticity score; a fraction are planted DEAD (never/always
    firing — the SAE degeneracy the field studies). `n_circuits` circuits each compose
    a small set of features and carry an ATTRIBUTION effect (how much ablating the
    circuit changes the modeled behaviour) plus FAITHFULNESS (does the circuit alone
    reproduce the behaviour) and SUFFICIENCY. Each circuit gets a Λ advisory in
    [_LAMBDA_MIN,_LAMBDA_MAX] from its attribution + faithfulness, and is ADMITTED iff
    the advisory clears the threshold AND it is consistent. The gate is ADVISORY
    (gray), never green; overall trust is capped at _TRUST_CAP.
    """
    n_features = max(1, min(n_features, 4096))
    n_circuits = max(1, min(n_circuits, 4096))
    sparsity = min(0.95, max(0.005, float(sparsity)))

    features = []
    for i in range(n_features):
        dead = (i % _DEAD_EVERY == 0)
        # activation frequency near the target sparsity (dead latents fire ~never).
        freq = 0.0 if dead else round(sparsity * (0.3 + 1.4 * _u01(seed, i, salt=5)), 6)
        # monosemanticity: how cleanly one feature = one concept (dead => degenerate).
        mono = 0.0 if dead else round(0.4 + 0.55 * _u01(seed, i, salt=6), 6)
        features.append({
            "id": i,
            "activation_freq": freq,
            "monosemanticity": mono,
            "dead": dead,
        })
    live_features = [f for f in features if not f["dead"]] or features

    circuits = []
    for c in range(n_circuits):
        # compose 2..4 features into this circuit (deterministic pick).
        k = 2 + int(_u01(seed, c, salt=11) * 3)
        fids = []
        for j in range(k):
            idx = int(_u01(seed, c, salt=20 + j) * len(live_features))
            fids.append(live_features[idx]["id"])
        fids = sorted(set(fids)) or [live_features[0]["id"]]
        member_mono = sum(next(f for f in features if f["id"] == fid)["monosemanticity"]
                          for fid in fids) / len(fids)

        # attribution effect: how much this circuit moves the modeled logit (0..1).
        attribution = round(0.15 + 0.8 * _u01(seed, c, salt=12), 6)
        # faithfulness: does the circuit ALONE reproduce the behaviour (rises with
        # attribution + member monosemanticity). planted low-faithfulness items keep
        # the consistency check honest.
        planted_low = (c % _CONFLICT_EVERY == 0)
        faithfulness = round(min(0.99, 0.35 * attribution + 0.55 * member_mono
                                 + 0.1 * _u01(seed, c, salt=13)), 6)
        sufficiency = round(min(0.99, 0.5 * faithfulness + 0.4 * attribution
                                + 0.1 * _u01(seed, c, salt=14)), 6)
        if planted_low:
            faithfulness = round(faithfulness * 0.4, 6)
            sufficiency = round(sufficiency * 0.4, 6)
        consistent = bool(faithfulness >= 0.45 and not planted_low)

        # Λ advisory: rises with attribution + faithfulness, penalised if
        # inconsistent; bounded so it is NEVER 1.0 (Λ = Conjecture 1, gray). SZL synth.
        base = _LAMBDA_MIN + (_LAMBDA_MAX - _LAMBDA_MIN) * (0.5 * attribution + 0.5 * faithfulness)
        if not consistent:
            base *= 0.5
        lam = round(min(_LAMBDA_MAX, max(_LAMBDA_MIN, base)), 6)
        admitted = bool(lam >= _LAMBDA_ADMIT and consistent)

        circuits.append({
            "id": c,
            "feature_ids": fids,
            "attribution": attribution,
            "faithfulness": faithfulness,
            "sufficiency": sufficiency,
            "consistent": consistent,
            "lambda_advisory": lam,
            "admitted": admitted,
        })

    admits = sum(1 for c in circuits if c["admitted"])
    gated_out = len(circuits) - admits
    consistent_n = sum(1 for c in circuits if c["consistent"])
    consistency_rate = round(consistent_n / len(circuits), 6) if circuits else 0.0
    mean_attr = round(sum(c["attribution"] for c in circuits) / len(circuits), 6) if circuits else 0.0
    mean_faith = round(sum(c["faithfulness"] for c in circuits) / len(circuits), 6) if circuits else 0.0
    mean_lambda = round(sum(c["lambda_advisory"] for c in circuits) / len(circuits), 6) if circuits else 0.0
    dead_n = sum(1 for f in features if f["dead"])
    dead_rate = round(dead_n / len(features), 6) if features else 0.0

    # Overall trust: rises with consistency, faithfulness and mean Λ advisory,
    # HARD-CAPPED at _TRUST_CAP so it is never green / never 1.0 (doctrine v11).
    trust_raw = (0.4 * consistency_rate + 0.3 * mean_faith
                 + 0.3 * (mean_lambda / _LAMBDA_MAX if _LAMBDA_MAX else 0.0))
    trust = round(min(_TRUST_CAP, trust_raw), 6)

    return {
        "n_features": n_features,
        "n_circuits": n_circuits,
        "sparsity": round(sparsity, 6),
        "features": features[:_FEATURE_CAP],
        "circuits": circuits[:_CIRCUIT_CAP],
        "attribution": {
            "circuits": len(circuits),
            "admitted": admits,
            "gated_out": gated_out,
            "mean_attribution": mean_attr,
            "mean_faithfulness": mean_faith,
            "consistency_rate": consistency_rate,
            "dead_feature_rate": dead_rate,
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
    """Describe the signed-attribution-receipt-PER-WRITE chain (CONJECTURE synthesis).

    RECEIPT-ON-WRITE, NOT ON-READ: this GET mints NOTHING and appends to no
    provenance chain. To make the design concrete we compute a plain SHA3-256 content
    hash of the attribution summary and return it as a clearly-UNSIGNED design PREVIEW
    (signed:false). A real deployment would emit one signed Khipu receipt per admitted
    interpretability CLAIM write, binding the feature/circuit ids, the attribution +
    faithfulness result, and the Λ-gate verdict into the hash-chained receipt DAG.
    """
    gate = payload["lambda_gate"]
    attr = payload["attribution"]
    canonical = "|".join([
        f"seed={seed}",
        f"features={payload['n_features']}",
        f"circuits={attr['circuits']}",
        "cids=" + ",".join(str(c["id"]) for c in payload["circuits"]),
        f"admits={gate['admits']}",
        f"gated_out={gate['gated_out']}",
        f"consistency_rate={attr['consistency_rate']}",
        f"mean_attribution={attr['mean_attribution']}",
        f"trust={gate['trust']}",
    ])
    preview_digest = hashlib.sha3_256(canonical.encode("utf-8")).hexdigest()
    return {
        "kind": "signed-attribution-receipt-per-write (SZL synthesis — CONJECTURE, design-only)",
        "binds": [
            "feature + circuit ids of the admitted interpretability claim",
            "attribution + faithfulness / sufficiency result",
            "Λ-gate verdict (admits / gated_out; Λ = Conjecture 1, gray)",
        ],
        "chain": "one hash-linked Khipu receipt per admitted-claim WRITE (Conjecture 2: "
                 "integrity real; BFT/consensus is the conjecture)",
        "signature": "DSSE_PLACEHOLDER (cosign founder-gated) — NOT applied here",
        "signed": False,
        "minted_on_this_get": False,
        "receipt_preview_digest": preview_digest,
        "preview_digest_alg": "SHA3-256 over a canonical attribution summary (UNSIGNED preview only)",
        "doctrine": "RECEIPT-ON-WRITE, NOT ON-READ — a GET signs nothing and grows no chain.",
        "verify_when_minted": "/api/a11oy/v1/khipu/verify/{digest}",
    }


def _ii(req, key, default):
    try:
        return int(float(req.query_params.get(key, default)))
    except Exception:
        return default


def _ff(req, key, default):
    try:
        return float(req.query_params.get(key, default))
    except Exception:
        return default


def _h_lgmi(req: Request):
    seed       = _ii(req, "seed", 42)
    n_features = max(1, min(_ii(req, "n_features", 64), 4096))
    n_circuits = max(1, min(_ii(req, "n_circuits", 48), 4096))
    sparsity   = min(0.95, max(0.005, _ff(req, "sparsity", 0.08)))

    p = _decompose(seed=seed, n_features=n_features, n_circuits=n_circuits, sparsity=sparsity)
    p["receipt_design"] = _receipt_design(p, seed)
    p.update({
        "label": "MODELED",
        "model": ("Λ-governed mechanistic interpretability: sparse-feature / circuit "
                  "attribution behind a szl-lambda-gate trust gate with a "
                  "signed-attribution-receipt-per-write design"),
        "seed": seed,
        "parts_labeled": {
            "MODELED": [
                "sparse-feature population (activation frequency / monosemanticity / dead latents)",
                "circuit composition + attribution effect",
                "faithfulness / sufficiency consistency check (consistency_rate, gated_out)",
                "trust (computed from consistency + faithfulness + mean Λ, hard-capped at 0.97)",
            ],
            "CONJECTURE": [
                "Λ as a per-circuit trust gate (szl-lambda-gate; Λ = Conjecture 1, gray — never green)",
                "signed-attribution-receipt-per-write chain (design-only; nothing minted on a GET)",
                "the interpretability + Λ-governance + signed-receipt synthesis as one surface "
                "(unshipped combination)",
            ],
        },
        "honest_note": (
            "MODELED + CONJECTURE. The sparse-feature population, circuit composition, "
            "attribution effect, and faithfulness / sufficiency checks are a "
            "deterministic seeded simulation; attribution, faithfulness, "
            "consistency_rate, admits/gated_out and trust are genuinely computed, "
            "reported not fabricated. It does NOT train a real sparse autoencoder, run "
            "attribution/ablation patching on a real model, execute automated circuit "
            "discovery, or reproduce any cited system's results. The SZL SYNTHESIS is "
            "CONJECTURE: Λ as a per-circuit trust gate is the szl-lambda-gate advisory "
            "Λ = Conjecture 1 (gray, NEVER green, not a theorem), and the "
            "signed-attribution-receipt-per-write chain is a DESIGN — no receipt is "
            "minted here (RECEIPT-ON-WRITE, never on a GET); the receipt_preview_digest "
            "is a plain UNSIGNED content hash, not a signature. Trust is capped at 0.97 "
            "and is never 1.0. Cites Towards Monosemanticity (Transformer Circuits "
            "2023), Sparse Autoencoders (arXiv:2309.08600), JumpReLU SAE "
            "(arXiv:2407.14435), ACDC (arXiv:2304.14997), IOI circuit "
            "(arXiv:2211.00593), Attribution Patching / AtP* (arXiv:2403.00745). SZL "
            "claims NONE of these methods as its own. Nothing here is in the locked-8."
        ),
        "citations": CITATIONS,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    })
    return JSONResponse({"label": "MODELED", "payload": p})


def register(app, ns: str = "a11oy"):
    """Wire /api/<ns>/v1/frontier/lgmi onto app. Additive, try/except-guarded."""
    base = f"/api/{ns}/v1/frontier"
    handlers = [(f"{base}/lgmi", _h_lgmi)]
    add_api_route = getattr(app, "add_api_route", None)
    for path, fn in handlers:
        if callable(add_api_route):
            app.add_api_route(path, fn, methods=["GET"])
        else:
            app.router.routes.append(Route(path, fn))
    return [p for p, _ in handlers]


if __name__ == "__main__":
    p = _decompose(seed=42, n_features=64, n_circuits=48, sparsity=0.08)
    p["receipt_design"] = _receipt_design(p, 42)
    g = p["lambda_gate"]
    a = p["attribution"]
    assert 0.0 <= g["trust"] <= _TRUST_CAP, "trust must be capped at 0.97"
    assert g["bounds"]["max"] < 1.0, "Λ advisory must never reach 1.0 (Conjecture 1)"
    assert p["receipt_design"]["signed"] is False, "no signing on a read path"
    assert p["receipt_design"]["minted_on_this_get"] is False
    assert g["admits"] + g["gated_out"] == a["circuits"]
    # determinism: same seed => same digest
    p2 = _decompose(seed=42, n_features=64, n_circuits=48, sparsity=0.08)
    p2["receipt_design"] = _receipt_design(p2, 42)
    assert p2["receipt_design"]["receipt_preview_digest"] == p["receipt_design"]["receipt_preview_digest"]
    print("features:", p["n_features"], "circuits:", a["circuits"], "admitted:", a["admitted"], "gated_out:", a["gated_out"])
    print("mean_attribution:", a["mean_attribution"], "mean_faithfulness:", a["mean_faithfulness"])
    print("consistency_rate:", a["consistency_rate"], "dead_feature_rate:", a["dead_feature_rate"], "mean_lambda:", g["mean_lambda_advisory"])
    print("trust:", g["trust"], "(cap", _TRUST_CAP, ")", "lambda_status:", g["status"])
    print("receipt signed:", p["receipt_design"]["signed"], "preview_digest:", p["receipt_design"]["receipt_preview_digest"][:16], "...")
    print("label: MODELED (synthesis parts CONJECTURE)")
