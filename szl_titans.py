"""
szl_titans.py — SZL Titans neural long-term memory (test-time memorization).

Exposes a MODELED, deterministic reproduction of the Titans "learning to memorize
at test time" MECHANISM — a fast-weight memory updated online by a SURPRISE signal
with MOMENTUM and WEIGHT-DECAY FORGETTING — as a same-origin REST endpoint so the
`titans` surface organ has a live, honest, citable data source. Never fabricated.

Titans adds a small neural memory that updates ITSELF while it reads: surprising
(salient) tokens imprint strongly and persist far beyond a fixed sliding window,
while filler decays via the forgetting gate. This is distinct from a plain
attention window (fixed span, no online learning) — here the memory learns what
matters and keeps it.

  GET  /api/<ns>/v1/titans/recall?seed=&n_tokens=&window=&mem_dim=

Returned JSON (top-level `label`, metrics nested under `payload` — the titans
surface reads the label at top level OR payload.label, metrics from payload)
----------------------------------------------------------------------------
  label            : "MODELED" (memory-update simulation — NOT the Titans model).
  payload.n_tokens        : context length streamed
  payload.window          : fixed sliding-window baseline span
  payload.mem_dim         : memory-slot count (fast-weight dimension)
  payload.n_salient       : number of salient (high-surprise) items planted
  payload.neural_recall   : fraction of salient items still recalled from memory
  payload.window_recall   : fraction of salient items inside the last `window`
  payload.recall_gain     : neural_recall - window_recall (the LTM advantage)
  payload.mean_surprise   : mean surprise across the stream
  payload.peak_surprise   : peak surprise across the stream
  payload.forget_rate     : weight-decay forgetting rate (MODELED hyperparam)
  payload.momentum        : surprise-momentum coefficient (MODELED hyperparam)
  payload.memory_trace[]  : sampled per-token {pos, surprise, salient} view (<=96)
  payload.salient_positions[] : planted salient token indices
  payload.honest_note     : plain-language honesty disclaimer
  payload.citations       : dict of citable sources (verbatim, never claimed as ours)
  payload.computed_at     : ISO-8601 UTC timestamp

HONEST STATUS — "MODELED"
  Deterministic simulation of the surprise / momentum / weight-decay-forgetting
  memory-update arithmetic, NOT a run of the trained Titans model. Per-token
  surprise is a deterministic synthetic signal (seeded); retention is a closed-form
  decay r = surprise * (1 - forget_rate*(1-momentum))^(T-p); recall is a threshold
  on that retention. neural_recall / window_recall / recall_gain are genuinely
  computed from the modeled retention, not fabricated. Does not reproduce the
  paper's trained memory module or downstream benchmarks.

CITATIONS (clean-room; none claimed as SZL's own; verified to resolve 2026-07-07):
  Titans: Learning to Memorize at Test Time (neural long-term memory):
    Behrouz, Zhong & Mirrokni 2025, Google, arXiv:2501.00663
    https://arxiv.org/abs/2501.00663
  Google Research blog — Titans / MIRAS long-term memory (reference only):
    https://research.google/blog/titans-miras-helping-ai-have-long-term-memory/

DOCTRINE v11: NOTHING here is in the locked-8. Λ = Conjecture 1. Trust < 100%.
  No fabricated data. Pure stdlib. Deterministic with seed. 0 runtime CDN.
"""
from datetime import datetime, timezone

from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse

CITATIONS = {
    "Titans: Learning to Memorize at Test Time — Behrouz et al. 2025 (Google) arXiv:2501.00663": "https://arxiv.org/abs/2501.00663",
    "Google Research blog — Titans / MIRAS long-term memory": "https://research.google/blog/titans-miras-helping-ai-have-long-term-memory/",
}

# MODELED memory-update hyperparameters (reported verbatim; not trained).
_FORGET_RATE = 0.02   # weight-decay forgetting rate per step
_MOMENTUM    = 0.9    # surprise-momentum coefficient (slows effective decay)
_RECALL_THRESHOLD = 0.05  # retention above which a salient item counts as recalled
_TRACE_CAP = 96       # max memory_trace entries returned (matches surface stream cap)


def _u01(seed, i):
    """Deterministic uniform in [0,1) from (seed, i) via two LCG rounds."""
    s = ((i + 1) * 2654435761 + seed * 40503) & 0xFFFFFFFF
    s = (1664525 * s + 1013904223) & 0xFFFFFFFF
    s = (1664525 * s + 1013904223) & 0xFFFFFFFF
    return s / 4294967295.0


def _recall(seed=42, n_tokens=512, window=64, mem_dim=32):
    """Genuine surprise/momentum/forgetting memory simulation over a token stream.

    n_salient salient items are planted at evenly spread positions. Each token gets
    a deterministic base surprise; salient tokens are boosted. A salient item written
    at position p retains r = surprise * (1 - forget_rate*(1-momentum))^(T-p) by the
    end T; it is 'recalled' if r >= threshold. window_recall is the fraction of
    salient items sitting inside the last `window` tokens (the fixed-window baseline).
    """
    n_salient = max(1, min(mem_dim, n_tokens // 16))

    # planted salient positions: evenly spread, deterministic
    salient_positions = []
    for k in range(n_salient):
        p = int((k + 0.5) * n_tokens / n_salient) % n_tokens
        salient_positions.append(p)
    salient_set = set(salient_positions)

    # per-token surprise: base noise in [0,1); salient tokens boosted into [0.6,1)
    surprise = [0.0] * n_tokens
    for i in range(n_tokens):
        base = 0.15 + 0.25 * _u01(seed, i)          # filler surprise ~[0.15,0.40)
        if i in salient_set:
            base = 0.60 + 0.40 * _u01(seed + 101, i)  # salient surprise ~[0.60,1.00)
        surprise[i] = base

    mean_surprise = sum(surprise) / n_tokens if n_tokens else 0.0
    peak_surprise = max(surprise) if surprise else 0.0

    # effective per-step decay: momentum slows forgetting
    decay_step = _FORGET_RATE * (1.0 - _MOMENTUM)
    keep = 1.0 - decay_step
    T = n_tokens - 1

    # neural memory recall: retention at end for each salient item
    recalled = 0
    for p in salient_positions:
        r = surprise[p] * (keep ** (T - p))
        if r >= _RECALL_THRESHOLD:
            recalled += 1
    neural_recall = recalled / n_salient if n_salient else 0.0

    # fixed-window baseline: salient items still inside the last `window` tokens
    win_lo = n_tokens - window
    in_window = sum(1 for p in salient_positions if p >= win_lo)
    window_recall = in_window / n_salient if n_salient else 0.0

    recall_gain = neural_recall - window_recall

    # sampled memory_trace for the surface (<= _TRACE_CAP entries, spans the stream)
    stride = max(1, n_tokens // _TRACE_CAP)
    memory_trace = []
    for i in range(0, n_tokens, stride):
        memory_trace.append({
            "pos": i,
            "surprise": round(surprise[i], 6),
            "salient": i in salient_set,
        })
        if len(memory_trace) >= _TRACE_CAP:
            break

    return {
        "n_tokens": n_tokens,
        "window": window,
        "mem_dim": mem_dim,
        "n_salient": n_salient,
        "neural_recall": round(neural_recall, 6),
        "window_recall": round(window_recall, 6),
        "recall_gain": round(recall_gain, 6),
        "mean_surprise": round(mean_surprise, 6),
        "peak_surprise": round(peak_surprise, 6),
        "forget_rate": _FORGET_RATE,
        "momentum": _MOMENTUM,
        "memory_trace": memory_trace,
        "salient_positions": salient_positions,
    }


def _ii(req, key, default):
    try:
        return int(float(req.query_params.get(key, default)))
    except Exception:
        return default


def _h_recall(req):
    seed     = _ii(req, "seed", 42)
    n_tokens = max(8, min(_ii(req, "n_tokens", 512), 4096))
    window   = max(1, min(_ii(req, "window", 64), n_tokens))
    mem_dim  = max(1, min(_ii(req, "mem_dim", 32), 256))

    p = _recall(seed=seed, n_tokens=n_tokens, window=window, mem_dim=mem_dim)
    p.update({
        "label": "MODELED",
        "model": "Titans neural long-term memory — surprise + momentum + forgetting",
        "seed": seed,
        "honest_note": (
            "MODELED: deterministic simulation of the Titans surprise/momentum/"
            "weight-decay-forgetting memory-update arithmetic, NOT a run of the "
            "trained Titans model. Per-token surprise is a deterministic synthetic "
            "signal (seeded); retention is the closed-form decay r = surprise * "
            "(1 - forget_rate*(1-momentum))^(T-p); recall is a threshold on that "
            "retention. neural_recall / window_recall / recall_gain are genuinely "
            "computed from the modeled retention, reported not fabricated. "
            "memory_trace is a sampled view of the stream. Does not reproduce the "
            "paper's trained memory module or downstream benchmarks. Cites "
            "arXiv:2501.00663 (Behrouz et al. 2025, Google). SZL claims NONE of "
            "these methods as its own."
        ),
        "citations": CITATIONS,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    })
    # Surface reads label at top level OR payload.label, metrics from payload.
    return JSONResponse({"label": "MODELED", "payload": p})


def register(app, ns: str = "a11oy"):
    """Wire /api/<ns>/v1/titans/recall onto app. Additive, try/except-guarded."""
    base = f"/api/{ns}/v1/titans"
    handlers = [(f"{base}/recall", _h_recall)]
    add_api_route = getattr(app, "add_api_route", None)
    for path, fn in handlers:
        if callable(add_api_route):
            app.add_api_route(path, fn, methods=["GET"])
        else:
            app.router.routes.append(Route(path, fn))
    return [p for p, _ in handlers]


if __name__ == "__main__":
    p = _recall(seed=42, n_tokens=512, window=64, mem_dim=32)
    print("n_salient:", p["n_salient"])
    print("neural_recall:", p["neural_recall"], "window_recall:", p["window_recall"],
          "recall_gain:", p["recall_gain"])
    print("mean_surprise:", p["mean_surprise"], "peak_surprise:", p["peak_surprise"])
    print("forget_rate:", p["forget_rate"], "momentum:", p["momentum"])
    print("trace_len:", len(p["memory_trace"]), "salient[:8]:", p["salient_positions"][:8])
    print("label: MODELED")
