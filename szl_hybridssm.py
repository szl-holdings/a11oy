"""
szl_hybridssm.py — SZL HYBRIDSSM: a MODELED comparison of attention vs
state-space (SSM) vs hybrid architectures on the compute / memory frontier.

The 2024-2026 architecture white-space this surface fills: pure Transformer
attention is exact-recall-strong but pays a KV cache that grows LINEARLY with
context and a per-token compute that grows linearly with context at decode time;
pure state-space models (Mamba) carry a CONSTANT recurrent state (no growing KV
cache) and constant per-token compute, but a fixed state is a bottleneck for
precise long-context recall; the HYBRID family (Jamba, Griffin, Samba, Zamba)
interleaves a MINORITY of (global or sliding-window) attention layers with a
MAJORITY of SSM / gated-recurrent layers to recover attention-grade recall at a
fraction of the attention memory / compute.

  GET  /api/<ns>/v1/frontier/hybridssm?d_model=&n_layers=&seq_max=

This endpoint returns a MODELED model of that frontier: for a reference model
size (d_model, n_layers) it computes, ACROSS a sweep of sequence lengths and for
each architecture, an ANALYTIC (closed-form) KV-cache memory curve, a per-token
decode-compute (FLOPs) curve, and an ILLUSTRATIVE long-context exact-recall
proxy. Every number is COMPUTED from the stated architecture composition and the
documented cost coefficients — none is a measured benchmark score.

Returned JSON (top-level `label`, metrics nested under `payload`)
----------------------------------------------------------------------------
  label                       : "MODELED" (analytic cost curves; illustrative
                                quality proxy — NOT measured benchmark numbers).
  payload.d_model             : reference model width used for the cost model
  payload.n_layers            : reference layer count
  payload.bytes_per_elem      : KV element size (bf16 = 2 bytes)
  payload.state_dim           : modeled SSM state dim (d_state)
  payload.seq_lengths[]       : the swept context lengths
  payload.architectures[]     : per-arch {name, family, attn_type, window,
                                composition {global_attn, sliding_attn, ssm},
                                citation, curve[], summary}
      curve[]                 : per seq_len {seq_len, kv_cache_mb,
                                flops_per_token_gflops, recall_proxy}
      summary                 : at seq_max {kv_cache_mb, flops_per_token_gflops,
                                recall_proxy, kv_vs_attention, flops_vs_attention}
  payload.frontier            : cross-arch summary at seq_max {attention_kv_mb,
                                min_hybrid_kv_mb, ssm_kv_mb, best_kv_reduction,
                                best_flops_reduction}
  payload.advisory            : MODELED Λ-advisory pick (Λ = Conjecture 1, gray;
                                trust capped ≤0.97; never green, never a mandate)
  payload.parts_labeled       : which parts are MODELED vs CONJECTURE
  payload.honest_note         : plain-language honesty disclaimer
  payload.citations           : dict of citable sources (verbatim, never claimed as ours)
  payload.computed_at         : ISO-8601 UTC timestamp

HONEST STATUS
  MODELED — the KV-cache memory and per-token decode FLOPs are ANALYTIC
    closed-form functions of the (documented) architecture composition and the
    stated cost coefficients: an attention layer keeps 2·d·L·bytes of KV per
    token and costs ~4·d·ctx FLOPs/token; a sliding-window attention layer caps
    both at the window W; an SSM / gated-recurrent layer keeps a CONSTANT state
    and costs a constant per token. These are genuinely computed, reported not
    fabricated. The long-context recall_proxy is an ILLUSTRATIVE quality model
    (a coverage ratio over the exactly-reachable context), NOT a measured
    benchmark: it encodes the qualitative, published finding that a fixed SSM
    state trades some exact long-range recall while (global or windowed)
    attention layers restore it. It does NOT run any of the cited models, does
    NOT measure FLOPs/latency/memory on hardware, and reports NO benchmark
    accuracy numbers.
  CONJECTURE — the per-architecture COMPOSITIONS (how many attention vs SSM
    layers, window sizes) are MODELED approximations of the published designs,
    not their exact released configs; and the Λ-advisory architecture pick is
    the SZL restraint advisory Λ = Conjecture 1 (gray, NEVER green), an advisory
    ranking of a MODELED cost/quality trade-off, never a mandate or a guarantee.

DOCTRINE v11
  Nothing here is in the locked-8 (adds 0). Λ = Conjecture 1 (gray, never green).
  Advisory trust is capped at 0.97 and is never 1.0. Curves are MODELED, never
  MEASURED (no profiler / no hardware). recall_proxy is illustrative, capped
  below 1.0, and NEVER presented as a benchmark. No fabricated numbers. Pure
  stdlib. Deterministic. 0 runtime CDN. This GET signs nothing and grows no chain.

CITATIONS (clean-room; none claimed as SZL's own; verified to resolve 2026-07-07):
  Mamba: Linear-Time Sequence Modeling with Selective State Spaces —
    Gu & Dao 2023, arXiv:2312.00752            https://arxiv.org/abs/2312.00752
  Jamba: A Hybrid Transformer-Mamba Language Model —
    Lieber et al. 2024, arXiv:2403.19887       https://arxiv.org/abs/2403.19887
  Griffin: Mixing Gated Linear Recurrences with Local Attention for Efficient
    Language Models — De et al. 2024, arXiv:2402.19427
    https://arxiv.org/abs/2402.19427
  Samba: Simple Hybrid State Space Models for Efficient Unlimited Context
    Language Modeling — Ren et al. 2024, arXiv:2406.07522
    https://arxiv.org/abs/2406.07522
  Zamba: A Compact 7B SSM Hybrid Model — Glorioso et al. 2024, arXiv:2405.16712
    https://arxiv.org/abs/2405.16712
"""
import math
from datetime import datetime, timezone

from starlette.requests import Request
from starlette.routing import Route
from starlette.responses import JSONResponse

CITATIONS = {
    "Mamba: Linear-Time Sequence Modeling w/ Selective State Spaces — Gu & Dao 2023 arXiv:2312.00752": "https://arxiv.org/abs/2312.00752",
    "Jamba: A Hybrid Transformer-Mamba Language Model — Lieber et al. 2024 arXiv:2403.19887": "https://arxiv.org/abs/2403.19887",
    "Griffin: Mixing Gated Linear Recurrences w/ Local Attention — De et al. 2024 arXiv:2402.19427": "https://arxiv.org/abs/2402.19427",
    "Samba: Simple Hybrid State Space Models for Unlimited Context — Ren et al. 2024 arXiv:2406.07522": "https://arxiv.org/abs/2406.07522",
    "Zamba: A Compact 7B SSM Hybrid Model — Glorioso et al. 2024 arXiv:2405.16712": "https://arxiv.org/abs/2405.16712",
}

# MODELED cost coefficients (reported verbatim; NOT measured on any device).
_BYTES_PER_ELEM = 2          # bf16 KV element (K and V each store d_model per token per layer)
_STATE_DIM = 16              # modeled SSM state dim (d_state), ~Mamba default
_TRUST_CAP = 0.97            # doctrine hard cap on advisory trust (never green / never 1.0)
_RECALL_FLOOR = 0.55         # illustrative recall proxy floor (no arch drops below this)
_RECALL_SPAN = 0.42          # recall proxy = floor + span * coverage_ratio (max 0.97, never 1.0)
_SSM_RECALL_SPAN = 4096      # modeled effective exact-recall span of a fixed SSM state (illustrative)

# Default sequence-length sweep (context lengths), powers of two.
_SEQ_DEFAULT = [512, 1024, 2048, 4096, 8192, 16384, 32768, 65536, 131072]

# Architecture compositions over `n_layers` layers. Each is a MODELED
# approximation of the published design (NOT its exact released config):
#   global  — full (global) attention layer: KV cache and compute grow with L.
#   sliding — sliding-window attention layer of width `window`: KV / compute
#             capped at the window (constant beyond W).
#   ssm     — SSM / gated-recurrent layer: constant state, constant per-token cost.
# fractions are given as (global, sliding, ssm) weights that are normalized to
# n_layers; `window` applies to the sliding fraction.
_ARCHS = [
    {
        "name": "attention", "family": "dense Transformer (baseline)",
        "attn_type": "global", "window": 0,
        "w_global": 1.0, "w_sliding": 0.0, "w_ssm": 0.0, "window_size": 0,
        "citation": "dense Transformer baseline (reference; not a cited system)",
        "note": "All layers full global attention — KV cache and decode compute grow linearly with context (the cost the hybrids attack).",
    },
    {
        "name": "mamba", "family": "pure SSM",
        "attn_type": "none", "window": 0,
        "w_global": 0.0, "w_sliding": 0.0, "w_ssm": 1.0, "window_size": 0,
        "citation": "Mamba arXiv:2312.00752",
        "note": "All layers selective-SSM — constant recurrent state (no growing KV), constant per-token compute; a fixed state limits exact long-range recall (modeled).",
    },
    {
        "name": "jamba", "family": "hybrid (Transformer-Mamba, MoE)",
        "attn_type": "global (1:7)", "window": 0,
        "w_global": 1.0, "w_sliding": 0.0, "w_ssm": 7.0, "window_size": 0,
        "citation": "Jamba arXiv:2403.19887",
        "note": "~1 global-attention layer per 8 (1:7 attn:SSM) — global attention restores exact recall at ~1/8 the attention KV.",
    },
    {
        "name": "griffin", "family": "hybrid (gated linear recurrence + local attn)",
        "attn_type": "sliding (local)", "window": 1024,
        "w_global": 0.0, "w_sliding": 1.0, "w_ssm": 2.0, "window_size": 1024,
        "citation": "Griffin arXiv:2402.19427",
        "note": "Gated linear recurrences (RG-LRU) with LOCAL attention (window 1024) — KV cache is bounded by the window (constant beyond it).",
    },
    {
        "name": "samba", "family": "hybrid (Mamba + sliding-window attn)",
        "attn_type": "sliding (SWA)", "window": 2048,
        "w_global": 0.0, "w_sliding": 1.0, "w_ssm": 1.0, "window_size": 2048,
        "citation": "Samba arXiv:2406.07522",
        "note": "Mamba interleaved with sliding-window attention (window 2048) — bounded KV; SSM carries the long-range gist for unlimited-context extrapolation.",
    },
    {
        "name": "zamba", "family": "hybrid (Mamba backbone + shared global attn)",
        "attn_type": "global (shared)", "window": 0,
        "w_global": 2.0, "w_sliding": 0.0, "w_ssm": 30.0, "window_size": 0,
        "citation": "Zamba arXiv:2405.16712",
        "note": "Mamba backbone with a small, weight-SHARED global-attention block applied periodically — a few global-attention layers restore recall at a low KV cost.",
    },
]


def _compose(arch, n_layers):
    """Split n_layers into (global, sliding, ssm) counts from the arch weights."""
    wg, wsl, wss = arch["w_global"], arch["w_sliding"], arch["w_ssm"]
    total = wg + wsl + wss
    if total <= 0:
        return 0, 0, n_layers
    g = int(round(n_layers * wg / total))
    sl = int(round(n_layers * wsl / total))
    ss = n_layers - g - sl
    if ss < 0:  # rounding overflow — trim from the largest attention bucket
        if g >= sl:
            g += ss
        else:
            sl += ss
        ss = 0
    # a pure-attention / pure-ssm arch keeps at least its defining layer type
    return max(0, g), max(0, sl), max(0, ss)


def _layer_const_flops(d_model):
    """Per-layer per-token FLOPs that do NOT depend on context length L.

    Projections (~8·d² for q/k/v/o or in/out/dt) + MLP (~4·d·d_ff, d_ff=4d),
    with the standard factor-2 (multiply-add) convention. Reported as a MODELED
    coefficient; a real profile would replace it with a MEASURED counter.
    """
    d_ff = 4 * d_model
    proj = 8 * d_model * d_model
    mlp = 4 * d_model * d_ff
    return proj + mlp


def _arch_curve(arch, d_model, n_layers, seq_lengths):
    """Analytic KV / compute / recall curves across the sequence-length sweep."""
    g, sl, ss = _compose(arch, n_layers)
    window = arch["window_size"]
    const_flops = _layer_const_flops(d_model)
    ssm_scan_flops = 4 * d_model * _STATE_DIM      # constant selective-scan per token
    kv_bytes_per_tok_layer = 2 * d_model * _BYTES_PER_ELEM  # K and V

    curve = []
    for L in seq_lengths:
        sliding_ctx = min(L, window) if window > 0 else 0

        # KV cache (bytes): global attn layers keep L tokens, sliding keep the
        # window, SSM layers keep only a constant state (not a growing KV cache).
        kv_bytes = kv_bytes_per_tok_layer * (g * L + sl * sliding_ctx)
        kv_mb = kv_bytes / (1024.0 * 1024.0)

        # Per-token decode FLOPs: every layer pays the constant backbone; an
        # attention mixing term (~4·d·ctx) is added per attention layer; SSM
        # layers add only the constant scan.
        mix_global = 4 * d_model * L
        mix_sliding = 4 * d_model * sliding_ctx
        flops = (n_layers * const_flops
                 + g * mix_global
                 + sl * mix_sliding
                 + ss * ssm_scan_flops)
        gflops = flops / 1e9

        # Illustrative long-context exact-recall proxy (NOT a benchmark): the
        # modeled probability that a long-range token is "exactly reachable" by
        # AT LEAST ONE mechanism in the stack. Even a FEW global-attention layers
        # route the full context (diminishing in count), so recall is NOT linear
        # in the attention-layer fraction — it saturates. Sliding attention
        # reaches only its window; a fixed SSM state reaches a modeled effective
        # span. coverage combines the mechanisms and maps to a bounded quality
        # proxy that is always < 1.0.
        cov_global = (1.0 - math.exp(-g / 1.5)) if g > 0 else 0.0
        cov_sliding = (min(L, window) / L) if (sl > 0 and window > 0) else 0.0
        cov_ssm = (min(L, _SSM_RECALL_SPAN) / L) if ss > 0 else 0.0
        cov_local = max(cov_sliding, cov_ssm)
        coverage = 1.0 - (1.0 - cov_global) * (1.0 - cov_local)
        coverage = max(0.0, min(1.0, coverage))
        recall = _RECALL_FLOOR + _RECALL_SPAN * coverage
        recall = round(min(_TRUST_CAP, recall), 6)

        curve.append({
            "seq_len": L,
            "kv_cache_mb": round(kv_mb, 4),
            "flops_per_token_gflops": round(gflops, 4),
            "recall_proxy": recall,
        })
    return g, sl, ss, curve


def _model(d_model=4096, n_layers=32, seq_lengths=None):
    """Deterministic MODELED attention/SSM/hybrid frontier over the sweep."""
    d_model = max(64, min(d_model, 16384))
    n_layers = max(1, min(n_layers, 200))
    seq_lengths = seq_lengths or _SEQ_DEFAULT
    seq_max = seq_lengths[-1]

    architectures = []
    attn_summary = None
    for arch in _ARCHS:
        g, sl, ss, curve = _arch_curve(arch, d_model, n_layers, seq_lengths)
        last = curve[-1]
        summary = {
            "kv_cache_mb": last["kv_cache_mb"],
            "flops_per_token_gflops": last["flops_per_token_gflops"],
            "recall_proxy": last["recall_proxy"],
        }
        entry = {
            "name": arch["name"],
            "family": arch["family"],
            "attn_type": arch["attn_type"],
            "window": arch["window"],
            "composition": {"global_attn": g, "sliding_attn": sl, "ssm": ss},
            "citation": arch["citation"],
            "note": arch["note"],
            "curve": curve,
            "summary": summary,
        }
        architectures.append(entry)
        if arch["name"] == "attention":
            attn_summary = summary

    # cross-arch ratios at seq_max (vs the dense-attention baseline).
    a_kv = attn_summary["kv_cache_mb"] if attn_summary else 0.0
    a_fl = attn_summary["flops_per_token_gflops"] if attn_summary else 0.0
    for e in architectures:
        s = e["summary"]
        s["kv_vs_attention"] = round(s["kv_cache_mb"] / a_kv, 6) if a_kv else None
        s["flops_vs_attention"] = round(s["flops_per_token_gflops"] / a_fl, 6) if a_fl else None

    hybrids = [e for e in architectures if e["name"] not in ("attention", "mamba")]
    ssm_entry = next((e for e in architectures if e["name"] == "mamba"), None)
    min_hybrid = min(hybrids, key=lambda e: e["summary"]["kv_cache_mb"]) if hybrids else None

    frontier = {
        "seq_max": seq_max,
        "attention_kv_mb": a_kv,
        "ssm_kv_mb": ssm_entry["summary"]["kv_cache_mb"] if ssm_entry else None,
        "min_hybrid": min_hybrid["name"] if min_hybrid else None,
        "min_hybrid_kv_mb": min_hybrid["summary"]["kv_cache_mb"] if min_hybrid else None,
        "best_kv_reduction_x": (round(a_kv / min_hybrid["summary"]["kv_cache_mb"], 2)
                                if (min_hybrid and min_hybrid["summary"]["kv_cache_mb"] > 0) else None),
        "best_flops_reduction_x": (round(a_fl / min_hybrid["summary"]["flops_per_token_gflops"], 2)
                                   if (min_hybrid and min_hybrid["summary"]["flops_per_token_gflops"] > 0) else None),
    }

    advisory = _advisory(architectures, seq_max)

    return {
        "d_model": d_model,
        "n_layers": n_layers,
        "bytes_per_elem": _BYTES_PER_ELEM,
        "state_dim": _STATE_DIM,
        "seq_lengths": seq_lengths,
        "architectures": architectures,
        "frontier": frontier,
        "advisory": advisory,
    }


def _advisory(architectures, seq_max):
    """MODELED Λ-advisory architecture pick at seq_max (Λ = Conjecture 1, gray).

    Ranks architectures by a MODELED cost/quality score = recall_proxy penalized
    by a log-memory and log-compute cost. The pick is ADVISORY (gray, never
    green); trust is hard-capped at _TRUST_CAP and never 1.0. This is a ranking
    of a MODELED trade-off, NOT a mandate or a performance guarantee.
    """
    scored = []
    for e in architectures:
        s = e["summary"]
        kv = max(1e-6, s["kv_cache_mb"])
        fl = max(1e-6, s["flops_per_token_gflops"])
        # higher recall is good; higher memory/compute is bad (log-damped).
        cost = math.log10(kv + 1.0) + math.log10(fl + 1.0)
        score = s["recall_proxy"] / (1.0 + 0.12 * cost)
        scored.append((score, e["name"], s["recall_proxy"], s["kv_cache_mb"], s["flops_per_token_gflops"]))
    scored.sort(reverse=True)
    best = scored[0]
    # advisory trust rises with the margin over the median but is capped.
    med = scored[len(scored) // 2][0]
    margin = (best[0] - med) / best[0] if best[0] > 0 else 0.0
    trust = round(min(_TRUST_CAP, 0.60 + 0.5 * margin), 6)
    return {
        "status": "Λ = Conjecture 1 (advisory, gray — NEVER green, not a mandate/guarantee)",
        "at_seq_len": seq_max,
        "recommended": best[1],
        "recommended_recall_proxy": best[2],
        "recommended_kv_cache_mb": best[3],
        "recommended_flops_per_token_gflops": best[4],
        "trust": trust,
        "trust_cap": _TRUST_CAP,
        "ranking": [{"arch": n, "score": round(sc, 6)} for sc, n, *_ in scored],
        "basis": ("MODELED cost/quality: illustrative recall_proxy penalized by "
                  "log KV-memory + log decode-FLOPs at seq_max. Advisory ranking "
                  "of a MODELED trade-off — not a benchmark, mandate, or guarantee."),
    }


def _ii(req, key, default):
    try:
        return int(float(req.query_params.get(key, default)))
    except Exception:
        return default


def _h_hybridssm(req: Request):
    d_model = max(64, min(_ii(req, "d_model", 4096), 16384))
    n_layers = max(1, min(_ii(req, "n_layers", 32), 200))
    seq_max = _ii(req, "seq_max", 0)
    seq_lengths = _SEQ_DEFAULT
    if seq_max and seq_max >= 512:
        seq_lengths = [L for L in _SEQ_DEFAULT if L <= seq_max] or [512]
        if seq_lengths[-1] != seq_max and seq_max <= 1_048_576:
            seq_lengths = seq_lengths + [seq_max]

    p = _model(d_model=d_model, n_layers=n_layers, seq_lengths=seq_lengths)
    p.update({
        "label": "MODELED",
        "model": ("attention vs state-space vs hybrid (Jamba/Griffin/Samba/Zamba) "
                  "compute/memory frontier — analytic MODELED cost curves"),
        "parts_labeled": {
            "MODELED": [
                "KV-cache memory curve (analytic: 2·d·L·bytes per global-attn layer, "
                "windowed for sliding-attn, constant state for SSM)",
                "per-token decode FLOPs curve (constant backbone + ~4·d·ctx per "
                "attention layer + constant SSM scan)",
                "long-context recall_proxy (illustrative coverage ratio — NOT a "
                "measured benchmark; capped below 1.0)",
            ],
            "CONJECTURE": [
                "per-architecture compositions / window sizes (MODELED approximations "
                "of the published designs, not their exact released configs)",
                "the Λ-advisory architecture pick (Λ = Conjecture 1, gray — an "
                "advisory ranking of a MODELED trade-off, never green/mandate/guarantee)",
            ],
        },
        "honest_note": (
            "MODELED + CONJECTURE. The KV-cache-memory and per-token decode-FLOPs "
            "curves are ANALYTIC closed-form functions of the documented "
            "architecture composition and the stated cost coefficients: a global "
            "attention layer keeps 2·d·L·bytes of KV and costs ~4·d·L FLOPs/token; "
            "a sliding-window layer caps both at the window; an SSM/gated-recurrent "
            "layer keeps a CONSTANT state and constant per-token cost. These are "
            "genuinely computed, reported not fabricated. The recall_proxy is an "
            "ILLUSTRATIVE quality model (a coverage ratio over the exactly-reachable "
            "context), NOT a measured benchmark accuracy — it encodes the "
            "qualitative published finding that a fixed SSM state trades some exact "
            "long-range recall while (global or windowed) attention layers restore "
            "it. This surface does NOT run any cited model, does NOT profile "
            "FLOPs/latency/memory on hardware, and reports NO benchmark numbers — "
            "curves are MODELED, never MEASURED. The per-arch compositions and "
            "window sizes are MODELED approximations of the published designs. The "
            "Λ-advisory pick is the SZL restraint advisory Λ = Conjecture 1 (gray, "
            "NEVER green), an advisory ranking of a MODELED trade-off, never a "
            "mandate or guarantee; its trust is capped at 0.97 and is never 1.0. "
            "Cites Mamba (arXiv:2312.00752), Jamba (arXiv:2403.19887), Griffin "
            "(arXiv:2402.19427), Samba (arXiv:2406.07522), Zamba (arXiv:2405.16712). "
            "SZL claims NONE of these architectures as its own. Nothing here is in "
            "the locked-8."
        ),
        "citations": CITATIONS,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    })
    return JSONResponse({"label": "MODELED", "payload": p})


def register(app, ns: str = "a11oy"):
    """Wire /api/<ns>/v1/frontier/hybridssm onto app. Additive, try/except-guarded."""
    base = f"/api/{ns}/v1/frontier"
    handlers = [(f"{base}/hybridssm", _h_hybridssm)]
    add_api_route = getattr(app, "add_api_route", None)
    for path, fn in handlers:
        if callable(add_api_route):
            app.add_api_route(path, fn, methods=["GET"])
        else:
            app.router.routes.append(Route(path, fn))
    return [p for p, _ in handlers]


if __name__ == "__main__":
    p = _model()
    archs = {e["name"]: e for e in p["architectures"]}
    fr = p["frontier"]
    adv = p["advisory"]
    # doctrine + sanity assertions
    assert adv["trust"] <= _TRUST_CAP, "advisory trust must be capped at 0.97"
    for e in p["architectures"]:
        for pt in e["curve"]:
            assert pt["recall_proxy"] < 1.0, "recall proxy must never reach 1.0"
    a = archs["attention"]["summary"]["kv_cache_mb"]
    m = archs["mamba"]["summary"]["kv_cache_mb"]
    # pure SSM must carry far less KV than dense attention at long context.
    assert m < a, "SSM KV cache must be lower than attention at seq_max"
    # every hybrid must sit between attention and pure SSM on KV memory (or below).
    for h in ("jamba", "griffin", "samba", "zamba"):
        assert archs[h]["summary"]["kv_cache_mb"] <= a, f"{h} KV must be <= attention"
    # compute at seq_max: attention must be the heaviest.
    a_fl = archs["attention"]["summary"]["flops_per_token_gflops"]
    for h in ("mamba", "jamba", "griffin", "samba", "zamba"):
        assert archs[h]["summary"]["flops_per_token_gflops"] <= a_fl, f"{h} FLOPs must be <= attention"
    print("seq_max:", fr["seq_max"])
    for e in p["architectures"]:
        s = e["summary"]
        print(f"  {e['name']:10s} comp={e['composition']} "
              f"KV={s['kv_cache_mb']:>12.2f} MB  GFLOP/tok={s['flops_per_token_gflops']:>8.2f}  "
              f"recall~{s['recall_proxy']:.3f}")
    print("frontier:", fr)
    print("advisory (Λ=Conjecture 1, gray):", adv["recommended"], "trust", adv["trust"], "(cap", _TRUST_CAP, ")")
    print("label: MODELED (compositions + Λ-advisory CONJECTURE)")
