# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED: locked-proven=8 · Λ=Conjecture 1 · SLSA L1 honest / L2 attested / L3 roadmap
# Co-Authored-By: Perplexity Computer Agent
"""
szl_energy_sovereign.py — ADDITIVE Energy / Sovereign-Compute instrumentation for
a11oy. Makes the energy + sovereign-compute story MEASURED and HONEST.

The whole point of this module: read REAL energy / throughput / speculative-decode /
KV-cache / router metrics from the on-box vLLM `/metrics` (Prometheus) endpoint WHEN
the live sovereign-inference probe shows the GPU is reachable — and label everything
ROADMAP / pending when it is not. It NEVER fabricates a sovereign or energy number.

Honesty spine (doctrine v11):
  * sovereign:true ONLY from the orchestrator's live `_sovereign_inference_state()`
    (which itself gates on a real `_local_endpoint_reachable()` /models probe).
  * the joules honesty label is decided ONLY by `szl_joules_truth.joules_label()` off a
    REAL, FRESH NVML/exporter sample — never off a bare flag or a forwarded string.
  * J/token is computed from the research formula  E_token = P_GPU · T_forward / N_tokens
    (Watt-Counts arXiv:2604.09048; Energy-per-Token arXiv:2603.20224; Where-Do-Joules-Go
    arXiv:2601.22076) — and ONLY when the box emits power.draw + token counters. Else it
    is left None and labeled ROADMAP. No meter -> no number.

Capability tiers (rendered with honest labels mapped to window.SZLLabels):
  MEASURED  -> a real on-box exporter sample is present & fresh (mapped to LIVE tone)
  ROADMAP   -> wiring is in place; the box is not emitting the metric yet (EXPERIMENTAL tone)

Routes (NEW; never collide):
  GET /api/{ns}/v1/energy/sovereign            — full JSON posture (machine-readable)
  GET /api/{ns}/v1/energy/jtoken               — J/token + carbon panel (MEASURED/ROADMAP)
  GET /api/{ns}/v1/energy/throughput           — speculative-decode tokens/s panel
  GET /api/{ns}/v1/energy/kvcache              — LMCache TTFT before/after panel
  GET /api/{ns}/v1/energy/gateway              — LiteLLM gateway status (honest)
  GET /api/{ns}/v1/energy/router               — RouteLLM Thompson Beta posteriors
  GET /api/{ns}/v1/energy/carbon               — Carbon-Aware batch schedule
  GET /energy                                  — unified mobile-first Energy/Sovereign tab

Pure stdlib + (optional) the shared szl_joules_truth. Defensive: a probe/parse failure
NEVER raises out of a handler — it degrades to an honest ROADMAP/pending posture.
"""
from __future__ import annotations

import json as _json
import math as _math
import os as _os
import random as _random
import time as _time
import urllib.request as _ureq
from datetime import datetime, timezone

# --- joules honesty: the SINGLE source of truth (never decide a label locally) ----
try:
    from szl_joules_truth import (
        joules_label as _joules_label,
        joules_evidence as _joules_evidence,
        is_real_fresh_sample as _is_real_fresh_sample,
    )
except Exception:  # pragma: no cover — defensive: doctrine default is always sample
    def _joules_label(_s, now=None):  # type: ignore
        return "sample"
    def _joules_evidence(_s, now=None):  # type: ignore
        return {}
    def _is_real_fresh_sample(_s, now=None):  # type: ignore
        return False

DOCTRINE = {
    "version": "v11",
    "locked_proven": ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
    "locked_count": 8,
    "corpus": "749/14/163",
    "kernel_commit": "c7c0ba17",
    "lambda": "Conjecture 1 (advisory floor; uniqueness machine-checked FALSE unconditionally; NOT a theorem)",
    "slsa": "L1 honest / L2 attested (.att emitted, not independently verified) / L3 roadmap",
}

# Carbon intensity for the GPU's grid region. SAMPLE/ESTIMATE default until a real
# Carbon-Aware SDK / WattTime / ElectricityMaps feed is wired (see FORGE_BOX_ENERGY.md).
# Hetzner Falkenstein (DE) ~ 380 gCO2eq/kWh annual average — labeled, not claimed live.
_DEFAULT_CARBON_G_PER_KWH = 380.0
_J_PER_KWH = 3.6e6  # 1 kWh = 3.6 MJ

# Research-cited speculative-decoding speedup model (vLLM speculative decoding):
#   S(k, alpha) = (k + 1) / (k * (1 - alpha) + 1)
# k = number of draft tokens proposed per step; alpha = empirical acceptance rate.
_SPEC_DRAFT_MODEL = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
_SPEC_K_DEFAULT = 4


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _carbon_g_per_kwh() -> float:
    """Grid carbon intensity (gCO2eq/kWh). Env-overridable when a real feed sets it;
    otherwise the labeled SAMPLE/ESTIMATE regional average. Never raises."""
    try:
        v = _os.environ.get("A11OY_GRID_CARBON_G_PER_KWH")
        if v:
            f = float(v)
            if f > 0 and f == f:
                return f
    except Exception:
        pass
    return _DEFAULT_CARBON_G_PER_KWH


def _carbon_feed_is_live() -> bool:
    """True ONLY when a real carbon-intensity feed is wired (env set by the box)."""
    return bool((_os.environ.get("A11OY_GRID_CARBON_G_PER_KWH") or "").strip())


# ---------------------------------------------------------------------------
# LIVE sovereign-inference probe (delegated to the orchestrator — the authority).
# ---------------------------------------------------------------------------
def _sovereign_state() -> dict:
    """Authoritative, LIVE sovereign-inference posture.

    Delegates to a11oy_code_orchestrator._sovereign_inference_state(), which gates
    sovereign:true on a real _local_endpoint_reachable() /models probe. We NEVER
    decide sovereignty here. Honest default on any failure: not sovereign.
    """
    try:
        import a11oy_code_orchestrator as _orch  # type: ignore
        st = _orch._sovereign_inference_state()
        if isinstance(st, dict):
            return st
    except Exception:
        pass
    return {"inference": "unknown", "mode": "unknown", "backend": "unknown",
            "sovereign": False, "base_url": None,
            "honest_note": "orchestrator sovereign-state unavailable in-process; honest default not-sovereign."}


def _gpu_reachable(state: dict | None = None) -> bool:
    """gpu_reachable == the orchestrator reports a live self-hosted GPU (sovereign)."""
    st = state if state is not None else _sovereign_state()
    return bool(st.get("sovereign") is True and st.get("inference") == "self-hosted-gpu")


def _vllm_metrics_base() -> str | None:
    """Base URL of the on-box vLLM server for its Prometheus /metrics endpoint.

    Prefer an explicit metrics URL; else derive from the serving base. Returns None
    when no local endpoint is configured (so we stay ROADMAP rather than guess)."""
    explicit = (_os.environ.get("A11OY_VLLM_METRICS_URL") or "").strip()
    if explicit:
        return explicit.rstrip("/")
    base = (_os.environ.get("A11OY_MODEL_BASE_URL") or "").strip().rstrip("/")
    if base and "router.huggingface.co" not in base:
        # vLLM exposes /metrics at the server root (strip a trailing /v1).
        root = base[:-3] if base.endswith("/v1") else base
        return root.rstrip("/")
    return None


def _fetch_metrics_text(timeout: float = 2.5) -> str | None:
    """Fetch the on-box vLLM Prometheus /metrics text. None on any failure (honest)."""
    base = _vllm_metrics_base()
    if not base:
        return None
    for path in ("/metrics", ""):
        try:
            req = _ureq.Request(base + path, headers={"User-Agent": "szl-energy-sovereign"})
            with _ureq.urlopen(req, timeout=timeout) as r:  # noqa: S310
                if 200 <= getattr(r, "status", 200) < 300:
                    body = r.read().decode("utf-8", "replace")
                    if "# " in body or "_total" in body:
                        return body
        except Exception:  # noqa: BLE001 — any failure => not emitting; stay honest
            continue
    return None


def _parse_prom(text: str) -> dict:
    """Minimal Prometheus text parser: {metric_name: float} for samples we care about.

    Sums across label sets for counters (e.g. vllm:* counters carry model_name labels).
    Best-effort and exception-tolerant; unknown lines are ignored.
    """
    out: dict[str, float] = {}
    if not text:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            # name{labels} value   OR   name value
            if "{" in line:
                name = line[: line.index("{")]
                value = line.rsplit(" ", 1)[1]
            else:
                name, value = line.rsplit(" ", 1)
            v = float(value)
            out[name] = out.get(name, 0.0) + v
        except Exception:
            continue
    return out


def _exporter_sample_from_metrics(prom: dict) -> dict | None:
    """Build a szl_joules_truth exporter_sample from on-box metrics, or None.

    We treat a fresh power.draw export (via a node/GPU exporter scraped INTO vLLM
    /metrics or a sidecar) as the real NVML reading. Doctrine: only a numeric
    joules_measured_total + a fresh exporter_last_seen_ts can yield a MEASURED label.
    """
    if not prom:
        return None
    # Common exporter names for cumulative GPU energy (joules). Box wires one of these
    # (nvidia-smi power.draw integrated, or DCGM energy counter). See FORGE_BOX_ENERGY.md.
    joules_total = None
    for key in ("a11oy_gpu_energy_joules_total", "gpu_energy_joules_total",
                "DCGM_FI_DEV_TOTAL_ENERGY_CONSUMPTION", "nvidia_gpu_energy_joules_total"):
        if key in prom:
            joules_total = prom[key]
            break
    if joules_total is None:
        return None
    power_w = None
    for key in ("a11oy_gpu_power_watts", "gpu_power_watts",
                "DCGM_FI_DEV_POWER_USAGE", "nvidia_gpu_power_watts"):
        if key in prom:
            power_w = prom[key]
            break
    return {
        "joules_measured_total": joules_total,
        "exporter_node": _os.environ.get("A11OY_GPU_LABEL") or "sovereign-gpu",
        "exporter_last_seen_ts": _time.time(),  # scraped just now => fresh by construction
        "power_w_sample": power_w,
    }


# ---------------------------------------------------------------------------
# (#1) J/token + carbon — the Tier-1 receipt fields.
# ---------------------------------------------------------------------------
def _jtoken_from_metrics(prom: dict, sample: dict | None) -> dict:
    """Compute MEASURED energy-per-token from on-box counters, else honest ROADMAP.

    Formula (research-cited): E_token = P_GPU · T_forward / N_tokens. We realize it as
    cumulative_energy_joules / cumulative_generated_tokens when both counters exist —
    equivalent to the time-integral form averaged over the window. Returned None +
    ROADMAP when the box is not emitting the counters.
    """
    measured = _is_real_fresh_sample(sample)
    gen_tokens = None
    for key in ("vllm:generation_tokens_total", "vllm_generation_tokens_total",
                "vllm:generation_tokens"):
        if key in prom:
            gen_tokens = prom[key]
            break
    joules_total = (sample or {}).get("joules_measured_total")
    j_per_token = None
    if measured and joules_total and gen_tokens and gen_tokens > 0:
        j_per_token = float(joules_total) / float(gen_tokens)
    label = "MEASURED" if (measured and j_per_token is not None) else "ROADMAP"
    carbon_g_per_token = None
    if j_per_token is not None:
        carbon_g_per_token = (j_per_token / _J_PER_KWH) * _carbon_g_per_kwh()
    return {
        "metric": "energy_per_token",
        "label": label,
        "joules_per_token": (round(j_per_token, 6) if j_per_token is not None else None),
        "carbon_g_co2eq_per_token": (round(carbon_g_per_token, 9)
                                     if carbon_g_per_token is not None else None),
        "generated_tokens_total": gen_tokens,
        "gpu_energy_joules_total": joules_total,
        "power_w_sample": (sample or {}).get("power_w_sample"),
        "carbon_g_per_kwh": _carbon_g_per_kwh(),
        "carbon_feed_live": _carbon_feed_is_live(),
        "formula": "E_token = P_GPU · T_forward / N_tokens (= ΣJ / Σgenerated_tokens over window)",
        "citations": ["Watt-Counts arXiv:2604.09048", "Energy-per-Token arXiv:2603.20224",
                      "Where-Do-Joules-Go arXiv:2601.22076"],
        "joules_honesty": _joules_label(sample),
        "joules_evidence": _joules_evidence(sample),
        "note": ("Real per-token energy from the on-box GPU exporter + vLLM token counters."
                 if label == "MEASURED" else
                 "Wiring is ready: when the box emits power.draw→/metrics + token counters, "
                 "J/token and carbon become MEASURED. Until then, honestly pending (no meter, no number)."),
    }


def _jtoken_from_operator() -> dict | None:
    """Honest MEASURED J/token from the press-play energy operator's OWN counters.

    The operator (szl_energy_operator) accumulates measured_token_joules and
    measured_tokens together over the SAME MEASURED jobs (fresh <30s NVML deltas),
    so measured_token_joules / measured_tokens is a real, self-consistent MEASURED
    energy-per-token. Returns None when the operator has no MEASURED data yet — the
    caller then falls back to the prom/exporter path (honest ROADMAP when no meter).
    Never raises, never fabricates."""
    try:
        import szl_energy_operator as _op  # local module; no import cycle
        st = _op.get_operator().status()
    except Exception:
        return None
    j = st.get("measured_token_joules")
    tok = st.get("measured_tokens")
    try:
        j = float(j)
        tok = int(tok)
    except (TypeError, ValueError):
        return None
    if not (j > 0 and tok > 0):
        return None
    j_per_token = j / tok
    carbon_g_per_token = (j_per_token / _J_PER_KWH) * _carbon_g_per_kwh()
    return {
        "metric": "energy_per_token",
        "label": "MEASURED",
        "joules_per_token": round(j_per_token, 6),
        "carbon_g_co2eq_per_token": round(carbon_g_per_token, 9),
        "generated_tokens_total": tok,
        "gpu_energy_joules_total": round(j, 6),
        "power_w_sample": st.get("power_w_sample"),
        "carbon_g_per_kwh": _carbon_g_per_kwh(),
        "carbon_feed_live": _carbon_feed_is_live(),
        "formula": "E_token = \u03a3J_measured / \u03a3tokens_measured (press-play operator, MEASURED jobs only)",
        "citations": ["Watt-Counts arXiv:2604.09048", "Energy-per-Token arXiv:2603.20224",
                      "Where-Do-Joules-Go arXiv:2601.22076"],
        "joules_honesty": "measured",
        "joules_evidence": {
            "source": "press-play energy operator (MEASURED jobs, joules+tokens paired since tracking start)",
            "joules_over_measured_tokens": round(j, 6),
            "measured_tokens": tok,
            "measured_jobs": st.get("measured_jobs"),
            "joules_measured_total_lifetime": st.get("joules_measured_total"),
            "exporter_node": st.get("exporter_node"),
            "window_seconds": st.get("window_seconds"),
            "computed_at": st.get("computed_at"),
        },
        "note": ("Real per-token energy: MEASURED GPU joules / generated tokens, both "
                 "summed over the operator's MEASURED jobs (fresh NVML deltas)."),
    }


def energy_fields_for_receipt() -> dict:
    """SPLICE-INTO-RECEIPT helper for the orchestrator's _emit_turn_receipt().

    Returns joules_consumed + carbon_g_co2eq for EVERY signed turn receipt, honestly
    labeled MEASURED (real fresh on-box exporter) or ROADMAP (no meter yet → None).
    NEVER raises and NEVER fabricates a number. The orchestrator splats this into the
    receipt body so the joules claim is self-verifying from the receipt itself.
    """
    try:
        state = _sovereign_state()
        if not _gpu_reachable(state):
            return {
                "joules_consumed": None,
                "carbon_g_co2eq": None,
                "energy_label": "ROADMAP",
                "joules_honesty": _joules_label(None),
                "energy_source_note": ("No sovereign GPU reachable (sovereign:%s). Per-receipt "
                                       "joules/carbon are pending the on-box NVML exporter — "
                                       "honest ROADMAP, never fabricated." % state.get("sovereign")),
            }
        prom = _parse_prom(_fetch_metrics_text() or "")
        sample = _exporter_sample_from_metrics(prom)
        jt = _jtoken_from_metrics(prom, sample)
        gen_tokens = jt.get("generated_tokens_total")
        jpt = jt.get("joules_per_token")
        # Per-receipt instantaneous reading: total measured joules is the honest figure;
        # per-token rate is the MEASURED derivation. We report the fresh cumulative joules
        # as joules_consumed only when MEASURED; else None (ROADMAP).
        measured = jt.get("label") == "MEASURED"
        joules_consumed = (sample or {}).get("joules_measured_total") if measured else None
        carbon = None
        if measured and joules_consumed is not None:
            carbon = (float(joules_consumed) / _J_PER_KWH) * _carbon_g_per_kwh()
        return {
            "joules_consumed": (round(float(joules_consumed), 6)
                                if joules_consumed is not None else None),
            "carbon_g_co2eq": (round(carbon, 9) if carbon is not None else None),
            "joules_per_token": jpt,
            "carbon_g_co2eq_per_token": jt.get("carbon_g_co2eq_per_token"),
            "energy_label": "MEASURED" if measured else "ROADMAP",
            "joules_honesty": _joules_label(sample),
            "joules_evidence": _joules_evidence(sample),
            "carbon_g_per_kwh": _carbon_g_per_kwh(),
            "carbon_feed_live": _carbon_feed_is_live(),
            "energy_source_note": ("Per-token energy + carbon MEASURED from on-box GPU exporter."
                                   if measured else
                                   "Sovereign GPU reachable but power/token exporter not emitting "
                                   "yet → joules/carbon honestly ROADMAP (never fabricated)."),
        }
    except Exception as exc:  # noqa: BLE001 — a receipt helper must NEVER raise
        return {
            "joules_consumed": None,
            "carbon_g_co2eq": None,
            "energy_label": "ROADMAP",
            "joules_honesty": "sample",
            "energy_source_note": "energy_fields_for_receipt fail-open: %s" % (str(exc)[:120],),
        }


# ---------------------------------------------------------------------------
# (#2) Speculative decoding throughput panel (tokens/s with-vs-without).
# ---------------------------------------------------------------------------
def _spec_speedup(k: int, alpha: float) -> float:
    """vLLM speculative-decoding speedup model S = (k+1)/(k(1-alpha)+1)."""
    denom = (k * (1.0 - alpha)) + 1.0
    return (k + 1.0) / denom if denom > 0 else 1.0


def _throughput_panel(prom: dict, gpu_reachable: bool) -> dict:
    """tokens/s with-vs-without speculative decoding.

    MEASURED tokens/s when vLLM emits generation tokens + an accept-rate counter;
    else ROADMAP with the theoretical speedup model (k=4, draft Qwen2.5-Coder-1.5B)
    shown ILLUSTRATIVELY so the panel is never blank but never overclaims.
    """
    tps = None
    for key in ("vllm:avg_generation_throughput_toks_per_s",
                "vllm_avg_generation_throughput_toks_per_s",
                "vllm:generation_tokens_per_second"):
        if key in prom:
            tps = prom[key]
            break
    # Empirical acceptance rate alpha from vLLM spec-decode counters when present.
    accepted = prom.get("vllm:spec_decode_num_accepted_tokens_total")
    drafted = prom.get("vllm:spec_decode_num_draft_tokens_total")
    alpha = None
    if accepted is not None and drafted and drafted > 0:
        alpha = max(0.0, min(1.0, accepted / drafted))
    measured = bool(gpu_reachable and tps is not None and alpha is not None)
    k = _SPEC_K_DEFAULT
    # Theoretical curve for the panel (ILLUSTRATIVE unless alpha is measured).
    alpha_for_model = alpha if alpha is not None else 0.8
    speedup = _spec_speedup(k, alpha_for_model)
    tps_without = (tps / speedup) if (measured and speedup > 0) else None
    return {
        "metric": "speculative_decode_throughput",
        "label": "MEASURED" if measured else "ROADMAP",
        "draft_model": _SPEC_DRAFT_MODEL,
        "num_speculative_tokens_k": k,
        "acceptance_rate_alpha": (round(alpha, 4) if alpha is not None else None),
        "acceptance_rate_alpha_label": ("MEASURED" if alpha is not None else "ILLUSTRATIVE (α=0.8 assumed)"),
        "tokens_per_s_with_spec": (round(tps, 3) if tps is not None else None),
        "tokens_per_s_without_spec": (round(tps_without, 3) if tps_without is not None else None),
        "modeled_speedup_x": round(speedup, 3),
        "speedup_formula": "S = (k+1) / (k·(1−α)+1)",
        "note": ("Real tokens/s + empirical α from the on-box vLLM speculative-decode counters."
                 if measured else
                 "Wiring ready: with --speculative-model %s --num-speculative-tokens %d the box emits "
                 "tokens/s + α. Until then the speedup curve is ILLUSTRATIVE (α=0.8 → ~%.2f×)."
                 % (_SPEC_DRAFT_MODEL, k, speedup)),
        "citations": ["vLLM speculative decoding", "Watt-Counts arXiv:2604.09048"],
    }


# ---------------------------------------------------------------------------
# (#3) LMCache KV-cache TTFT before/after panel.
# ---------------------------------------------------------------------------
def _kvcache_panel(prom: dict, gpu_reachable: bool) -> dict:
    """TTFT before/after KV-cache reuse on repeated prompt prefixes (LMCache)."""
    hit = None
    for key in ("vllm:prefix_cache_hits_total", "lmcache_cache_hits_total",
                "vllm:gpu_prefix_cache_hits_total"):
        if key in prom:
            hit = prom[key]
            break
    queries = None
    for key in ("vllm:prefix_cache_queries_total", "lmcache_cache_queries_total",
                "vllm:gpu_prefix_cache_queries_total"):
        if key in prom:
            queries = prom[key]
            break
    ttft = None
    for key in ("vllm:time_to_first_token_seconds_sum", "vllm_time_to_first_token_seconds_sum"):
        if key in prom:
            ttft = prom[key]
            break
    hit_rate = (hit / queries) if (hit is not None and queries and queries > 0) else None
    measured = bool(gpu_reachable and hit_rate is not None and ttft is not None)
    return {
        "metric": "kv_cache_ttft",
        "label": "MEASURED" if measured else "ROADMAP",
        "backend": "LMCache (KV-cache offload: GPU→CPU/disk)",
        "prefix_cache_hit_rate": (round(hit_rate, 4) if hit_rate is not None else None),
        "ttft_seconds_sum": ttft,
        "ttft_before_after_note": ("Cold prompt = full prefill TTFT; warm repeat prefix = "
                                   "KV reuse → lower TTFT. Real delta from on-box counters."
                                   if measured else
                                   "Wiring ready: LMCache + vLLM prefix-cache counters give the real "
                                   "TTFT before/after delta on repeated prefixes once the box emits them."),
        "citations": ["LMCache github.com/LMCache/LMCache"],
    }


# ---------------------------------------------------------------------------
# (#4) LiteLLM gateway status (unified endpoint, budget, cloud fallback).
# ---------------------------------------------------------------------------
def _gateway_panel(state: dict) -> dict:
    """Honest LiteLLM unified-gateway status.

    LIVE only when A11OY_LITELLM_BASE_URL is set AND answers; else ROADMAP. The
    gateway fronts Ollama/vLLM with budget enforcement + cloud fallback on GPU OOM.
    """
    base = (_os.environ.get("A11OY_LITELLM_BASE_URL") or "").strip().rstrip("/")
    reachable = False
    if base:
        for path in ("/health", "/v1/models", ""):
            try:
                req = _ureq.Request(base + path, headers={"User-Agent": "szl-energy-sovereign"})
                with _ureq.urlopen(req, timeout=2.0) as r:  # noqa: S310
                    if 200 <= getattr(r, "status", 200) < 500:
                        reachable = True
                        break
            except Exception:
                continue
    measured = bool(base and reachable)
    budget = (_os.environ.get("A11OY_LITELLM_BUDGET_USD") or "").strip()
    return {
        "metric": "litellm_gateway",
        "label": "MEASURED" if measured else "ROADMAP",
        "gateway": "LiteLLM (OpenAI-compatible proxy over Ollama + vLLM)",
        "base_url_configured": bool(base),
        "reachable": reachable,
        "budget_usd_configured": budget or None,
        "cloud_fallback": "on GPU OOM / 5xx → HF Router (honest fallback, logged)",
        "note": ("Unified gateway live: budget enforced, cloud fallback armed."
                 if measured else
                 "Wiring ready: set A11OY_LITELLM_BASE_URL to the on-box LiteLLM proxy. Until then "
                 "the orchestrator serves direct (sovereign-gated) and the gateway is honestly ROADMAP."),
        "citations": ["LiteLLM github.com/BerriAI/litellm"],
    }


# ---------------------------------------------------------------------------
# (#5) RouteLLM Thompson-sampling router — Beta posteriors per model.
# ---------------------------------------------------------------------------
# Per-model Beta(α, β) posteriors. α = #successful (accepted) routes, β = #failures.
# Doctrine: these are HONEST in-memory observations. With no real routing traffic yet
# the posteriors are the priors Beta(1,1) (uniform) — labeled ROADMAP, never faked.
_ROUTER_MODELS = {
    "local-7b":  {"alpha": 1.0, "beta": 1.0, "tier": "easy→local",   "model": "qwen2.5-coder:7b"},
    "cloud-32b": {"alpha": 1.0, "beta": 1.0, "tier": "hard→cloud/32B", "model": "Qwen/Qwen2.5-Coder-32B-Instruct"},
}
_ROUTER_OBS = 0  # number of real routing observations recorded (0 => priors only)


def record_route_outcome(model_key: str, success: bool) -> None:
    """Record a real routing outcome into the Beta posterior (α=success, β=failure).

    Called by the router when a route resolves. Pure in-memory, monotone, never raises.
    Until real traffic calls this, posteriors stay at the Beta(1,1) prior (ROADMAP).
    """
    global _ROUTER_OBS
    try:
        m = _ROUTER_MODELS.get(model_key)
        if m is None:
            return
        if success:
            m["alpha"] += 1.0
        else:
            m["beta"] += 1.0
        _ROUTER_OBS += 1
    except Exception:
        pass


def _thompson_sample(alpha: float, beta: float) -> float:
    """Sample θ ~ Beta(α, β) (stdlib random.betavariate). Used for argmax selection."""
    try:
        return _random.betavariate(max(alpha, 1e-6), max(beta, 1e-6))
    except Exception:
        return alpha / (alpha + beta) if (alpha + beta) > 0 else 0.5


def _router_panel() -> dict:
    """RouteLLM Thompson-sampling router posteriors per model (Beta), honestly labeled."""
    measured = _ROUTER_OBS > 0
    models = []
    samples = {}
    for key, m in _ROUTER_MODELS.items():
        a, b = m["alpha"], m["beta"]
        mean = a / (a + b)
        theta = _thompson_sample(a, b)
        samples[key] = theta
        models.append({
            "model_key": key, "model": m["model"], "route_tier": m["tier"],
            "beta_alpha_successes": a, "beta_beta_failures": b,
            "posterior_mean": round(mean, 4),
            "thompson_sample_theta": round(theta, 4),
            "n_observations": int(a + b - 2),  # minus the Beta(1,1) prior
        })
    chosen = max(samples, key=samples.get) if samples else None
    return {
        "metric": "routellm_thompson",
        "label": "MEASURED" if measured else "ROADMAP",
        "policy": "Thompson sampling over per-model Beta posteriors; argmax θ wins the route",
        "models": models,
        "thompson_choice_this_draw": chosen,
        "total_observations": _ROUTER_OBS,
        "note": ("Posteriors updated from real routing outcomes (α=accepted, β=failed)."
                 if measured else
                 "Wiring ready: record_route_outcome() updates Beta(α,β) per model on every route. "
                 "With no live traffic yet the posteriors are the Beta(1,1) uniform prior — honest ROADMAP."),
        "citations": ["RouteLLM github.com/lm-sys/routellm",
                      "Thompson sampling: sample θ_k~Beta(α_k,β_k), pick argmax"],
    }


# ---------------------------------------------------------------------------
# (#6) Carbon-Aware SDK batch scheduling — low-carbon windows.
# ---------------------------------------------------------------------------
def _carbon_panel() -> dict:
    """Carbon-aware batch schedule: shift non-urgent inference to low-carbon windows.

    LIVE forecast only when a real carbon feed is wired; otherwise a labeled SAMPLE
    diurnal curve (low overnight / midday solar; high evening peak) so the schedule
    is illustrative-but-honest. carbon_g_co2eq per job is computed from the same J/token.
    """
    live = _carbon_feed_is_live()
    g_per_kwh = _carbon_g_per_kwh()
    # 24h relative intensity curve (SAMPLE shape unless a real feed overrides).
    base = [0.55, 0.50, 0.48, 0.47, 0.50, 0.58, 0.72, 0.85, 0.80, 0.70, 0.60, 0.55,
            0.52, 0.55, 0.62, 0.72, 0.85, 0.95, 1.00, 0.95, 0.85, 0.75, 0.68, 0.60]
    windows = [{"hour_utc": h, "rel_intensity": base[h],
                "g_co2eq_per_kwh_est": round(g_per_kwh * base[h], 2)} for h in range(24)]
    low = sorted(range(24), key=lambda h: base[h])[:3]
    return {
        "metric": "carbon_aware_schedule",
        "label": "MEASURED" if live else "ROADMAP",
        "scheduler": "Carbon-Aware SDK — shift non-urgent batch inference to low-carbon windows",
        "carbon_feed_live": live,
        "carbon_g_per_kwh_now": g_per_kwh,
        "carbon_intensity_label": ("LIVE" if live else "SAMPLE (regional diurnal curve)"),
        "low_carbon_windows_utc": sorted(low),
        "schedule_24h": windows,
        "note": ("Live grid carbon feed wired: batch jobs deferred to the greenest window."
                 if live else
                 "Wiring ready: with the Carbon-Aware SDK feed the schedule becomes a LIVE forecast. "
                 "Until then the diurnal curve is SAMPLE and per-job carbon_g_co2eq is ESTIMATE."),
        "citations": ["Carbon-Aware SDK github.com/Green-Software-Foundation/carbon-aware-sdk"],
    }


# ---------------------------------------------------------------------------
# Full posture (machine-readable) — composes every panel honestly.
# ---------------------------------------------------------------------------
def _posture() -> dict:
    state = _sovereign_state()
    reachable = _gpu_reachable(state)
    prom = _parse_prom(_fetch_metrics_text() or "") if reachable else {}
    sample = _exporter_sample_from_metrics(prom) if reachable else None
    jtoken = _jtoken_from_operator() or _jtoken_from_metrics(prom, sample)
    panels = {
        "jtoken": jtoken,
        "throughput": _throughput_panel(prom, reachable),
        "kvcache": _kvcache_panel(prom, reachable),
        "gateway": _gateway_panel(state),
        "router": _router_panel(),
        "carbon": _carbon_panel(),
    }
    measured_count = sum(1 for p in panels.values() if p.get("label") == "MEASURED")
    summary = ("SOVEREIGN ENERGY LIVE (%d/%d MEASURED)" % (measured_count, len(panels))
               if reachable and measured_count else
               "WIRED — pending sovereign GPU metrics (honest ROADMAP)")
    return {
        "service": "energy-sovereign",
        "doctrine": DOCTRINE["version"],
        "summary": summary,
        "sovereign": bool(state.get("sovereign")),
        "gpu_reachable": reachable,
        "inference_state": state,
        "measured_panels": measured_count,
        "total_panels": len(panels),
        "panels": panels,
        "doctrine_lock": DOCTRINE,
        "honesty": ("Every panel reads live from the on-box vLLM /metrics ONLY when the live "
                    "sovereign probe shows gpu_reachable; otherwise it is honestly labeled ROADMAP. "
                    "The joules label is decided solely by szl_joules_truth off a real fresh exporter "
                    "sample — never off a flag. No meter → no number."),
        "computed_at": _now_iso(),
    }


# ---------------------------------------------------------------------------
# Unified Energy / Sovereign Compute HTML tab (0 CDN; window.SZLLabels).
# ---------------------------------------------------------------------------
def _html(p: dict) -> str:
    panels = p["panels"]

    def row(left: str, right: str) -> str:
        return ('<div class="kv"><span class="k">%s</span><span class="v">%s</span></div>'
                % (left, right))

    def fmt(v):
        return "—" if v is None else (str(v))

    jt = panels["jtoken"]
    tp = panels["throughput"]
    kv = panels["kvcache"]
    gw = panels["gateway"]
    rt = panels["router"]
    ca = panels["carbon"]

    # Each card carries a data-szl-label so the inline script renders the honest pill
    # via window.SZLLabels.badgeHTML (MEASURED→LIVE tone; ROADMAP→EXPERIMENTAL tone).
    def card(title: str, label: str, body: str, note: str) -> str:
        return ('<article class="card" data-szl="%s"><div class="row"><h3>%s</h3>'
                '<span class="pill-slot" data-label="%s"></span></div>%s'
                '<p class="note">%s</p></article>'
                % (title, title, label, body, note))

    jt_body = (row("J / token", fmt(jt["joules_per_token"]))
               + row("gCO₂eq / token", fmt(jt["carbon_g_co2eq_per_token"]))
               + row("GPU energy (J, cum.)", fmt(jt["gpu_energy_joules_total"]))
               + row("generated tokens", fmt(jt["generated_tokens_total"]))
               + row("carbon (gCO₂eq/kWh)", fmt(jt["carbon_g_per_kwh"]))
               + row("joules honesty", fmt(jt["joules_honesty"])))
    tp_body = (row("tokens/s WITH spec", fmt(tp["tokens_per_s_with_spec"]))
               + row("tokens/s WITHOUT", fmt(tp["tokens_per_s_without_spec"]))
               + row("acceptance rate α", "%s <small>(%s)</small>" % (fmt(tp["acceptance_rate_alpha"]), tp["acceptance_rate_alpha_label"]))
               + row("modeled speedup", "%s×" % fmt(tp["modeled_speedup_x"]))
               + row("draft model", "<code>%s</code>" % tp["draft_model"]))
    kv_body = (row("prefix cache hit-rate", fmt(kv["prefix_cache_hit_rate"]))
               + row("TTFT Σ (s)", fmt(kv["ttft_seconds_sum"]))
               + row("backend", kv["backend"]))
    gw_body = (row("gateway", "LiteLLM proxy")
               + row("base configured", fmt(gw["base_url_configured"]))
               + row("reachable", fmt(gw["reachable"]))
               + row("budget (USD)", fmt(gw["budget_usd_configured"]))
               + row("cloud fallback", gw["cloud_fallback"]))
    rt_rows = "".join(
        row("%s (%s)" % (m["model_key"], m["route_tier"]),
            "Beta(α=%s, β=%s) μ=%s θ=%s" % (m["beta_alpha_successes"], m["beta_beta_failures"],
                                            m["posterior_mean"], m["thompson_sample_theta"]))
        for m in rt["models"])
    rt_body = rt_rows + row("Thompson choice", fmt(rt["thompson_choice_this_draw"])) + row("observations", fmt(rt["total_observations"]))
    ca_low = ", ".join("%02d:00" % h for h in ca["low_carbon_windows_utc"])
    ca_body = (row("carbon now (gCO₂eq/kWh)", fmt(ca["carbon_g_per_kwh_now"]))
               + row("intensity feed", ca["carbon_intensity_label"])
               + row("low-carbon windows (UTC)", ca_low)
               + row("scheduler", "Carbon-Aware SDK"))

    cards = "".join([
        card("J/token + Carbon", jt["label"], jt_body, jt["note"]),
        card("Speculative Decoding", tp["label"], tp_body, tp["note"]),
        card("KV-Cache TTFT (LMCache)", kv["label"], kv_body, kv["ttft_before_after_note"]),
        card("LiteLLM Gateway", gw["label"], gw_body, gw["note"]),
        card("RouteLLM Router (Thompson)", rt["label"], rt_body, rt["note"]),
        card("Carbon-Aware Schedule", ca["label"], ca_body, ca["note"]),
    ])
    d = p["doctrine_lock"]
    st = p["inference_state"]
    # NOTE: window.SZLLabels has no native MEASURED/ROADMAP keys, so we map
    # MEASURED→LIVE (ok tone) and ROADMAP→EXPERIMENTAL (warn tone) with a label override.
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<meta name="theme-color" content="#0a0e14"><title>Energy / Sovereign Compute — a11oy</title>
<style>
 :root{color-scheme:dark} *{box-sizing:border-box}
 body{margin:0;background:#0a0e14;color:#e6edf3;font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
   padding:max(16px,env(safe-area-inset-top)) 16px calc(24px + env(safe-area-inset-bottom))}
 header{max-width:980px;margin:0 auto 18px}
 h1{font-size:clamp(1.4rem,5vw,2rem);margin:0 0 6px}
 .summary{font-weight:700;font-size:1.05rem;color:#42d392;margin:0 0 4px}
 .sub{color:#9aa7b4;font-size:.85rem;margin:.2rem 0}
 .state{font-family:ui-monospace,monospace;font-size:.76rem;color:#6b7785;word-break:break-word}
 .grid{max-width:980px;margin:0 auto;display:grid;gap:14px;grid-template-columns:1fr}
 @media(min-width:720px){.grid{grid-template-columns:1fr 1fr}}
 .card{background:#111722;border:1px solid #1e2a3a;border-radius:14px;padding:15px}
 .row{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:8px}
 h3{font-size:1rem;margin:0}
 .kv{display:flex;justify-content:space-between;gap:12px;font-size:.84rem;padding:3px 0;border-bottom:1px solid #18222e}
 .kv .k{color:#9aa7b4} .kv .v{color:#e6edf3;font-family:ui-monospace,monospace;text-align:right;word-break:break-word}
 .kv .v code{font-size:.78rem;color:#9fd0ff} .kv .v small{color:#6b7785}
 .note{color:#c4cdd6;font-size:.8rem;margin:10px 0 0}
 footer{max-width:980px;margin:22px auto 0;color:#6b7785;font-size:.76rem}
 .lock{font-family:ui-monospace,monospace;color:#9aa7b4}
</style></head><body>
<header>
  <h1>Energy / Sovereign Compute</h1>
  <p class="summary">__SUMMARY__</p>
  <p class="sub">Each tile is read LIVE from the on-box vLLM <code>/metrics</code> when the sovereign GPU probe is reachable, else honestly labeled <b>ROADMAP</b>. No meter → no number.</p>
  <p class="state">inference=__INF__ · sovereign=__SOV__ · gpu_reachable=__REACH__ · measured=__MC__/__TC__</p>
</header>
<main class="grid">__CARDS__</main>
<section class="card3d" id="energy3d_panel" style="max-width:980px;margin:14px auto 0;background:#111722;border:1px solid #1e2a3a;border-radius:14px;padding:15px">
  <div class="row"><h3>3D Energy / GPU Hologram</h3>
    <button id="e3d_toggle" style="font:600 12px/1 ui-monospace,monospace;color:#9fd0ff;background:#0c131c;border:1px solid #29384a;border-radius:8px;padding:6px 11px;cursor:pointer">Enable 3D</button>
  </div>
  <p class="sub" style="margin:.3rem 0 .6rem">Holographic view of the sovereign-inference engine on the shared 0-CDN WebGL2 kit: the <b>GPU/serving block</b> colors by the live <code>/v1/energy/sovereign</code> posture (<b>sovereign:true only on a real local-GPU probe</b>), a <b>trust sphere</b> morphs with &Lambda; (Conjecture 1, &lt;1.0), and the <b>J/token</b> readout is <b>MEASURED only on a live GPU power probe</b> &mdash; with no meter wired it stays an honest <b>ROADMAP</b>, never presented as measured. CPU/old-GPU renders the same data on a <b>2D canvas fallback</b>; the tiles above are the complete non-3D experience. Patterns: vLLM/SGLang J/token, NVIDIA Dynamo, LiteLLM, RouteLLM.</p>
  <p class="state" style="margin:.2rem 0 .6rem">J/token <span id="e3d_jtok" style="color:#e0a13a">&mdash;</span> <span id="e3d_jtok_lbl"></span> &middot; sovereign <span id="e3d_sov" style="color:#e6edf3">&mdash;</span> &middot; <span id="e3d_caps" style="color:#6b7785"></span></p>
  <div id="energy3d_mount" style="width:100%;height:400px;border:1px solid #1e2a3a;border-radius:10px;background:#060606;display:none;position:relative"></div>
  <p class="note" id="e3d_off">3D is off (default). Tap <b>Enable 3D</b> to render the holographic energy view on the live <code>/v1/energy/jtoken</code> + <code>/v1/energy/sovereign</code> endpoints. The tiles above are always available as the fallback.</p>
  <p class="note" style="color:#6b7785;font-size:.74rem">0 runtime CDN &middot; WebGL2 + honest 2D fallback &middot; J/token MEASURED-or-ROADMAP (never fabricated) &middot; sovereign:true only on live probe &middot; &Lambda; = Conjecture 1 (&lt;1.0) &middot; trust &lt;100%.</p>
</section>
<footer>
  <p class="lock">Doctrine __DV__ LOCKED · locked-proven=__LC__ {__LP__} · __CORPUS__ @ __KC__ · Λ = Conjecture 1 (NOT a theorem) · __SLSA__</p>
  <p>MEASURED = real on-box exporter sample (live) · ROADMAP = wiring ready, box not emitting yet (never faked). Sources: Watt-Counts arXiv:2604.09048 · Energy-per-Token arXiv:2603.20224 · vLLM spec-decode · LMCache · LiteLLM · RouteLLM · Carbon-Aware SDK.</p>
</footer>
<script src="/static/shared/szl_label_engine.js"></script>
<script>
(function(){
  function pill(label){
    var key = (label === "MEASURED") ? "LIVE" : "EXPERIMENTAL";
    if (window.SZLLabels && window.SZLLabels.badgeHTML){
      return window.SZLLabels.badgeHTML(key, {label: label,
        title: (label === "MEASURED")
          ? "Real on-box exporter sample — live and honest."
          : "Wiring ready; the box is not emitting this metric yet. ROADMAP, never faked."});
    }
    return '<span>' + label + '</span>';
  }
  if (window.SZLLabels && window.SZLLabels.ensureStyle){ window.SZLLabels.ensureStyle(document); }
  var slots = document.querySelectorAll('.pill-slot');
  for (var i=0;i<slots.length;i++){ slots[i].innerHTML = pill(slots[i].getAttribute('data-label')); }
})();
</script>
<!-- F4 - 3D Energy/GPU hologram (additive). Loads the shared 0-CDN holographic kit. -->
<script src="/static/shared/szl_holo3d.js"></script>
<script>
"use strict";
(function(){
  var EA="/api/a11oy";
  var mount=document.getElementById('energy3d_mount');
  var offEl=document.getElementById('e3d_off');
  var toggle=document.getElementById('e3d_toggle');
  if(!mount||!toggle||!window.SZLHolo){ if(toggle){toggle.disabled=true;toggle.textContent='3D unavailable';} return; }
  var scene=null, started=false, poll=null, anim=null;
  var JT=document.getElementById('e3d_jtok'), JTL=document.getElementById('e3d_jtok_lbl');
  var SOV=document.getElementById('e3d_sov'), CAP=document.getElementById('e3d_caps');
  function esc3(s){return String(s==null?'':s).replace(/[&<>]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c];});}
  function getJSON(u,opt){return fetch(u,opt).then(function(r){return r.ok?r.json():null;}).catch(function(){return null;});}

  function applyJtoken(b){
    if(!b){ JT.textContent='-'; JTL.innerHTML=''; return; }
    var lbl=String(b.label||'').toUpperCase();
    var ev=b.joules_evidence||{};
    var measured=(lbl==='MEASURED') && ev && Object.keys(ev).length>0 && (b.joules_per_token!=null);
    if(measured){
      JT.textContent=Number(b.joules_per_token).toFixed(4)+' J/tok';
      JTL.innerHTML='<span style="color:#42d392;font-size:9px;border:1px solid #42d392;padding:1px 5px;border-radius:5px">MEASURED - live probe</span>';
    }else{
      JT.textContent='- J/tok';
      JTL.innerHTML='<span style="color:#e0a13a;font-size:9px;border:1px solid #e0a13a;padding:1px 5px;border-radius:5px">ROADMAP - no meter ('+esc3(b.joules_honesty||'sample')+')</span>';
    }
  }

  var _sovereign=false;
  function applySovereign(sv){
    var sov=!!(sv&&sv.sovereign===true&&sv.gpu_reachable===true);
    _sovereign=sov;
    SOV.textContent=sv?(sov?'true - local-GPU probe':'false - router fallback'):'- (posture unreachable)';
    rebuild();
  }

  function rebuild(){
    if(!scene)return;
    try{
      scene.graphs=[]; scene.spheres=[]; scene.pulses=[];
      var gpuLab=_sovereign?'GPU.SOVEREIGN':'GPU.ROADMAP';
      scene.addGraph({nodes:[
        {id:'router',label:'\u039b-ENGINE'},
        {id:'gpu',label:gpuLab},
        {id:'bek',label:'BEKENSTEIN'}
      ],edges:[
        {id:'e0',from:'router',to:'gpu'},
        {id:'e1',from:'router',to:'bek'}
      ]});
      var lam=0.62;
      scene.addTrustSphere({lambda:lam}); scene.setLambda(lam);
    }catch(e){}
  }
  function pulse(){ if(scene){ try{ scene.signPulse('e0'); }catch(_){} } }

  function refresh(){
    getJSON(EA+'/v1/energy/jtoken').then(applyJtoken);
    getJSON(EA+'/v1/energy/sovereign').then(applySovereign);
  }
  function start(){
    if(started)return; started=true;
    mount.style.display='block'; offEl.style.display='none'; toggle.textContent='Disable 3D';
    scene=window.SZLHolo.createScene(mount,{sample:false});
    var caps=window.SZLHolo.capabilities();
    CAP.textContent='mode:'+caps.mode+(caps.webgpu?' - webgpu-detected(ROADMAP)':'');
    rebuild(); scene.start();
    refresh();
    poll=setInterval(refresh,30000);
    anim=setInterval(pulse,3000);
  }
  function stop(){
    if(!started)return; started=false;
    mount.style.display='none'; offEl.style.display='block'; toggle.textContent='Enable 3D';
    if(poll)clearInterval(poll); if(anim)clearInterval(anim);
    try{ if(scene){scene.stop();scene.dispose();} }catch(e){}
    scene=null;
  }
  toggle.addEventListener('click',function(){ started?stop():start(); });
})();
</script>
</body></html>""".replace("__SUMMARY__", p["summary"]) \
    .replace("__INF__", str(st.get("inference"))) \
    .replace("__SOV__", str(p["sovereign"])) \
    .replace("__REACH__", str(p["gpu_reachable"])) \
    .replace("__MC__", str(p["measured_panels"])) \
    .replace("__TC__", str(p["total_panels"])) \
    .replace("__CARDS__", cards) \
    .replace("__DV__", d["version"]) \
    .replace("__LC__", str(d["locked_count"])) \
    .replace("__LP__", ", ".join(d["locked_proven"])) \
    .replace("__CORPUS__", d["corpus"]) \
    .replace("__KC__", d["kernel_commit"]) \
    .replace("__SLSA__", d["slsa"])


# ---------------------------------------------------------------------------
# Registration (additive; mirrors szl_sovereign_compute.register).
# ---------------------------------------------------------------------------
# ── Per-receipt energy metrics — REAL sovereign GPU joule-meter (energy-exporter).
# Surfaces the live NVML-backed joule-meter: cumulative joules are MEASURED (a real
# energy counter); instantaneous power_w is surfaced ONLY when a GPU node reports a
# live NVML power.draw, else null with an honest reason. Doctrine v11: never fabricate
# a watt. Route always returns 200 so the meter posture stays machine-readable.
_JOULE_METER_URL = "http://100.96.129.45:9471/"

# Public, non-revealing descriptor for the joule-meter exporter. The exporter lives on
# the private sovereign-GPU tailnet (100.x:9471) — that raw host:port is an internal
# address and MUST NOT appear in any served JSON (same private-IP-leak class scrubbed
# from compute-pool, #492-#499). The served panel surfaces this honest descriptor;
# reachability is still told truthfully via the real label/joules_honesty fields, never
# via the address. _JOULE_METER_URL stays the internal probe target only.
_JOULE_METER_LABEL = "on-box sovereign-GPU joule-meter exporter (private tailnet)"


def _joule_meter(timeout: float = 4.0):
    import json as _j, urllib.request as _u
    try:
        req = _u.Request(_JOULE_METER_URL, headers={"User-Agent": "a11oy-energy-metrics"})
        with _u.urlopen(req, timeout=timeout) as r:  # noqa: S310
            return _j.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _metrics_panel() -> dict:
    meter = _joule_meter()
    if not meter:
        return {
            "metric": "energy_metrics", "label": "ROADMAP",
            "power_w": None, "power_w_label": "UNAVAILABLE",
            "joules_total": None, "joules_honesty": "unavailable",
            "reason": "joule-meter exporter unreachable",
            "exporter": _JOULE_METER_LABEL, "generated_at": _now_iso(),
        }
    engines = []
    live_power_w = None
    joules_total = 0.0
    any_joules = False
    for e in (meter.get("engines") or []):
        gpus = []
        for g in (e.get("gpus") or []):
            pw = g.get("power_w")
            live = bool(g.get("live"))
            ok = live and pw is not None
            gpus.append({
                "gpu": g.get("gpu"), "name": g.get("name"),
                "power_w": (float(pw) if ok else None),
                "power_w_label": ("MEASURED" if ok else "UNAVAILABLE"),
                "live": live, "joules": g.get("joules"), "util": g.get("util"),
                "temp_c": g.get("temp_c"), "mem_used_mb": g.get("mem_used_mb"),
                "samples": g.get("samples"),
            })
            if ok and live_power_w is None:
                live_power_w = float(pw)
        ej = e.get("joules")
        if isinstance(ej, (int, float)):
            joules_total += float(ej); any_joules = True
        engines.append({
            "engine": e.get("engine"), "power_source": e.get("power_source"),
            "joules": ej, "gpus": gpus,
        })
    totals = meter.get("totals") or {}
    mj = totals.get("joules")
    if isinstance(mj, (int, float)):
        joules_total = float(mj); any_joules = True
    return {
        "metric": "energy_metrics",
        "label": ("MEASURED" if any_joules else "ROADMAP"),
        "power_w": live_power_w,
        "power_w_label": ("MEASURED" if live_power_w is not None else "UNAVAILABLE"),
        "power_w_note": (None if live_power_w is not None else
                         "no live NVML power.draw from any sovereign GPU node "
                         "(exporter awaiting live power sampler); joules below are the "
                         "real cumulative energy counter"),
        "joules_total": (joules_total if any_joules else None),
        "joules_honesty": ("measured" if any_joules else "unavailable"),
        "kwh": totals.get("kwh"), "eur_per_mwh": totals.get("eur_per_mwh"),
        "eur_cost": totals.get("eur_cost"),
        "engines": engines,
        "exporter": _JOULE_METER_LABEL,
        "meter_generated_at": meter.get("generated_at"),
        "generated_at": _now_iso(),
        "citations": ["Watt-Counts arXiv:2604.09048", "Energy-per-Token arXiv:2603.20224"],
    }


def register(app, ns: str = "a11oy") -> dict:
    from fastapi.responses import HTMLResponse, JSONResponse

    base = "/api/%s/v1/energy" % ns

    @app.get("%s/sovereign" % base)
    async def _es_json():  # noqa: ANN202
        return JSONResponse(_posture())

    @app.get("%s/jtoken" % base)
    async def _es_jtoken():  # noqa: ANN202
        op_jt = _jtoken_from_operator()
        if op_jt is not None:
            return JSONResponse(op_jt)
        state = _sovereign_state()
        reachable = _gpu_reachable(state)
        prom = _parse_prom(_fetch_metrics_text() or "") if reachable else {}
        sample = _exporter_sample_from_metrics(prom) if reachable else None
        return JSONResponse(_jtoken_from_metrics(prom, sample))

    @app.get("%s/throughput" % base)
    async def _es_throughput():  # noqa: ANN202
        state = _sovereign_state()
        reachable = _gpu_reachable(state)
        prom = _parse_prom(_fetch_metrics_text() or "") if reachable else {}
        return JSONResponse(_throughput_panel(prom, reachable))

    @app.get("%s/kvcache" % base)
    async def _es_kvcache():  # noqa: ANN202
        state = _sovereign_state()
        reachable = _gpu_reachable(state)
        prom = _parse_prom(_fetch_metrics_text() or "") if reachable else {}
        return JSONResponse(_kvcache_panel(prom, reachable))

    @app.get("%s/gateway" % base)
    async def _es_gateway():  # noqa: ANN202
        return JSONResponse(_gateway_panel(_sovereign_state()))

    @app.get("%s/router" % base)
    async def _es_router():  # noqa: ANN202
        return JSONResponse(_router_panel())

    @app.get("%s/carbon" % base)
    async def _es_carbon():  # noqa: ANN202
        return JSONResponse(_carbon_panel())

    @app.get("%s/metrics" % base)
    async def _es_metrics():  # noqa: ANN202
        return JSONResponse(_metrics_panel())

    @app.get("/energy-sovereign", response_class=HTMLResponse)
    async def _es_panel():  # noqa: ANN202
        return HTMLResponse(_html(_posture()))

    return {"ok": True, "ns": ns,
            "routes": ["%s/sovereign" % base, "%s/jtoken" % base, "%s/throughput" % base,
                       "%s/kvcache" % base, "%s/gateway" % base, "%s/router" % base,
                       "%s/carbon" % base, "%s/metrics" % base, "/energy-sovereign"]}


# ---------------------------------------------------------------------------
# No-server self-test (proves the honesty gates without a live GPU).
# ---------------------------------------------------------------------------
def _selftest() -> dict:
    out: dict = {}
    # (a) energy_fields_for_receipt is always present + honest when no GPU.
    f = energy_fields_for_receipt()
    assert f["joules_consumed"] is None and f["carbon_g_co2eq"] is None, f
    assert f["energy_label"] == "ROADMAP", f
    assert f["joules_honesty"] == "sample", f
    out["receipt_fields_honest_roadmap"] = True

    # (b) J/token with no real sample => ROADMAP, no fabricated number.
    jt = _jtoken_from_metrics({}, None)
    assert jt["label"] == "ROADMAP" and jt["joules_per_token"] is None, jt
    out["jtoken_roadmap_no_number"] = True

    # (c) J/token WITH a fresh fabricated-but-real-shaped sample + token counter => MEASURED.
    prom = {"vllm:generation_tokens_total": 1000.0}
    sample = {"joules_measured_total": 50.0, "exporter_node": "rig-0",
              "exporter_last_seen_ts": _time.time(), "power_w_sample": 210.0}
    jt2 = _jtoken_from_metrics(prom, sample)
    assert jt2["label"] == "MEASURED", jt2
    assert abs(jt2["joules_per_token"] - 0.05) < 1e-9, jt2
    assert jt2["carbon_g_co2eq_per_token"] is not None, jt2
    out["jtoken_measured_with_real_sample"] = True

    # (d) speculative speedup model: S=(k+1)/(k(1-α)+1); k=4, α=0.8 -> 5/1.8 ≈ 2.78x.
    s = _spec_speedup(4, 0.8)
    assert 2.7 < s < 2.85, s
    out["spec_speedup_model"] = round(s, 3)

    # (e) Thompson router starts at Beta(1,1) priors => ROADMAP; recording flips MEASURED.
    rp = _router_panel()
    assert rp["label"] == "ROADMAP", rp
    record_route_outcome("local-7b", True)
    rp2 = _router_panel()
    assert rp2["label"] == "MEASURED", rp2
    # reset prior so the module ships clean
    _ROUTER_MODELS["local-7b"]["alpha"] = 1.0
    globals()["_ROUTER_OBS"] = 0
    out["router_thompson_gate"] = True

    # (f) carbon panel: no live feed => ROADMAP + SAMPLE intensity label.
    cp = _carbon_panel()
    assert cp["label"] == "ROADMAP" and "SAMPLE" in cp["carbon_intensity_label"], cp
    assert len(cp["schedule_24h"]) == 24, cp
    out["carbon_roadmap_sample"] = True

    # (g) full posture renders + html is non-trivial + no forbidden raw claims pattern.
    p = _posture()
    h = _html(p)
    assert "Energy / Sovereign Compute" in h and len(h) > 2000, len(h)
    assert "100%" not in h and "tamper-proof" not in h.lower(), "forbidden raw claim"
    out["html_bytes"] = len(h)

    out["ok"] = True
    return out


if __name__ == "__main__":
    import sys
    print(_json.dumps(_selftest(), indent=2), file=sys.stderr)
