"""
szl_governed_api.py — the SELLABLE governed-inference surface.

What a buyer calls:
    POST /govern/infer   {"prompt": "...", "vertical": "general", "declared": "PUBLIC"}

What they get back (the product):
    {
      "answer":   "<model output, ONLY if governance decision == allow>",
      "decision": "allow" | "review" | "deny",
      "governance": {                      # from a11oy_vertical_feeds.governed_turn
          "lambda": float,                 # Λ (Conjecture 1 — advisory, never a theorem)
          "lambda_floor": float,
          "lambda_pass": bool,
          "gates": [...],                  # deny-by-default safety gates that fired
          "route": {...},
          "doctrine": {...}
      },
      "receipt": {...},                    # SIGNED, hash-chained Khipu receipt (P5/P6)
      "dsse":    {...},                    # DSSE envelope over the receipt
      "energy": {                          # per-turn attribution, honestly labeled
          "joules": None,                  # no exclusive-workload witness
          "label": "UNAVAILABLE",
          "evidence": {"device_window": {...} | None, ...}
      },
      "honesty": "..."                     # plain-English statement of what is/!is proven
    }

DOCTRINE (non-negotiable, enforced here):
  - Λ is Conjecture 1, never a theorem. Labeled "advisory" everywhere.
  - The answer is returned ONLY if governed_turn decision == "allow".
    On "review"/"deny" we return the governance verdict + receipt and NO answer.
    (Never claim more than is real — the half-state is the only unacceptable outcome.)
  - A fresh direct NVML delta can MEASURE a GPU device window, not exclusive
    energy for one inference. Per-turn joules remain UNAVAILABLE without measured
    exclusive-workload bounds; no joule is fabricated or billed as exact.
  - The receipt is whatever szl_khipu/szl_dsse actually produced — if signing was
    unavailable, the receipt says so (chain_verified / honesty fields preserved).
"""
from __future__ import annotations

import os
import time
import json
import hashlib
import ipaddress
import math
import threading as _threading
import urllib.request
import urllib.error
from urllib.parse import urlsplit

# --- the governance IP (merged on main) ---------------------------------------
try:
    import a11oy_vertical_feeds as _avf          # provides governed_turn(...)
except Exception:  # pragma: no cover
    _avf = None

# --- config (env-overridable; honest defaults) --------------------------------
# THE SOVEREIGN MESH. Each engine is a real (ollama_base, meter_base, model, name)
# backend. A governed turn is routed to a LIVE engine; energy is aggregated across
# every reachable meter. Engines that are down are honestly skipped (never faked).
# Override the whole mesh with SZL_MESH_JSON='[{"name":..,"ollama":..,"meter":..,"model":..}]'.
_DEFAULT_MESH = [
    {"name": "Sovereign GPU 2 (tower · RTX 4060 Ti · anchor)",
     "ollama": "https://gpu.a-11-oy.com",  "meter": "https://meter.a-11-oy.com",  "model": "llama3.1:8b",
     "exporter": "omen"},
    {"name": "Sovereign GPU 1 (laptop · RTX 5050 · Blackwell)",
     "ollama": "https://gpu2.a-11-oy.com", "meter": "https://meter2.a-11-oy.com", "model": "qwen2.5:3b",
     "exporter": "betterwithage"},
]
try:
    MESH = json.loads(os.environ["SZL_MESH_JSON"]) if os.environ.get("SZL_MESH_JSON") else _DEFAULT_MESH
except Exception:
    MESH = _DEFAULT_MESH
# Back-compat single-engine envs still honored as an override of engine 0.
if os.environ.get("SZL_OLLAMA_BASE"):
    MESH[0]["ollama"] = os.environ["SZL_OLLAMA_BASE"]
if os.environ.get("SZL_METER_BASE"):
    MESH[0]["meter"] = os.environ["SZL_METER_BASE"]
if os.environ.get("SZL_MODEL"):
    MESH[0]["model"] = os.environ["SZL_MODEL"]

# --- GLM (MIT, license-clean) as a first-class sovereign engine ---------------
# GLM-4.7-Flash GGUF (unsloth/GLM-4.7-Flash-GGUF) runs in Ollama on the user's
# consumer GPUs. We add it as a frontier (T2) tier engine pointing at the user's
# own nodes. The exact Ollama tag depends on how the user imports the GGUF, so it
# is env-overridable and we DO NOT assume it is installed — _engine_live() checks
# /api/tags for the model and honestly reports the engine DOWN until the user pulls
# it. Until then GLM never serves and is never claimed live.
SZL_GLM_MODEL  = os.environ.get("SZL_GLM_MODEL", "glm-4.7-flash")
SZL_GLM_OLLAMA = os.environ.get("SZL_GLM_OLLAMA", MESH[0].get("ollama", "https://gpu.a-11-oy.com"))
SZL_GLM_METER  = os.environ.get("SZL_GLM_METER",  MESH[0].get("meter",  "https://meter.a-11-oy.com"))
# Tag pre-existing engines as T1 (fast) unless they already carry a tier — keeps
# default (no-effort) behavior identical: anchor (engine 0) stays first-preferred.
for _e in MESH:
    _e.setdefault("tier", "T1")
    _e.setdefault("effort", "fast")
# Append GLM (frontier) so default pick order is unchanged (anchor first). Skip if
# the user already wired a GLM-like engine via SZL_MESH_JSON, or opted out.
if not os.environ.get("SZL_GLM_DISABLE") and not any(e.get("is_glm") for e in MESH) \
        and not any(e.get("model") == SZL_GLM_MODEL for e in MESH):
    MESH.append({
        "name":   f"GLM-4.7-Flash (sovereign · MIT · {SZL_GLM_MODEL})",
        "ollama": SZL_GLM_OLLAMA, "meter": SZL_GLM_METER, "model": SZL_GLM_MODEL,
        "tier": "T2", "effort": "frontier", "is_glm": True,
    })

# Map a buyer-requested effort onto an engine tier (used by _pick_engine).
_EFFORT_TO_TIER = {
    "fast": "T1", "low": "T1", "t1": "T1", "quick": "T1",
    "high": "T2", "frontier": "T2", "t2": "T2", "deep": "T2",
}

METER_FRESH_S = float(os.environ.get("SZL_METER_FRESH_S", "30"))
METER_SAMPLE_MAX_AGE_S = min(METER_FRESH_S, 12.0)
HTTP_TIMEOUT  = float(os.environ.get("SZL_HTTP_TIMEOUT", "60"))
# Browser-like UA: Cloudflare 403s the default python-urllib UA.
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """An engine probe must not follow a redirect to a different endpoint."""

    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _http_json(url: str, payload: dict | None = None, timeout: float = HTTP_TIMEOUT) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    if data is None:
        try:
            if (not isinstance(url, str) or not url or not url.isascii()
                    or any(ord(char) <= 32 or ord(char) == 127 for char in url)):
                raise ValueError
            parsed = urlsplit(url)
            if (parsed.scheme not in ("http", "https") or not parsed.hostname
                    or parsed.username is not None or parsed.password is not None
                    or parsed.fragment):
                raise ValueError
            _ = parsed.port
            if parsed.scheme == "http" and not ipaddress.ip_address(parsed.hostname).is_loopback:
                raise ValueError
        except (TypeError, ValueError):
            raise ValueError("invalid engine JSON target") from None
        req = urllib.request.Request(url, headers={
            "User-Agent": _UA, "Accept": "application/json"}, method="GET")
        with urllib.request.build_opener(_NoRedirect()).open(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    req = urllib.request.Request(
        url, data=data,
        headers={"User-Agent": _UA, "Content-Type": "application/json"},
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _meter_json(url: str, *, timeout: float) -> dict:
    """Only meter reads receive exact-target HMAC and Access headers."""
    from szl_meter_access import open_meter_get
    with open_meter_get(url, timeout=timeout, headers={
            "User-Agent": _UA, "Accept": "application/json"}) as response:
        return json.loads(response.read().decode())


def _finite_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _counter_samples(doc: dict, now: float) -> dict | None:
    """Accept only complete, fresh, direct NVML counters, not exporter aggregates."""
    engines = doc.get("engines") if isinstance(doc, dict) else None
    if not isinstance(engines, list) or not engines:
        return None
    samples, seen_gpu_ids = {}, set()
    for engine in engines:
        if not isinstance(engine, dict):
            return None
        name = str(engine.get("engine") or "").strip().lower()
        gpus = engine.get("gpus")
        if not name or name in samples or not isinstance(gpus, list) or not gpus:
            return None
        counters, joules = [], []
        for gpu in gpus:
            if not isinstance(gpu, dict) or gpu.get("live") is not True \
                    or gpu.get("joules_method") != "NVML_COUNTER_DELTA":
                return None
            gpu_id, epoch = gpu.get("gpu_uuid"), gpu.get("counter_epoch")
            sample_ts, value = gpu.get("sample_ts"), gpu.get("joules")
            if (not isinstance(gpu_id, str) or not gpu_id.strip()
                    or gpu_id in seen_gpu_ids or not isinstance(epoch, str)
                    or not epoch.strip() or not _finite_number(sample_ts)
                    or not 0 <= now - sample_ts <= METER_SAMPLE_MAX_AGE_S
                    or not _finite_number(value) or value < 0):
                return None
            seen_gpu_ids.add(gpu_id)
            counters.append((gpu_id, epoch))
            joules.append(float(value))
        total_joules = sum(joules)
        if not _finite_number(total_joules):
            return None
        samples[name] = {
            "joules": total_joules,
            "sample_ts_min": min(gpu["sample_ts"] for gpu in gpus),
            "sample_ts_max": max(gpu["sample_ts"] for gpu in gpus),
            "counter_id": hashlib.sha256(json.dumps(sorted(counters)).encode()).hexdigest(),
            "gpu_ids": [hashlib.sha256(gpu_id.encode()).hexdigest()
                        for gpu_id, _ in sorted(counters)],
            "gpu_counters": {hashlib.sha256(gpu["gpu_uuid"].encode()).hexdigest():
                             float(gpu["joules"]) for gpu in gpus},
        }
    return samples


def _meter_one(meter_base: str) -> tuple[float | None, dict]:
    """Read one meter; accept only its complete per-GPU counter evidence."""
    meter_base = meter_base.rstrip("/")
    try:
        m = _meter_json(meter_base + "/", timeout=10)
    except Exception as e:
        return None, {"meter": meter_base, "reachable": False, "note": str(e)[:80]}
    samples = _counter_samples(m, time.time())
    total = sum(s["joules"] for s in samples.values()) if samples is not None else None
    qualified = samples is not None and _finite_number(total)
    return (total if qualified else None), {
        "meter": meter_base, "reachable": True, "fresh": qualified, "live": qualified,
        "exporter": m.get("exporter") if isinstance(m, dict) else None,
        "ts": m.get("ts") if isinstance(m, dict) else None,
        "counter_samples": samples or {},
        "gpu_ids": [gpu_id for sample in (samples or {}).values()
                    for gpu_id in sample["gpu_ids"]],
        "note": None if qualified else "complete fresh NVML counter evidence unavailable",
    }


def _meter_snapshot() -> tuple[float | None, dict]:
    """Read each physical meter once; never count a shared GLM/anchor URL twice."""
    per = []
    total = 0.0
    any_ok = False
    sources = {}
    gpu_ids = set()
    duplicate_gpu_source = False
    for eng in MESH:
        meter = str(eng.get("meter") or "").rstrip("/")
        if meter not in sources:
            sources[meter] = _meter_one(meter)
            for gpu_id in sources[meter][1].get("gpu_ids", []) or []:
                if gpu_id in gpu_ids:
                    duplicate_gpu_source = True
                gpu_ids.add(gpu_id)
            source_joules = sources[meter][0]
            if source_joules is not None:
                total += source_joules
                any_ok = True
        j, source_ev = sources[meter]
        ev = {**source_ev, "engine": eng.get("name")}
        if j is not None:
            ev["source_qualified"] = True
        per.append(ev)
    aggregate_ok = any_ok and not duplicate_gpu_source and _finite_number(total)
    return (total if aggregate_ok else None), {
        "engines": per, "aggregated": aggregate_ok,
        "unique_meter_count": len(sources),
        "duplicate_gpu_source": duplicate_gpu_source,
        "aggregate_overflow": any_ok and not _finite_number(total),
    }


def _served_meter_delta(served_by: str | None, before: dict, after: dict, *,
                        call_start_ts: float, call_end_ts: float) -> tuple[float | None, str]:
    """Measure an enclosing GPU device window, not energy exclusive to a turn."""
    name = (served_by or "").removesuffix(" (failover)")
    matches = [e for e in MESH if e.get("name") == name]
    if len(matches) != 1:
        return None, "serving engine is not uniquely identified in the mesh"
    engine = matches[0]
    meter = str(engine.get("meter") or "").rstrip("/")
    exporter = str(engine.get("exporter") or "").strip().lower()
    if not meter or not exporter or sum(
            str(e.get("meter") or "").rstrip("/") == meter for e in MESH) != 1:
        return None, "serving GPU meter source is ambiguous or shared"
    values = []
    for snapshot in (before, after):
        if not isinstance(snapshot, dict) or snapshot.get("duplicate_gpu_source"):
            return None, "meter source duplicated across snapshots"
        entries = snapshot.get("engines")
        if not isinstance(entries, list):
            return None, "serving meter source changed or is missing"
        rows = [e for e in entries if isinstance(e, dict) and e.get("engine") == name]
        if len(rows) != 1 or rows[0].get("meter") != meter:
            return None, "serving meter source changed or is missing"
        row = rows[0]
        counter_samples = row.get("counter_samples")
        sample = counter_samples.get(exporter) if isinstance(counter_samples, dict) else None
        if not all(row.get(k) is True for k in ("reachable", "fresh", "live")) \
                or not isinstance(sample, dict) \
                or not isinstance(sample.get("counter_id"), str) \
                or not sample["counter_id"]:
            return None, "serving engine has no fresh direct NVML counter"
        values.append(sample)
    if values[0].get("counter_id") != values[1].get("counter_id"):
        return None, "serving GPU identity or counter epoch changed"
    start_counters, end_counters = (value.get("gpu_counters") for value in values)
    start_ts = values[0].get("sample_ts_max")
    end_ts = values[1].get("sample_ts_min")
    if (not isinstance(start_counters, dict) or not start_counters
            or not isinstance(end_counters, dict)
            or start_counters.keys() != end_counters.keys()
            or isinstance(call_start_ts, bool) or isinstance(call_end_ts, bool)
            or not isinstance(call_start_ts, (int, float))
            or not isinstance(call_end_ts, (int, float))
            or not math.isfinite(call_start_ts) or not math.isfinite(call_end_ts)
            or call_end_ts <= call_start_ts
            or isinstance(start_ts, bool) or isinstance(end_ts, bool)
            or not isinstance(start_ts, (int, float))
            or not isinstance(end_ts, (int, float))
            or not math.isfinite(start_ts) or not math.isfinite(end_ts)
            or end_ts <= start_ts or start_ts > call_start_ts
            or end_ts < call_end_ts):
        return None, "GPU counter samples do not enclose the model call"
    deltas = []
    for gpu_id, start in start_counters.items():
        end = end_counters[gpu_id]
        if (not _finite_number(start) or not _finite_number(end)
                or start < 0 or end < start):
            return None, "serving GPU counter is invalid or reset"
        deltas.append(end - start)
    delta = sum(deltas)
    if not _finite_number(delta):
        return None, "serving GPU counter aggregate is invalid"
    if delta <= 0.5:
        return None, "no positive source-bound GPU window delta"
    return round(delta, 3), "serving GPU device-window NVML counter delta"


def _engine_live(eng: dict) -> bool:
    """An engine is LIVE only if its Ollama is reachable AND the engine's model is
    actually installed there (present in /api/tags). This is what keeps GLM honest:
    until the user `ollama pull`s the GLM tag, the GLM engine reports DOWN — we never
    fake it live. (A model-less engine entry falls back to reachability only.)"""
    base = eng.get("ollama", "")
    model = eng.get("model", "")
    try:
        tags = _http_json(base + "/api/tags", timeout=6)
    except Exception:
        return False
    if not model:
        return True
    names = [m.get("name", "") for m in (tags.get("models") or [])]
    if model in names:
        return True
    bm = model.split(":")[0]
    return any(n.split(":")[0] == bm for n in names)


# Least-connections coordinator state (folded from szl-router/mesh_coordinator.py,
# our reimplementation). Spreads concurrent turns across live nodes instead of
# pinning the anchor under load. Single-request behavior is UNCHANGED: with all
# inflight == 0, MESH order wins (anchor first), exactly as before.
_INFLIGHT: dict = {}
_INFLIGHT_LOCK = _threading.Lock()


def _pick_engine(effort: str | None = None) -> dict | None:
    """Choose a LIVE engine for this turn: least-inflight first, MESH order as the
    tie-break (so a single idle turn still picks the anchor). Effort/tier preference
    preserved: when an effort is requested, restrict to that tier's live engines if
    any, else honest failover to any live engine. None only if the whole mesh is down."""
    live = [eng for eng in MESH if _engine_live(eng)]
    if not live:
        return None
    pool = live
    if effort:
        want = _EFFORT_TO_TIER.get(str(effort).strip().lower())
        if want is not None:
            match = [eng for eng in live if eng.get("tier") == want]
            if match:
                pool = match
    with _INFLIGHT_LOCK:
        return sorted(pool, key=lambda e: (_INFLIGHT.get(e["name"], 0), MESH.index(e)))[0]


def _inflight_inc(name: str):
    with _INFLIGHT_LOCK:
        _INFLIGHT[name] = _INFLIGHT.get(name, 0) + 1


def _inflight_dec(name: str):
    with _INFLIGHT_LOCK:
        _INFLIGHT[name] = max(0, _INFLIGHT.get(name, 0) - 1)


def _glm_engine() -> dict | None:
    return next((e for e in MESH if e.get("is_glm")), None)


def _provider_config() -> dict | None:
    """OPTIONAL remote GLM provider (z.ai / HF inference). DISABLED by default.

    Returns None unless BOTH SZL_GLM_PROVIDER is set AND a key is in the env —
    we never call a remote provider without an explicit opt-in and a key, and the
    key is read from the environment, never hardcoded. A remote turn is honestly
    labeled NOT sovereign / NOT on-metal."""
    name = (os.environ.get("SZL_GLM_PROVIDER") or "").strip().lower()
    if not name:
        return None
    key = os.environ.get("SZL_GLM_PROVIDER_KEY", "")
    if not key:
        return None  # opt-in present but no key → stay OFF, never call unauthenticated
    defaults = {
        "zai": ("https://api.z.ai/api/paas/v4/chat/completions", "z.ai"),
        "z.ai": ("https://api.z.ai/api/paas/v4/chat/completions", "z.ai"),
        "hf": ("https://router.huggingface.co/v1/chat/completions", "HuggingFace Inference"),
        "huggingface": ("https://router.huggingface.co/v1/chat/completions", "HuggingFace Inference"),
    }
    url, label = defaults.get(name, (None, name))
    url = os.environ.get("SZL_GLM_PROVIDER_URL") or url
    model = os.environ.get("SZL_GLM_PROVIDER_MODEL") or SZL_GLM_MODEL
    if not url:
        return None
    return {"name": name, "label": label, "url": url, "key": key, "model": model}


def _provider_generate(prompt: str, prov: dict) -> tuple[str, dict]:
    """Route a GLM turn to the remote provider (OpenAI-compatible chat completions).
    Honestly labeled remote: sovereign=False, on_metal=False, so the energy join
    will report UNAVAILABLE (no NVML meter behind a remote API — never fabricated)."""
    payload = {"model": prov["model"],
               "messages": [{"role": "user", "content": prompt}],
               "stream": False}
    req = urllib.request.Request(
        prov["url"], data=json.dumps(payload).encode(),
        headers={"User-Agent": _UA, "Content-Type": "application/json",
                 "Authorization": "Bearer " + prov["key"]},
        method="POST")
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
        out = json.loads(r.read().decode())
    text = ""
    try:
        text = out["choices"][0]["message"]["content"]
    except Exception:
        text = out.get("response", "")
    return text, {
        "engine": f"GLM remote provider ({prov['label']})",
        "provider": prov["name"],
        "provider_url": prov["url"],
        "model": out.get("model", prov["model"]),
        "sovereign": False,
        "on_metal": False,
    }


def _ollama_generate(prompt: str, eng: dict) -> tuple[str, dict]:
    out = _http_json(eng["ollama"] + "/api/generate",
                     {"model": eng["model"], "prompt": prompt, "stream": False})
    return out.get("response", ""), {
        "engine": eng.get("name"),
        "ollama_base": eng["ollama"],
        "model": out.get("model", eng["model"]),
        "eval_count": out.get("eval_count"),
        "total_duration_ns": out.get("total_duration"),
    }


def _with_pb_reference(energy: dict) -> dict:
    """Attach the founder-captured MEASURED physical-bounds reference to an energy
    block when the shipped certificate is READABLE. This is a point-in-time on-metal
    reading (2026-06-14), NOT this request's live joules — its own label says so, and
    the per-request `joules`/`label` keep their honest meaning. If the cert cannot be
    read the reference is simply absent (never a fabricated MEASURED). Single source
    of truth: szl_physical_bounds reads the file; numbers are never hardcoded here."""
    try:
        import szl_physical_bounds as _szl_pb
        ref = _szl_pb.energy_reference_block()
        if ref is not None and isinstance(energy, dict):
            energy["physical_bounds_reference"] = ref
    except Exception as _pb_e:  # pragma: no cover - additive, defensive
        import sys as _pb_sys
        print(f"[a11oy] physical-bounds reference skipped (non-fatal): {_pb_e!r}",
              file=_pb_sys.stderr)
    return energy


def govern_infer(prompt: str, *, vertical: str = "general",
                 declared: str = "PUBLIC", severity: float = 0.0,
                 effort: str | None = None, request_id: str | None = None,
                 request_origin: str = "") -> dict:
    """The product. Governance-first, answer only if allowed, honest energy + receipt.

    `effort` (optional, e.g. "fast"/"frontier") is a tier hint: a "frontier"/T2 turn
    prefers the GLM engine on-metal; if GLM is requested but not live on-metal AND the
    optional remote provider is enabled, the turn is routed to the provider (honestly
    labeled remote). Governance (Λ + gates + signed receipt) is IDENTICAL regardless of
    which engine answers — the governance is the product; GLM is just another engine."""
    if _avf is None or not hasattr(_avf, "governed_turn"):
        return {"decision": "error",
                "honesty": "governance module a11oy_vertical_feeds.governed_turn not importable",
                "answer": None}

    # 1) GOVERN FIRST (Λ + deny-by-default gates + signed receipt). Never skipped.
    g = _avf.governed_turn(vertical, prompt, declared=declared,
                           severity=severity, action_kind="inference")
    decision = g.get("decision", "deny")

    # 1b) CONFORMAL + ECE on the advisory Λ (GAP 1/2). Guarded + additive: on any
    #     failure this is None and Λ falls back to MODELED — never breaks the turn.
    cb = _conformal_blocks(g, prompt)

    # 2) Read GPU counters around the model call; they cannot prove exclusivity.
    gateway_requested = effort == "szl-router"
    _, ev_before = (None, {}) if gateway_requested else _meter_snapshot()
    call_start_ts = time.time()

    answer = None
    gen_meta: dict = {}
    served_by = None
    if decision == "allow" and gateway_requested:
        import szl_router_client
        # The existing governance result supplies the sensitivity floor. The
        # remote gateway cannot establish an air-gap, even if its provider says so.
        sensitivity = (g.get("route") or {}).get("sensitivity", {}).get("class")
        if not isinstance(declared, str) or declared.upper() not in {"PUBLIC", "INTERNAL"}:
            sensitivity = None
        gen_meta = szl_router_client.complete(
            prompt, classification=sensitivity, request_id=request_id,
            request_origin=request_origin,
        )
        answer = gen_meta.get("answer")
        if gen_meta.get("state") in {"COMPLETED", "REFUSED"}:
            served_by = "szl-router:" + gen_meta["receipt"]["provider_id"]
    elif decision == "allow":
        eng = _pick_engine(effort)
        # Optional remote-provider fallback for a GLM/frontier turn: only when the
        # user explicitly requested frontier effort, the GLM engine is NOT live
        # on-metal, AND the provider is opt-in+keyed. Sovereign on-metal always wins.
        want_frontier = bool(effort) and _EFFORT_TO_TIER.get(str(effort).strip().lower()) == "T2"
        glm = _glm_engine()
        prov = _provider_config() if (want_frontier and (glm is None or not _engine_live(glm))) else None
        if prov is not None:
            try:
                answer, gen_meta = _provider_generate(prompt, prov)
                served_by = f"GLM remote provider — {prov['label']} (REMOTE; NOT sovereign, NOT on-metal)"
            except Exception:
                prov = None  # provider failed → fall through to sovereign mesh
        if prov is None:
            if eng is None:
                return {"decision": decision, "answer": None,
                        "governance": _pub_gov(g, cb), "receipt": g.get("receipt"), "dsse": g.get("dsse"),
                        "energy": _with_pb_reference({"joules": None, "label": "UNAVAILABLE", "evidence": {"mesh": "no live engine"}}),
                        "honesty": "governance allowed the turn but NO mesh engine was reachable; "
                                   "no answer and no joules fabricated."}
            served_by = eng.get("name")
            _inflight_inc(eng["name"])
            try:
                answer, gen_meta = _ollama_generate(prompt, eng)
            except Exception:
                # failover: try any OTHER live engine once
                alt = next((e for e in MESH if e is not eng and _engine_live(e)), None)
                if alt is None:
                    _inflight_dec(eng["name"])
                    return {"decision": decision, "answer": None,
                            "governance": _pub_gov(g, cb), "receipt": g.get("receipt"), "dsse": g.get("dsse"),
                            "energy": _with_pb_reference({"joules": None, "label": "UNAVAILABLE", "evidence": {"mesh": "engine failed, no failover"}}),
                            "honesty": "governance allowed the turn but the chosen engine failed and no "
                                       "failover engine was live; no answer and no joules fabricated."}
                served_by = alt.get("name") + " (failover)"
                _inflight_inc(alt["name"])
                try:
                    answer, gen_meta = _ollama_generate(prompt, alt)
                finally:
                    _inflight_dec(alt["name"])
            finally:
                _inflight_dec(eng["name"])

    call_end_ts = time.time()
    _, ev_after = (None, {}) if gateway_requested else _meter_snapshot()

    # 3) A source-bound delta measures the GPU device window. It can include
    # concurrent work and cannot be billed or claimed as this turn's energy.
    delta, why = _served_meter_delta(
        served_by, ev_before, ev_after,
        call_start_ts=call_start_ts, call_end_ts=call_end_ts)
    if delta is not None:
        energy = {"joules": None, "label": "UNAVAILABLE",
                  "evidence": {"served_by": served_by,
                               "reason": "exclusive per-inference attribution unavailable",
                               "device_window": {"joules": delta, "label": "MEASURED",
                                                 "method": "NVML_COUNTER_DELTA",
                                                 "scope": "SHARED_GPU_DEVICE_WINDOW",
                                                 "billable": False},
                               "before": ev_before, "after": ev_after}}
    else:
        energy = {"joules": None, "label": "UNAVAILABLE",
                  "evidence": {"served_by": served_by, "reason": why,
                               "before": ev_before, "after": ev_after,
                               "note": "joule NOT fabricated; no source-bound device window"}}

    # Cite the founder-captured MEASURED physical-bounds reference (honest label;
    # NOT this request's live joules). Absent when the cert is unreadable — never
    # a fabricated MEASURED. See _with_pb_reference.
    energy = _with_pb_reference(energy)

    honesty = {
        "allow":  "Governance allowed the turn; answer returned with a signed receipt. "
                  "Λ is Conjecture 1 (advisory), not a theorem. "
                  "Joules UNAVAILABLE for this turn; any measured GPU device "
                  "window is shared and nonbillable.",
        "review": "Λ below advisory floor — flagged for HUMAN REVIEW. No answer returned. "
                  "Receipt records the verdict.",
        "deny":   "A deny-by-default safety gate fired. No answer returned. Receipt records the denial.",
    }.get(decision, "Unrecognized decision.")
    if gateway_requested and decision == "allow":
        honesty = (
            "Governance allowed this request. Gateway state: "
            + gen_meta.get("state", "UNAVAILABLE")
            + ". Gateway receipts provide unsigned SHA-256 integrity only; "
            "source reads bind the configured revision, not model weights or "
            "independently witnessed inference. Joules UNAVAILABLE."
        )

    # ── UNIFIED LEDGER WIRE-UP ──────────────────────────────────────────────
    # After the DSSE/Khipu receipt is built, record THIS governed turn into the
    # unified receipt ledger (organ="a11oy") via an in-process call. Non-blocking
    # (HFBucket mirror is debounced/background) and fully guarded — a ledger or
    # dataset hiccup must NEVER affect the governed turn's response.
    _receipt = g.get("receipt")
    if isinstance(_receipt, dict):
        try:
            import szl_lake_ingest as _lake
            _rec = dict(_receipt)
            # Carry the FULL governance proof into the ledger receipt (explicit
            # assignment — the raw Khipu receipt may already hold differently-shaped
            # keys; the half-state of a receipt that omits its own verdict/Λ/
            # signature is unacceptable). _pub_gov already labels Λ as Conjecture 1.
            _rec["decision"] = decision
            _rec["governance"] = _pub_gov(g, cb)
            _rec["dsse"] = g.get("dsse")
            _rec["energy"] = energy
            _lake.record_receipt(_rec, organ="a11oy")
        except Exception as _lake_e:  # pragma: no cover
            import sys as _lake_sys
            print(f"[a11oy] govern/infer ledger record skipped (non-fatal): {_lake_e!r}",
                  file=_lake_sys.stderr)

    # ── IN-TOTO STATEMENT V1 + TRANSPARENCY LOG ──────────────────────────────
    # Add in-toto Statement v1 serialization and per-receipt Merkle inclusion proof.
    # Fully guarded — ANY failure here is non-fatal and logs; the governed turn
    # response ALWAYS returns even if in-toto serialization is unavailable.
    # Pattern: in-toto Attestation Framework v1 (Apache-2.0) — reimplemented in
    # szl_intoto.py, NO library imported, NO AGPL dependency.
    _intoto_statement = None
    _intoto_transparency = None
    if isinstance(g.get("receipt"), dict):
        try:
            import szl_intoto as _intoto
            # Enrich the receipt with governance/answer/energy context before attesting
            _full_receipt = dict(g.get("receipt") or {})
            _full_receipt["decision"] = decision
            _full_receipt["answer"] = answer
            _full_receipt["energy"] = energy
            _full_receipt["governance"] = _pub_gov(g, cb)
            _attest = _intoto.attest_receipt(_full_receipt, try_rekor=False)
            _intoto_statement = _attest["intoto_statement"]
            _intoto_transparency = _attest["transparency"]
        except Exception as _it_e:
            import sys as _it_sys
            print(f"[a11oy] in-toto attestation skipped (non-fatal): {_it_e!r}",
                  file=_it_sys.stderr)


    # ── SCITT AGENT ACTION CAPSULE ───────────────────────────────────────────
    # Build a SCITT Agent Action Capsule per draft-mih-scitt-agent-action-capsule-01.
    # ADDITIVE: does NOT replace DSSE + in-toto formats. Appends scitt_capsule
    # alongside existing receipt formats.
    # CRITICAL DOCTRINE: BLOCK verdicts MUST produce a capsule (the whole point —
    # refusals are signed too). We do NOT gate capsule production on decision==allow.
    # Fully guarded — ANY failure is non-fatal; the governed turn always returns.
    _scitt_capsule = None
    try:
        import szl_scitt as _szl_scitt
        import hashlib as _sc_hashlib
        _prompt_hash = _sc_hashlib.sha3_256(
            (prompt or "").encode("utf-8")
        ).hexdigest()
        _output_hash = (
            _sc_hashlib.sha3_256(
                (answer or "").encode("utf-8")
            ).hexdigest()
            if answer else None
        )
        _gates_raw = (_pub_gov(g, cb) or {}).get("gates") if g else None
        if isinstance(_gates_raw, dict):
            _gates = list(_gates_raw.keys())
        elif isinstance(_gates_raw, (list, tuple, set)):
            _gates = list(_gates_raw)
        else:
            _gates = []
        _model_id = served_by or "unknown"
        _receipt_id = (g.get("receipt") or {}).get("receipt_id", "") if g else ""
        _scitt_capsule = _szl_scitt.build_and_store_capsule(
            prompt_hash=_prompt_hash,
            model_id=_model_id,
            verdict=decision,
            gates=_gates,
            output_hash=_output_hash,
            extra={"receipt_id": _receipt_id, "organ": "a11oy"},
        )
    except Exception as _sc_e:
        import sys as _sc_sys
        print(f"[a11oy] SCITT capsule skipped (non-fatal): {_sc_e!r}",
              file=_sc_sys.stderr)

    return {
        "decision": decision,
        "answer": answer,
        "served_by": served_by,
        "governance": _pub_gov(g, cb),
        "receipt": g.get("receipt"),
        "dsse": g.get("dsse"),
        "intoto_statement": _intoto_statement,
        "intoto_transparency": _intoto_transparency,
        "scitt_capsule": _scitt_capsule,
        "generation": gen_meta or None,
        "energy": energy,
        "honesty": honesty,
    }


def _conformal_blocks(g: dict, prompt: str) -> dict | None:
    """Compute the split-conformal interval + ECE calibration blocks for this turn's
    advisory Λ (GAP_ML.md GAP 1/2). FULLY GUARDED + ADDITIVE: any failure (numpy
    absent, cold-start buffer, import error) logs and returns None so the infer path
    falls back to the existing MODELED Λ behaviour. NEVER breaks the turn or startup.

    Honest labelling is enforced inside szl_conformal: MEASURED only on a real
    held-out split of n ≥ 500; SAMPLE for the seed bootstrap; UNAVAILABLE on cold
    start. Λ stays Conjecture 1 (advisory, ≤0.99) regardless of the conformal label."""
    lam = g.get("lambda")
    if not isinstance(lam, (int, float)):
        return None
    try:
        import szl_conformal as _cf
        return _cf.lambda_conformal_blocks(float(lam), prompt=prompt, alpha=0.10)
    except Exception as _cf_e:  # pragma: no cover
        import sys as _cf_sys
        print(f"[a11oy] conformal/ECE block skipped (non-fatal): {_cf_e!r}",
              file=_cf_sys.stderr)
        return None


def _pub_gov(g: dict, conformal_blocks: dict | None = None) -> dict:
    pub = {
        "lambda": g.get("lambda"),
        "lambda_floor": g.get("lambda_floor"),
        "lambda_pass": g.get("lambda_pass"),
        "lambda_kind": "Conjecture 1 (advisory; NOT a theorem)",
        "gates": g.get("gates"),
        "route": g.get("route"),
        "doctrine": g.get("doctrine"),
    }
    if isinstance(conformal_blocks, dict):
        # Additive, honestly-labelled. The conformal block upgrades Λ's trust label
        # to MEASURED only when its own label says so; otherwise Λ stays MODELED.
        pub["conformal"] = conformal_blocks.get("conformal")
        pub["calibration"] = conformal_blocks.get("calibration")
        pub["lambda_label"] = conformal_blocks.get("lambda_label")
    return pub


# --- register on the a11oy FastAPI app (repo convention) ----------------------
def register(app, ns: str = "a11oy", *, public_pem: str | None = None):  # pragma: no cover
    """Attach the buyer-facing governed-inference surface to the a11oy app.

    Routes (ADDITIVE — no overlap with existing /api/a11oy/* namespaces):
      POST /api/a11oy/v1/govern/infer   {prompt, vertical?, declared?, severity?}
      GET  /api/a11oy/v1/govern/health
      GET  /govern                      (also alias for buyer-facing short URL)
    Honest degrade: if FastAPI import or governance module is missing, returns
    the app unchanged (never raises into import). Follows the same register()
    contract as dev2/devA/devB packs.
    """
    # Use raw Starlette Route objects inserted at the HEAD of app.router.routes —
    # the PROVEN pattern in serve.py (compliance-crosswalk mesh). add_api_route +
    # reorder is fragile against the /api/a11oy/{path:path} Node proxy + SPA
    # catch-all; inserting Route(...) at index 0 deterministically wins.
    try:
        from starlette.routing import Route
        from starlette.responses import JSONResponse
    except Exception:
        return {"registered": [], "status": "starlette-absent"}

    async def _infer(request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        prompt = (body or {}).get("prompt", "")
        if not prompt:
            return JSONResponse({"error": "missing 'prompt'"}, status_code=400)
        kwargs = dict(
            vertical=body.get("vertical", "general"),
            declared=body.get("declared", "PUBLIC"),
            severity=float(body.get("severity", 0.0)),
            effort=body.get("effort"),
            request_id=request.headers.get("X-Request-ID"),
            request_origin=str(request.base_url),
        )
        if body.get("effort") == "szl-router":
            # Gateway HTTP is synchronous; keep the serving event loop available.
            from starlette.concurrency import run_in_threadpool
            result = await run_in_threadpool(govern_infer, prompt, **kwargs)
        else:
            result = govern_infer(prompt, **kwargs)
        status = 200
        if body.get("effort") == "szl-router" and result.get("decision") == "allow":
            status = (result.get("generation") or {}).get("http_status", 503)
        return JSONResponse(result, status_code=status)

    async def _health(request=None):
        import szl_router_client
        jb, ev = _meter_snapshot()
        engines = []
        for e in MESH:
            engines.append({"name": e.get("name"), "model": e.get("model"),
                            "ollama": e.get("ollama"), "tier": e.get("tier"),
                            "effort": e.get("effort"), "is_glm": bool(e.get("is_glm")),
                            "live": _engine_live(e)})
        glm = _glm_engine()
        prov = _provider_config()
        return JSONResponse({
            "product": "a11oy Governed Agent Change Management",
            "governance": _avf is not None and hasattr(_avf, "governed_turn"),
            "router_gateway": szl_router_client.configuration_status(),
            "mesh": engines,
            "engines_live": sum(1 for e in engines if e["live"]),
            "engines_total": len(engines),
            "glm": {
                "model_tag": SZL_GLM_MODEL,
                "on_metal_live": bool(glm is not None and _engine_live(glm)),
                "note": ("GLM engine present but model not pulled on-metal yet — honestly DOWN until "
                         "`ollama pull`/`create` of the GLM tag" if (glm is not None and not _engine_live(glm))
                         else "GLM live on-metal" if glm is not None else "GLM engine not in mesh"),
                "remote_provider_enabled": prov is not None,
                "remote_provider": (prov["label"] if prov is not None else None),
            },
            "meter_fresh_live": jb is not None, "meter_evidence": ev,
            "honesty": "Λ is Conjecture 1 (advisory). Answer returned only on decision==allow. "
                       "Energy aggregated across all live mesh meters; never fabricated. "
                       "GLM is just another governed engine; remote provider (if enabled) is "
                       "labeled REMOTE/not-sovereign and yields UNAVAILABLE energy.",
        })

    # Front door ("/"): serve the INVESTOR landing (a11oy_landing.html) — the
    # collapsed flagship story (signs-its-work / refuses / formally-backed cards,
    # killinchu vertical, Conjecture 1 advisory). The holographic govern showcase
    # remains available at /govern + /govern/. Previously "/" served
    # govern_showcase.html, which front-insert-shadowed serve.py's spa_root and
    # pinned the old 941KB showcase as the front door — root cause of the stale
    # landing. Doctrine v11 LOCKED, Lambda Conjecture 1 (advisory, never theorem).
    try:
        from starlette.responses import FileResponse, HTMLResponse
        import os as _os
        _DIR = _os.path.dirname(_os.path.abspath(__file__))
        _PAGE = _os.path.join(_DIR, "govern_showcase.html")          # /govern showcase
        _FRONT = _os.path.join(_DIR, "a11oy_landing.html")            # "/" investor front door
        async def _landing(request=None):
            if _os.path.exists(_PAGE):
                return FileResponse(_PAGE, media_type="text/html")
            return HTMLResponse("<h1>a11oy Governed Agent Change Management</h1><p>showcase asset missing</p>")
        async def _front_door(request=None):
            # Investor front door first; fall back to the govern showcase, then a stub.
            if _os.path.exists(_FRONT):
                return FileResponse(_FRONT, media_type="text/html")
            if _os.path.exists(_PAGE):
                return FileResponse(_PAGE, media_type="text/html")
            return HTMLResponse("<h1>a11oy Governed Agent Change Management</h1><p>front-door asset missing</p>")
    except Exception:
        _landing = None

    # Serve the shared runtime key at /cosign.pub + /.well-known/cosign.pub.
    # serve.py injects the same PEM exposed by /api/a11oy/cosign.pub and
    # Series-A; standalone callers use szl_dsse's active signer key. The routes
    # are front-inserted so they win over the SPA catch-all.
    try:
        from starlette.responses import PlainTextResponse
        import szl_dsse as _dsse
        _selected_public_pem = (
            public_pem if public_pem is not None
            else _dsse.active_public_key_pem()
        )
        _PUBPEM = (_selected_public_pem or "").strip()
        _PUB_SHA256 = (
            hashlib.sha256(_PUBPEM.encode("ascii")).hexdigest()
            if _PUBPEM else ""
        )
        async def _pubkey(request=None):
            if not _PUBPEM:
                return PlainTextResponse(
                    "# shared signing key unavailable\n",
                    status_code=503,
                    headers={"cache-control": "no-store"},
                )
            return PlainTextResponse(
                _PUBPEM + "\n",
                media_type="application/x-pem-file",
                headers={
                    "cache-control": "no-store",
                    "x-pub-sha256": _PUB_SHA256,
                },
            )
    except Exception:
        _pubkey = None

    # Register at the FULL /api/a11oy/v1/govern/* path (proven to resolve locally,
    # like /api/a11oy/v1/reason) AND the post-strip /v1/govern/* + short /govern/*
    # forms, so it wins regardless of how the front-door forwards.
    paths = [
        ("/",             (_front_door if '_front_door' in dir() else _landing) or _health, ["GET"]),  # front door: investor landing
        ("/govern",       _landing or _health, ["GET"]),
        ("/govern/",      _landing or _health, ["GET"]),
        ("/api/a11oy/v1/govern/infer",  _infer,  ["POST"]),
        ("/api/a11oy/v1/govern/health", _health, ["GET"]),
        ("/v1/govern/infer",  _infer,  ["POST"]),
        ("/v1/govern/health", _health, ["GET"]),
        ("/govern/infer",  _infer,  ["POST"]),
        ("/govern/health", _health, ["GET"]),
    ]
    if _pubkey is not None:
        paths += [("/cosign.pub", _pubkey, ["GET"]),
                  ("/.well-known/cosign.pub", _pubkey, ["GET"])]
    registered = []
    for path, fn, methods in paths:
        app.router.routes.insert(0, Route(path, fn, methods=methods))
        registered.append(path)

    # ── SCITT TRANSPARENCY ENDPOINTS ────────────────────────────────────────
    # Register GET /api/a11oy/v1/scitt/capsule/<id> and
    #         GET /api/a11oy/v1/scitt/transparency
    # Fully guarded — absent szl_scitt is non-fatal.
    try:
        import szl_scitt as _szl_scitt_reg
        _scitt_reg = _szl_scitt_reg.register(app, ns=ns)
        registered.extend(_scitt_reg.get("registered", []))
    except Exception as _scitt_reg_e:
        import sys as _scitt_sys
        print(f"[a11oy] SCITT route registration skipped (non-fatal): {_scitt_reg_e!r}",
              file=_scitt_sys.stderr)

    return {"registered": registered, "status": "ok"}


# Backward-compat alias
def mount(app):  # pragma: no cover
    register(app)
    return app


if __name__ == "__main__":
    import sys
    p = " ".join(sys.argv[1:]) or "Summarize the doctrine of governed agent change management in two sentences."
    print(json.dumps(govern_infer(p), indent=2, default=str))
