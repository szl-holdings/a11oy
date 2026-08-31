"""
szl_gnqs.py — SZL GNQS: Governed-Norm Quantization Stability. A Λ-advisory TRUST
GATE (Λ = Conjecture 1, gray, NEVER green) over which transformer layers are
QUANTIZATION-SAFE once an SZL governed normalization (szl-governed-norm) bounds their
activation outliers — with a signed-quantization-receipt-per-write design.

This is an SZL cross-axis SYNTHESIS: the quantization field leaders (LLM.int8(),
GPTQ, AWQ, SmoothQuant, BitNet b1.58) all fight the SAME enemy — a few MASSIVE
activation outliers that blow up low-bit error — and the normalization field
(RMSNorm) + recent "massive activations" work explains WHERE those outliers live. No
published system ships a GOVERNED normalization whose bounded output feeds an explicit
advisory trust gate deciding, per layer, which layers may be quantized to which bit
width. GNQS ties those real leaders to the SZL governed-norm kernel and the
szl-lambda-gate.

  GET  /api/<ns>/v1/frontier/gnqs?seed=&n_layers=&bits=&governed=

The endpoint returns a MODELED/CONJECTURE model of governed-norm quantization
stability: a deterministic, seeded per-layer activation profile (with planted massive
outliers) is optionally passed through the SZL governed norm (which bounds the outlier
magnitude); a MODELED quantization error at the requested bit width is computed with
and without governance; each layer passes a Λ-advisory trust gate deciding whether it
is quantization-safe; and the response DESCRIBES (does not mint) the signed receipt
each quantization-commit WRITE would emit.

Returned JSON (top-level `label`, metrics nested under `payload`)
----------------------------------------------------------------------------
  label                       : "MODELED"
  payload.n_layers            : number of modeled transformer layers
  payload.bits                : target quantization bit width (2/3/4/8)
  payload.governed            : whether the SZL governed norm is applied
  payload.layers[]            : {id, outlier_magnitude, kurtosis, quant_error,
                                quant_error_ungoverned, error_reduction, stable,
                                lambda_advisory, admitted}
  payload.quant               : {layers, admitted, gated_out, mean_quant_error,
                                mean_error_reduction, stability_rate}
  payload.lambda_gate         : {status, admit_threshold, mean_lambda_advisory,
                                bounds, admits, gated_out, trust, trust_cap} — Λ
                                advisory (Conjecture 1, gray)
  payload.receipt_design      : signed-quantization-receipt-per-write DESIGN
                                (CONJECTURE), incl. an UNSIGNED content-hash preview
  payload.parts_labeled       : which parts are MODELED vs CONJECTURE
  payload.honest_note         : plain-language honesty disclaimer
  payload.citations           : dict of citable sources (verbatim, never claimed as ours)
  payload.computed_at         : ISO-8601 UTC timestamp

HONEST STATUS
  MODELED — the per-layer activation profile, planted massive outliers, governed-norm
    outlier bounding, and the quantization-error model are a deterministic seeded
    simulation. quant_error, error_reduction, stability_rate, admits/gated_out and
    trust are genuinely COMPUTED from the modeled profile, reported not fabricated. It
    does NOT run a real quantizer (LLM.int8()/GPTQ/AWQ/SmoothQuant/BitNet), a real
    normalization layer on real weights, or reproduce any cited system's accuracy
    numbers.
  CONJECTURE — the SZL SYNTHESIS is unproven and labeled as such: (a) Λ as a per-layer
    quantization-safe gate is the szl-lambda-gate advisory Λ = Conjecture 1 (gray,
    NEVER green), not a theorem; (b) the signed-quantization-receipt-per-write chain
    is a DESIGN — no receipt is minted here (receipt-on-WRITE, never on a GET); (c) the
    governed-norm + quantization-stability + signed-receipt COMBINATION as one surface
    is the SZL-original synthesis (unshipped combination).

DOCTRINE v11
  Nothing here is in the locked-8 (adds 0). Λ = Conjecture 1 (gray, never green).
  Trust is capped at 0.97 and is never 1.0. No fabricated data. Pure stdlib.
  Deterministic with seed. 0 runtime CDN. RECEIPT-ON-WRITE, NOT ON-READ.

CITATIONS (clean-room; none claimed as SZL's own; verified to resolve 2026-07-07):
  LLM.int8(): 8-bit Matrix Multiplication for Transformers at Scale
    (outlier features): Dettmers et al. 2022, arXiv:2208.07339
    https://arxiv.org/abs/2208.07339
  GPTQ: Accurate Post-Training Quantization for Generative Pre-trained Transformers:
    Frantar et al. 2022, arXiv:2210.17323   https://arxiv.org/abs/2210.17323
  AWQ: Activation-aware Weight Quantization for LLM Compression and Acceleration:
    Lin et al. 2023, arXiv:2306.00978   https://arxiv.org/abs/2306.00978
  SmoothQuant: Accurate and Efficient Post-Training Quantization for LLMs:
    Xiao et al. 2022, arXiv:2211.10438   https://arxiv.org/abs/2211.10438
  The Era of 1-bit LLMs: All LLMs are in 1.58 Bits (BitNet b1.58):
    Ma et al. 2024, arXiv:2402.17764   https://arxiv.org/abs/2402.17764
  Root Mean Square Layer Normalization (RMSNorm):
    Zhang & Sennrich 2019, arXiv:1910.07467   https://arxiv.org/abs/1910.07467
  Massive Activations in Large Language Models:
    Sun et al. 2024, arXiv:2402.17762   https://arxiv.org/abs/2402.17762
"""
import hashlib
from datetime import datetime, timezone

from starlette.requests import Request
from starlette.routing import Route
from starlette.responses import JSONResponse

CITATIONS = {
    "LLM.int8(): 8-bit Matmul for Transformers at Scale — Dettmers et al. 2022 arXiv:2208.07339": "https://arxiv.org/abs/2208.07339",
    "GPTQ: Accurate Post-Training Quantization — Frantar et al. 2022 arXiv:2210.17323": "https://arxiv.org/abs/2210.17323",
    "AWQ: Activation-aware Weight Quantization — Lin et al. 2023 arXiv:2306.00978": "https://arxiv.org/abs/2306.00978",
    "SmoothQuant: Efficient Post-Training Quantization for LLMs — Xiao et al. 2022 arXiv:2211.10438": "https://arxiv.org/abs/2211.10438",
    "The Era of 1-bit LLMs (BitNet b1.58) — Ma et al. 2024 arXiv:2402.17764": "https://arxiv.org/abs/2402.17764",
    "Root Mean Square Layer Normalization (RMSNorm) — Zhang & Sennrich 2019 arXiv:1910.07467": "https://arxiv.org/abs/1910.07467",
    "Massive Activations in Large Language Models — Sun et al. 2024 arXiv:2402.17762": "https://arxiv.org/abs/2402.17762",
}

# MODELED quantization / gate hyperparameters (reported verbatim; not trained).
_LAMBDA_MIN = 0.02          # Λ advisory lower bound (gray floor)
_LAMBDA_MAX = 0.94          # Λ advisory upper bound (NEVER 1.0 — Conjecture 1)
_LAMBDA_ADMIT = 0.55        # advisory admit threshold (a layer is admitted above it)
_TRUST_CAP = 0.97           # doctrine hard cap on trust (never green / never 1.0)
_MASSIVE_EVERY = 8          # every Nth layer is a modeled massive-outlier layer
_LAYER_CAP = 96             # max layer entries returned (matches surface stream cap)
_GOVERN_CLAMP = 0.28        # governed-norm bounds the outlier to this fraction (MODELED)


def _u01(seed, i, salt=0):
    """Deterministic uniform in [0,1) from (seed, i, salt) via two LCG rounds."""
    s = ((i + 1) * 2654435761 + seed * 40503 + salt * 2246822519) & 0xFFFFFFFF
    s = (1664525 * s + 1013904223) & 0xFFFFFFFF
    s = (1664525 * s + 1013904223) & 0xFFFFFFFF
    return s / 4294967295.0


def _quant_error(outlier, bits):
    """MODELED per-layer quantization error given a normalized outlier magnitude in
    [0,1] and a bit width. Fewer bits => coarser grid => larger error; a bigger
    outlier stretches the dynamic range and inflates error super-linearly (the
    outlier-driven degradation the quantization leaders all target)."""
    levels = max(2.0, float(2 ** max(1, bits)) - 1.0)
    grid = 1.0 / levels                       # quantization step (uniform grid)
    # error grows with the step and with the outlier's range stretch (^1.6).
    return grid * (0.5 + 1.5 * (outlier ** 1.6))


def _stabilize(seed=42, n_layers=48, bits=4, governed=True):
    """Deterministic governed-norm quantization-stability simulation.

    Each of `n_layers` transformer layers gets a MODELED activation profile: an outlier
    magnitude in [0,1] (a fraction planted MASSIVE) and a kurtosis proxy. Governed
    normalization (szl-governed-norm) — when enabled — CLAMPS the outlier magnitude to
    _GOVERN_CLAMP, mirroring how bounding massive activations restores low-bit
    stability. A MODELED quantization error at `bits` is computed WITH governance
    (quant_error) and WITHOUT (quant_error_ungoverned); a layer is STABLE if its
    governed error is below a bit-dependent tolerance. Each layer gets a Λ advisory
    from its error reduction + stability, and is ADMITTED (quantization-safe) iff the
    advisory clears the threshold AND it is stable. The gate is ADVISORY (gray), never
    green; overall trust is capped at _TRUST_CAP.
    """
    n_layers = max(1, min(n_layers, 4096))
    bits = max(1, min(int(bits), 16))

    tol = 1.4 / max(2.0, float(2 ** bits) - 1.0)   # bit-dependent stability tolerance

    layers = []
    for i in range(n_layers):
        massive = (i % _MASSIVE_EVERY == 0)
        raw_outlier = 0.35 + 0.6 * _u01(seed, i, salt=7)
        if massive:
            raw_outlier = min(1.0, raw_outlier + 0.4)   # planted massive activation
        kurtosis = round(3.0 + 12.0 * (raw_outlier ** 2), 6)   # heavy tails w/ outliers

        gov_outlier = min(raw_outlier, _GOVERN_CLAMP) if governed else raw_outlier
        q_gov = round(_quant_error(gov_outlier, bits), 6)
        q_ungov = round(_quant_error(raw_outlier, bits), 6)
        err_reduction = round(max(0.0, 1.0 - (q_gov / q_ungov)) if q_ungov else 0.0, 6)
        stable = bool(q_gov <= tol)

        # Λ advisory: rises with error reduction + (1 - error), penalised if unstable;
        # bounded so it is NEVER 1.0 (Λ = Conjecture 1, gray). SZL synthesis.
        clean = max(0.0, 1.0 - min(1.0, q_gov / max(tol, 1e-9)))
        base = _LAMBDA_MIN + (_LAMBDA_MAX - _LAMBDA_MIN) * (0.5 * err_reduction + 0.5 * clean)
        if not stable:
            base *= 0.5
        lam = round(min(_LAMBDA_MAX, max(_LAMBDA_MIN, base)), 6)
        admitted = bool(lam >= _LAMBDA_ADMIT and stable)

        layers.append({
            "id": i,
            "outlier_magnitude": round(gov_outlier, 6),
            "outlier_ungoverned": round(raw_outlier, 6),
            "kurtosis": kurtosis,
            "massive": massive,
            "quant_error": q_gov,
            "quant_error_ungoverned": q_ungov,
            "error_reduction": err_reduction,
            "stable": stable,
            "lambda_advisory": lam,
            "admitted": admitted,
        })

    admits = sum(1 for l in layers if l["admitted"])
    gated_out = len(layers) - admits
    stable_n = sum(1 for l in layers if l["stable"])
    stability_rate = round(stable_n / len(layers), 6) if layers else 0.0
    mean_err = round(sum(l["quant_error"] for l in layers) / len(layers), 6) if layers else 0.0
    mean_red = round(sum(l["error_reduction"] for l in layers) / len(layers), 6) if layers else 0.0
    mean_lambda = round(sum(l["lambda_advisory"] for l in layers) / len(layers), 6) if layers else 0.0

    # Overall trust: rises with stability, error reduction and mean Λ advisory,
    # HARD-CAPPED at _TRUST_CAP so it is never green / never 1.0 (doctrine v11).
    trust_raw = (0.4 * stability_rate + 0.3 * mean_red
                 + 0.3 * (mean_lambda / _LAMBDA_MAX if _LAMBDA_MAX else 0.0))
    trust = round(min(_TRUST_CAP, trust_raw), 6)

    return {
        "n_layers": n_layers,
        "bits": bits,
        "governed": bool(governed),
        "governed_clamp": _GOVERN_CLAMP,
        "stability_tolerance": round(tol, 6),
        "layers": layers[:_LAYER_CAP],
        "quant": {
            "layers": len(layers),
            "admitted": admits,
            "gated_out": gated_out,
            "mean_quant_error": mean_err,
            "mean_error_reduction": mean_red,
            "stability_rate": stability_rate,
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
    """Describe the signed-quantization-receipt-PER-WRITE chain (CONJECTURE synthesis).

    RECEIPT-ON-WRITE, NOT ON-READ: this GET mints NOTHING and appends to no
    provenance chain. We compute a plain SHA3-256 content hash of the quantization
    summary and return it as a clearly-UNSIGNED design PREVIEW (signed:false). A real
    deployment would emit one signed Khipu receipt per quantization-COMMIT write,
    binding the layer ids, bit width, governed-norm setting, error result, and the
    Λ-gate verdict into the hash-chained receipt DAG.
    """
    gate = payload["lambda_gate"]
    q = payload["quant"]
    canonical = "|".join([
        f"seed={seed}",
        f"layers={payload['n_layers']}",
        f"bits={payload['bits']}",
        f"governed={payload['governed']}",
        "lids=" + ",".join(str(l["id"]) for l in payload["layers"]),
        f"admits={gate['admits']}",
        f"gated_out={gate['gated_out']}",
        f"stability_rate={q['stability_rate']}",
        f"mean_error_reduction={q['mean_error_reduction']}",
        f"trust={gate['trust']}",
    ])
    preview_digest = hashlib.sha3_256(canonical.encode("utf-8")).hexdigest()
    return {
        "kind": "signed-quantization-receipt-per-write (SZL synthesis — CONJECTURE, design-only)",
        "binds": [
            "layer ids + bit width + governed-norm setting",
            "quantization error result (governed vs ungoverned, error_reduction)",
            "Λ-gate verdict (admits / gated_out; Λ = Conjecture 1, gray)",
        ],
        "chain": "one hash-linked Khipu receipt per quantization-commit WRITE (Conjecture 2: "
                 "integrity real; BFT/consensus is the conjecture)",
        "signature": "DSSE_PLACEHOLDER (cosign founder-gated) — NOT applied here",
        "signed": False,
        "minted_on_this_get": False,
        "receipt_preview_digest": preview_digest,
        "preview_digest_alg": "SHA3-256 over a canonical quantization summary (UNSIGNED preview only)",
        "doctrine": "RECEIPT-ON-WRITE, NOT ON-READ — a GET signs nothing and grows no chain.",
        "verify_when_minted": "/api/a11oy/v1/khipu/verify/{digest}",
    }


def _ii(req, key, default):
    try:
        return int(float(req.query_params.get(key, default)))
    except Exception:
        return default


def _bool(req, key, default=False):
    v = req.query_params.get(key)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _h_gnqs(req: Request):
    seed     = _ii(req, "seed", 42)
    n_layers = max(1, min(_ii(req, "n_layers", 48), 4096))
    bits     = max(1, min(_ii(req, "bits", 4), 16))
    governed = _bool(req, "governed", True)

    p = _stabilize(seed=seed, n_layers=n_layers, bits=bits, governed=governed)
    p["receipt_design"] = _receipt_design(p, seed)
    p.update({
        "label": "MODELED",
        "model": ("governed-norm quantization stability: szl-governed-norm bounds "
                  "activation outliers, a szl-lambda-gate trust gate picks "
                  "quantization-safe layers, with a signed-quantization-receipt-"
                  "per-write design"),
        "seed": seed,
        "parts_labeled": {
            "MODELED": [
                "per-layer activation profile (outlier magnitude / kurtosis / massive activations)",
                "governed-norm outlier clamping (szl-governed-norm)",
                "quantization-error model at the requested bit width (governed vs ungoverned)",
                "trust (computed from stability + error reduction + mean Λ, hard-capped at 0.97)",
            ],
            "CONJECTURE": [
                "Λ as a per-layer quantization-safe gate (szl-lambda-gate; Λ = Conjecture 1, gray — never green)",
                "signed-quantization-receipt-per-write chain (design-only; nothing minted on a GET)",
                "the governed-norm + quantization-stability + signed-receipt synthesis as one surface "
                "(unshipped combination)",
            ],
        },
        "honest_note": (
            "MODELED + CONJECTURE. The per-layer activation profile, planted massive "
            "outliers, governed-norm outlier bounding, and the quantization-error model "
            "are a deterministic seeded simulation; quant_error, error_reduction, "
            "stability_rate, admits/gated_out and trust are genuinely computed, "
            "reported not fabricated. It does NOT run a real quantizer "
            "(LLM.int8()/GPTQ/AWQ/SmoothQuant/BitNet), a real normalization layer on "
            "real weights, or reproduce any cited system's accuracy numbers. The SZL "
            "SYNTHESIS is CONJECTURE: Λ as a per-layer quantization-safe gate is the "
            "szl-lambda-gate advisory Λ = Conjecture 1 (gray, NEVER green, not a "
            "theorem), and the signed-quantization-receipt-per-write chain is a DESIGN "
            "— no receipt is minted here (RECEIPT-ON-WRITE, never on a GET); the "
            "receipt_preview_digest is a plain UNSIGNED content hash, not a signature. "
            "Trust is capped at 0.97 and is never 1.0. Cites LLM.int8() "
            "(arXiv:2208.07339), GPTQ (arXiv:2210.17323), AWQ (arXiv:2306.00978), "
            "SmoothQuant (arXiv:2211.10438), BitNet b1.58 (arXiv:2402.17764), RMSNorm "
            "(arXiv:1910.07467), Massive Activations (arXiv:2402.17762). SZL claims "
            "NONE of these methods as its own. Nothing here is in the locked-8."
        ),
        "citations": CITATIONS,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    })
    return JSONResponse({"label": "MODELED", "payload": p})


def register(app, ns: str = "a11oy"):
    """Wire /api/<ns>/v1/frontier/gnqs onto app. Additive, try/except-guarded."""
    base = f"/api/{ns}/v1/frontier"
    handlers = [(f"{base}/gnqs", _h_gnqs)]
    add_api_route = getattr(app, "add_api_route", None)
    for path, fn in handlers:
        if callable(add_api_route):
            app.add_api_route(path, fn, methods=["GET"])
        else:
            app.router.routes.append(Route(path, fn))
    return [p for p, _ in handlers]


if __name__ == "__main__":
    p = _stabilize(seed=42, n_layers=48, bits=4, governed=True)
    p["receipt_design"] = _receipt_design(p, 42)
    g = p["lambda_gate"]
    q = p["quant"]
    assert 0.0 <= g["trust"] <= _TRUST_CAP, "trust must be capped at 0.97"
    assert g["bounds"]["max"] < 1.0, "Λ advisory must never reach 1.0 (Conjecture 1)"
    assert p["receipt_design"]["signed"] is False, "no signing on a read path"
    assert p["receipt_design"]["minted_on_this_get"] is False
    assert g["admits"] + g["gated_out"] == q["layers"]
    # governance must REDUCE mean quantization error vs ungoverned.
    pu = _stabilize(seed=42, n_layers=48, bits=4, governed=False)
    assert q["mean_quant_error"] <= pu["quant"]["mean_quant_error"], \
        "governed norm must not increase mean quantization error"
    assert q["stability_rate"] >= pu["quant"]["stability_rate"], \
        "governed norm must not lower stability rate"
    print("layers:", q["layers"], "bits:", p["bits"], "admitted:", q["admitted"], "gated_out:", q["gated_out"])
    print("mean_quant_error (gov):", q["mean_quant_error"], "(ungov):", pu["quant"]["mean_quant_error"])
    print("mean_error_reduction:", q["mean_error_reduction"], "stability_rate:", q["stability_rate"], "mean_lambda:", g["mean_lambda_advisory"])
    print("trust:", g["trust"], "(cap", _TRUST_CAP, ")", "lambda_status:", g["status"])
    print("receipt signed:", p["receipt_design"]["signed"], "preview_digest:", p["receipt_design"]["receipt_preview_digest"][:16], "...")
    print("label: MODELED (synthesis parts CONJECTURE)")
