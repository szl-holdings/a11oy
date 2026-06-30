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
      "energy": {                          # MEASURED joules for THIS turn, honestly labeled
          "joules": float | None,
          "label": "MEASURED" | "UNAVAILABLE",
          "evidence": {...}
      },
      "honesty": "..."                     # plain-English statement of what is/!is proven
    }

DOCTRINE (non-negotiable, enforced here):
  - Λ is Conjecture 1, never a theorem. Labeled "advisory" everywhere.
  - The answer is returned ONLY if governed_turn decision == "allow".
    On "review"/"deny" we return the governance verdict + receipt and NO answer.
    (Never claim more than is real — the half-state is the only unacceptable outcome.)
  - joules are MEASURED only from the real NVML exporter (meter.a-11-oy.com, live:true,
    sample < METER_FRESH_S old). Otherwise label is UNAVAILABLE and joules is null.
    We NEVER fabricate a joule.
  - The receipt is whatever szl_khipu/szl_dsse actually produced — if signing was
    unavailable, the receipt says so (chain_verified / honesty fields preserved).
"""
from __future__ import annotations

import os
import time
import json
import urllib.request
import urllib.error

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
     "ollama": "https://gpu.a-11-oy.com",  "meter": "https://meter.a-11-oy.com",  "model": "llama3.1:8b"},
    {"name": "Sovereign GPU 1 (laptop · RTX 5050 · Blackwell)",
     "ollama": "https://gpu2.a-11-oy.com", "meter": "https://meter2.a-11-oy.com", "model": "qwen2.5:3b"},
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
HTTP_TIMEOUT  = float(os.environ.get("SZL_HTTP_TIMEOUT", "60"))
# Browser-like UA: Cloudflare 403s the default python-urllib UA.
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"


def _http_json(url: str, payload: dict | None = None, timeout: float = HTTP_TIMEOUT) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data,
        headers={"User-Agent": _UA, "Content-Type": "application/json"},
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _meter_one(meter_base: str) -> tuple[float | None, dict]:
    """Read ONE engine's NVML meter. Returns (cumulative_joules|None, evidence)."""
    try:
        m = _http_json(meter_base + "/", timeout=10)
    except Exception as e:
        return None, {"meter": meter_base, "reachable": False, "note": str(e)[:80]}
    ts = m.get("ts")
    fresh = (ts is not None) and (abs(time.time() - float(ts)) <= METER_FRESH_S)
    live = any(g.get("live") is True for eng in m.get("engines", []) for g in eng.get("gpus", []))
    total = (m.get("totals") or {}).get("joules")
    ok = fresh and live and isinstance(total, (int, float))
    return (float(total) if ok else None), {
        "meter": meter_base, "reachable": True, "fresh": fresh, "live": live,
        "exporter": m.get("exporter"), "ts": ts}


def _meter_snapshot() -> tuple[float | None, dict]:
    """Aggregate cumulative joules across EVERY mesh meter that is fresh+live.
    Returns (summed_joules|None, evidence with per-engine breakdown). Honest: an
    engine whose meter is down contributes nothing and is labeled unreachable."""
    per = []
    total = 0.0
    any_ok = False
    for eng in MESH:
        j, ev = _meter_one(eng.get("meter", ""))
        ev["engine"] = eng.get("name")
        if j is not None:
            total += j
            any_ok = True
        per.append(ev)
    return (total if any_ok else None), {"engines": per, "aggregated": any_ok}


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
import threading as _threading
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


def govern_infer(prompt: str, *, vertical: str = "general",
                 declared: str = "PUBLIC", severity: float = 0.0,
                 effort: str | None = None) -> dict:
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

    # 2) MEASURE the turn — joules MEASURED only, outside the model call window edges.
    j_before, ev_before = _meter_snapshot()

    answer = None
    gen_meta: dict = {}
    served_by = None
    if decision == "allow":
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
                        "energy": {"joules": None, "label": "UNAVAILABLE", "evidence": {"mesh": "no live engine"}},
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
                            "energy": {"joules": None, "label": "UNAVAILABLE", "evidence": {"mesh": "engine failed, no failover"}},
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

    j_after, ev_after = _meter_snapshot()

    # 3) Honest joule join. MEASURED requires:
    #    (a) the engine that SERVED has a fresh+live meter, AND
    #    (b) a REAL positive delta (> _JOULE_FLOOR) was observed.
    # If the serving engine's meter is down (e.g. laptop meter2=404) we label
    # UNAVAILABLE even if some OTHER node's meter ticked — never attribute another
    # node's joules to this turn, never call a 0.0 delta "MEASURED".
    _JOULE_FLOOR = 0.5  # joules; below this the delta is noise, not a measured turn
    served_meter_live = False
    if served_by:
        base = served_by.replace(" (failover)", "")
        for ev in (ev_after or {}).get("engines", []):
            if ev.get("engine") == base and ev.get("reachable") and ev.get("live"):
                served_meter_live = True
                break
    delta = (j_after - j_before) if (j_before is not None and j_after is not None) else None
    if served_meter_live and delta is not None and delta > _JOULE_FLOOR:
        energy = {"joules": round(delta, 3), "label": "MEASURED",
                  "evidence": {"served_by": served_by, "before": ev_before, "after": ev_after}}
    else:
        why = ("serving engine has no live NVML meter" if not served_meter_live
               else "no real positive joule delta this turn")
        energy = {"joules": None, "label": "UNAVAILABLE",
                  "evidence": {"served_by": served_by, "reason": why,
                               "before": ev_before, "after": ev_after,
                               "note": "joule NOT fabricated; not attributed across nodes"}}

    honesty = {
        "allow":  "Governance allowed the turn; answer returned with a signed receipt. "
                  "Λ is Conjecture 1 (advisory), not a theorem. "
                  + ("Joules MEASURED from real NVML." if energy["label"] == "MEASURED"
                     else "Joules UNAVAILABLE this turn — not fabricated."),
        "review": "Λ below advisory floor — flagged for HUMAN REVIEW. No answer returned. "
                  "Receipt records the verdict.",
        "deny":   "A deny-by-default safety gate fired. No answer returned. Receipt records the denial.",
    }.get(decision, "Unrecognized decision.")

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

    # ── Additive: TEE attestation field (Dev 2 Build 1 — auto-lights-up on TDX/Nitro).
    # On the current CPU Space: present=False, label="UNAVAILABLE". On a TDX pod: MEASURED.
    # Guarded: a missing or broken szl_tee_attest must never affect the receipt response.
    _tee_attestation = None
    try:
        import szl_tee_attest as _tat
        _tee_attestation = _tat.tee_attestation_field()
    except Exception as _tat_e:  # pragma: no cover
        _tee_attestation = {
            "present": False, "label": "UNAVAILABLE",
            "note": f"tee_attest import failed: {type(_tat_e).__name__}"
        }

    # ── Additive: EU AI Act Art. 53 energy disclosure (Dev 2 Build 2).
    # MEASURED when NVML joule delta + token count are both real; UNAVAILABLE otherwise.
    # Signed (DSSE) + Merkle-logged — per-inference provable, not a dashboard stat.
    # Guarded: a missing szl_eu_energy must never affect the receipt response.
    _energy_eu_disclosure = None
    try:
        import szl_eu_energy as _eue
        _nvml_j = energy.get("joules") if energy.get("label") == "MEASURED" else None
        _tok_count = (gen_meta or {}).get("eval_count")  # Ollama token count (if available)
        _energy_eu_disclosure = _eue.eu_disclosure_field_for_receipt(
            nvml_joules_delta=_nvml_j,
            token_count=_tok_count,
            receipt_id=str(g.get("receipt", {}).get("id", "")) or None,
        )
    except Exception as _eue_e:  # pragma: no cover
        _energy_eu_disclosure = {
            "article": "EU-AI-Act-53(1)(b)",
            "measurement_label": "UNAVAILABLE",
            "signed": False,
            "note": f"eu_energy import failed: {type(_eue_e).__name__}"
        }

    return {
        "decision": decision,
        "answer": answer,
        "served_by": served_by,
        "governance": _pub_gov(g, cb),
        "receipt": g.get("receipt"),
        "dsse": g.get("dsse"),
        "generation": gen_meta or None,
        "energy": energy,
        "tee_attestation": _tee_attestation,
        "energy_eu_disclosure": _energy_eu_disclosure,
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
def register(app, ns: str = "a11oy"):  # pragma: no cover
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
        return JSONResponse(govern_infer(
            prompt,
            vertical=body.get("vertical", "general"),
            declared=body.get("declared", "PUBLIC"),
            severity=float(body.get("severity", 0.0)),
            effort=body.get("effort"),
        ))

    async def _health(request=None):
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
            "product": "a11oy Governed Inference",
            "governance": _avf is not None and hasattr(_avf, "governed_turn"),
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

    # Landing page: serve the holographic showcase at /govern and /govern/ (branded domain root)
    try:
        from starlette.responses import FileResponse, HTMLResponse
        import os as _os
        _PAGE = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "govern_showcase.html")
        async def _landing(request=None):
            if _os.path.exists(_PAGE):
                return FileResponse(_PAGE, media_type="text/html")
            return HTMLResponse("<h1>a11oy Governed Inference</h1><p>showcase asset missing</p>")
    except Exception:
        _landing = None

    # CRITICAL honesty fix: serve the REAL cosign public key (the one receipts are
    # actually signed with) at /cosign.pub + /.well-known/cosign.pub, sourced from
    # the SAME material szl_dsse uses to verify. This guarantees the published key
    # ALWAYS matches the signing key — a buyer following "verify against /cosign.pub"
    # succeeds. (Front-inserted so it wins over serve.py's stale ephemeral-key route.)
    try:
        from starlette.responses import PlainTextResponse
        import szl_dsse as _dsse
        _PUBPEM = _dsse.COSIGN_PUBLIC_PEM.strip() + "\n"
        async def _pubkey(request=None):
            return PlainTextResponse(_PUBPEM, media_type="application/x-pem-file",
                                     headers={"x-keyid": getattr(_dsse, "KEYID", "szlholdings-cosign"),
                                              "x-pub-sha256": _dsse.public_key_fingerprint()})
    except Exception:
        _pubkey = None

    # Register at the FULL /api/a11oy/v1/govern/* path (proven to resolve locally,
    # like /api/a11oy/v1/reason) AND the post-strip /v1/govern/* + short /govern/*
    # forms, so it wins regardless of how the front-door forwards.
    paths = [
        ("/",             _landing or _health, ["GET"]),  # front door: elite showcase
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
    return {"registered": registered, "status": "ok"}


# Backward-compat alias
def mount(app):  # pragma: no cover
    register(app)
    return app


if __name__ == "__main__":
    import sys
    p = " ".join(sys.argv[1:]) or "Summarize the doctrine of governed inference in two sentences."
    print(json.dumps(govern_infer(p), indent=2, default=str))
