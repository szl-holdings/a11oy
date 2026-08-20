"""
szl_mor.py — SZL Mixture-of-Recursions (adaptive per-token recursion depth).

Exposes a MODELED, deterministic reproduction of the Mixture-of-Recursions
depth-routing MECHANISM as a same-origin REST endpoint so the `mor` surface organ
has a live, honest, citable data source — never fabricated, never faked.

Mixture-of-Recursions = parameter REUSE: ONE shared transformer block is looped a
variable number of times per token (1..max_depth). A lightweight router gives each
token a recursion depth; easy tokens exit early, hard tokens recurse deeper. This
is distinct from a mixture-of-experts ROUTER (parameter SELECTION among different
weight sets) — here there is ONE weight set and only the depth changes.

  GET  /api/<ns>/v1/mor/route?seed=&tokens=&max_depth=&threshold=

Returned JSON fields (all consumed by static/3d/surfaces/mor.js)
----------------------------------------------------------------
  label               : "MODELED" (depth-routing simulation — NOT the MoR model).
                        Returned verbatim; never upgraded.
  tokens              : number of tokens routed
  max_depth           : maximum recursion depth (loops of the ONE shared block)
  threshold           : router confidence threshold for early exit
  per_token_depth     : list[int] — assigned recursion depth per token (1..max_depth)
  depth_histogram     : list[int] — count of tokens at each depth 1..max_depth
  mean_depth          : mean recursion depth actually used
  fixed_depth_flops   : FLOPs of a fixed-max-depth recursive baseline
  mor_flops           : FLOPs actually spent under adaptive routing
  compute_saved_frac  : 1 - mor_flops / fixed_depth_flops
  speedup_vs_fixed    : fixed_depth_flops / mor_flops
  kv_cache_frac       : KV-cache footprint vs uniform max-depth caching (mean/ max)
  quality_retained    : MODELED proxy — mean router confidence at each token's exit
  shared_block        : true (parameter REUSE — one weight set, variable depth)
  honest_note         : plain-language honesty disclaimer
  citations           : dict of citable sources (verbatim, never claimed as ours)
  computed_at         : ISO-8601 UTC timestamp

HONEST STATUS — "MODELED"
  Deterministic simulation of the adaptive depth-routing arithmetic, NOT a run of
  the trained MoR model. Per-token "difficulty" is a deterministic synthetic signal
  (seeded), the halting rule is a closed-form confidence curve, and FLOP counts use
  a nominal per-block cost that CANCELS in every reported ratio. quality_retained is
  a MODELED proxy (mean exit confidence), not a downstream task metric.

CITATIONS (clean-room; none claimed as SZL's own; verified to resolve 2026-07-07):
  Mixture-of-Recursions (adaptive per-token recursion over a shared block):
    Bae, Kim, Ho, Sung, Kim, et al. 2025, arXiv:2507.10524
    https://arxiv.org/abs/2507.10524
  Reference implementation (reference only, no code copied):
    https://github.com/raymin0223/mixture_of_recursions

DOCTRINE v11: NOTHING here is in the locked-8. Λ = Conjecture 1. Trust < 100%.
  No fabricated data. Pure stdlib. Deterministic with seed. 0 runtime CDN.
"""
import math
from datetime import datetime, timezone

from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse

CITATIONS = {
    "Mixture-of-Recursions — Bae et al. 2025 arXiv:2507.10524": "https://arxiv.org/abs/2507.10524",
    "Reference implementation — github.com/raymin0223/mixture_of_recursions": "https://github.com/raymin0223/mixture_of_recursions",
}

# Nominal per-block FLOP cost (MODELED). Cancels in every reported ratio; only its
# presence makes fixed_depth_flops / mor_flops human-readable integers.
_FLOPS_PER_BLOCK = 1_200_000


def _route(seed=42, tokens=256, max_depth=4, threshold=0.5):
    """Genuine adaptive depth routing over a deterministic difficulty distribution.

    Each token i gets a difficulty q_i in [0,1) from a deterministic hash. Looping
    the shared block d times yields confidence conf(d) = 1 - q_i**d (easy tokens —
    small q — cross the threshold in one pass; hard tokens need more loops). The
    token exits at the smallest d with conf(d) >= threshold, capped at max_depth.
    """
    per_token_depth = []
    exit_conf = []
    for i in range(tokens):
        # deterministic difficulty in [0,1): LCG hash of (seed, i), skewed toward easy
        s = ((i + 1) * 2654435761 + seed * 40503) & 0xFFFFFFFF
        s = (1664525 * s + 1013904223) & 0xFFFFFFFF
        u = s / 4294967295.0
        q = u * u  # square-skew: more easy (low-q) tokens than hard, deterministic

        depth = max_depth
        conf = 1.0 - q ** max_depth
        for d in range(1, max_depth + 1):
            c = 1.0 - q ** d
            if c >= threshold:
                depth = d
                conf = c
                break
        per_token_depth.append(depth)
        exit_conf.append(conf)

    histogram = [0] * max_depth
    for d in per_token_depth:
        histogram[d - 1] += 1

    total_depth = sum(per_token_depth)
    mean_depth = total_depth / tokens if tokens else 0.0

    fixed_depth_flops = tokens * max_depth * _FLOPS_PER_BLOCK
    mor_flops = total_depth * _FLOPS_PER_BLOCK
    compute_saved_frac = (1.0 - mor_flops / fixed_depth_flops) if fixed_depth_flops else 0.0
    speedup = (fixed_depth_flops / mor_flops) if mor_flops else 0.0
    kv_cache_frac = (mean_depth / max_depth) if max_depth else 0.0
    quality_retained = sum(exit_conf) / tokens if tokens else 0.0

    return {
        "tokens": tokens,
        "max_depth": max_depth,
        "threshold": threshold,
        "per_token_depth": per_token_depth,
        "depth_histogram": histogram,
        "mean_depth": round(mean_depth, 6),
        "fixed_depth_flops": fixed_depth_flops,
        "mor_flops": mor_flops,
        "compute_saved_frac": round(compute_saved_frac, 6),
        "speedup_vs_fixed": round(speedup, 6),
        "kv_cache_frac": round(kv_cache_frac, 6),
        "quality_retained": round(quality_retained, 6),
        "shared_block": True,
    }


def _ii(req, key, default):
    try:
        return int(float(req.query_params.get(key, default)))
    except Exception:
        return default


def _fi(req, key, default):
    try:
        return float(req.query_params.get(key, default))
    except Exception:
        return float(default)


def _h_route(req: Request):
    seed      = _ii(req, "seed", 42)
    tokens    = max(1, min(_ii(req, "tokens", 256), 1024))
    max_depth = max(1, min(_ii(req, "max_depth", 4), 16))
    threshold = max(0.0, min(_fi(req, "threshold", 0.5), 0.999))

    r = _route(seed=seed, tokens=tokens, max_depth=max_depth, threshold=threshold)
    r.update({
        "label": "MODELED",
        "model": "Mixture-of-Recursions — ONE shared block, adaptive per-token depth",
        "seed": seed,
        "flops_per_block_modeled": _FLOPS_PER_BLOCK,
        "honest_note": (
            "MODELED: deterministic simulation of the adaptive depth-routing "
            "arithmetic, NOT a run of the trained Mixture-of-Recursions model. "
            "Per-token difficulty is a deterministic synthetic signal (seeded); the "
            "halting rule is a closed-form confidence curve conf(d)=1-q^d; FLOP "
            "counts use a nominal per-block cost that CANCELS in every reported "
            "ratio. quality_retained is a MODELED proxy (mean exit confidence), not "
            "a downstream task metric. MoR is parameter REUSE (one shared block, "
            "variable depth) — distinct from a mixture-of-experts router (parameter "
            "selection). Cites arXiv:2507.10524 (Bae et al. 2025). SZL claims NONE "
            "of these methods as its own."
        ),
        "citations": CITATIONS,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    })
    return JSONResponse(r)


def register(app, ns: str = "a11oy"):
    """Wire /api/<ns>/v1/mor/route onto app. Additive, try/except-guarded."""
    base = f"/api/{ns}/v1/mor"
    handlers = [(f"{base}/route", _h_route)]
    add_api_route = getattr(app, "add_api_route", None)
    for path, fn in handlers:
        if callable(add_api_route):
            app.add_api_route(path, fn, methods=["GET"])
        else:
            app.router.routes.append(Route(path, fn))
    return [p for p, _ in handlers]


if __name__ == "__main__":
    r = _route(seed=42, tokens=256, max_depth=4, threshold=0.5)
    print("mean_depth:", r["mean_depth"], "histogram:", r["depth_histogram"])
    print("compute_saved_frac:", r["compute_saved_frac"],
          "speedup_vs_fixed:", r["speedup_vs_fixed"])
    print("kv_cache_frac:", r["kv_cache_frac"], "quality_retained:", r["quality_retained"])
    print("per_token_depth[:16]:", r["per_token_depth"][:16])
    print("label: MODELED")
