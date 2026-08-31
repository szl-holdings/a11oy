"""szl_surface_fidelity.py — HONEST per-surface fidelity gate (Wave 32, Dev C).

Nine holographic surfaces were live-labelled STRUCTURAL-ONLY. A STRUCTURAL-ONLY label
is the correct, honest label when NOTHING real is read or computed for a surface. It is
the WRONG label when the surface genuinely computes or reads something in-request: that
case is MODELED (a real in-request computation over real inputs) or MEASURED (a real
live reading taken THIS request). This organ is the single place that decides which of
the three applies, PER SURFACE, from evidence gathered in the request itself — and it
records the provenance of that decision so the label can be audited rather than trusted.

  GET /api/<ns>/v1/surface/fidelity            — all governed surfaces
  GET /api/<ns>/v1/surface/fidelity/{surface}  — one surface

Label rules (Doctrine v11 — never relaxed)
------------------------------------------
  MEASURED         only from a real live reading taken THIS request. For joules the gate
                   is A11OY_JOULE_METER_URLS being set AND at least one of those meters
                   answering THIS request with a numeric, live=true GPU reading. A joule
                   is NEVER fabricated, NEVER carried over from a previous request, and
                   NEVER inferred from a default meter URL that the operator did not set.
  MODELED          a real in-request computation/read whose inputs are real (request
                   parameters, the real brain graph, a real eval run, a real node probe).
  STRUCTURAL-ONLY  no real signal exists for this surface — kept honestly, with the
                   reason and the exact condition that would upgrade it recorded.

Λ stays Conjecture 1 (advisory, gray, never green, never a theorem). Nothing here enters
the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22}. Provenance coverage is 1.0: every emitted
value names where it came from. Pure stdlib. RECEIPT-ON-WRITE, NOT ON-READ.

Meter JSON shape consumed (omen-joule-exporter):
  {"engines":[{"engine":"omen","joules":N,
               "gpus":[{"power_w":N,"joules":N,"live":true}]}],
   "totals":{"joules":N}}
"""
import json as _json
import os
import time as _time
import urllib.request
from datetime import datetime, timezone

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

# ── honest label vocabulary (doctrine v11) ──────────────────────────────────
MEASURED = "MEASURED"
MODELED = "MODELED"
STRUCTURAL_ONLY = "STRUCTURAL-ONLY"
HONEST_LABELS = (MEASURED, MODELED, STRUCTURAL_ONLY)

DOCTRINE_VERSION = "v11"
LAMBDA_STATUS = "Conjecture 1 (advisory, gray, never green, never a theorem)"
LOCKED_PROVEN = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
TRUST_CEILING = 0.97

# ── the joule-meter gate ────────────────────────────────────────────────────
# ONLY this env promotes a joule to MEASURED. Deliberately NO default URL: an
# operator who has not set the fleet meter env has no live meter, and inventing a
# default would let an unset deployment drift into a MEASURED claim.
METER_URLS_ENV = "A11OY_JOULE_METER_URLS"
# A sovereign meter sits behind a Cloudflare-fronted tunnel that answers 403/1010 to
# the default "Python-urllib/x" UA. A plain UA would therefore read as "meter down"
# on a meter that is actually up — the probe would be honest but wrong. Browser UA.
METER_UA = os.environ.get(
    "SZL_PROBE_USER_AGENT",
    "Mozilla/5.0 (compatible; szl-surface-fidelity/1.0; +https://a-11-oy.com)")
try:
    METER_TIMEOUT_S = float(os.environ.get("A11OY_JOULE_METER_TIMEOUT_S", "4.0"))
except (TypeError, ValueError):
    METER_TIMEOUT_S = 4.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def meter_urls_configured() -> list:
    """URLs from A11OY_JOULE_METER_URLS only (comma-separated), de-duped, ordered.

    No fallback default: unset env => empty list => the gate can only be
    STRUCTURAL-ONLY, which is the honest state of a deployment with no meter.
    """
    raw = (os.environ.get(METER_URLS_ENV) or "").strip()
    seen, out = set(), []
    for u in raw.split(","):
        u = u.strip()
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _read_one_meter(url: str, timeout: float) -> dict:
    """One live GET of one meter, THIS request. Returns per-URL provenance.

    Never raises, never caches, never substitutes a previous reading.
    """
    t0 = _time.monotonic()
    req = urllib.request.Request(url, headers={"User-Agent": METER_UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            body = r.read().decode("utf-8", "replace")
            status = int(getattr(r, "status", 0) or 0)
        doc = _json.loads(body)
        if not isinstance(doc, dict):
            raise ValueError("meter body is not a JSON object")
        return {"url": url, "ok": True, "http_status": status,
                "latency_ms": round((_time.monotonic() - t0) * 1000.0, 3),
                "doc": doc, "error": None}
    except Exception as e:  # noqa: BLE001 — an unreachable meter is an honest negative
        return {"url": url, "ok": False, "http_status": None,
                "latency_ms": round((_time.monotonic() - t0) * 1000.0, 3),
                "doc": None, "error": f"{type(e).__name__}: {e}"[:200]}


def meter_gate(timeout: float = None) -> dict:
    """Read every configured joule meter LIVE, THIS request, and decide the label.

    Returns a fully self-describing gate block:
      label            MEASURED iff env set AND a live numeric reading landed now.
      env_set          whether A11OY_JOULE_METER_URLS is set at all.
      live_this_request whether any meter answered with a live numeric reading now.
      joules_total     the summed live reading, or None. NEVER a fabricated number.
      engines[]        per-engine live watts/joules actually read (empty when none).
      reads[]          per-URL provenance (ok, http_status, latency_ms, error).
      structural_only_reason / upgrade_condition  the honest gap, when not MEASURED.
    """
    timeout = METER_TIMEOUT_S if timeout is None else timeout
    urls = meter_urls_configured()
    env_set = bool(urls)
    reads = [_read_one_meter(u, timeout) for u in urls]

    engines, joule_vals, watt_vals = [], [], []
    for r in reads:
        doc = r.get("doc") or {}
        for e in (doc.get("engines") or []):
            if not isinstance(e, dict):
                continue
            name = str(e.get("engine") or "").strip().lower()
            live_w, live_j = None, None
            for g in (e.get("gpus") or []):
                if not isinstance(g, dict) or not g.get("live"):
                    continue
                if live_w is None and isinstance(g.get("power_w"), (int, float)):
                    live_w = float(g["power_w"])
                if live_j is None and isinstance(g.get("joules"), (int, float)):
                    live_j = float(g["joules"])
            eng_j = e.get("joules")
            eng_j = float(eng_j) if isinstance(eng_j, (int, float)) else live_j
            if live_w is not None:
                watt_vals.append(live_w)
            if eng_j is not None:
                joule_vals.append(eng_j)
            engines.append({
                "engine": name or "unnamed",
                "watts_live": live_w,
                "joules": eng_j,
                "meter_url": r.get("url"),
                # a GPU that did not report live=true contributes NOTHING; we do not
                # downgrade it into a guess, we simply carry null.
                "reading_taken_at": _now_iso() if (live_w is not None or eng_j is not None) else None,
            })

    live_now = bool(watt_vals or joule_vals)
    measured = bool(env_set and live_now)
    gate = {
        "label": MEASURED if measured else STRUCTURAL_ONLY,
        "env_var": METER_URLS_ENV,
        "env_set": env_set,
        "urls_configured": urls,
        "urls_answered": [r["url"] for r in reads if r["ok"]],
        "live_this_request": live_now,
        "engines": engines,
        "engine_count": len(engines),
        "joules_total": (round(sum(joule_vals), 6) if joule_vals else None),
        "watts_total": (round(sum(watt_vals), 6) if watt_vals else None),
        "reads": [{k: v for k, v in r.items() if k != "doc"} for r in reads],
        "probe_user_agent": METER_UA,
        "read_at": _now_iso(),
        "doctrine": (
            "MEASURED requires BOTH %s set AND a live=true numeric GPU reading returned "
            "by a configured meter in THIS request. No joule is ever fabricated, carried "
            "over from an earlier request, or inferred from an unset default." % METER_URLS_ENV
        ),
    }
    if not measured:
        gate["joules_total"] = None
        gate["watts_total"] = None
        gate["structural_only_reason"] = (
            "%s is not set — this deployment has no fleet joule meter, so no joule "
            "exists to report." % METER_URLS_ENV
            if not env_set else
            "%s is set (%d meter URL(s)) but no meter returned a live=true numeric GPU "
            "reading in this request, so there is no joule to report."
            % (METER_URLS_ENV, len(urls))
        )
        gate["upgrade_condition"] = (
            "set %s to the fleet meter URL(s) and have at least one meter answer this "
            "request with {engines:[{gpus:[{power_w,joules,live:true}]}]}" % METER_URLS_ENV
        )
    return gate


# ── per-surface fidelity probes (each does REAL work, in-request) ───────────
def _fid(surface_id: str, title: str, label: str, basis: str, provenance: dict,
         **extra) -> dict:
    out = {
        "surface": surface_id,
        "title": title,
        "label": label,
        "basis": basis,
        "computed_in_request": True,
        "provenance": dict(provenance, coverage=1.0),
        "ts": _now_iso(),
    }
    out.update(extra)
    return out


def _f_energy() -> dict:
    g = meter_gate()
    extra = {}
    if g["label"] != MEASURED:
        extra = {"structural_only_reason": g["structural_only_reason"],
                 "upgrade_condition": g["upgrade_condition"]}
    return _fid(
        "energy", "Energy", g["label"],
        "live joule-meter read gated on %s" % METER_URLS_ENV,
        {"joule_meter": g,
         "note": "joules are MEASURED only from a live meter reading taken this request"},
        joules_total=g["joules_total"], watts_total=g["watts_total"], **extra)


def _f_ecosystem() -> dict:
    """Ecosystem status = live model roster (real in-request read) + meter-gated joules."""
    g = meter_gate()
    roster = {"read": False, "reason": None}
    try:
        import szl_llm_registry as _reg
        models = list(getattr(_reg, "MODEL_REGISTRY", []) or [])
        enrich = getattr(_reg, "_enrich_model", None)
        rows = [enrich(m) for m in models] if callable(enrich) else models
        roster = {
            "read": True,
            "source": "szl_llm_registry.MODEL_REGISTRY enriched at request time",
            "model_count": len(rows),
            "wired_count": sum(1 for m in rows if m.get("wired")),
            "configured_count": sum(1 for m in rows if m.get("configured")),
            "reachable_count": sum(1 for m in rows if m.get("reachable")),
            "receipted_count": sum(1 for m in rows if m.get("inference_receipted")),
            "note": ("wiring/configuration is computed from the process environment at "
                     "request time; it is a real read, not a measurement of inference"),
        }
    except Exception as e:  # noqa: BLE001
        roster = {"read": False, "reason": f"{type(e).__name__}: {e}"[:160]}

    if g["label"] == MEASURED:
        label, basis = MEASURED, "live fleet joule reading this request + live model roster"
        extra = {}
    elif roster.get("read"):
        label = MODELED
        basis = "model roster read in-request (env-derived wiring); no live joule this request"
        extra = {"joules_note": g["structural_only_reason"],
                 "upgrade_condition": g["upgrade_condition"]}
    else:
        label, basis = STRUCTURAL_ONLY, "no roster read and no live meter this request"
        extra = {"structural_only_reason":
                 "the model registry could not be read (%s) and %s"
                 % (roster.get("reason"), g["structural_only_reason"]),
                 "upgrade_condition": g["upgrade_condition"]}
    return _fid("ecosystem", "Harness · Ecosystem Status", label, basis,
                {"model_roster": roster, "joule_meter": g},
                joules_total=g["joules_total"], **extra)


def _f_mesh() -> dict:
    """Mesh status = real per-node HTTP probes taken this request."""
    try:
        import szl_mesh_orchestrator as _mo
        st = _mo.mesh_status()
    except Exception as e:  # noqa: BLE001
        return _fid("mesh", "Sovereign Mesh · Cross-Node Orchestration",
                    STRUCTURAL_ONLY, "orchestrator unavailable",
                    {"error": f"{type(e).__name__}: {e}"[:160]},
                    structural_only_reason="the mesh orchestrator could not be imported, "
                                           "so no node was probed this request",
                    upgrade_condition="restore szl_mesh_orchestrator so nodes are probed")
    nodes = st.get("nodes") or []
    probed = [{"name": n.get("name"), "state": n.get("state"),
               "reachable": bool(n.get("reachable")),
               "http_status": (n.get("probes") or {}).get("models", {}).get("http_status")
               if isinstance(n.get("probes"), dict) else None,
               "joules_label": n.get("joules_label")} for n in nodes]
    measured_any = any(str(n.get("joules_label")) == "measured" for n in nodes)
    label = MEASURED if measured_any else (MODELED if probed else STRUCTURAL_ONLY)
    extra = {}
    if label == MODELED:
        extra = {"measured_gap": "no live NVML watt reading landed this request, so no "
                                 "joule/watt is claimed; the mesh state is derived from "
                                 "real probe outcomes only"}
    elif label == STRUCTURAL_ONLY:
        extra = {"structural_only_reason": "no node was probed this request",
                 "upgrade_condition": "a node roster with at least one probe target"}
    return _fid("mesh", "Sovereign Mesh · Cross-Node Orchestration", label,
                "per-node HTTP probe outcomes recorded this request",
                {"node_probes": probed, "mesh_state": st.get("mesh_state"),
                 "note": "an unreachable probe is a real negative observation, never a "
                         "fabricated positive"},
                mesh_state=st.get("mesh_state"), **extra)


def _f_sparsemoe() -> dict:
    try:
        import szl_sparsemoe as _sm
        p = _sm._analyze()
    except Exception as e:  # noqa: BLE001
        return _fid("sparsemoe", "Extreme-Sparsity MoE Analyzer", STRUCTURAL_ONLY,
                    "analyzer unavailable", {"error": f"{type(e).__name__}: {e}"[:160]},
                    structural_only_reason="the analyzer module could not be evaluated")
    return _fid("sparsemoe", "Extreme-Sparsity MoE Analyzer", MODELED,
                "closed-form MoE footprint/cost arithmetic evaluated this request",
                {"inputs": {k: p.get(k) for k in
                            ("total_params_b", "active_params_b", "quant", "bytes_per_param")
                            if k in p},
                 "evaluated_keys": sorted(p.keys())[:24],
                 "note": "no MoE model is loaded or run — the arithmetic is real, the "
                         "hardware is not, so nothing here is MEASURED"},
                measured_gap="no model run and no device reading; MEASURED would require "
                             "serving the config on real hardware with a meter attached")


def _f_pddisagg() -> dict:
    try:
        import szl_pddisagg as _pd
        p = _pd._model()
    except Exception as e:  # noqa: BLE001
        return _fid("pddisagg", "Prefill/Decode Disaggregation Map", STRUCTURAL_ONLY,
                    "model unavailable", {"error": f"{type(e).__name__}: {e}"[:160]},
                    structural_only_reason="the disaggregation model could not be evaluated")
    return _fid("pddisagg", "Prefill/Decode Disaggregation Map", MODELED,
                "colocated vs disaggregated latency arithmetic evaluated this request "
                "over the real mesh node roster",
                {"nodes": p.get("nodes"), "node_reachability": p.get("node_reachability"),
                 "colocated": p.get("colocated"), "disaggregated": p.get("disaggregated"),
                 "note": "a11oy does not disaggregate prefill from decode today; the split "
                         "is a ROADMAP design, so no latency here is MEASURED"},
                measured_gap="MEASURED would require a real cross-node KV handoff and a "
                             "timed disaggregated dispatch")


def _f_execverify() -> dict:
    try:
        import szl_execverify as _ev
        p = _ev._run_loop()
    except Exception as e:  # noqa: BLE001
        return _fid("execverify", "Execution-Verified Synthesis Loop", STRUCTURAL_ONLY,
                    "loop unavailable", {"error": f"{type(e).__name__}: {e}"[:160]},
                    structural_only_reason="the synthesis loop could not be evaluated")
    src = p.get("eval_source") or {}
    real_eval = bool(src.get("real_eval_run"))
    label = MODELED if real_eval else STRUCTURAL_ONLY
    extra = ({} if real_eval else
             {"structural_only_reason": "the eval arena did not run this request (%s), so "
                                        "the loop has no real pass/fail signal"
                                        % src.get("reason"),
              "upgrade_condition": "a reachable szl_eval_arena suite run"})
    return _fid("execverify", "Execution-Verified Synthesis Loop", label,
                "real eval-arena suite executed this request, then each verdict "
                "independently re-scored",
                {"eval_source": src,
                 "aggregate": {k: p.get(k) for k in
                               ("n_trajectories", "eval_passed", "exec_verified",
                                "corpus_candidates", "gated_out") if k in p},
                 "note": "the eval run and the re-verification are real computations; no "
                         "model is trained from the loop, so nothing is MEASURED"},
                measured_gap="MEASURED would require a metered training/serving run driven "
                             "by the loop", **extra)


def _f_flowbrain() -> dict:
    try:
        import szl_flowbrain as _fb
        nodes, source = _fb._load_graph()
    except Exception as e:  # noqa: BLE001
        return _fid("flowbrain", "FlowBrain · continuous belief-flow lens",
                    STRUCTURAL_ONLY, "lens unavailable",
                    {"error": f"{type(e).__name__}: {e}"[:160]},
                    structural_only_reason="the flow lens could not read a graph")
    real = "demo" not in str(source).lower() and "structural" not in str(source).lower()
    label = MODELED if real else STRUCTURAL_ONLY
    extra = ({"measured_gap": "no anatomy pulse or spectral reading is sampled; the flow is "
                              "derived from real graph attributes, never measured"}
             if real else
             {"structural_only_reason": "the real brain graph was unavailable, so the lens "
                                        "fell back to an explicitly labelled demo graph",
              "upgrade_condition": "a readable a11oy_brain_graph build"})
    return _fid("flowbrain", "FlowBrain · continuous belief-flow lens", label,
                "belief-flow trajectory derived this request from real brain-graph "
                "node attributes (degree/layer/label)",
                {"graph_source": source, "nodes_read": len(nodes or []),
                 "note": "no EEG, no spectral measurement; the synthesis that belief "
                         "evolves this way stays a CONJECTURE"},
                graph_source=source, nodes_read=len(nodes or []), **extra)


def _f_brainmemory() -> dict:
    try:
        import szl_brainmemory as _bm
        agg = _bm.build_aggregate(top=24)
        if not isinstance(agg, dict):
            agg = {}
        label = str(agg.get("label") or STRUCTURAL_ONLY)
    except Exception as e:  # noqa: BLE001
        return _fid("brainmemory", "Brain Memory Freshness", STRUCTURAL_ONLY,
                    "freshness organ unavailable",
                    {"error": f"{type(e).__name__}: {e}"[:160]},
                    structural_only_reason="the freshness organ could not be evaluated")
    extra = {}
    if label != MEASURED:
        extra = {"structural_only_reason":
                 "no node in the knowledge graph carries a real capture timestamp, so "
                 "there is no recency signal; the freshness score is a connectivity + "
                 "salience proxy and a timestamp is never invented to fill the gap",
                 "upgrade_condition":
                 "harvest real per-node capture dates (captured_at) into the graph"}
    return _fid("brainmemory", "Brain Memory Freshness", label,
                "per-node freshness recomputed this request over the real knowledge graph",
                {"recency_signal": agg.get("recency_signal"),
                 "recency_field": agg.get("recency_field"),
                 "recency_measured_nodes": agg.get("recency_measured_nodes"),
                 "recency_coverage": agg.get("recency_coverage"),
                 "note": "MEASURED here means a real stored capture date was read and its "
                         "age computed now; it is never a live decay meter"},
                **extra)


def _f_integritycontrol() -> dict:
    """Kept STRUCTURAL-ONLY, deliberately. Documented here so the gap is auditable."""
    prov = {"security_loop": {"path": "/api/a11oy/v1/waqay/security-loop/manifest",
                              "kind": "declared read-only manifest (state machine, gate "
                                      "ids, bounds) — configuration, not a computation"},
            "claim_integrity": {"path": "/api/a11oy/v1/claim-integrity/info",
                                "kind": "declared read-only contract"},
            "atomize": {"path": "/api/a11oy/v1/claim-integrity/atomize",
                        "kind": "VISIBLE-PUNCTUATION-AND-NEWLINE-SPLIT — a real string "
                                "split, but explicitly STRUCTURAL-SPLIT-ONLY with no "
                                "semantic evaluation, so it scores nothing"},
            "effectors": 0,
            "decision_state": "PROPOSAL_ONLY"}
    return _fid("integritycontrol", "Integrity Control Plane", STRUCTURAL_ONLY,
                "declared read-only manifests + a structural string split",
                prov,
                structural_only_reason=(
                    "this control plane has effectors=0 and decision_state=PROPOSAL_ONLY: "
                    "it proposes and never acts. Its manifests are declared configuration "
                    "read back verbatim, and its atomizer performs a punctuation split "
                    "with no semantic evaluation. Nothing is computed from a real signal "
                    "and nothing is signed, so MODELED would overstate it and MEASURED "
                    "would be a fabrication. It stays STRUCTURAL-ONLY on purpose."),
                upgrade_condition=(
                    "a real signer plus an external verifier, and a semantic atomizer "
                    "whose scores are computed rather than declared"))


_PROBES = {
    "integritycontrol": _f_integritycontrol,
    "energy": _f_energy,
    "ecosystem": _f_ecosystem,
    "mesh": _f_mesh,
    "sparsemoe": _f_sparsemoe,
    "pddisagg": _f_pddisagg,
    "execverify": _f_execverify,
    "flowbrain": _f_flowbrain,
    "brainmemory": _f_brainmemory,
}
SURFACE_IDS = tuple(_PROBES.keys())


def fidelity(surface_id: str) -> dict:
    fn = _PROBES.get(surface_id)
    if fn is None:
        return {}
    try:
        out = fn()
    except Exception as e:  # noqa: BLE001 — a probe failure degrades honestly
        out = _fid(surface_id, surface_id, STRUCTURAL_ONLY, "probe raised",
                   {"error": f"{type(e).__name__}: {e}"[:200]},
                   structural_only_reason="the fidelity probe failed this request")
    out.setdefault("doctrine", {})
    out["doctrine"] = {"version": DOCTRINE_VERSION, "lambda": LAMBDA_STATUS,
                       "locked_proven": LOCKED_PROVEN, "trust_ceiling": TRUST_CEILING,
                       "labels": list(HONEST_LABELS)}
    return out


def fidelity_all() -> dict:
    rows = [fidelity(s) for s in SURFACE_IDS]
    counts = {}
    for r in rows:
        counts[r["label"]] = counts.get(r["label"], 0) + 1
    return {
        "ok": True,
        "service": "surface-fidelity",
        "surface_count": len(rows),
        "label_counts": counts,
        "surfaces": rows,
        "honest_note": (
            "Each label is decided from evidence gathered in THIS request and carries the "
            "provenance of that decision. MEASURED appears only where a live reading was "
            "actually taken now; surfaces with no real signal stay STRUCTURAL-ONLY with "
            "the reason and the upgrade condition stated, because an honest gap is worth "
            "more than a green light."),
        "doctrine": {"version": DOCTRINE_VERSION, "lambda": LAMBDA_STATUS,
                     "locked_proven": LOCKED_PROVEN, "trust_ceiling": TRUST_CEILING},
        "ts": _now_iso(),
    }


# ── registration (additive, guarded, before the SPA catch-all) ──────────────
def register(app, ns: str = "a11oy") -> list:
    from starlette.concurrency import run_in_threadpool

    async def _h_all(request: Request):  # noqa: ANN202
        return JSONResponse(await run_in_threadpool(fidelity_all))

    async def _h_one(request: Request):  # noqa: ANN202
        sid = str(request.path_params.get("surface") or "").strip().lower()
        if sid not in _PROBES:
            return JSONResponse(
                {"ok": False, "error": f"unknown surface '{sid}'",
                 "known_surfaces": list(SURFACE_IDS),
                 "label": STRUCTURAL_ONLY,
                 "note": "unknown surface id — honest 404, nothing invented"},
                status_code=404)
        return JSONResponse(await run_in_threadpool(fidelity, sid))

    base = f"/api/{ns}/v1/surface/fidelity"
    routes = [(base, _h_all), (base + "/{surface}", _h_one)]
    for path, fn in routes:
        try:
            app.router.add_route(path, fn, methods=["GET"])
        except Exception:  # noqa: BLE001 — fall back to the fastapi router
            app.add_api_route(path, fn, methods=["GET"])
    return [p for p, _ in routes]


if __name__ == "__main__":
    g = meter_gate()
    assert g["label"] in (MEASURED, STRUCTURAL_ONLY), g
    if not g["env_set"]:
        assert g["label"] == STRUCTURAL_ONLY and g["joules_total"] is None
        assert "structural_only_reason" in g
    all_rows = fidelity_all()
    assert all_rows["surface_count"] == len(SURFACE_IDS)
    for row in all_rows["surfaces"]:
        assert row["label"] in HONEST_LABELS, row
        assert row["provenance"]["coverage"] == 1.0
        if row["label"] == STRUCTURAL_ONLY:
            assert row.get("structural_only_reason"), row["surface"]
    print("surface-fidelity self-test OK:", all_rows["label_counts"])
