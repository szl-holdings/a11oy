"""
szl_sparsemoe.py — SZL Extreme-Sparsity MoE Analyzer. An HONEST, STRUCTURAL-ONLY
visualizer/estimator of the activation-ratio ↔ inference-cost tradeoff for
Mixture-of-Experts configurations.

Frontier context (cited, NEVER claimed as SZL's own): the July-2026 state of open
source is defined by extreme-sparsity MoE — e.g. GLM-5.2 ships ≈744B TOTAL parameters
with ≈40B ACTIVE per token (≈5.4% activation) under an MIT license (see llmcheck.net
state-of-open-source, July 2026, and the Anthony Maio "Checkpoint" survey). a11oy does
NOT run, host, or reproduce a 744B model. This surface is a deterministic STRUCTURAL
estimator: given a user-supplied (total, active, quant) it computes the activation
ratio, a frozen-weight VRAM footprint estimate, an active-slice footprint, and a
relative cost-per-token curve versus a dense model of the same total size. Every number
is MODELED / STRUCTURAL-ONLY (an arithmetic model of the config), never MEASURED — there
is no live GPU/node reading behind it.

  GET  /api/<ns>/v1/frontier/sparsemoe?total=&active=&quant=&dense_baseline=

Returned JSON (top-level `label`, metrics nested under `payload`)
----------------------------------------------------------------------------
  label                       : "STRUCTURAL-ONLY"
  payload.total_params_b      : total parameter count (billions)
  payload.active_params_b     : active parameter count per token (billions)
  payload.quant               : weight quant format key (fp16/bf16/fp8/int4/int8/ternary)
  payload.bytes_per_param     : modeled bytes/param for that quant
  payload.activation_ratio    : active / total (the sparsity headline)
  payload.frozen_weight_vram_gb : full-model frozen-weight VRAM estimate (all experts resident)
  payload.active_slice_vram_gb  : per-token active-slice weight VRAM estimate
  payload.relative_cost_per_token : active-FLOP cost relative to a dense model of `total`
  payload.curve[]             : sampled (active_ratio, relative_cost) points for the UI curve
  payload.reference_configs[] : cited frontier points (GLM-5.2 etc.) plotted for scale
  payload.parts_labeled       : which parts are STRUCTURAL-ONLY vs MODELED
  payload.honest_note         : plain-language honesty disclaimer
  payload.citations           : dict of citable sources (verbatim, never claimed as ours)
  payload.computed_at         : ISO-8601 UTC timestamp

HONEST STATUS
  STRUCTURAL-ONLY / MODELED — the activation ratio, VRAM footprints, and cost curve are
    a closed-form arithmetic MODEL of a MoE config. They are genuinely COMPUTED from the
    (total, active, quant) inputs and reported, not fabricated; but nothing here loads or
    runs a real model, so no value is ever MEASURED. The GLM-5.2 / frontier reference
    points are cited public figures plotted for scale, NOT a claim that a11oy runs them.

DOCTRINE v11
  Nothing here is in the locked-8 (adds 0). Λ stays Conjecture 1 (advisory, gray, never
  green). No fabricated data; no MEASURED label without a live reading. Pure stdlib.
  Deterministic. 0 runtime CDN. RECEIPT-ON-WRITE, NOT ON-READ (this GET signs nothing).

CITATIONS (clean-room; none claimed as SZL's own; verified to resolve 2026-07-08):
  State of Open-Source LLMs (activation-ratio / GLM-5.2 744B-total ~40B-active, MIT):
    llmcheck.net — state-of-open-source, July 2026   https://llmcheck.net/
  Anthony Maio, "Checkpoint" (open-source frontier survey, July 2026):
    https://checkpoint.anthonymaio.com/
  DeepSeekMoE (fine-grained expert specialization; the sparse-activation lineage):
    Dai et al. 2024, arXiv:2401.06066   https://arxiv.org/abs/2401.06066
  Mixtral of Experts (sparse-MoE serving reference):
    Jiang et al. 2024, arXiv:2401.04088   https://arxiv.org/abs/2401.04088
"""
import hashlib
from datetime import datetime, timezone

from starlette.requests import Request
from starlette.routing import Route
from starlette.responses import JSONResponse

CITATIONS = {
    "State of Open-Source LLMs (GLM-5.2 ~744B total / ~40B active, MIT) — llmcheck.net July 2026": "https://llmcheck.net/",
    "Anthony Maio — Checkpoint open-source frontier survey (July 2026)": "https://checkpoint.anthonymaio.com/",
    "DeepSeekMoE — Dai et al. 2024 arXiv:2401.06066": "https://arxiv.org/abs/2401.06066",
    "Mixtral of Experts — Jiang et al. 2024 arXiv:2401.04088": "https://arxiv.org/abs/2401.04088",
}

# Modeled bytes-per-parameter by weight quant format (STRUCTURAL estimate; a real
# deployment's footprint also carries KV-cache + activations + overhead, not modeled here).
_QUANT_BYTES = {
    "fp16": 2.0, "bf16": 2.0, "fp8": 1.0, "int8": 1.0,
    "int4": 0.5, "nf4": 0.5, "ternary": 0.2,   # 1.58-bit ≈ 0.2 bytes/param (packed)
}
_DEFAULT_QUANT = "fp8"
_TRUST_CAP = 0.97          # doctrine hard cap on any advisory trust (never green / 1.0)

# Cited frontier reference points (public figures; plotted for scale, NOT run here).
_REFERENCE_CONFIGS = [
    {"name": "GLM-5.2 (open, MIT)", "total_b": 744.0, "active_b": 40.0, "note": "cited: llmcheck.net July 2026"},
    {"name": "Mixtral 8x22B", "total_b": 141.0, "active_b": 39.0, "note": "cited: arXiv:2401.04088"},
    {"name": "DeepSeek-V3-class", "total_b": 671.0, "active_b": 37.0, "note": "cited: DeepSeekMoE lineage arXiv:2401.06066"},
]


def _bytes_per_param(quant: str) -> float:
    return _QUANT_BYTES.get((quant or "").strip().lower(), _QUANT_BYTES[_DEFAULT_QUANT])


def _analyze(total_b=744.0, active_b=40.0, quant=_DEFAULT_QUANT, dense_baseline=None):
    """Closed-form STRUCTURAL model of a MoE config's sparsity/cost tradeoff.

    total_b / active_b are in BILLIONS of parameters. activation_ratio = active/total.
    frozen_weight_vram = total_params * bytes_per_param (all experts resident in VRAM,
    the dominant serving cost for sparse MoE); active_slice_vram = active_params *
    bytes_per_param (the weights actually touched per token). relative_cost_per_token is
    active-FLOP cost vs a DENSE model of `dense_baseline` (defaults to `total_b`) total
    params — i.e. how much cheaper the sparse forward is than dense-of-same-size.
    """
    total_b = max(0.001, min(float(total_b), 100000.0))
    active_b = max(0.001, min(float(active_b), total_b))
    q = (quant or _DEFAULT_QUANT).strip().lower()
    if q not in _QUANT_BYTES:
        q = _DEFAULT_QUANT
    bpp = _bytes_per_param(q)
    dense_b = float(dense_baseline) if dense_baseline else total_b
    dense_b = max(0.001, min(dense_b, 100000.0))

    activation_ratio = round(active_b / total_b, 6)
    frozen_vram = round(total_b * 1e9 * bpp / (1024 ** 3), 3)     # GiB, all weights resident
    active_vram = round(active_b * 1e9 * bpp / (1024 ** 3), 3)    # GiB, per-token active slice
    # Relative active-FLOP cost per token vs dense-of-baseline (dense touches all params).
    relative_cost = round(active_b / dense_b, 6)

    # Sampled curve for the UI: relative cost as activation ratio sweeps 1%..100% at fixed total.
    curve = []
    for i in range(1, 21):
        r = i / 20.0
        curve.append({
            "activation_ratio": round(r, 4),
            "active_b": round(total_b * r, 4),
            "relative_cost_per_token": round((total_b * r) / dense_b, 6),
        })

    refs = []
    for rc in _REFERENCE_CONFIGS:
        refs.append({
            "name": rc["name"],
            "total_b": rc["total_b"],
            "active_b": rc["active_b"],
            "activation_ratio": round(rc["active_b"] / rc["total_b"], 6),
            "note": rc["note"],
        })

    return {
        "total_params_b": round(total_b, 4),
        "active_params_b": round(active_b, 4),
        "quant": q,
        "bytes_per_param": bpp,
        "dense_baseline_b": round(dense_b, 4),
        "activation_ratio": activation_ratio,
        "activation_pct": round(activation_ratio * 100.0, 4),
        "frozen_weight_vram_gb": frozen_vram,
        "active_slice_vram_gb": active_vram,
        "relative_cost_per_token": relative_cost,
        "curve": curve,
        "reference_configs": refs,
    }


def _receipt_design(payload, seed_str):
    """UNSIGNED content-hash preview of the analysis (design-only).

    RECEIPT-ON-WRITE, NOT ON-READ: this GET mints nothing and grows no chain. We compute
    a plain SHA-256 over a canonical config summary and return it as a clearly UNSIGNED
    preview (signed:false). A real deployment would emit a signed Khipu receipt only on a
    persisted analysis WRITE, never on this read path.
    """
    canonical = "|".join([
        f"seed={seed_str}",
        f"total_b={payload['total_params_b']}",
        f"active_b={payload['active_params_b']}",
        f"quant={payload['quant']}",
        f"activation_ratio={payload['activation_ratio']}",
        f"frozen_vram_gb={payload['frozen_weight_vram_gb']}",
        f"relative_cost={payload['relative_cost_per_token']}",
    ])
    return {
        "kind": "sparse-moe-analysis-receipt (STRUCTURAL-ONLY design — no model run)",
        "binds": [
            "config (total, active, quant) supplied by the caller",
            "computed activation_ratio + VRAM footprints + relative cost",
        ],
        "signature": "DSSE_PLACEHOLDER (cosign founder-gated) — NOT applied here",
        "signed": False,
        "minted_on_this_get": False,
        "receipt_preview_digest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "preview_digest_alg": "SHA-256 over a canonical config summary (UNSIGNED preview only)",
        "doctrine": "RECEIPT-ON-WRITE, NOT ON-READ — a GET signs nothing and grows no chain.",
    }


def _ff(req, key, default):
    try:
        return float(req.query_params.get(key, default))
    except Exception:
        return default


def _h_sparsemoe(req: Request):
    total = _ff(req, "total", 744.0)
    active = _ff(req, "active", 40.0)
    quant = req.query_params.get("quant", _DEFAULT_QUANT)
    dense_baseline = req.query_params.get("dense_baseline")
    try:
        dense_baseline = float(dense_baseline) if dense_baseline is not None else None
    except Exception:
        dense_baseline = None

    p = _analyze(total_b=total, active_b=active, quant=quant, dense_baseline=dense_baseline)
    seed_str = f"{p['total_params_b']}/{p['active_params_b']}/{p['quant']}"
    p["receipt_design"] = _receipt_design(p, seed_str)
    p.update({
        "label": "STRUCTURAL-ONLY",
        "model": ("closed-form MoE activation-ratio ↔ inference-cost estimator "
                  "(frozen-weight VRAM + active-slice VRAM + relative cost-per-token). "
                  "No model is loaded or run — STRUCTURAL-ONLY."),
        "parts_labeled": {
            "STRUCTURAL-ONLY": [
                "activation ratio (active/total)",
                "frozen-weight VRAM footprint (all experts resident)",
                "active-slice VRAM footprint (weights touched per token)",
                "relative cost-per-token vs dense-of-same-total",
                "the sampled cost curve",
            ],
            "MODELED": [
                "bytes-per-param by quant format (approximate; excludes KV-cache/activations/overhead)",
            ],
            "CITED (not ours)": [
                "GLM-5.2 744B-total / ~40B-active MIT (llmcheck.net July 2026)",
                "Anthony Maio Checkpoint survey",
                "DeepSeekMoE (arXiv:2401.06066), Mixtral (arXiv:2401.04088)",
            ],
        },
        "honest_note": (
            "STRUCTURAL-ONLY. Every number is a closed-form arithmetic MODEL of a MoE "
            "config, genuinely computed from the supplied (total, active, quant) and "
            "reported — not fabricated — but a11oy loads or runs NO model here, so nothing "
            "is MEASURED. The frozen-weight VRAM estimate assumes all experts resident and "
            "ignores KV-cache, activations, and runtime overhead; treat it as a lower-bound "
            "sketch, not a capacity guarantee. The GLM-5.2 (≈744B total / ≈40B active, MIT) "
            "and other reference points are CITED public figures (llmcheck.net July 2026; "
            "Anthony Maio Checkpoint; DeepSeekMoE arXiv:2401.06066; Mixtral arXiv:2401.04088) "
            "plotted for scale — a11oy claims NONE of these systems as its own and does not "
            "run a 744B model. Λ stays Conjecture 1. Nothing here is in the locked-8."
        ),
        "citations": CITATIONS,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    })
    return JSONResponse({"label": "STRUCTURAL-ONLY", "payload": p})


def register(app, ns: str = "a11oy"):
    """Wire /api/<ns>/v1/frontier/sparsemoe onto app. Additive, try/except-guarded."""
    base = f"/api/{ns}/v1/frontier"
    handlers = [(f"{base}/sparsemoe", _h_sparsemoe)]
    add_api_route = getattr(app, "add_api_route", None)
    for path, fn in handlers:
        if callable(add_api_route):
            app.add_api_route(path, fn, methods=["GET"])
        else:
            app.router.routes.append(Route(path, fn))
    return [p for p, _ in handlers]


if __name__ == "__main__":
    p = _analyze(total_b=744.0, active_b=40.0, quant="fp8")
    p["receipt_design"] = _receipt_design(p, "744.0/40.0/fp8")
    assert 0.0 < p["activation_ratio"] < 1.0, "activation ratio must be a proper fraction < 1"
    assert abs(p["activation_ratio"] - (40.0 / 744.0)) < 1e-6
    assert p["active_slice_vram_gb"] < p["frozen_weight_vram_gb"], "active slice < full frozen footprint"
    assert 0.0 < p["relative_cost_per_token"] < 1.0, "sparse forward must be cheaper than dense-of-same-total"
    assert p["receipt_design"]["signed"] is False and p["receipt_design"]["minted_on_this_get"] is False
    assert len(p["curve"]) == 20 and p["curve"][-1]["activation_ratio"] == 1.0
    print("activation_ratio:", p["activation_ratio"], "(", p["activation_pct"], "% active )")
    print("frozen_weight_vram_gb:", p["frozen_weight_vram_gb"], "active_slice_vram_gb:", p["active_slice_vram_gb"])
    print("relative_cost_per_token:", p["relative_cost_per_token"])
    print("receipt preview:", p["receipt_design"]["receipt_preview_digest"][:16], "... signed:", p["receipt_design"]["signed"])
    print("label: STRUCTURAL-ONLY")
