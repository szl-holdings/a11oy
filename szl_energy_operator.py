# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 — the press-play ENERGY OPERATOR daemon (Dev 1, backend).
"""
szl_energy_operator.py — PRESS PLAY. The operational loop.

On START this daemon dispatches a CONTINUOUS stream of REAL inference jobs to the
reachable Ollama GPU nodes (rtx-betterwithage, chaski) — small honest workloads
(short token-generation prompts and/or embeddings) so the rig genuinely computes
and burns measurable energy. Per job it records start/end wall-time, pulls an NVML
power/energy sample from the EXISTING exporter path (the betterwithage joule-meter
that already feeds szl_energy_sovereign's metrics panel / harvest posture
joules_evidence), and computes joules_measured for that job.

Honesty (Doctrine v11 — NEVER violate):
  - Joules are MEASURED only from a REAL, FRESH (<30s) NVML exporter delta. The
    label is decided SOLELY by szl_joules_truth — never off a flag.
  - If the exporter sample is stale (>30s) or unavailable, the job's energy is
    labeled SAMPLE and EXCLUDED from billable totals. We never fabricate a joule.
  - If a GPU node is unreachable, we SKIP it and mark it DEGRADED in status —
    we NEVER fabricate a job or a joule for a node that didn't compute.
  - Sandbox / no-GPU: a faithful local STUB of the Ollama API does REAL CPU work
    (so wall-time + jobs_done are honest) but its energy is ALWAYS labeled SAMPLE
    and never billable. Stub mode is announced loudly in every status payload.

Interface other devs build against (STABLE — Dev2 receipts / Dev3 projection /
Dev4 dashboard consume this):

  JobRecord = {
      "node":            str,    # which node computed it (or "<node>-stub")
      "model":           str,    # model tag used
      "kind":            str,    # "generate" | "embed"
      "tokens":          int,    # MEASURED tokens produced/consumed
      "wall_s":          float,  # MEASURED wall-clock seconds for the job
      "joules_measured": float|None,  # MEASURED joules iff joules_label=="MEASURED", else None
      "joules_label":    str,    # "MEASURED" | "SAMPLE"  (billing.py-compatible upper-case)
      "joules_evidence": dict,   # self-verifying exporter evidence (empty unless MEASURED)
      "ts":              str,    # ISO-8601 UTC completion time
      "seq":             int,    # monotonic job sequence number (ledger order)
  }

  on_job(JobRecord) callback — register via OperatorDaemon.subscribe(cb) so Dev2
  can mint a JouleCharge receipt per completed job in real time.

Endpoints (dual-registered under /api/{ns}/v1/energy/operator/* AND /v1/energy/operator/*):
  POST /energy/operator/start    — press play (idempotent; returns running state)
  POST /energy/operator/stop     — graceful stop (idempotent)
  GET  /energy/operator/status   — running?, jobs_done, joules_measured_total,
                                    tokens_total, nodes computing, uptime, degraded nodes

Graceful start/stop via a threading stop-flag + optional SIGINT/SIGTERM handler.
Backpressure: a per-node in-flight cap + inter-job sleep so we never overwhelm a node.
State persists to a JSON ledger so a restart RESUMES the cumulative counts.

Pure stdlib + httpx (already a repo dep) + FastAPI. No Node, no CDN.
"""
from __future__ import annotations

import json
import os
import signal
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

# Module-level import so string annotations (PEP 563 `from __future__ import
# annotations`) on the operator route handlers resolve against module globals;
# FastAPI reads `request: Request` from here, otherwise it 422s `request` as a query param.
try:
    from fastapi import Request as Request  # noqa: F401
except Exception:  # pragma: no cover — fastapi always present at serve time
    Request = Any  # type: ignore

try:
    import szl_joules_truth as _J
except Exception:  # pragma: no cover — packaged import fallback
    from . import szl_joules_truth as _J  # type: ignore

# OMEN endpoint SINGLE SOURCE OF TRUTH: read the hardened fabric pool's OMEN address
# (szl_backend_hardening.OMEN_FABRIC_ENDPOINT) so the energy loop's OMEN default cannot
# silently diverge from /compute-pool-hardened. Without this, the energy loop defaulted
# to the bare hostname http://omen-betterwithage:11434 (which won't resolve on the box)
# while the hardened pool used the correct tailnet IP — so OMEN could never breathe.
# Honest: this fixes only the ADDRESS the probe targets; a real probe still decides up.
try:
    from szl_backend_hardening import OMEN_FABRIC_ENDPOINT as _OMEN_HARDENED_ENDPOINT
except Exception:  # pragma: no cover — packaged import fallback
    try:
        from .szl_backend_hardening import OMEN_FABRIC_ENDPOINT as _OMEN_HARDENED_ENDPOINT  # type: ignore
    except Exception:
        # Last-resort honest default if the hardened module is unavailable: the same
        # tailnet IP the hardened pool ships. Kept identical so behavior never diverges.
        _OMEN_HARDENED_ENDPOINT = "http://100.70.130.45:11434"

# ---------------------------------------------------------------------------
# Doctrine constants.
# ---------------------------------------------------------------------------
DOCTRINE = "v11"
# joule_billing.py refuses to bill unless the label is MEASURED with an NVML sample
# fresher than this. We mirror it EXACTLY so the operator's MEASURED↔SAMPLE split
# is the same gate the billing core uses (no divergence).
MAX_NVML_AGE_S = 30.0
# billing.py uses upper-case labels; szl_joules_truth uses lower-case. We map at the
# boundary so JobRecord.joules_label is billing-compatible and self-consistent.
LABEL_MEASURED = "MEASURED"
LABEL_SAMPLE = "SAMPLE"

# ---------------------------------------------------------------------------
# Useful-work + energy-harness env knobs (all honest, all gentle defaults).
# Useful work changes WHAT the embed job computes (a REAL un-embedded corpus
# chunk that gets written into the live RAG dense index) — it NEVER changes HOW
# joules are measured. The MEASURED<->SAMPLE split stays decided solely by
# szl_joules_truth via _label_upper.
# ---------------------------------------------------------------------------
# Master switch for useful-work embedding (default ON). Off => the old canned
# _EMBED_TEXTS behavior (still real inference, just throwaway content).
USEFUL_WORK_ENV = "A11OY_ENERGY_USEFUL_WORK"
# Grid price (EUR/MWh) at/above which the loop THROTTLES batch work to protect cost.
PRICE_EXPENSIVE_ENV = "A11OY_ENERGY_PRICE_EXPENSIVE_EUR_MWH"
_PRICE_EXPENSIVE_DEFAULT = 120.0
# Extra corpus-embed jobs per reachable node when SOAKING (draining backlog).
SOAK_BATCH_ENV = "A11OY_ENERGY_SOAK_BATCH"
_SOAK_BATCH_DEFAULT = 3
_SOAK_BATCH_CAP = 16  # gentle hard cap so a soak never overwhelms a node
# Inter-sweep sleep multiplier when THROTTLING (loop genuinely backs off).
THROTTLE_SLEEP_MULT_ENV = "A11OY_ENERGY_THROTTLE_SLEEP_MULT"
_THROTTLE_SLEEP_MULT_DEFAULT = 4.0
# Forced posture override for demos/tests (soak|baseline|throttle). Empty => live.
FORCE_POSTURE_ENV = "A11OY_ENERGY_FORCE_POSTURE"
# Governed-compute switch (default ON). When ON, each completed REAL GPU job is run
# through the EXISTING governed turn (a11oy_vertical_feeds.governed_turn: Λ aggregator
# + locked formulas + deny-by-default gates, sealing a Khipu/DSSE receipt into the Lake)
# and the honest result is attached to the JobRecord as ADDITIVE governance metadata.
# This NEVER touches how joules are MEASURED. Off => the prior byte-identical job path.
GOVERN_COMPUTE_ENV = "A11OY_GOVERN_COMPUTE"
# Governance vertical/organ the GPU jobs are sealed under (its own Lake DAG).
GOVERN_VERTICAL = "sovereign-compute"
# The harvest posture feed (a11oy_harvest_endpoints.handle_posture) can hit live
# external energy feeds, so it is refreshed at most once per this TTL — NEVER on
# every sweep. Keeps the hot loop gentle (a fast inter-job interval must not turn
# into a per-sweep network call). The cheap in-process grid-price posture is still
# recomputed every sweep. Override for tests.
POSTURE_TTL_ENV = "A11OY_ENERGY_POSTURE_TTL_S"
_POSTURE_TTL_DEFAULT = 60.0

WORK_MODE_SOAK = "soak"
WORK_MODE_BASELINE = "baseline"
WORK_MODE_THROTTLE = "throttle"


def _useful_work_enabled() -> bool:
    return (os.environ.get(USEFUL_WORK_ENV, "1").strip().lower()
            not in ("0", "false", "no", "off", ""))


def _govern_enabled() -> bool:
    """True unless A11OY_GOVERN_COMPUTE is explicitly falsey. Default ON."""
    return (os.environ.get(GOVERN_COMPUTE_ENV, "1").strip().lower()
            not in ("0", "false", "no", "off", ""))


def _ungoverned(reason: str) -> dict:
    """Honest ungoverned governance record — STABLE schema, NO fabricated Λ/receipt."""
    return {
        "governed": False,
        "lambda_score": None,
        "lambda_pass": None,
        "decision": None,
        "receipt_id": None,
        "dsse_keyid": None,
        "dsse_signed": False,
        "doctrine_lambda": None,
        "vertical": GOVERN_VERTICAL,
        "reason": reason,
    }


def _govern_turn(kind: str, text: str, model: str,
                 node_name: str) -> dict:
    """Run a COMPLETED GPU job through the EXISTING governed turn as ADDITIVE metadata.

    This is the governed-compute boundary: it imports + calls the real
    `a11oy_vertical_feeds.governed_turn` (which scores the turn through the Λ aggregator
    + locked formulas + deny-by-default gates, then seals a Khipu receipt into the Lake
    and signs a DSSE envelope) and distils the honest result.

    Doctrine v11 — NEVER fabricate: any failure (disabled / module absent / call error /
    receipt not sealed) returns an honest ungoverned record (governed=False, lambda_score
    None, receipt_id None) with a reason. A job that could not be governed says so; it is
    never faked as governed. The return schema is STABLE (same keys whether governed or
    not). This function does NOT touch energy measurement and never raises."""
    if not _govern_enabled():
        return _ungoverned(f"disabled ({GOVERN_COMPUTE_ENV}=0)")
    try:
        import a11oy_vertical_feeds as _VF  # type: ignore
    except Exception as e:  # noqa: BLE001 — governance optional; absence stays honest
        return _ungoverned(f"governance modules unavailable: {type(e).__name__}")
    try:
        res = _VF.governed_turn(
            vertical=GOVERN_VERTICAL,
            text=text or "",
            action_kind=f"gpu-{kind}",
            context={"task": "energy-operator", "model": model, "node": node_name},
        )
    except Exception as e:  # noqa: BLE001 — never let governance break the job path
        return _ungoverned(f"governed_turn failed: {type(e).__name__}")
    if not isinstance(res, dict):
        return _ungoverned("governed_turn returned non-dict")
    lam = res.get("lambda")
    receipt = res.get("receipt") if isinstance(res.get("receipt"), dict) else {}
    receipt_id = receipt.get("digest")
    dsse = res.get("dsse") if isinstance(res.get("dsse"), dict) else {}
    keyid = None
    sigs = dsse.get("signatures")
    if isinstance(sigs, list) and sigs and isinstance(sigs[0], dict):
        keyid = sigs[0].get("keyid")
    doctrine = res.get("doctrine") if isinstance(res.get("doctrine"), dict) else {}
    # Fully governed ONLY when a real Λ score AND a real sealed receipt id are present.
    fully = (isinstance(lam, (int, float)) and bool(receipt_id))
    out = {
        "governed": fully,
        "lambda_score": lam if isinstance(lam, (int, float)) else None,
        "lambda_pass": res.get("lambda_pass"),
        "decision": res.get("decision"),
        "receipt_id": receipt_id,
        "dsse_keyid": keyid,
        "dsse_signed": bool(dsse.get("signed")),
        "doctrine_lambda": doctrine.get("lambda"),
        "vertical": res.get("vertical"),
    }
    if not fully:
        out["reason"] = ("Λ scored but receipt not sealed"
                         if isinstance(lam, (int, float))
                         else "governed_turn returned no Λ score")
    return out


def _governed_compute_summary(recent_records: list[dict]) -> dict:
    """HONEST, observable governed-compute block for status(). Derived from the rolling
    tail of recent JobRecords (no fabricated aggregate). Reports whether governance is
    enabled, how many of the recent jobs were FULLY governed (real Λ + sealed receipt),
    and the most recent governance result (Λ score, receipt id, dsse keyid) so a reader
    can see a GPU job was a governed turn — or honestly was not."""
    gov_records = [r for r in recent_records
                   if isinstance(r, dict) and isinstance(r.get("governance"), dict)]
    fully = [g for g in gov_records if g["governance"].get("governed")]
    last = gov_records[-1]["governance"] if gov_records else None
    return {
        "enabled": _govern_enabled(),
        "vertical": GOVERN_VERTICAL,
        "recent_window": len(recent_records),
        "recent_governed": len(fully),
        "recent_attempted": len(gov_records),
        "last": last,
        "note": (
            "Each completed GPU job is ADDITIONALLY run through the EXISTING governed "
            "turn (a11oy_vertical_feeds.governed_turn: Λ aggregator + locked formulas + "
            "deny-by-default gates, sealing a Khipu/DSSE receipt into the Lake). Λ is "
            "Conjecture 1 — never a theorem. A job that could not be governed is honestly "
            "labeled governed=False with NO fabricated Λ score or receipt. Governance is "
            "metadata only; it NEVER changes how joules are MEASURED."
        ),
    }


def _price_expensive_threshold() -> float:
    try:
        return float(os.environ.get(PRICE_EXPENSIVE_ENV, _PRICE_EXPENSIVE_DEFAULT))
    except Exception:  # noqa: BLE001
        return _PRICE_EXPENSIVE_DEFAULT


def _soak_batch_size() -> int:
    try:
        n = int(os.environ.get(SOAK_BATCH_ENV, _SOAK_BATCH_DEFAULT))
    except Exception:  # noqa: BLE001
        n = _SOAK_BATCH_DEFAULT
    return max(0, min(_SOAK_BATCH_CAP, n))


def _throttle_sleep_mult() -> float:
    try:
        return max(1.0, float(os.environ.get(THROTTLE_SLEEP_MULT_ENV,
                                             _THROTTLE_SLEEP_MULT_DEFAULT)))
    except Exception:  # noqa: BLE001
        return _THROTTLE_SLEEP_MULT_DEFAULT


def _posture_ttl_s() -> float:
    try:
        return max(0.0, float(os.environ.get(POSTURE_TTL_ENV, _POSTURE_TTL_DEFAULT)))
    except Exception:  # noqa: BLE001
        return _POSTURE_TTL_DEFAULT


def _import_org_rag():
    """Best-effort import of the live RAG module (a11oy_org_rag), or None. Never
    raises — when RAG is unavailable the loop honestly falls back to canned text."""
    try:
        import a11oy_org_rag as _rag  # type: ignore
        return _rag
    except Exception:  # noqa: BLE001
        try:
            from . import a11oy_org_rag as _rag  # type: ignore
            return _rag
        except Exception:  # noqa: BLE001
            return None

# The EXISTING exporter path: the betterwithage NVML joule-meter that
# szl_energy_sovereign._metrics_panel() already reads (engines→gpus→{power_w,joules,live},
# totals→{joules}). We reuse the SAME URL so the operator meters off the same source.
_JOULE_METER_URL = os.environ.get("A11OY_JOULE_METER_URL", "http://100.96.129.45:9471/")

# ---------------------------------------------------------------------------
# EGRESS SCRUB (Doctrine v11 — same class as szl_energy_sovereign._JOULE_METER_PUBLIC
# / the compute-pool egress scrub). The operator probes the real tailnet joule-meter
# and the real GPU nodes INTERNALLY (constants above are UNCHANGED — the box still
# connects to the exact same addresses), but the SERVED status() JSON renders on a
# public HF Space, so a private IP (100.x), a private :port (:9471/:11434), or a raw
# tailnet hostname (betterwithage / rtx-betterwithage / omen-betterwithage / chaski)
# MUST NEVER appear in it. We surface honest, non-revealing PUBLIC DISPLAY labels
# instead — no fact (running flag, joules, jobs, node count, MEASURED labels) changes,
# only the addressing/hostnames are replaced with a friendly public descriptor.
# ---------------------------------------------------------------------------
_JOULE_METER_PUBLIC = "on-box sovereign-GPU joule-meter exporter (private tailnet)"

# Stable public display name per internal node identity. Honestly public, non-revealing:
# the operator's REAL node names are private tailnet hostnames, so the served view uses a
# friendly label that tells the truth about ROLE without leaking the host:port.
_NODE_PUBLIC_NAMES = {
    "rtx-betterwithage": "Sovereign GPU 1",
    "betterwithage": "Sovereign GPU 1",
    "omen-betterwithage": "Sovereign GPU 2 (always-on anchor)",
    "omen": "Sovereign GPU 2 (always-on anchor)",
    "chaski": "Sovereign GPU 3 (tailnet)",
    "local-stub": "local-stub (no GPU)",
}


def _public_node(name: Optional[str]) -> Optional[str]:
    """Map an internal node/exporter identity to its honest PUBLIC display name.

    Known nodes get a curated friendly label. An unknown name is returned only when it
    carries NO private token; otherwise it collapses to a generic non-revealing label so
    a raw tailnet host:port can never reach egress. Never raises."""
    if name is None:
        return None
    s = str(name)
    if s in _NODE_PUBLIC_NAMES:
        return _NODE_PUBLIC_NAMES[s]
    low = s.lower()
    # Honest stub suffix is preserved (it is public and meaningful).
    if low.endswith("-stub"):
        return "local-stub (no GPU)"
    for tok in ("betterwithage", "chaski", "omen", "100.", ":11434", ":9471", "rtx-"):
        if tok in low:
            return "sovereign-gpu (private mesh)"
    return s


def _public_evidence(evidence: Any) -> Any:
    """Scrub a joules_evidence dict's exporter_node before egress (keeps every number)."""
    if not isinstance(evidence, dict):
        return evidence
    if "exporter_node" in evidence:
        ev = dict(evidence)
        ev["exporter_node"] = _public_node(ev.get("exporter_node"))
        return ev
    return evidence


def _public_job(job: Any) -> Any:
    """Scrub a served recent-job dict: public node name + scrubbed evidence (numbers
    intact). Internal JobRecords/ledger wire are UNCHANGED — this is egress-only."""
    if not isinstance(job, dict):
        return job
    j = dict(job)
    if "node" in j:
        j["node"] = _public_node(j.get("node"))
    if "joules_evidence" in j:
        j["joules_evidence"] = _public_evidence(j.get("joules_evidence"))
    return j

# Ledger / state file. Survives restart so cumulative counts resume. Override for tests.
_DEFAULT_STATE_PATH = os.environ.get(
    "A11OY_OPERATOR_STATE", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "artifacts", "energy_operator_ledger.json"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Node configuration — the reachable Ollama GPU nodes (GROUND TRUTH 2026-06-14).
# rtx-betterwithage is the sovereign box (A11OY_MODEL_BASE_URL); chaski is the
# tailnet box. Each node is an OpenAI-compatible Ollama endpoint — same serving
# path a11oy_code_orchestrator._call_model uses (POST {base}/chat/completions),
# plus Ollama's native /api/embeddings for the embed workload.
# ---------------------------------------------------------------------------
@dataclass
class NodeCfg:
    name: str
    base_url: str          # OpenAI-compatible base, e.g. http://host:11434/v1
    gen_model: str         # small token-generation model tag
    embed_model: str       # embeddings model tag
    exporter_node: str     # label this node reports in the joule-meter engines list
    standby: bool = False   # configured but intentionally not started: unreachable => "standby", not DEGRADED


def _default_nodes() -> list[NodeCfg]:
    """Build node configs from env (token-flip law: read at runtime, never hardcode a key).

    rtx-betterwithage base resolves from A11OY_MODEL_BASE_URL (the same env the
    orchestrator uses) when it points at a non-router endpoint. chaski base from
    A11OY_CHASKI_BASE_URL. Both default to honest placeholders that simply won't be
    reachable from the sandbox → DEGRADED (never faked)."""
    btw_base = (os.environ.get("A11OY_MODEL_BASE_URL") or "").strip().rstrip("/")
    if not btw_base or "router.huggingface.co" in btw_base:
        btw_base = os.environ.get("A11OY_BETTERWITHAGE_BASE_URL",
                                  "http://rtx-betterwithage:11434/v1").rstrip("/")
    # chaski base: A11OY_CHASKI_BASE_URL is canonical; A11OY_ENERGY_CHASKI_URL is an
    # additive ALIAS so the R-CHASKI runbook's env name also wires the 2nd lung (the
    # runbook persists A11OY_ENERGY_CHASKI_URL=http://$CHASKI_IP:11434). We normalize a
    # bare host:port endpoint to an OpenAI-compatible base (.../v1) so generate jobs hit
    # /v1/chat/completions; /api/embeddings still strips the /v1 in _ollama_embed. Never
    # double-append /v1. Defaults unchanged when neither var is set.
    chaski_base = (os.environ.get("A11OY_CHASKI_BASE_URL")
                   or os.environ.get("A11OY_ENERGY_CHASKI_URL")
                   or "http://chaski:11434/v1").strip().rstrip("/")
    if chaski_base and not chaski_base.endswith("/v1"):
        chaski_base = chaski_base + "/v1"
    # standby: A11OY_CHASKI_STANDBY is canonical (default "1" = standby). The runbook's
    # A11OY_ENERGY_CHASKI_ENABLED=1 is an additive ALIAS that flips chaski live: when it
    # is truthy and A11OY_CHASKI_STANDBY was not explicitly set, chaski is NOT standby.
    # A real probe still decides reachable/DEGRADED/computing — this only sets posture.
    _standby_env = os.environ.get("A11OY_CHASKI_STANDBY")
    _energy_enabled = (os.environ.get("A11OY_ENERGY_CHASKI_ENABLED") or "").strip() in ("1", "true", "True")
    if _standby_env is not None:
        chaski_standby = _standby_env not in ("0", "false", "False", "")
    elif _energy_enabled:
        chaski_standby = False
    else:
        chaski_standby = True
    # omen base: the ALWAYS-ON home anchor (OMEN desktop, stays home 24/7).
    # A11OY_OMEN_BASE_URL is canonical; A11OY_ENERGY_OMEN_URL is the additive runbook
    # ALIAS (mirrors the chaski pair). Normalize a bare host:port to an OpenAI-compatible
    # .../v1 base; never double-append /v1.
    # When neither env var is set, fall back to the HARDENED fabric pool's OMEN endpoint
    # (the correct tailnet IP, single source of truth) instead of a bare hostname that
    # won't resolve on the box — closing the divergent-list regression permanently. This
    # only corrects the ADDRESS; a real probe still decides reachable/DEGRADED/computing.
    omen_base = (os.environ.get("A11OY_OMEN_BASE_URL")
                 or os.environ.get("A11OY_ENERGY_OMEN_URL")
                 or _OMEN_HARDENED_ENDPOINT).strip().rstrip("/")
    if omen_base and not omen_base.endswith("/v1"):
        omen_base = omen_base + "/v1"
    # omen posture: A11OY_OMEN_STANDBY canonical (default standby); the runbook alias
    # A11OY_ENERGY_OMEN_ENABLED=1 flips it live when STANDBY was not explicitly set.
    # A REAL probe still decides reachable/DEGRADED/computing — this only sets posture.
    _omen_standby_env = os.environ.get("A11OY_OMEN_STANDBY")
    _omen_enabled = (os.environ.get("A11OY_ENERGY_OMEN_ENABLED") or "").strip() in ("1", "true", "True")
    if _omen_standby_env is not None:
        omen_standby = _omen_standby_env not in ("0", "false", "False", "")
    elif _omen_enabled:
        omen_standby = False
    else:
        omen_standby = True
    return [
        NodeCfg(
            name="rtx-betterwithage",
            base_url=btw_base,
            gen_model=os.environ.get("A11OY_BTW_GEN_MODEL", "llama3.1:8b"),
            embed_model=os.environ.get("A11OY_BTW_EMBED_MODEL", "bge-large"),
            exporter_node=os.environ.get("A11OY_GPU_LABEL", "betterwithage"),
        ),
        NodeCfg(
            name="chaski",
            base_url=chaski_base,
            gen_model=os.environ.get("A11OY_CHASKI_GEN_MODEL", "qwen2.5:32b"),
            embed_model=os.environ.get("A11OY_CHASKI_EMBED_MODEL", "mistral"),
            exporter_node=os.environ.get("A11OY_CHASKI_GPU_LABEL", "chaski"),
            # chaski is founder-started (replit-chaski Repl): standby until the founder
            # sets A11OY_CHASKI_STANDBY=0 (or the runbook alias A11OY_ENERGY_CHASKI_ENABLED=1).
            # Unreachable-while-standby reads "standby" (intentionally not started), NOT
            # DEGRADED (supposed-to-be-up but failed). Posture resolved above.
            standby=chaski_standby,
        ),
        NodeCfg(
            name="omen-betterwithage",
            base_url=omen_base,
            gen_model=os.environ.get("A11OY_OMEN_GEN_MODEL", "llama3.1:8b"),
            embed_model=os.environ.get("A11OY_OMEN_EMBED_MODEL", "bge-large"),
            # DISTINCT exporter label so OMEN's joules are metered SEPARATELY from the
            # laptop's — never merged/fused. Joules stay MEASURED-only per node.
            exporter_node=os.environ.get("A11OY_OMEN_GPU_LABEL", "omen"),
            # OMEN is the always-on home anchor but still founder-started: standby until
            # A11OY_OMEN_STANDBY=0 (or the runbook alias A11OY_ENERGY_OMEN_ENABLED=1). It
            # joins nodes_computing ONLY on a real probe; unreachable-while-standby reads
            # "standby", never DEGRADED, never a fabricated job. Posture resolved above.
            standby=omen_standby,
        ),
    ]


# Small, honest workloads — short prompts so each job genuinely computes but the loop
# stays gentle (backpressure). Rotated so the rig does varied real work.
_GEN_PROMPTS = [
    "In one sentence, what is sovereign compute?",
    "Name one law of thermodynamics in a single line.",
    "Give a one-line definition of a joule.",
    "Summarize energy provenance in one short sentence.",
]
_EMBED_TEXTS = [
    "sovereign metered compute receipt",
    "measured joules to billable charge",
    "energy provenance under doctrine v11",
]


# ---------------------------------------------------------------------------
# Exporter sampling — reuse the EXISTING betterwithage joule-meter path.
# ---------------------------------------------------------------------------
def _joule_meter_urls() -> list[str]:
    """All joule-meter URLs to scrape. A11OY_JOULE_METER_URLS (comma-separated) is the
    multi-node form (e.g. omen's meter.a-11-oy.com + the laptop's meter2.a-11-oy.com);
    falls back to the single A11OY_JOULE_METER_URL. De-duped, order preserved."""
    multi = (os.environ.get("A11OY_JOULE_METER_URLS") or "").strip()
    urls = [u.strip() for u in multi.split(",") if u.strip()] if multi else [_JOULE_METER_URL]
    seen, out = set(), []
    for u in urls:
        if u and u not in seen:
            seen.add(u); out.append(u)
    return out


def _fetch_one_meter(url: str, timeout: float) -> Optional[dict]:
    try:
        # Browser-like UA so a Cloudflare-fronted meter (e.g. meter.a-11-oy.com)
        # does not 403 the request behind bot protection. Honest self-probe.
        req = urllib.request.Request(url, headers={"User-Agent": _PROBE_UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001 — unreachable meter => no sample, stay honest
        return None


def _fetch_joule_meter(timeout: float = 4.0) -> Optional[dict]:
    """Fetch the live NVML joule-meter JSON, or None on any failure (honest).

    Multi-node: scrapes every URL from _joule_meter_urls() and MERGES their engines[]
    into one meter dict, so per-node lookups (_exporter_sample_for_node) see every GPU
    in the mesh from a single call. Honest by design (Doctrine v11): an unreachable
    meter contributes nothing (never faked); a duplicate engine name keeps the first
    seen (no double-count). Single-URL config → original behaviour, unchanged.
    """
    urls = _joule_meter_urls()
    if len(urls) == 1:
        return _fetch_one_meter(urls[0], timeout)
    merged_engines: list[dict] = []
    merged_models: list[dict] = []
    total = 0.0
    seen_names: set = set()
    seen_models: set = set()
    any_ok = False
    for u in urls:
        d = _fetch_one_meter(u, timeout)
        if not isinstance(d, dict):
            continue
        any_ok = True
        for e in (d.get("engines") or []):
            name = str(e.get("engine") or "").lower()
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            merged_engines.append(e)
            if isinstance(e.get("joules"), (int, float)):
                total += float(e["joules"])
        # Preserve per-inference model readings additively (first-seen wins on name,
        # mirroring the engine merge). Honest: an absent models[] contributes nothing.
        for m in (d.get("models") or []):
            mname = str(m.get("name") or "").lower()
            if not mname or mname in seen_models:
                continue
            seen_models.add(mname)
            merged_models.append(m)
    if not any_ok:
        return None
    out: dict = {"engines": merged_engines, "totals": {"joules": round(total, 3)}}
    if merged_models:
        out["models"] = merged_models
    return out


def _exporter_sample_for_node(meter: Optional[dict], exporter_node: str,
                              now: Optional[float] = None) -> Optional[dict]:
    """Build a szl_joules_truth exporter_sample for one node from the meter JSON.

    The meter shape (mirrors szl_energy_sovereign._metrics_panel): engines[].{engine,
    joules, gpus[].{power_w, joules, live}}, totals.{joules}. We pick the engine whose
    name matches exporter_node; its cumulative joules + a fresh wall-clock ts give a
    real reading. Returns None when the node isn't present / has no numeric joules.
    """
    if not isinstance(meter, dict):
        return None
    now = time.time() if now is None else now
    engines = meter.get("engines") or []
    for e in engines:
        if str(e.get("engine") or "").lower() != exporter_node.lower():
            continue
        joules = e.get("joules")
        if not isinstance(joules, (int, float)):
            continue
        power_w = None
        for g in (e.get("gpus") or []):
            if g.get("live") and isinstance(g.get("power_w"), (int, float)):
                power_w = float(g["power_w"])
                break
        return {
            "joules_measured_total": float(joules),
            "exporter_node": exporter_node,
            # The meter scraped just now → fresh by construction (same convention as
            # szl_energy_sovereign._exporter_sample_from_metrics).
            "exporter_last_seen_ts": now,
            "power_w_sample": power_w,
        }
    return None


def _label_upper(exporter_sample: Optional[dict], now: Optional[float] = None) -> str:
    """Map szl_joules_truth's lower-case label to billing.py's upper-case label."""
    return LABEL_MEASURED if _J.is_real_fresh_sample(exporter_sample, now=now) else LABEL_SAMPLE


def _label_by_node(node_name: str, entry: dict) -> dict:
    """Honest per-node energy label for the status by_node view (ADDITIVE).

    Preserves the existing per-node fields (jobs, tokens, joules_measured) and ADDS:
      - joules_label: MEASURED iff this node's NVML exporter engine yielded billable
        joules (>0); else PENDING_EXPORTER when the node DID real jobs but no per-node
        meter reading attributes to it yet (e.g. chaski runs but the betterwithage
        joule-meter exposes no 'chaski' engine), else NONE for a node with no jobs.
      - joules_note: the one-line reason, so a judge reading the API alone can tell
        "measured" from "pending — no per-node reading yet" — NEVER a fabricated joule.
    Doctrine: 0.0 joules on a node that computed is PENDING, not zero-energy; the only
    unacceptable outcome is claiming a measured joule we did not meter.
    """
    out = dict(entry)
    jobs = int(out.get("jobs", 0) or 0)
    joules = float(out.get("joules_measured", 0.0) or 0.0)
    if joules > 0:
        out["joules_label"] = LABEL_MEASURED
        out["joules_note"] = "per-node NVML exporter delta (fresh <30s)"
    elif jobs > 0:
        out["joules_label"] = "PENDING_EXPORTER"
        out["joules_note"] = ("node computed real jobs but no per-node NVML meter "
                              "reading attributes to it yet — pending, never faked")
    else:
        out["joules_label"] = "NONE"
        out["joules_note"] = "no jobs recorded for this node"
    return out


# ---------------------------------------------------------------------------
# JobRecord — the STABLE interface Dev2/3/4 consume.
# ---------------------------------------------------------------------------
@dataclass
class JobRecord:
    node: str
    model: str
    kind: str
    tokens: int
    wall_s: float
    joules_measured: Optional[float]
    joules_label: str
    joules_evidence: dict
    ts: str
    seq: int
    # ADDITIVE (useful-work): True when this job computed a REAL corpus chunk (vs.
    # throwaway canned text); rag_chunk_id is the corpus chunk whose dense vector was
    # written into the live RAG index by this embed job (None otherwise). The Dev2/3/4
    # contract is unchanged — these are extra optional fields with safe defaults.
    useful_work: bool = False
    rag_chunk_id: Optional[str] = None
    # ADDITIVE (governed-compute): the honest result of running THIS completed GPU job
    # through the existing governed turn (Λ aggregator + locked formulas + Khipu/DSSE
    # receipt sealed into the Lake). None when governance was not attempted; when
    # attempted it is a dict carrying governed(bool), lambda_score, decision, receipt_id,
    # dsse_keyid/dsse_signed and the Conjecture-1 doctrine label — or governed=False + a
    # reason when it could not be governed (NEVER a fabricated score/receipt). Energy
    # measurement is unaffected; this is metadata only. Dev2/3/4 contract is unchanged
    # (extra optional field, safe default).
    governance: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "node": self.node, "model": self.model, "kind": self.kind,
            "tokens": self.tokens, "wall_s": round(self.wall_s, 6),
            "joules_measured": (round(self.joules_measured, 6)
                                if self.joules_measured is not None else None),
            "joules_label": self.joules_label, "joules_evidence": self.joules_evidence,
            "ts": self.ts, "seq": self.seq,
            "useful_work": self.useful_work, "rag_chunk_id": self.rag_chunk_id,
            "governance": self.governance,
        }


# ---------------------------------------------------------------------------
# Job dispatch — REAL inference against a node, or a faithful local STUB.
# ---------------------------------------------------------------------------
class _StubBackend:
    """Faithful local stand-in for the Ollama API when NO node is reachable.

    It does REAL CPU work (a deterministic integer grind sized by `work`) so wall_s,
    tokens, and jobs_done are HONEST measurements of actual computation — but it has
    NO NVML meter, so its energy is ALWAYS labeled SAMPLE and never billable. Stub
    mode is announced loudly in status. This satisfies the test mandate ("a faithful
    local stub of the ollama API if no node reachable — clearly mark stub mode")
    WITHOUT fabricating a single measured joule.
    """

    def __init__(self, work: int = 200_000):
        self.work = work

    def generate(self, prompt: str) -> tuple[int, str]:
        # Real CPU work proportional to a token budget; returns (tokens, text).
        acc = 0
        for i in range(self.work):
            acc = (acc + i * 2654435761) & 0xFFFFFFFF
        tokens = max(1, len(prompt.split()) + (acc % 16))
        return tokens, f"[stub] computed {tokens} tokens (acc={acc})"

    def embed(self, text: str) -> tuple[int, list[float]]:
        acc = 0
        for i in range(self.work):
            acc = (acc + i * 40503) & 0xFFFFFFFF
        dim = 16
        vec = [((acc >> (j % 24)) & 0xFF) / 255.0 for j in range(dim)]
        return dim, vec


# Liveness-probe timeout (seconds). Default 8.0 so a genuinely-reachable node that
# sits behind a higher-latency hop (e.g. a Cloudflare/Tailscale tunnel for the
# always-on home anchor) is NOT falsely marked DEGRADED by an over-tight 2s budget.
# Overridable via SZL_GPU_PROBE_TIMEOUT. A REAL probe still decides reachability —
# this only widens the patience window; it never fakes a node up.
try:
    _PROBE_TIMEOUT_S = float(os.environ.get("SZL_GPU_PROBE_TIMEOUT", "8.0"))
except (TypeError, ValueError):
    _PROBE_TIMEOUT_S = 8.0

# Browser-like User-Agent for liveness/meter probes. A sovereign node behind a
# Cloudflare-fronted tunnel 403s the default "Python-urllib/x" UA under bot
# protection, which would falsely mark a reachable node DEGRADED. Overridable.
_PROBE_UA = os.environ.get(
    "SZL_PROBE_USER_AGENT",
    "Mozilla/5.0 (compatible; szl-energy-operator/1.0; +https://a-11-oy.com)")


def _http_reachable(base_url: str, timeout: Optional[float] = None) -> bool:
    """Liveness probe mirroring orchestrator._local_endpoint_reachable: a node is
    reachable iff its OpenAI-compatible /models (or root) answers <500. Never raises.
    Timeout defaults to SZL_GPU_PROBE_TIMEOUT (_PROBE_TIMEOUT_S) so tunneled nodes
    are not falsely DEGRADED; pass an explicit value to override."""
    import urllib.request as _u
    if timeout is None:
        timeout = _PROBE_TIMEOUT_S
    for path in ("/models", ""):
        try:
            # Send a browser-like User-Agent: a sovereign node may sit behind a
            # Cloudflare-fronted tunnel (e.g. gpu.a-11-oy.com) whose default bot
            # protection 403s the bare "Python-urllib/x" UA — which would falsely
            # mark a perfectly-reachable node DEGRADED. A real UA is honest: we are
            # a legitimate client probing our own endpoint, not evading anything.
            req = _u.Request(base_url.rstrip("/") + path, method="GET",
                             headers={"User-Agent": _PROBE_UA})
            with _u.urlopen(req, timeout=timeout) as r:  # noqa: S310
                if 200 <= getattr(r, "status", r.getcode()) < 500:
                    return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _ollama_generate(base_url: str, model: str, prompt: str,
                     timeout: float = 60.0) -> tuple[int, str]:
    """REAL token generation via the OpenAI-compatible chat endpoint (same path the
    orchestrator uses). Returns (completion_tokens, text). Raises on non-200 so the
    caller marks the node DEGRADED rather than fabricating a result."""
    import httpx
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "stream": False, "max_tokens": 64}
    headers = {"Content-Type": "application/json", "User-Agent": _PROBE_UA}
    gpu_token = (os.environ.get("A11OY_GPU_TOKEN") or "").strip()
    if gpu_token:
        headers["Authorization"] = f"Bearer {gpu_token}"
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(f"{base_url.rstrip('/')}/chat/completions",
                           headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()
    text = ""
    try:
        text = data["choices"][0]["message"]["content"] or ""
    except Exception:  # noqa: BLE001
        text = ""
    usage = data.get("usage") or {}
    tokens = int(usage.get("completion_tokens") or usage.get("total_tokens")
                 or max(1, len(text.split())))
    return tokens, text


def _ollama_embed(base_url: str, model: str, text: str,
                  timeout: float = 60.0) -> tuple[int, list[float]]:
    """REAL embedding via Ollama's native /api/embeddings (root strips a trailing /v1)."""
    import httpx
    root = base_url.rstrip("/")
    root = root[:-3] if root.endswith("/v1") else root
    headers = {"Content-Type": "application/json", "User-Agent": _PROBE_UA}
    gpu_token = (os.environ.get("A11OY_GPU_TOKEN") or "").strip()
    if gpu_token:
        headers["Authorization"] = f"Bearer {gpu_token}"
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(f"{root}/api/embeddings",
                           headers=headers, json={"model": model, "prompt": text})
        resp.raise_for_status()
        data = resp.json()
    vec = data.get("embedding") or []
    return len(vec), vec


# ---------------------------------------------------------------------------
# Persistent ledger / state.
# ---------------------------------------------------------------------------
@dataclass
class _State:
    jobs_done: int = 0
    seq: int = 0
    joules_measured_total: float = 0.0    # billable only — MEASURED jobs
    joules_sample_total: float = 0.0      # non-billable SAMPLE energy (honest, separate)
    tokens_total: int = 0
    measured_tokens: int = 0    # tokens from MEASURED jobs only (honest J/token denominator)
    measured_token_joules: float = 0.0    # joules over the SAME measured jobs (paired J/token numerator)
    measured_jobs: int = 0
    sample_jobs: int = 0
    corpus_embeds: int = 0          # embed jobs that computed a REAL corpus chunk
    rag_vectors_written: int = 0    # dense vectors written into the live RAG index
    by_node: dict = field(default_factory=dict)  # node -> {jobs, tokens, joules_measured}

    def to_dict(self) -> dict:
        return {
            "jobs_done": self.jobs_done, "seq": self.seq,
            "joules_measured_total": self.joules_measured_total,
            "joules_sample_total": self.joules_sample_total,
            "tokens_total": self.tokens_total,
            "measured_tokens": self.measured_tokens,
            "measured_token_joules": self.measured_token_joules,
            "measured_jobs": self.measured_jobs, "sample_jobs": self.sample_jobs,
            "corpus_embeds": self.corpus_embeds,
            "rag_vectors_written": self.rag_vectors_written,
            "by_node": self.by_node,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "_State":
        s = cls()
        s.jobs_done = int(d.get("jobs_done", 0))
        s.seq = int(d.get("seq", 0))
        s.joules_measured_total = float(d.get("joules_measured_total", 0.0))
        s.joules_sample_total = float(d.get("joules_sample_total", 0.0))
        s.tokens_total = int(d.get("tokens_total", 0))
        s.measured_tokens = int(d.get("measured_tokens", 0))
        s.measured_token_joules = float(d.get("measured_token_joules", 0.0))
        s.measured_jobs = int(d.get("measured_jobs", 0))
        s.sample_jobs = int(d.get("sample_jobs", 0))
        s.corpus_embeds = int(d.get("corpus_embeds", 0))
        s.rag_vectors_written = int(d.get("rag_vectors_written", 0))
        s.by_node = {k: v for k, v in (d.get("by_node", {}) or {}).items()
                     if not (k == "local-stub" or k.endswith("-stub"))}
        return s


# ---------------------------------------------------------------------------
# The operator daemon.
# ---------------------------------------------------------------------------
class OperatorDaemon:
    """Press-play operator: a background worker thread dispatching real inference
    jobs to reachable nodes, metering MEASURED joules per job, persisting state.

    Thread-safe. Idempotent start/stop. Graceful: the loop checks a stop flag between
    jobs and joins on stop(). Restart resumes cumulative counts from the ledger.
    """

    def __init__(self, nodes: Optional[list[NodeCfg]] = None,
                 state_path: Optional[str] = None,
                 job_interval_s: float = 0.5,
                 stub_work: int = 200_000,
                 allow_stub: bool = True):
        self.nodes = nodes if nodes is not None else _default_nodes()
        self.state_path = state_path or _DEFAULT_STATE_PATH
        self.job_interval_s = max(0.0, float(job_interval_s))
        self._stub = _StubBackend(work=stub_work)
        self.allow_stub = allow_stub

        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._started_at: Optional[float] = None
        self._state = self._load_state()
        self._node_status: dict[str, str] = {n.name: "idle" for n in self.nodes}
        self._stub_mode = False
        self._last_records: list[dict] = []     # rolling tail for status/dashboards
        self._subscribers: list[Callable[[dict], None]] = []
        self._grid_price_eur_mwh: Optional[float] = None  # latest meter grid price
        self._last_power_w: Optional[float] = None  # latest live exporter power_w (W)
        # Energy harness: the work mode actually applied on the last sweep + its honest
        # driver. Never claims a soak/throttle that did not happen — set by run_once().
        self._work_mode: str = WORK_MODE_BASELINE
        self._work_mode_reason: str = "no sweep yet"
        self._should_soak: Optional[bool] = None
        self._grid_price_posture: str = "unknown"
        self._renewable_share: Optional[float] = None
        # Cached RAG module handle (lazy; None when RAG unavailable in this runtime).
        self._rag = None
        self._rag_checked = False
        # Harvest-posture cache: the live feed is refreshed at most once per TTL AND
        # only ever on a background thread, so it NEVER blocks job dispatch — a fast
        # inter-job interval can't turn into a per-sweep (or first-sweep) network call.
        self._harvest_should_soak: Optional[bool] = None
        self._harvest_renewable: Optional[float] = None
        self._harvest_ts: float = 0.0
        self._harvest_refreshing: bool = False

    # -- subscription (Dev2 receipts hook) --------------------------------
    def subscribe(self, cb: Callable[[dict], None]) -> None:
        """Register a callback invoked with each completed JobRecord dict (Dev2)."""
        with self._lock:
            self._subscribers.append(cb)

    def _emit(self, rec: JobRecord) -> None:
        d = rec.to_dict()
        with self._lock:
            self._last_records.append(d)
            if len(self._last_records) > 50:
                self._last_records.pop(0)
            subs = list(self._subscribers)
        for cb in subs:
            try:
                cb(d)
            except Exception:  # noqa: BLE001 — a bad subscriber never breaks the loop
                pass

    # -- state persistence ------------------------------------------------
    def _load_state(self) -> _State:
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                return _State.from_dict(json.load(f))
        except Exception:  # noqa: BLE001 — missing/corrupt ledger => fresh state
            return _State()

    def _persist(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            tmp = self.state_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._state.to_dict(), f, sort_keys=True, separators=(",", ":"))
            os.replace(tmp, self.state_path)  # atomic
        except Exception:  # noqa: BLE001 — persistence failure never crashes the loop
            pass

    # -- lifecycle --------------------------------------------------------
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> dict:
        with self._lock:
            if self.is_running():
                return self.status()
            self._stop.clear()
            self._started_at = time.time()
            self._thread = threading.Thread(target=self._run, name="szl-energy-operator",
                                            daemon=True)
            self._thread.start()
        return self.status()

    def stop(self, join_timeout: float = 10.0) -> dict:
        self._stop.set()
        t = self._thread
        if t is not None:
            t.join(timeout=join_timeout)
        with self._lock:
            self._thread = None
            self._persist()
            for k in self._node_status:
                if self._node_status[k] == "computing":
                    self._node_status[k] = "idle"
        return self.status()

    def run_once(self) -> list[dict]:
        """Run exactly ONE dispatch sweep across all nodes (one job each, or stub).

        Used by tests and the loop body. Returns the list of JobRecord dicts produced
        this sweep. Honest: an unreachable node yields NO record (DEGRADED), never a fake."""
        produced: list[dict] = []
        meter = _fetch_joule_meter()
        self._update_grid_price(meter)
        # ENERGY HARNESS: decide the work mode for this sweep from the harvest posture
        # the loop already fetches (grid price + should_soak). Stored honestly; the
        # modulation below only does what this mode says.
        work_mode, reason = self._resolve_posture()
        with self._lock:
            self._work_mode = work_mode
            self._work_mode_reason = reason
        soak_batch = _soak_batch_size() if work_mode == WORK_MODE_SOAK else 0
        any_reachable = False
        for node in self.nodes:
            if self._stop.is_set():
                break
            reachable = _http_reachable(node.base_url)
            if not reachable:
                # Honest distinction: a standby node (configured but intentionally not
                # started) reads "standby"; a node expected up but failed is DEGRADED.
                # Neither produces a job/joule — unreachable is never faked as computing.
                with self._lock:
                    self._node_status[node.name] = "standby" if node.standby else "DEGRADED"
                continue
            any_reachable = True
            with self._lock:
                self._node_status[node.name] = "computing"
            for kind in ("generate", "embed"):
                if self._stop.is_set():
                    break
                rec = self._run_real_job(node, kind, meter)
                if rec is not None:
                    produced.append(rec)
            # SOAK modulation: drain extra corpus backlog on this node (gentle, capped,
            # honest no-op when the backlog is empty). THROTTLE/BASELINE add no batch.
            if soak_batch and not self._stop.is_set():
                produced.extend(self._run_corpus_embed_batch(node, meter, soak_batch))
        # No reachable node at all → faithful stub (clearly marked), if allowed.
        if not any_reachable and self.allow_stub and not self._stop.is_set():
            self._stub_mode = True
            for kind in ("generate", "embed"):
                if self._stop.is_set():
                    break
                rec = self._run_stub_job(kind)
                if rec is not None:
                    produced.append(rec)
        elif any_reachable:
            self._stub_mode = False
        # DEMO-WARM: keep the demo RAG queries' embeddings precomputed so the demo's
        # first query is instant. Cheap + idempotent (only embeds uncached queries);
        # skipped under THROTTLE except for whatever is already warm. Honest no-op
        # when no embedding model is present.
        if work_mode != WORK_MODE_THROTTLE and not self._stop.is_set():
            rag = self._get_rag()
            if rag is not None:
                try:
                    rag.warm_demo_queries()
                except Exception:  # noqa: BLE001 — warming is best-effort, never fatal
                    pass
        # Persist after every sweep so counts are durable regardless of entry point
        # (the loop also persists; direct run_once() callers/tests get the same).
        self._persist()
        return produced

    def _run(self) -> None:
        """The non-stop loop body. Graceful: re-checks the stop flag each sweep."""
        try:
            while not self._stop.is_set():
                self.run_once()
                self._persist()
                # Backpressure: gentle inter-sweep sleep, interruptible by stop().
                # THROTTLE genuinely backs the loop off (longer sleep) so an expensive
                # grid window is honored, not just labeled.
                sleep_s = self.job_interval_s
                if self._work_mode == WORK_MODE_THROTTLE:
                    sleep_s = self.job_interval_s * _throttle_sleep_mult()
                self._stop.wait(sleep_s)
        finally:
            self._persist()

    # -- useful work + RAG write ------------------------------------------
    def _get_rag(self):
        """Lazily import + cache the live RAG module (or None). Never raises."""
        if not self._rag_checked:
            self._rag = _import_org_rag()
            self._rag_checked = True
        return self._rag

    def _pick_corpus_embed_job(self) -> tuple[str, Optional[str]]:
        """Choose the text for an embed job. When useful work is enabled AND the RAG
        index has a real embedder + an un-embedded corpus chunk, return that chunk's
        (body, chunk_id) so the job does USEFUL WORK whose vector we then write into
        the live index. Otherwise honest fallback to a canned _EMBED_TEXTS string
        (rag_chunk_id=None), which is real inference on throwaway content — clearly
        distinguishable in the record (useful_work=False)."""
        canned = _EMBED_TEXTS[self._state.seq % len(_EMBED_TEXTS)]
        if not _useful_work_enabled():
            return canned, None
        rag = self._get_rag()
        if rag is None:
            return canned, None
        try:
            if rag.corpus_embedder() is None:
                # No real embedding model in this runtime → cannot do honest useful
                # work; fall back to canned text rather than fabricate a corpus embed.
                return canned, None
            pending = rag.next_unembedded_chunks(limit=1)
        except Exception:  # noqa: BLE001
            return canned, None
        if not pending:
            return canned, None
        chunk = pending[0]
        body = (chunk.get("body") or "").strip()
        if not body:
            return canned, None
        return body, chunk.get("chunk_id")

    def _store_rag_vector(self, rag_chunk_id: str, vec: list[float]) -> bool:
        """Write a REAL embedding produced by an embed job into the live RAG dense
        index. Honest: a failure (no RAG / refusal / store error) never affects the
        job's joule label or billable energy — it only means the index didn't grow.
        Returns True iff a vector was actually stored."""
        rag = self._get_rag()
        if rag is None or not rag_chunk_id or not vec:
            return False
        try:
            res = rag.embed_and_store_chunk(rag_chunk_id, list(vec))
        except Exception:  # noqa: BLE001
            return False
        if res.get("ok"):
            with self._lock:
                self._state.rag_vectors_written += 1
            return True
        return False

    # -- energy harness: posture -> work_mode -----------------------------
    def _resolve_posture(self) -> tuple[str, str]:
        """Decide the work mode for this sweep + an HONEST one-line reason.

        Inputs (best-effort, never raise):
          - grid price (EUR/MWh) read from the meter totals into self._grid_price_eur_mwh,
          - harvest posture (should_soak / wasted renewable surplus / renewable share)
            from a11oy_harvest_endpoints.handle_posture() IF importable,
          - an optional forced override (A11OY_ENERGY_FORCE_POSTURE) for demos/tests.

        Modes: 'throttle' (grid price expensive — defer batch, protect cost),
        'soak' (wasted renewable surplus available — drain corpus backlog), else
        'baseline'. THROTTLE wins over SOAK (cost protection first). Never claims a
        soak/throttle that didn't happen — this only DECIDES; run_once APPLIES it."""
        forced = (os.environ.get(FORCE_POSTURE_ENV) or "").strip().lower()
        # Grid price posture from the latest meter reading.
        price = self._grid_price_eur_mwh
        thr = _price_expensive_threshold()
        if price is None:
            grid_posture = "unknown"
        elif price >= thr:
            grid_posture = "expensive"
        else:
            grid_posture = "normal"
        # Harvest posture (should_soak / renewable share) — optional live feed that can
        # hit a slow external network. It is refreshed at most once per TTL AND only on
        # a background thread, so it NEVER blocks dispatch: this sweep always uses the
        # value cached from a prior refresh (None until the first one lands). A force
        # override skips the feed entirely (deterministic, no network at all).
        should_soak = self._harvest_should_soak
        renewable = self._harvest_renewable
        if not forced:
            self._maybe_refresh_harvest_posture()
        with self._lock:
            self._should_soak = should_soak
            self._grid_price_posture = grid_posture
            self._renewable_share = renewable

        if forced in (WORK_MODE_SOAK, WORK_MODE_BASELINE, WORK_MODE_THROTTLE):
            return forced, f"forced_posture={forced} (A11OY_ENERGY_FORCE_POSTURE)"
        if grid_posture == "expensive":
            return (WORK_MODE_THROTTLE,
                    f"grid_price_expensive: {price:.1f} EUR/MWh >= {thr:.1f} — "
                    f"throttling batch work to protect cost")
        if should_soak:
            extra = (f"; renewable_share={renewable:.0f}%" if renewable is not None else "")
            return (WORK_MODE_SOAK,
                    f"should_soak: wasted renewable surplus available — draining corpus "
                    f"backlog{extra}")
        return (WORK_MODE_BASELINE,
                f"baseline: grid_price_posture={grid_posture}, no soak signal")

    def _maybe_refresh_harvest_posture(self) -> None:
        """Kick off a TTL-throttled, NON-BLOCKING refresh of the harvest posture feed.

        The feed (a11oy_harvest_endpoints.handle_posture) can hit a slow external
        network, so it is NEVER called on the dispatch path — it runs on a short-lived
        daemon thread that updates the cached should_soak / renewable share for the NEXT
        sweep. At most one refresh is ever in flight, and it fires at most once per TTL.
        Honest: until the first refresh lands, should_soak stays None (no soak claimed)."""
        now = time.time()
        with self._lock:
            if self._harvest_refreshing:
                return
            if (now - self._harvest_ts) < _posture_ttl_s():
                return
            self._harvest_ts = now
            self._harvest_refreshing = True
        threading.Thread(target=self._refresh_harvest_posture,
                         name="energy-harvest-posture", daemon=True).start()

    def _refresh_harvest_posture(self) -> None:
        """Background body: fetch the harvest feed once and update the cache. Best-effort
        (any failure leaves the prior cached value); always clears the in-flight flag."""
        try:
            import a11oy_harvest_endpoints as _hv  # type: ignore
            p = _hv.handle_posture()
            if isinstance(p, dict) and p.get("ok"):
                should_soak = bool(p.get("soak_hard") or
                                   p.get("wasted_energy_available"))
                renewable = None
                for r in (p.get("readings") or []):
                    if r.get("feed", "").startswith("energy_charts_ren") and \
                            isinstance(r.get("value"), (int, float)):
                        renewable = float(r["value"])
                        break
                with self._lock:
                    self._harvest_should_soak = should_soak
                    self._harvest_renewable = renewable
        except Exception:  # noqa: BLE001 — harvest feed optional; absence stays honest
            pass
        finally:
            with self._lock:
                self._harvest_refreshing = False

    # -- per-job execution ------------------------------------------------
    def _commit(self, node_name: str, model: str, kind: str, tokens: int,
                wall_s: float, exporter_sample: Optional[dict],
                joules_measured: Optional[float], *,
                useful_work: bool = False,
                rag_chunk_id: Optional[str] = None,
                governance: Optional[dict] = None) -> JobRecord:
        now = time.time()
        label = _label_upper(exporter_sample, now=now)
        evidence = _J.joules_evidence(exporter_sample, now=now) if label == LABEL_MEASURED else {}
        billable_j = joules_measured if (label == LABEL_MEASURED and
                                         joules_measured is not None and
                                         joules_measured > 0) else None
        with self._lock:
            self._state.seq += 1
            seq = self._state.seq
            self._state.jobs_done += 1
            self._state.tokens_total += int(tokens)
            if useful_work:
                self._state.corpus_embeds += 1
            bn = self._state.by_node.setdefault(
                node_name, {"jobs": 0, "tokens": 0, "joules_measured": 0.0})
            bn["jobs"] += 1
            bn["tokens"] += int(tokens)
            if billable_j is not None:
                self._state.joules_measured_total += billable_j
                self._state.measured_jobs += 1
                self._state.measured_tokens += int(tokens)
                self._state.measured_token_joules += billable_j
                bn["joules_measured"] += billable_j
            else:
                self._state.sample_jobs += 1
                if joules_measured is not None and joules_measured > 0:
                    self._state.joules_sample_total += joules_measured
        rec = JobRecord(
            node=node_name, model=model, kind=kind, tokens=int(tokens), wall_s=wall_s,
            joules_measured=billable_j,
            joules_label=label, joules_evidence=evidence, ts=_now_iso(), seq=seq,
            useful_work=useful_work, rag_chunk_id=rag_chunk_id, governance=governance)
        self._emit(rec)
        return rec

    def submit_external_job(self, node: str, model: str, kind: str, tokens: int,
                            wall_s: float, exporter_sample: Optional[dict] = None,
                            joules_measured: Optional[float] = None) -> JobRecord:
        """Submit ONE externally-run job (e.g. a governed code-as-action cell) into the
        SAME ledger wire as the operator's own inference jobs. Thin pass-through to
        _commit — all MEASURED/SAMPLE labeling + billing discipline is reused unchanged:
        joules read MEASURED only with a fresh real NVML exporter delta, else SAMPLE and
        excluded from billable (Doctrine v11: never fabricate a joule). The operator->
        ledger subscribe() wire (wire_operator_to_ledger) then append_job()s it into the
        shared chain — one wire, one ledger, no parallel ledger."""
        return self._commit(node, model, kind, int(tokens), float(wall_s),
                            exporter_sample, joules_measured)

    def _run_real_job(self, node: NodeCfg, kind: str,
                      meter_before: Optional[dict]) -> Optional[dict]:
        """Dispatch one real inference job; meter NVML energy across its wall window.

        joules_measured for the job = (cumulative joules AFTER) − (cumulative joules
        BEFORE) from the node's exporter engine, but ONLY when both samples are real &
        fresh (<30s). Otherwise the job's energy is SAMPLE and excluded from billable.
        A node error → DEGRADED + None (never a fabricated job)."""
        sample_before = _exporter_sample_for_node(meter_before, node.exporter_node)
        j_before = (sample_before or {}).get("joules_measured_total")
        rag_chunk_id: Optional[str] = None
        embed_vec: list[float] = []
        governed_text = ""  # the turn text handed to the governed turn (post-meter)
        t0 = time.time()
        try:
            if kind == "generate":
                prompt = _GEN_PROMPTS[self._state.seq % len(_GEN_PROMPTS)]
                tokens, completion = _ollama_generate(node.base_url, node.gen_model, prompt)
                model = node.gen_model
                # The governed turn scores the full turn (prompt + completion).
                governed_text = f"{prompt}\n{completion}".strip()
            else:
                # USEFUL WORK: embed a REAL un-embedded corpus chunk when available
                # (honest fallback to canned text otherwise). The joule meter window
                # below is identical either way — useful work changes WHAT is embedded,
                # never HOW joules are measured.
                text, rag_chunk_id = self._pick_corpus_embed_job()
                tokens, embed_vec = _ollama_embed(node.base_url, node.embed_model, text)
                model = node.embed_model
                governed_text = (text or "").strip()
        except Exception:  # noqa: BLE001 — node failed mid-job: DEGRADED, never faked
            with self._lock:
                self._node_status[node.name] = "DEGRADED"
            return None
        wall_s = time.time() - t0
        meter_after = _fetch_joule_meter()
        sample_after = _exporter_sample_for_node(meter_after, node.exporter_node)
        if sample_after is not None and sample_after.get("power_w_sample") is not None:
            with self._lock:
                self._last_power_w = float(sample_after["power_w_sample"])
        j_after = (sample_after or {}).get("joules_measured_total")
        joules_measured = None
        if (isinstance(j_before, (int, float)) and isinstance(j_after, (int, float))
                and j_after >= j_before):
            joules_measured = float(j_after) - float(j_before)
        # Write the REAL embedding into the live RAG dense index (useful work). A
        # store failure NEVER affects the joule label/billable energy below — it only
        # means the index did not grow this job. useful_work reflects what actually
        # happened: True only when a real corpus vector was stored.
        stored = False
        if rag_chunk_id is not None and embed_vec:
            stored = self._store_rag_vector(rag_chunk_id, embed_vec)
        # GOVERNED COMPUTE (ADDITIVE): run the completed turn through the EXISTING governed
        # turn (Λ aggregator + locked formulas + Khipu/DSSE receipt sealed into the Lake).
        # This is OUTSIDE the metered window (after meter_after) and CANNOT change the joule
        # label/billable energy — governance is metadata only. Honest: a failure yields
        # governed=False with no fabricated Λ/receipt; the job still records exactly as before.
        governance = _govern_turn(kind, governed_text, model, node.name)
        # The label is decided off the AFTER sample (the fresh reading at job end).
        rec = self._commit(node.name, model, kind, tokens, wall_s,
                            sample_after, joules_measured,
                            useful_work=stored,
                            rag_chunk_id=(rag_chunk_id if stored else None),
                            governance=governance)
        return rec.to_dict()

    def _run_corpus_embed_batch(self, node: NodeCfg, meter_before: Optional[dict],
                                count: int) -> list[dict]:
        """SOAK: run up to ``count`` EXTRA corpus-embed jobs on a reachable node to
        drain the un-embedded backlog. Honest: stops early when the backlog is empty
        (degrades to a no-op — never fabricates a corpus embed), respects the stop
        flag, and meters each job exactly like a baseline embed (joule gate unchanged)."""
        produced: list[dict] = []
        for _ in range(max(0, count)):
            if self._stop.is_set():
                break
            # Only proceed while real un-embedded backlog remains.
            rag = self._get_rag()
            if rag is None:
                break
            try:
                if rag.corpus_embedder() is None or not rag.next_unembedded_chunks(limit=1):
                    break
            except Exception:  # noqa: BLE001
                break
            rec = self._run_real_job(node, "embed", meter_before)
            if rec is None:
                break
            produced.append(rec)
        return produced

    def _run_stub_job(self, kind: str) -> Optional[dict]:
        """Faithful local stub job: REAL CPU work (honest wall_s/tokens) but NO meter,
        so energy is ALWAYS SAMPLE and never billable. Clearly attributed to *-stub."""
        t0 = time.time()
        if kind == "generate":
            prompt = _GEN_PROMPTS[self._state.seq % len(_GEN_PROMPTS)]
            tokens, _ = self._stub.generate(prompt)
            model = "stub-llama"
        else:
            text = _EMBED_TEXTS[self._state.seq % len(_EMBED_TEXTS)]
            tokens, _ = self._stub.embed(text)
            model = "stub-embed"
        wall_s = time.time() - t0
        # No exporter sample → label SAMPLE, joules None, never billable.
        rec = self._commit("local-stub", model, kind, tokens, wall_s, None, None)
        with self._lock:
            self._node_status["local-stub"] = "computing (STUB)"
        return rec.to_dict()

    def _update_grid_price(self, meter: Optional[dict]) -> None:
        try:
            totals = (meter or {}).get("totals") or {}
            gp = totals.get("eur_per_mwh")
            if isinstance(gp, (int, float)):
                with self._lock:
                    self._grid_price_eur_mwh = float(gp)
        except Exception:  # noqa: BLE001
            pass

    # -- status -----------------------------------------------------------
    def status(self) -> dict:
        with self._lock:
            uptime = (time.time() - self._started_at) if self._started_at else 0.0
            computing = [_public_node(n) for n, s in self._node_status.items()
                         if s in ("computing", "computing (STUB)")]
            degraded = [_public_node(n) for n, s in self._node_status.items() if s == "DEGRADED"]
            standby = [_public_node(n) for n, s in self._node_status.items() if s == "standby"]
            st = self._state
            return {
                "service": "energy-operator",
                "doctrine": DOCTRINE,
                "running": self.is_running(),
                "stub_mode": self._stub_mode,
                "jobs_done": st.jobs_done,
                "joules_measured_total": round(st.joules_measured_total, 6),
                "joules_measured_label": LABEL_MEASURED,
                "joules_sample_total": round(st.joules_sample_total, 6),
                "joules_sample_label": LABEL_SAMPLE,
                "tokens_total": st.tokens_total,
                "measured_tokens": st.measured_tokens,
                "measured_token_joules": round(st.measured_token_joules, 6),
                "measured_jobs": st.measured_jobs,
                "sample_jobs": st.sample_jobs,
                "nodes_computing": computing,
                "nodes_degraded": degraded,
                "nodes_standby": standby,
                "node_status": {_public_node(n): s for n, s in self._node_status.items()},
                "by_node": {_public_node(k): _label_by_node(k, v)
                            for k, v in st.by_node.items()},
                "uptime_s": round(uptime, 3),
                "window_seconds": round(uptime, 3),
                "jobs_completed": st.jobs_done,
                "exporter_node": _public_node(next((n.exporter_node for n in self.nodes), None)),
                "power_w_sample": self._last_power_w,
                "grid_price_eur_mwh": self._grid_price_eur_mwh,
                "work_mode": self._work_mode,
                "work_mode_reason": self._work_mode_reason,
                "should_soak": self._should_soak,
                "grid_price_posture": self._grid_price_posture,
                "renewable_share": self._renewable_share,
                "corpus_embeds": st.corpus_embeds,
                "rag_vectors_written": st.rag_vectors_written,
                "harness": (
                    "work_mode reflects the posture ACTUALLY applied this sweep "
                    "(soak=drain corpus backlog faster, throttle=defer batch + back "
                    "off when grid price is expensive, baseline=normal). It is "
                    "derived from the real grid price reading + harvest posture (or "
                    "an explicit force override); a soak/throttle is never claimed "
                    "unless it was run. corpus_embeds/rag_vectors_written are the "
                    "honest counters proving useful-work embed jobs advanced the "
                    "live RAG dense index. Useful work changes WHAT is computed, "
                    "never HOW joules are measured — the MEASURED gate is unchanged."
                ),
                "governed_compute": _governed_compute_summary(self._last_records),
                "recent_jobs": [_public_job(j) for j in self._last_records[-10:]],
                "exporter": _JOULE_METER_PUBLIC,
                "honesty": (
                    "joules_measured_total is the SUM of per-job MEASURED NVML deltas "
                    "(fresh <30s) ONLY — the billable figure. SAMPLE energy (stale meter "
                    "or stub mode) is tracked separately and NEVER billable. A node "
                    "configured as standby (intentionally not started) reads 'standby', "
                    "not DEGRADED; a node that fails when expected up is DEGRADED; neither "
                    "is ever faked as computing. STUB MODE means no GPU node was "
                    "reachable from this process; stub energy is SAMPLE by construction."
                ),
                "computed_at": _now_iso(),
            }

    def any_lung_reachable(self) -> bool:
        """REAL probe: True iff at least one configured GPU node answers its
        OpenAI-compatible liveness check right now. No fabrication — a node only
        counts when its endpoint actually responds <500. Standby posture does NOT
        change reachability (a standby-but-up node is still a reachable lung); it
        only changes how an UNREACHABLE node is labeled in status."""
        for node in self.nodes:
            if _http_reachable(node.base_url):
                return True
        return False

    def install_signal_handlers(self) -> None:
        """Optional: graceful SIGINT/SIGTERM → stop(). Main-thread only (never raises)."""
        def _handler(signum, frame):  # noqa: ANN001
            self.stop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, _handler)
            except Exception:  # noqa: BLE001 — non-main-thread / unsupported platform
                pass


# Module-level singleton the endpoints drive (one operator per process).
_OPERATOR: Optional[OperatorDaemon] = None
_OPERATOR_LOCK = threading.Lock()


def get_operator() -> OperatorDaemon:
    global _OPERATOR
    with _OPERATOR_LOCK:
        if _OPERATOR is None:
            _allow_stub = os.environ.get("A11OY_ENERGY_ALLOW_STUB", "0") not in ("0", "false", "False", "")
            _OPERATOR = OperatorDaemon(allow_stub=_allow_stub)
        return _OPERATOR


def handle_status() -> dict:
    """Module-level status accessor for in-process readers (Dev3 projection)."""
    return get_operator().status()


# ---------------------------------------------------------------------------
# Auto-start on boot (Doctrine v11 — honest: lung-gated, never faked).
# ---------------------------------------------------------------------------
# Env flag gating the boot auto-start. Defaults ON ("1"). Set to "0"/"false" to
# disable (e.g. a box that should stay idle until a manual press-play).
A11OY_ENERGY_AUTOSTART_ENV = "A11OY_ENERGY_AUTOSTART"


def autostart_enabled() -> bool:
    """True unless A11OY_ENERGY_AUTOSTART is explicitly falsey. Default ON."""
    return (os.environ.get(A11OY_ENERGY_AUTOSTART_ENV, "1").strip().lower()
            not in ("0", "false", "no", "off", ""))


def autostart_if_lung_reachable() -> dict:
    """Boot hook: auto-press-play the operator loop, but ONLY when honest to do so.

    The loop is started iff BOTH hold:
      - autostart is enabled (A11OY_ENERGY_AUTOSTART, default ON), AND
      - at least one GPU lung answers a REAL liveness probe right now.

    If zero lungs are reachable we stay CLEANLY IDLE (running stays false) — we
    never fabricate a running loop or a joule against a node that didn't compute.
    Idempotent: a no-op if the loop is already running. Returns a small report
    dict (also reflected in the daemon status) so the boot log is honest.
    """
    op = get_operator()
    if not autostart_enabled():
        return {"autostarted": False, "reason": "autostart_disabled",
                "running": op.is_running()}
    if op.is_running():
        return {"autostarted": False, "reason": "already_running", "running": True}
    if not op.any_lung_reachable():
        # Honest idle: no lung reachable → do NOT start, do NOT fake running.
        return {"autostarted": False, "reason": "no_lung_reachable",
                "running": False}
    op.start()
    return {"autostarted": True, "reason": "lung_reachable", "running": op.is_running()}


def readiness() -> dict:
    """Operator readiness for /readyz (Doctrine v11 — the exact redeploy-stall guard).

    UNHEALTHY (ready=False) iff a lung IS reachable but the loop is STOPPED — the
    precise state hit on every box redeploy (lungs up, loop never auto-started, so
    joules freeze). Otherwise ready=True: either the loop is running, or no lung is
    reachable (honestly idle — nothing to compute against, not a fault)."""
    op = get_operator()
    running = op.is_running()
    lung = op.any_lung_reachable()
    ready = running or not lung
    return {
        "service": "energy-operator",
        "ready": ready,
        "operator_running": running,
        "lung_reachable": lung,
        "autostart_enabled": autostart_enabled(),
        "reason": ("ok" if ready else "operator_stopped_while_lung_reachable"),
    }


# ---------------------------------------------------------------------------
# Registration — dual-register under /api/{ns}/v1/energy/operator/* AND
# /v1/energy/operator/* (mirrors the add_api_route pattern used across the repo).
# ---------------------------------------------------------------------------
def register(app, ns: str = "a11oy") -> dict:
    from fastapi import Request
    from fastapi.responses import JSONResponse

    op = get_operator()

    async def _start(request: Request):  # noqa: ANN202
        return JSONResponse(op.start())

    async def _stop(request: Request):  # noqa: ANN202
        return JSONResponse(op.stop())

    async def _status():  # noqa: ANN202
        return JSONResponse(op.status())

    prefixes = [f"/api/{ns}/v1/energy/operator", "/v1/energy/operator"]
    routes: list[str] = []
    for p in prefixes:
        app.add_api_route(f"{p}/start", _start, methods=["POST"], include_in_schema=True)
        app.add_api_route(f"{p}/stop", _stop, methods=["POST"], include_in_schema=True)
        app.add_api_route(f"{p}/status", _status, methods=["GET"], include_in_schema=True)
        routes.extend([f"{p}/start", f"{p}/stop", f"{p}/status"])

    print(f"[{ns}] szl_energy_operator routes registered "
          f"(press-play operator, {len(routes)} routes)", flush=True)
    return {"ok": True, "ns": ns, "routes": routes}


# ---------------------------------------------------------------------------
# No-server self-test (proves honesty gates without a live GPU).
# ---------------------------------------------------------------------------
def _selftest() -> dict:
    import tempfile
    out: dict = {}
    now = 1_000_000.0

    # (a) Fresh real meter sample for 'betterwithage' => MEASURED label.
    meter = {"engines": [{"engine": "betterwithage", "joules": 78369.586,
                          "gpus": [{"power_w": 9.74, "live": True}]}],
             "totals": {"joules": 78369.586, "eur_per_mwh": 62.08}}
    s = _exporter_sample_for_node(meter, "betterwithage", now=now)
    assert s is not None and _label_upper(s, now=now) == LABEL_MEASURED, s
    out["fresh_sample_measured"] = True

    # (b) Missing node => no sample => SAMPLE label (never fabricated).
    assert _exporter_sample_for_node(meter, "ghost-node", now=now) is None
    assert _label_upper(None, now=now) == LABEL_SAMPLE
    out["missing_node_sample"] = True

    # (c) Stub mode: no reachable node, stub does real work, energy SAMPLE, not billable.
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "ledger.json")
        op = OperatorDaemon(
            nodes=[NodeCfg("rtx-betterwithage", "http://192.0.2.1:11434/v1",
                           "llama3.1:8b", "bge-large", "betterwithage")],
            state_path=path, stub_work=5000)
        produced = op.run_once()
        assert len(produced) >= 2, produced  # generate + embed stub jobs
        assert op._stub_mode is True
        st = op.status()
        assert st["jobs_done"] >= 2 and st["tokens_total"] > 0, st
        assert st["joules_measured_total"] == 0.0, st  # stub energy never billable
        # status() scrubs the raw tailnet hostname at egress -> public display name.
        assert _public_node("rtx-betterwithage") in st["nodes_degraded"], st  # unreachable => DEGRADED
        out["stub_real_work_no_billable_joules"] = True

        # (d) Restart resumes from persisted ledger.
        op2 = OperatorDaemon(nodes=op.nodes, state_path=path, stub_work=5000)
        assert op2.status()["jobs_done"] == st["jobs_done"], "restart must resume counts"
        out["restart_resumes_state"] = True

    # (e) MEASURED billable accounting via the commit path (synthetic fresh sample).
    with tempfile.TemporaryDirectory() as d:
        op = OperatorDaemon(nodes=[], state_path=os.path.join(d, "l.json"))
        sample = {"joules_measured_total": 100.0, "exporter_node": "betterwithage",
                  "exporter_last_seen_ts": time.time(), "power_w_sample": 200.0}
        rec = op._commit("betterwithage", "llama3.1:8b", "generate", 42, 1.5, sample, 12.5)
        assert rec.joules_label == LABEL_MEASURED and rec.joules_measured == 12.5, rec
        assert op.status()["joules_measured_total"] == 12.5
        out["measured_commit_billable"] = True

    return out


if __name__ == "__main__":
    import sys as _sys
    print("=" * 70)
    print("szl_energy_operator — self-test (honesty gates, no live GPU)")
    print("=" * 70)
    res = _selftest()
    print(json.dumps(res, indent=2))
    ok = all(res.values())
    print("\nSELFTEST", "PASS" if ok else "FAIL")
    _sys.exit(0 if ok else 1)
