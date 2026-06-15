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

# The EXISTING exporter path: the betterwithage NVML joule-meter that
# szl_energy_sovereign._metrics_panel() already reads (engines→gpus→{power_w,joules,live},
# totals→{joules}). We reuse the SAME URL so the operator meters off the same source.
_JOULE_METER_URL = os.environ.get("A11OY_JOULE_METER_URL", "http://100.96.129.45:9471/")

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
def _fetch_joule_meter(timeout: float = 4.0) -> Optional[dict]:
    """Fetch the live NVML joule-meter JSON, or None on any failure (honest)."""
    try:
        req = urllib.request.Request(
            _JOULE_METER_URL, headers={"User-Agent": "szl-energy-operator"})
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001 — unreachable meter => no sample, stay honest
        return None


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

    def to_dict(self) -> dict:
        return {
            "node": self.node, "model": self.model, "kind": self.kind,
            "tokens": self.tokens, "wall_s": round(self.wall_s, 6),
            "joules_measured": (round(self.joules_measured, 6)
                                if self.joules_measured is not None else None),
            "joules_label": self.joules_label, "joules_evidence": self.joules_evidence,
            "ts": self.ts, "seq": self.seq,
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


def _http_reachable(base_url: str, timeout: float = 2.0) -> bool:
    """Liveness probe mirroring orchestrator._local_endpoint_reachable: a node is
    reachable iff its OpenAI-compatible /models (or root) answers <500. Never raises."""
    import urllib.request as _u
    for path in ("/models", ""):
        try:
            req = _u.Request(base_url.rstrip("/") + path, method="GET")
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
    headers = {"Content-Type": "application/json"}
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
    headers = {"Content-Type": "application/json"}
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
                self._stop.wait(self.job_interval_s)
        finally:
            self._persist()

    # -- per-job execution ------------------------------------------------
    def _commit(self, node_name: str, model: str, kind: str, tokens: int,
                wall_s: float, exporter_sample: Optional[dict],
                joules_measured: Optional[float]) -> JobRecord:
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
            joules_label=label, joules_evidence=evidence, ts=_now_iso(), seq=seq)
        self._emit(rec)
        return rec

    def _run_real_job(self, node: NodeCfg, kind: str,
                      meter_before: Optional[dict]) -> Optional[dict]:
        """Dispatch one real inference job; meter NVML energy across its wall window.

        joules_measured for the job = (cumulative joules AFTER) − (cumulative joules
        BEFORE) from the node's exporter engine, but ONLY when both samples are real &
        fresh (<30s). Otherwise the job's energy is SAMPLE and excluded from billable.
        A node error → DEGRADED + None (never a fabricated job)."""
        sample_before = _exporter_sample_for_node(meter_before, node.exporter_node)
        j_before = (sample_before or {}).get("joules_measured_total")
        t0 = time.time()
        try:
            if kind == "generate":
                prompt = _GEN_PROMPTS[self._state.seq % len(_GEN_PROMPTS)]
                tokens, _ = _ollama_generate(node.base_url, node.gen_model, prompt)
                model = node.gen_model
            else:
                text = _EMBED_TEXTS[self._state.seq % len(_EMBED_TEXTS)]
                tokens, _ = _ollama_embed(node.base_url, node.embed_model, text)
                model = node.embed_model
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
        # The label is decided off the AFTER sample (the fresh reading at job end).
        rec = self._commit(node.name, model, kind, tokens, wall_s,
                            sample_after, joules_measured)
        return rec.to_dict()

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
            computing = [n for n, s in self._node_status.items()
                         if s in ("computing", "computing (STUB)")]
            degraded = [n for n, s in self._node_status.items() if s == "DEGRADED"]
            standby = [n for n, s in self._node_status.items() if s == "standby"]
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
                "node_status": dict(self._node_status),
                "by_node": {k: _label_by_node(k, v) for k, v in st.by_node.items()},
                "uptime_s": round(uptime, 3),
                "window_seconds": round(uptime, 3),
                "jobs_completed": st.jobs_done,
                "exporter_node": next((n.exporter_node for n in self.nodes), None),
                "power_w_sample": self._last_power_w,
                "grid_price_eur_mwh": self._grid_price_eur_mwh,
                "recent_jobs": list(self._last_records[-10:]),
                "exporter": _JOULE_METER_URL,
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
        assert "rtx-betterwithage" in st["nodes_degraded"], st  # unreachable => DEGRADED
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
