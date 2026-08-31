"""
szl_ternary.py — SZL native 1.58-bit ternary-weight (BitNet b1.58) endpoint.

Exposes a MODELED, deterministic reproduction of the BitNet b1.58 BitLinear
ternary-quantization + multiply-free integer-arithmetic MECHANISM on a small
synthetic weight matrix, as a same-origin REST endpoint so the `ternary` surface
organ has a live, honest, citable data source — never fabricated, never faked.

  GET  /api/<ns>/v1/ternary/quantize?seed=&rows=&cols=&batch=&act_bits=

Returned JSON fields (all consumed by static/3d/surfaces/ternary.js)
--------------------------------------------------------------------
  label                    : "MODELED" (mechanism repro on a toy matrix — NOT the
                             trained BitNet model). Returned verbatim; never upgraded.
  rows, cols, batch        : synthetic problem dimensions
  act_bits                 : activation bit-width (absmax int quantization)
  beta                     : gamma = mean(|W|) absmean scale (BitLinear)
  sparsity                 : fraction of weights that ternarize to 0
  ternary_counts           : {neg, zero, pos} exact counts in the ternarized matrix
  bits_per_weight_ternary  : log2(3) ≈ 1.585 (the "1.58-bit" figure)
  compression_vs_fp16/32   : storage-shrink ratios vs fp16 / fp32
  rel_l2_error             : MEASURED relative L2 error of the ternary matmul vs fp
  cosine_error             : MEASURED (1 - cosine similarity) of the two outputs
  float_muls_full          : per-weight float multiplies of the full matmul
  float_muls_ternary       : residual float multiplies after ternarization (dequant
                             scale only — the per-weight multiplies are eliminated)
  muls_eliminated          : float_muls_full - float_muls_ternary
  muls_eliminated_frac     : eliminated fraction (0..1)
  int_ops_ternary          : integer add/sub ops that replace the float multiplies
  fidelity_label           : "MEASURED" (rel_l2_error / cosine_error are real deltas)
  honest_note              : plain-language honesty disclaimer
  citations                : dict of citable sources (verbatim, never claimed as ours)
  computed_at              : ISO-8601 UTC timestamp

HONEST STATUS — "MODELED" (with MEASURED fidelity deltas)
  This is a deterministic reproduction of the ternary-quantization and multiply-free
  arithmetic MECHANISM on a small synthetic matrix. It is NOT the trained BitNet
  b1.58 model; it does not reproduce downstream accuracy, the 2B-param / 4T-token
  training, or the paper's energy figures. The compression ratios are exact
  arithmetic; the rel_l2_error / cosine_error are MEASURED (genuinely computed
  deltas between the fp and ternary matmul on this toy matrix) and are reported,
  not hidden. "Matches full precision" is Microsoft's claim about their trained
  model — the estate does not independently verify it.

CITATIONS (clean-room; none claimed as SZL's own; verified to resolve 2026-07-07):
  BitNet b1.58 2B4T Technical Report (Microsoft Research):
    arXiv:2504.12285  https://arxiv.org/abs/2504.12285
  "The Era of 1-bit LLMs: All Large Language Models are in 1.58 Bits" (genealogy):
    arXiv:2402.17764  https://arxiv.org/abs/2402.17764
  Official open weights: https://huggingface.co/microsoft/bitnet-b1.58-2B-4T
  Official inference stack: https://github.com/microsoft/BitNet

DOCTRINE v11: NOTHING here is in the locked-8. Λ = Conjecture 1. Trust < 100%.
  No fabricated data. Pure stdlib. Deterministic with seed. 0 runtime CDN.
"""
import math
from datetime import datetime, timezone

from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse

CITATIONS = {
    "BitNet b1.58 2B4T — Microsoft Research arXiv:2504.12285": "https://arxiv.org/abs/2504.12285",
    "The Era of 1-bit LLMs — arXiv:2402.17764": "https://arxiv.org/abs/2402.17764",
    "Official weights — microsoft/bitnet-b1.58-2B-4T": "https://huggingface.co/microsoft/bitnet-b1.58-2B-4T",
    "Official inference stack — github.com/microsoft/BitNet": "https://github.com/microsoft/BitNet",
}

_BITS_PER_WEIGHT_TERNARY = math.log2(3.0)  # ≈ 1.5849625 — the "1.58-bit" figure


def _lcg(seed):
    """Deterministic 0..1 generator (linear congruential); pure stdlib, seedable."""
    s = (seed * 2654435761 + 1013904223) & 0xFFFFFFFF
    while True:
        s = (1664525 * s + 1013904223) & 0xFFFFFFFF
        yield s / 4294967295.0


def _gauss(gen):
    """Box–Muller standard normal from a uniform generator (deterministic)."""
    u1 = max(1e-12, next(gen))
    u2 = next(gen)
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


def _quantize(seed=42, rows=32, cols=32, batch=16, act_bits=8):
    """Genuine BitNet b1.58 BitLinear ternarization + measured matmul fidelity.

    W (rows x cols) synthetic Gaussian weights; ternarized via absmean scale
    gamma = mean(|W|), W_t = clip(round(W/gamma), -1, 1). Activations X (batch x
    cols) quantized to act_bits via per-row absmax. We MEASURE the relative L2 and
    cosine error between the full-precision matmul Y = X Wᵀ and the ternary matmul
    Y_q = X_q (gamma·W_t)ᵀ. All deltas are genuinely computed, not fabricated.
    """
    gw = _lcg(seed)
    W = [[_gauss(gw) for _ in range(cols)] for _ in range(rows)]

    # --- BitLinear ternarization (absmean scale) ---
    abs_sum = sum(abs(W[r][c]) for r in range(rows) for c in range(cols))
    n_w = rows * cols
    beta = abs_sum / n_w if n_w else 0.0
    inv_beta = 1.0 / beta if beta > 0 else 0.0

    Wt = [[max(-1, min(1, int(round(W[r][c] * inv_beta)))) for c in range(cols)]
          for r in range(rows)]

    neg = sum(1 for r in range(rows) for c in range(cols) if Wt[r][c] == -1)
    pos = sum(1 for r in range(rows) for c in range(cols) if Wt[r][c] == 1)
    zero = n_w - neg - pos
    sparsity = zero / n_w if n_w else 0.0

    # --- synthetic activations X (batch x cols), act_bits absmax quantization ---
    ga = _lcg(seed + 7919)
    X = [[_gauss(ga) for _ in range(cols)] for _ in range(batch)]
    qmax = (1 << (act_bits - 1)) - 1  # symmetric signed range, e.g. 127 for 8-bit
    Xq = []
    for b in range(batch):
        amax = max((abs(v) for v in X[b]), default=0.0)
        scale = (amax / qmax) if (amax > 0 and qmax > 0) else 0.0
        inv = (1.0 / scale) if scale > 0 else 0.0
        row_q = [(max(-qmax, min(qmax, int(round(v * inv)))) * scale) for v in X[b]]
        Xq.append(row_q)

    # --- full-precision vs ternary matmul (MEASURED fidelity) ---
    num = 0.0   # ||Y_q - Y||^2
    den = 0.0   # ||Y||^2
    dot = 0.0   # <Y_q, Y>
    nq = 0.0    # ||Y_q||^2
    for b in range(batch):
        for r in range(rows):
            yf = 0.0
            yq = 0.0
            xb = X[b]
            xqb = Xq[b]
            Wr = W[r]
            Wtr = Wt[r]
            for c in range(cols):
                yf += xb[c] * Wr[c]
                yq += xqb[c] * (beta * Wtr[c])
            d = yq - yf
            num += d * d
            den += yf * yf
            dot += yq * yf
            nq += yq * yq
    rel_l2_error = math.sqrt(num / den) if den > 0 else 0.0
    cosine = (dot / math.sqrt(nq * den)) if (nq > 0 and den > 0) else 0.0
    cosine_error = 1.0 - cosine

    # --- arithmetic profile ---
    float_muls_full = batch * rows * cols
    # per-weight float multiplies vanish; a single dequant scale per output remains
    float_muls_ternary = batch * rows
    muls_eliminated = float_muls_full - float_muls_ternary
    muls_elim_frac = muls_eliminated / float_muls_full if float_muls_full else 0.0
    # nonzero ternary weights become integer add(+1)/sub(-1) accumulations
    int_ops_ternary = batch * (neg + pos)

    return {
        "rows": rows, "cols": cols, "batch": batch, "act_bits": act_bits,
        "beta": round(beta, 6),
        "sparsity": round(sparsity, 6),
        "ternary_counts": {"neg": neg, "zero": zero, "pos": pos},
        "bits_per_weight_ternary": round(_BITS_PER_WEIGHT_TERNARY, 6),
        "compression_vs_fp16": round(16.0 / _BITS_PER_WEIGHT_TERNARY, 4),
        "compression_vs_fp32": round(32.0 / _BITS_PER_WEIGHT_TERNARY, 4),
        "rel_l2_error": round(rel_l2_error, 6),
        "cosine_error": round(cosine_error, 6),
        "float_muls_full": float_muls_full,
        "float_muls_ternary": float_muls_ternary,
        "muls_eliminated": muls_eliminated,
        "muls_eliminated_frac": round(muls_elim_frac, 6),
        "int_ops_ternary": int_ops_ternary,
    }


def _ii(req, key, default):
    try:
        return int(float(req.query_params.get(key, default)))
    except Exception:
        return default


def _h_quantize(req: Request):
    seed     = _ii(req, "seed", 42)
    rows     = max(2, min(_ii(req, "rows", 32), 128))
    cols     = max(2, min(_ii(req, "cols", 32), 128))
    batch    = max(1, min(_ii(req, "batch", 16), 128))
    act_bits = max(2, min(_ii(req, "act_bits", 8), 16))

    q = _quantize(seed=seed, rows=rows, cols=cols, batch=batch, act_bits=act_bits)
    q.update({
        "label": "MODELED",
        "fidelity_label": "MEASURED",
        "model": "BitNet b1.58 BitLinear ternarization {-1,0,+1}, absmean scale",
        "seed": seed,
        "honest_note": (
            "MODELED: deterministic reproduction of the BitNet b1.58 ternary-"
            "quantization + multiply-free integer-arithmetic MECHANISM on a small "
            "synthetic matrix — NOT the trained model. Compression ratios are exact "
            "arithmetic; rel_l2_error / cosine_error are MEASURED (genuinely computed "
            "deltas between the fp and ternary matmul, reported not hidden). Does not "
            "reproduce downstream accuracy, the 2B-param/4T-token training, or the "
            "paper's energy figures. 'Matches full precision' is Microsoft's claim "
            "about their trained model — the estate does not independently verify it. "
            "Cites arXiv:2504.12285 (BitNet b1.58 2B4T) and arXiv:2402.17764 (Era of "
            "1-bit LLMs). SZL claims NONE of these methods as its own."
        ),
        "citations": CITATIONS,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    })
    return JSONResponse(q)


def register(app, ns: str = "a11oy"):
    """Wire /api/<ns>/v1/ternary/quantize onto app. Additive, try/except-guarded."""
    base = f"/api/{ns}/v1/ternary"
    handlers = [(f"{base}/quantize", _h_quantize)]
    add_api_route = getattr(app, "add_api_route", None)
    for path, fn in handlers:
        if callable(add_api_route):
            app.add_api_route(path, fn, methods=["GET"])
        else:
            app.router.routes.append(Route(path, fn))
    return [p for p, _ in handlers]


if __name__ == "__main__":
    q = _quantize(seed=42, rows=32, cols=32, batch=16, act_bits=8)
    print("beta:", q["beta"])
    print("ternary_counts:", q["ternary_counts"], "sparsity:", q["sparsity"])
    print("bits/weight:", q["bits_per_weight_ternary"],
          "comp16:", q["compression_vs_fp16"], "comp32:", q["compression_vs_fp32"])
    print("rel_l2_error (MEASURED):", q["rel_l2_error"],
          "cosine_error (MEASURED):", q["cosine_error"])
    print("muls_eliminated_frac:", q["muls_eliminated_frac"],
          "int_ops_ternary:", q["int_ops_ternary"])
    print("label: MODELED")
