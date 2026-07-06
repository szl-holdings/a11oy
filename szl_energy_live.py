"""szl_energy_live.py — LIVE energy feed binding the dashboards to real hardware.

Three additive read endpoints under /api/<ns>/v1/energy that turn the Proven Energy
Engine from EMPTY/SAMPLE surfaces into a real-time feed wired to (a) the on-box NVML
power-meter exporter and (b) the in-process sovereign-mesh governance posture.

  GET /api/<ns>/v1/energy/live     real-time power+energy snapshot (NVML + mesh posture)
  GET /api/<ns>/v1/energy/mesh     per-node energy + governance posture for the 3D view
  GET /api/<ns>/v1/energy/harvest  Bekenstein budget series + a heuristic tariff window

DOCTRINE (v11 — NEVER violate):
  - HONEST LABELS. joules read MEASURED only from a REAL, reachable NVML exporter;
    when the meter is unreachable the label is UNAVAILABLE and joules is null with a
    note that joules were NOT fabricated. We NEVER invent a number.
  - The exporter is the SZL_GLM_METER NVML exporter (default https://meter2.a-11-oy.com),
    scraped at GET /metrics in Prometheus exposition format (szl_gpu_power_watts{...},
    szl_gpu_energy_joules{...}).
  - The sovereign-mesh posture (which nodes are live/down) is read from the SAME mesh the
    in-process govern/health surface uses (szl_governed_api.MESH + _engine_live), so /live
    and /mesh never diverge from /api/<ns>/v1/govern/health.
  - The tariff window in /harvest is a CLIENT-SIDE HEURISTIC from the server clock — it is
    explicitly NOT a live tariff feed. NO free-energy / perpetual-motion claims anywhere.
  - FAST + NEVER HANGS: the meter is fetched with httpx on a SHORT (2s) timeout and the last
    good sample is cached ~5s; mesh liveness probes are bounded by a deadline. A slow or down
    backend degrades to an honest UNAVAILABLE/empty state, never a hang and never a fake.

Pure stdlib + httpx (already a repo dep) + Starlette. No key, no Node, no CDN.
"""
import json as _json
import os
import re
import threading
import time
import concurrent.futures
from datetime import datetime, timezone

from starlette.requests import Request
from starlette.routing import Route
from starlette.responses import JSONResponse

# Honest labels (mirror szl_governed_api / szl_joules_truth vocabulary).
LABEL_MEASURED = "MEASURED"
LABEL_UNAVAILABLE = "UNAVAILABLE"

# The NVML exporter URL — SAME env the governed-inference GLM engine meters off.
METER_URL = os.environ.get("SZL_GLM_METER", "https://meter2.a-11-oy.com").rstrip("/")
# Short timeout so a down/slow meter can never hang the endpoint.
METER_TIMEOUT_S = float(os.environ.get("SZL_ENERGY_LIVE_TIMEOUT_S", "2.0"))
# Cache the last good meter sample this long (fire-and-forget freshness window).
SNAPSHOT_TTL_S = float(os.environ.get("SZL_ENERGY_LIVE_TTL_S", "5.0"))
# Bounded deadline for the mesh-liveness probe so /live/mesh stay fast.
MESH_PROBE_DEADLINE_S = float(os.environ.get("SZL_ENERGY_LIVE_MESH_DEADLINE_S", "2.5"))

_UA = "Mozilla/5.0 (compatible; szl-energy-live/1.0; +https://a-11-oy.com)"

# Prometheus exposition line: metric{labels} value  (comments/# lines ignored).
_PROM_LINE = re.compile(
    r"^(?P<metric>szl_gpu_[a-zA-Z_]+)(?:\{(?P<labels>[^}]*)\})?\s+(?P<val>[-+0-9.eEnN]+)\s*$"
)
_PROM_LABEL = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)="((?:[^"\\]|\\.)*)"')


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Prometheus parsing — szl_gpu_power_watts{gpu,name}, szl_gpu_energy_joules{...}.
# ---------------------------------------------------------------------------
def _parse_labels(raw: str) -> dict:
    if not raw:
        return {}
    return {k: v for k, v in _PROM_LABEL.findall(raw)}


def _coerce_float(s: str):
    try:
        f = float(s)
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):  # NaN / inf are not readings
        return None
    return f


def parse_meter_metrics(text: str) -> dict:
    """Parse a meter response into per-GPU watts + cumulative joules.

    Accepts BOTH exporter formats (honest, never fabricated):
      (a) JSON (omen-joule-exporter): {engines:[{engine,gpus:[{index,name,power_w,joules,live}]}], totals:{joules}}
      (b) Prometheus exposition text (szl_gpu_power_watts{gpu,name}, szl_gpu_energy_joules{...}).
    Returns {gpus:[{gpu,name,watts,joules}], total_watts, total_joules}. Pure + deterministic."""
    # --- (a) JSON exporter (real NVML via nvidia-smi) ---
    stripped = text.lstrip()
    if stripped.startswith("{"):
        try:
            doc = _json.loads(stripped)
            rows = []
            for eng in doc.get("engines", []):
                ename = eng.get("engine", "")
                for g in eng.get("gpus", []):
                    rows.append({
                        "gpu": str(g.get("index", "")),
                        "name": g.get("name") or ename,
                        "watts": g.get("power_w"),
                        "joules": g.get("joules"),
                    })
            tw = sum(g["watts"] for g in rows if isinstance(g["watts"], (int, float)))
            jv = [g["joules"] for g in rows if isinstance(g["joules"], (int, float))]
            tj = doc.get("totals", {}).get("joules")
            if tj is None and jv:
                tj = sum(jv)
            return {
                "gpus": rows,
                "total_watts": round(tw, 6),
                "total_joules": (round(tj, 6) if isinstance(tj, (int, float)) else None),
            }
        except Exception:
            pass  # fall through to Prometheus parse; never fabricate
    # --- (b) Prometheus exposition text ---
    gpus: dict = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _PROM_LINE.match(line)
        if not m:
            continue
        metric = m.group("metric")
        if metric not in ("szl_gpu_power_watts", "szl_gpu_energy_joules"):
            continue
        val = _coerce_float(m.group("val"))
        if val is None:
            continue
        labels = _parse_labels(m.group("labels") or "")
        key = (labels.get("gpu", ""), labels.get("name", ""))
        slot = gpus.setdefault(key, {"gpu": labels.get("gpu"), "name": labels.get("name"),
                                     "watts": None, "joules": None})
        if metric == "szl_gpu_power_watts":
            slot["watts"] = val
        else:
            slot["joules"] = val
    rows = list(gpus.values())
    total_watts = sum(g["watts"] for g in rows if isinstance(g["watts"], (int, float)))
    j_vals = [g["joules"] for g in rows if isinstance(g["joules"], (int, float))]
    total_joules = sum(j_vals) if j_vals else None
    return {
        "gpus": rows,
        "total_watts": round(total_watts, 6),
        "total_joules": (round(total_joules, 6) if total_joules is not None else None),
    }


# ---------------------------------------------------------------------------
# Meter fetch + ~5s last-good cache (fire-and-forget; never hangs > timeout).
# ---------------------------------------------------------------------------
_snap_lock = threading.Lock()
_snap_cache: dict = {"ts": 0.0, "data": None}


def _fetch_meter() -> dict:
    """Fetch + parse {METER_URL}/metrics with a SHORT timeout. Honest result dict:
    on success {reachable:True, status:'ok', **parsed}; on failure {reachable:False,
    status:'offline:<reason>'|'http-<code>'} with no fabricated numbers."""
    url = f"{METER_URL}/metrics"
    try:
        import httpx
    except Exception as e:  # pragma: no cover — httpx is a repo dep
        return {"reachable": False, "status": f"offline:httpx-import:{type(e).__name__}"}
    try:
        with httpx.Client(timeout=METER_TIMEOUT_S, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": _UA})
        code = resp.status_code
        if code >= 400:
            return {"reachable": False, "status": f"http-{code}"}
        parsed = parse_meter_metrics(resp.text)
        parsed.update({"reachable": True, "status": "ok"})
        return parsed
    except Exception as e:  # noqa: BLE001 — unreachable/timeout meter => honest offline
        return {"reachable": False, "status": f"offline:{type(e).__name__}"}


def meter_snapshot(force: bool = False) -> dict:
    """Return the latest meter snapshot, served from the ~5s last-good cache when fresh.

    Caches only REACHABLE samples; when the meter is down we report the live offline
    status but keep the prior good sample available under 'stale' so callers can show a
    last-known reading WITHOUT relabeling it MEASURED (it carries a stale flag)."""
    now = time.time()
    with _snap_lock:
        cached = _snap_cache.get("data")
        age = now - _snap_cache.get("ts", 0.0)
        if not force and cached is not None and cached.get("reachable") and age <= SNAPSHOT_TTL_S:
            out = dict(cached)
            out["cache_age_s"] = round(age, 3)
            return out
    fresh = _fetch_meter()
    with _snap_lock:
        if fresh.get("reachable"):
            _snap_cache["data"] = fresh
            _snap_cache["ts"] = now
            out = dict(fresh)
            out["cache_age_s"] = 0.0
            return out
        # Meter down: surface the live offline status; attach last-good as stale (no relabel).
        prior = _snap_cache.get("data")
        out = dict(fresh)
        if prior is not None:
            out["stale"] = {**prior, "cache_age_s": round(now - _snap_cache.get("ts", 0.0), 3)}
        return out


# ---------------------------------------------------------------------------
# Sovereign-mesh posture — read the SAME mesh govern/health uses, liveness bounded.
# ---------------------------------------------------------------------------
def _role_for_engine(eng: dict, index: int) -> str:
    """Honest role label for the 3D view: glm | anchor | blackwell | engine-N."""
    if eng.get("is_glm"):
        return "glm"
    name = (eng.get("name") or "").lower()
    if "anchor" in name or "tower" in name:
        return "anchor"
    if "blackwell" in name or "laptop" in name:
        return "blackwell"
    return "anchor" if index == 0 else f"engine-{index}"


def _gpu_model_token(name: str):
    """Extract a GPU model token (e.g. 'RTX 4060 Ti', 'RTX 5050') from a mesh engine
    name so a meter GPU 'name' label can be honestly matched to a mesh node. None when
    no recognizable model is present (then per-node watts/joules stay UNAVAILABLE)."""
    if not name:
        return None
    m = re.search(r"RTX\s*\w+(?:\s+Ti)?", name, re.IGNORECASE)
    return m.group(0).strip() if m else None


def govern_posture(deadline_s: float = MESH_PROBE_DEADLINE_S) -> dict:
    """In-process sovereign-mesh posture (which nodes are live/down), bounded in time.

    Uses szl_governed_api.MESH + _engine_live — the EXACT mesh + liveness definition the
    /api/<ns>/v1/govern/health surface uses, so postures never diverge. Liveness probes
    run concurrently under a hard deadline; a probe that does not finish in time reports
    live=None (UNKNOWN — honestly not claimed up or down), never a fabricated state."""
    try:
        import szl_governed_api as G
    except Exception as e:  # noqa: BLE001 — governed surface optional; absence is honest
        return {"available": False, "nodes": [], "reason": f"govern surface unavailable: {type(e).__name__}"}
    mesh = list(getattr(G, "MESH", []) or [])
    engine_live = getattr(G, "_engine_live", None)
    nodes = []
    live_by_idx: dict = {}
    if callable(engine_live) and mesh:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(mesh)) as ex:
            futs = {ex.submit(_safe_engine_live, engine_live, e): i for i, e in enumerate(mesh)}
            deadline = time.time() + max(0.1, deadline_s)
            for fut, i in futs.items():
                remaining = deadline - time.time()
                try:
                    live_by_idx[i] = fut.result(timeout=max(0.0, remaining))
                except Exception:  # noqa: BLE001 — timeout/error => UNKNOWN, not a guess
                    live_by_idx[i] = None
    for i, eng in enumerate(mesh):
        nodes.append({
            "name": eng.get("name"),
            "role": _role_for_engine(eng, i),
            "model": eng.get("model"),
            "gpu_model": _gpu_model_token(eng.get("name") or ""),
            # The NVML joule-meter engine label this node reports (e.g. 'omen' for the
            # tower, 'betterwithage' for the laptop) — used to attribute live watts/joules
            # from the MERGED multi-meter scrape by engine name (see build_mesh).
            "exporter": eng.get("exporter"),
            "is_glm": bool(eng.get("is_glm")),
            "live": live_by_idx.get(i),
        })
    return {
        "available": True,
        "nodes": nodes,
        "live_count": sum(1 for n in nodes if n["live"] is True),
        "total": len(nodes),
    }


def _safe_engine_live(fn, eng) -> bool:
    try:
        return bool(fn(eng))
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# /energy/live — real-time power+energy snapshot (NVML + mesh posture).
# ---------------------------------------------------------------------------
def build_live() -> dict:
    snap = meter_snapshot()
    reachable = bool(snap.get("reachable"))
    posture = govern_posture()
    if reachable:
        label = LABEL_MEASURED
        joules_label = LABEL_MEASURED
        gpus = snap.get("gpus") or []
        nodes = [{
            "name": (g.get("name") or f"gpu{g.get('gpu')}"),
            "live": True,
            "watts": g.get("watts"),
            "joules": g.get("joules"),
            "source": "NVML",
        } for g in gpus]
        total_watts = snap.get("total_watts")
        total_joules = snap.get("total_joules")
        note = "joules MEASURED from the live NVML exporter (Prometheus /metrics)"
    else:
        label = LABEL_UNAVAILABLE
        joules_label = LABEL_UNAVAILABLE
        # Honest empty draw-list: surface the sovereign nodes that EXIST (mesh posture)
        # so the dashboard still shows the topology, but with null watts/joules — never faked.
        nodes = [{
            "name": n.get("name"),
            "live": n.get("live"),
            "watts": None,
            "joules": None,
            "source": "mesh-posture",
        } for n in (posture.get("nodes") or [])]
        total_watts = None
        total_joules = None
        note = "meter offline — joules NOT fabricated"
    return {
        "ts": _now_iso(),
        "label": label,
        "nodes": nodes,
        "total_watts": total_watts,
        "total_joules": total_joules,
        "joules_label": joules_label,
        "meter_url": METER_URL,
        "meter_status": snap.get("status"),
        "exporter": "NVML" if reachable else None,
        "mesh": posture,
        "note": note,
        "doctrine": "v11 — joules MEASURED only from a reachable NVML exporter; never fabricated.",
    }


# ---------------------------------------------------------------------------
# /energy/mesh — per-node energy + governance posture for the 3D view.
# ---------------------------------------------------------------------------
def _merged_engine_readings() -> dict:
    """Per-engine live watts + cumulative joules from the MERGED multi-meter scrape.

    Reuses szl_energy_operator._fetch_joule_meter(), which scrapes EVERY meter in
    A11OY_JOULE_METER_URLS (e.g. the tower's meter.a-11-oy.com AND the laptop's
    meter2.a-11-oy.com) and merges their engines[] into one dict. Returns a map keyed
    by lower-cased engine name ('omen', 'betterwithage') → {watts, joules}, so a mesh
    node can be attributed its OWN engine's live NVML numbers the same way the operator
    does (_exporter_sample_for_node). Honest (Doctrine v11): an unreachable meter simply
    contributes no engine, so that node stays null/UNAVAILABLE — never fabricated; watts
    are read only from a GPU flagged live, else None."""
    try:
        import szl_energy_operator as _op
        meter = _op._fetch_joule_meter()
    except Exception:  # noqa: BLE001 — operator/meter absent => empty map, honest fallback
        return {}
    out: dict = {}
    for e in (meter or {}).get("engines", []) or []:
        name = str(e.get("engine") or "").strip().lower()
        if not name:
            continue
        watts = None
        for g in (e.get("gpus") or []):
            if g.get("live") and isinstance(g.get("power_w"), (int, float)):
                watts = float(g["power_w"])
                break
        joules = e.get("joules")
        out[name] = {
            "watts": watts,
            "joules": float(joules) if isinstance(joules, (int, float)) else None,
        }
    return out


def build_mesh() -> dict:
    snap = meter_snapshot()
    reachable = bool(snap.get("reachable"))
    posture = govern_posture()
    gpus = snap.get("gpus") or [] if reachable else []
    # Live NVML per-engine readings from the MERGED multi-meter scrape (both the tower's
    # and the laptop's meters). This is what lets the laptop node pull its own engine's
    # watts/joules instead of showing null when its meter is a SEPARATE URL from METER_URL.
    engine_map = _merged_engine_readings()

    # Fallback attribution: match a meter GPU to a mesh node by GPU model token (e.g. the
    # node "…RTX 4060 Ti…" gets the meter GPU whose name label contains "RTX 4060 Ti").
    # Only used when the node has no engine reading. A node with neither keeps null
    # watts/joules (UNAVAILABLE), never a guess.
    def _match_gpu(gpu_model):
        if not gpu_model:
            return None
        gm = gpu_model.lower()
        for g in gpus:
            if gm in (g.get("name") or "").lower():
                return g
        return None

    nodes = []
    watt_vals = []
    for n in (posture.get("nodes") or []):
        # Primary: attribute by the node's own NVML engine name from the merged meters
        # ('omen' → tower, 'betterwithage' → laptop). Same mapping the operator uses.
        exporter = str(n.get("exporter") or "").strip().lower()
        reading = engine_map.get(exporter) if exporter else None
        if reading is not None:
            watts = reading.get("watts")
            joules = reading.get("joules")
            source = "NVML"
        else:
            g = _match_gpu(n.get("gpu_model"))
            watts = g.get("watts") if g else None
            joules = g.get("joules") if g else None
            source = "NVML" if g else "mesh-posture"
        if isinstance(watts, (int, float)):
            watt_vals.append(watts)
        nodes.append({
            "name": n.get("name"),
            "role": n.get("role"),
            "live": n.get("live"),
            "watts": watts,
            "joules": joules,
            "joules_label": LABEL_MEASURED if isinstance(joules, (int, float)) else LABEL_UNAVAILABLE,
            "source": source,
        })

    # Normalized 0..1 draw for visualization (relative to the busiest live node this tick).
    max_w = max(watt_vals) if watt_vals else 0.0
    for node in nodes:
        w = node["watts"]
        node["draw"] = (round(w / max_w, 6) if (isinstance(w, (int, float)) and max_w > 0) else None)

    # Totals from the per-node attributed readings (honest sum of what we actually
    # metered this tick); fall back to the single-meter snapshot when nothing attributed.
    node_watts = [nd["watts"] for nd in nodes if isinstance(nd["watts"], (int, float))]
    node_joules = [nd["joules"] for nd in nodes if isinstance(nd["joules"], (int, float))]
    any_reading = bool(node_watts) or bool(node_joules) or reachable
    total_watts = (round(sum(node_watts), 6) if node_watts
                   else (snap.get("total_watts") if reachable else None))
    total_joules = (round(sum(node_joules), 6) if node_joules
                    else (snap.get("total_joules") if reachable else None))
    label = LABEL_MEASURED if any_reading else LABEL_UNAVAILABLE
    return {
        "ts": _now_iso(),
        "label": label,
        "nodes": nodes,
        "node_count": len(nodes),
        "live_count": posture.get("live_count", 0),
        "total_watts": total_watts,
        "total_joules": total_joules,
        "joules_label": label,
        "meter_url": METER_URL,
        "meter_status": snap.get("status"),
        "draw_basis": "watts normalized 0..1 vs the busiest live node this tick (null when no live watts)",
        "note": ("per-node watts/joules attributed by NVML engine name from the MERGED "
                 "multi-meter scrape ('omen' → tower, 'betterwithage' → laptop), GPU-model "
                 "match as fallback; unmatched nodes are UNAVAILABLE, never fabricated"),
        "doctrine": "v11 — honest empty-states; joules MEASURED only with a real exporter reading.",
    }


# ---------------------------------------------------------------------------
# /energy/harvest — Bekenstein budget series + a heuristic tariff window.
# ---------------------------------------------------------------------------
_TARIFF_LABEL = ("client-side heuristic from the server clock, NOT a live tariff feed "
                 "(no real-time grid price wired)")


def _tariff_window(now=None) -> dict:
    """Off-peak / normal / peak window from the LOCAL server clock. Explicitly a
    heuristic — NOT a live tariff feed. Honest, mirrors the energy surface copy."""
    now = datetime.now() if now is None else now
    hour = now.hour
    if 0 <= hour < 7:
        window = "off-peak"
    elif 17 <= hour < 21:
        window = "peak"
    else:
        window = "normal"
    return {
        "window": window,
        "local_hour": hour,
        "label": _TARIFF_LABEL,
        "bands": {"off-peak": "00:00-07:00", "normal": "07:00-17:00 & 21:00-24:00", "peak": "17:00-21:00"},
    }


def _budget_series() -> dict:
    """Time-ordered Bekenstein budget series from the in-memory energy-budget ledger
    (szl_energy_budget): each task receipt's joules_est over time + cumulative, plus the
    F19/TH6 all_within_bound gate. Honest SAMPLE/ESTIMATE labels carried through."""
    try:
        import szl_energy_budget as B
    except Exception as e:  # noqa: BLE001
        return {"available": False, "series": [], "reason": f"budget unavailable: {type(e).__name__}"}
    receipts = list(getattr(B, "_LEDGER", []) or [])
    ordered = sorted(receipts, key=lambda r: r.get("ts") or "")
    series = []
    cum = 0.0
    for r in ordered:
        j = float(r.get("joules_est", 0.0) or 0.0)
        cum += j
        series.append({
            "ts": r.get("ts"),
            "joules_est": round(j, 6),
            "cumulative_joules_est": round(cum, 6),
            "within_bound": bool(r.get("within_bound")),
            "shannon_bits": r.get("shannon_bits"),
            "bekenstein_bound_bits": r.get("bekenstein_bound_bits"),
        })
    summary = {}
    try:
        summary = B.budget_summary()
    except Exception:  # noqa: BLE001
        summary = {}
    return {
        "available": True,
        "series": series,
        "task_count": len(series),
        "all_within_bound": summary.get("all_within_bound"),
        "gate": "F19/TH6 Bekenstein: Σ shannon_bits <= Σ output_bytes*8 (proven inequality, locked-8)",
        "total_joules_est": summary.get("total_joules_est"),
        "total_joules_est_label": summary.get("total_joules_est_label"),
        "joules_label": summary.get("joules_label", "sample"),
    }


def _ledger_totals() -> dict:
    """Signed-receipt-chain totals from szl_energy_ledger (MEASURED-billable joules are
    honest; SAMPLE/blocked entries contribute 0). Guarded — a missing ledger degrades
    to an honest unavailable block, never a fabricated total."""
    try:
        import szl_energy_ledger as L
        led = L.get_ledger()
        totals = led.totals()
        chain = led.verify()
        return {
            "available": True,
            "jobs": totals.get("jobs"),
            "joules_measured_billable": totals.get("joules_measured_billable"),
            "joules_measured_label": LABEL_MEASURED,
            "kwh_total": totals.get("kwh_total"),
            "chain_ok": chain.get("ok"),
            "chain_length": chain.get("length"),
        }
    except Exception as e:  # noqa: BLE001
        return {"available": False, "reason": f"ledger unavailable: {type(e).__name__}"}


def build_harvest() -> dict:
    budget = _budget_series()
    ledger = _ledger_totals()
    return {
        "ts": _now_iso(),
        "model": "Proven Energy Engine — harvest/grid view",
        "tariff_window": _tariff_window(),
        "budget": budget,
        "signed_ledger": ledger,
        "total_joules": budget.get("total_joules_est"),
        "total_joules_label": budget.get("total_joules_est_label"),
        "honesty": (
            "The joules_est series is SAMPLE/ESTIMATE (no on-box meter behind the budget "
            "layer); the signed_ledger joules_measured_billable is MEASURED (real NVML "
            "deltas only). The tariff window is a client-side heuristic, NOT a live feed. "
            "We harvest WASTED energy and PROVE bounded work — NO free-energy / "
            "perpetual-motion claims, EVER. Bekenstein gate F19/TH6 is a proven inequality."
        ),
        "doctrine": "v11 — honest labels; no fabricated joules; no free-energy claims.",
    }


# ---------------------------------------------------------------------------
# HTTP handlers + registration (matches szl_energy_budget: add_api_route, before SPA).
# ---------------------------------------------------------------------------
def _h_live(req: Request):
    return JSONResponse(build_live())


def _h_mesh(req: Request):
    return JSONResponse(build_mesh())


def _h_harvest(req: Request):
    return JSONResponse(build_harvest())


# ---------------------------------------------------------------------------
# GSF SCI (ISO 21031:2024) energy + carbon receipt field.
# SCI = (E × I + M) / R
#   E = energy kWh (measured or UNAVAILABLE)
#   I = grid carbon intensity gCO2eq/kWh (MEASURED from Electricity Maps if
#       ELECTRICITY_MAPS_API_KEY is set; else MODELED static default)
#   M = embodied carbon gCO2eq per call (MODELED fraction of hardware LCA)
#   R = functional unit = 1 inference call
#
# Formula source: Green Software Foundation SCI (MIT + CC-BY-4.0, ISO 21031:2024).
# Reimplemented in own code; no AGPL boavizta code imported.
# DOCTRINE (v11, HARD):
#   - When GPU / meter is OFF: energy_joules=null, label=UNAVAILABLE. NEVER fabricate.
#   - Grid intensity: MODELED (static US avg 436 gCO2eq/kWh) unless Electricity Maps
#     API key is set, in which case it is MEASURED from the free-tier API.
#   - carbon_gco2eq is null whenever energy_joules is null.
#   - sci_score_gco2_per_call is null whenever energy_joules is null.
# ---------------------------------------------------------------------------

# Static US-average grid intensity (EPA eGRID 2023, location-based, gCO2eq/kWh).
# Label: MODELED. Upgrade path: set ELECTRICITY_MAPS_API_KEY.
_SCI_DEFAULT_GRID_INTENSITY_GCO2_KWH = float(
    os.environ.get("SZL_SCI_DEFAULT_GRID_INTENSITY", "436.0")
)
# Zone for Electricity Maps free tier (override with SZL_ELEC_MAPS_ZONE).
_SCI_ELEC_MAPS_ZONE = os.environ.get("SZL_ELEC_MAPS_ZONE", "US")
# Modeled embodied carbon per inference call (gCO2eq).
# Based on GSF SCI M formula fragment: TE × (TiR/EL) × (RR/ToR) / daily_calls.
# Conservative estimate for a mid-range GPU (RTX 4060 Ti class).
# Label: MODELED. Never measured without real LCA data.
_SCI_EMBODIED_GCO2_PER_CALL = float(
    os.environ.get("SZL_SCI_EMBODIED_GCO2_PER_CALL", "0.0001")
)


def _fetch_grid_intensity() -> tuple[float, str, str]:
    """Return (intensity_gco2_per_kwh, label, source).

    If ELECTRICITY_MAPS_API_KEY is set and reachable, returns MEASURED from
    the Electricity Maps carbon intensity API (free tier, zone=US by default).
    Otherwise returns the static MODELED default.
    NEVER raises; failures degrade to the static default."""
    import urllib.request as _ur
    api_key = os.environ.get("ELECTRICITY_MAPS_API_KEY", "").strip()
    if not api_key:
        return (_SCI_DEFAULT_GRID_INTENSITY_GCO2_KWH, "MODELED",
                f"static default ({_SCI_DEFAULT_GRID_INTENSITY_GCO2_KWH} gCO2eq/kWh "
                "EPA eGRID 2023 US avg); set ELECTRICITY_MAPS_API_KEY for MEASURED")
    # Electricity Maps free-tier zone carbon intensity endpoint.
    url = f"https://api.electricitymap.org/v3/carbon-intensity/latest?zone={_SCI_ELEC_MAPS_ZONE}"
    try:
        req = _ur.Request(
            url,
            headers={"auth-token": api_key, "User-Agent": _UA},
        )
        with _ur.urlopen(req, timeout=4) as r:
            data = __import__("json").loads(r.read().decode())
        ci = data.get("carbonIntensity")
        if ci is not None:
            return (
                float(ci),
                "MEASURED",
                f"electricity_maps_v3 zone={_SCI_ELEC_MAPS_ZONE}",
            )
    except Exception:
        pass  # fall through to static default
    return (
        _SCI_DEFAULT_GRID_INTENSITY_GCO2_KWH,
        "MODELED",
        f"electricity_maps_unavailable; fallback static {_SCI_DEFAULT_GRID_INTENSITY_GCO2_KWH}",
    )


def build_sci() -> dict:
    """Build a GSF SCI (ISO 21031:2024) energy+carbon receipt payload.

    Called by /api/a11oy/v1/energy/sci.

    DOCTRINE (hard):
      - energy_joules is null and label UNAVAILABLE when meter is down.
      - carbon_gco2eq and sci_score_gco2_per_call are null when energy_joules is null.
      - grid_intensity is MODELED (static) or MEASURED (Electricity Maps) — never fabricated.
      - When everything is UNAVAILABLE, the payload is still returned so the caller
        can see what fields exist and why they’re null.
      - The Khipu receipt consumer MUST include these fields before DSSE signing.
    """
    snap = meter_snapshot()  # cached, short TTL
    energy_joules: float | None = snap.get("total_joules")  # None when meter is down
    meter_reachable: bool = bool(snap.get("reachable"))

    grid_intensity, grid_label, grid_source = _fetch_grid_intensity()

    if energy_joules is not None and energy_joules > 0 and meter_reachable:
        energy_kwh = energy_joules / 3_600_000.0
        operational_gco2 = energy_kwh * grid_intensity      # E × I
        embodied_gco2 = _SCI_EMBODIED_GCO2_PER_CALL          # M (MODELED share)
        sci_score = operational_gco2 + embodied_gco2          # (O + M) / R, R=1
        carbon_gco2 = round(operational_gco2, 8)
        sci_rounded = round(sci_score, 8)
        energy_label = LABEL_MEASURED
        overall_label = LABEL_MEASURED if grid_label == "MEASURED" else "MODELED"
        note = "Energy MEASURED from live NVML meter; SCI computed per ISO 21031:2024."
    else:
        energy_kwh = None
        carbon_gco2 = None
        sci_rounded = None
        energy_label = LABEL_UNAVAILABLE
        overall_label = LABEL_UNAVAILABLE
        note = ("energy_joules UNAVAILABLE — sovereign GPU + meter are offline. "
                "Joules NOT fabricated. Turn on the sovereign GPU and start "
                "the cloudflared meter tunnel to get MEASURED SCI scores.")

    return {
        "label": overall_label,
        "energy_joules": energy_joules,
        "energy_kwh": energy_kwh,
        "energy_label": energy_label,
        "carbon_gco2eq": carbon_gco2,
        "grid_intensity_gco2_per_kwh": grid_intensity,
        "grid_intensity_label": grid_label,
        "grid_source": grid_source,
        "embodied_gco2eq_per_call": _SCI_EMBODIED_GCO2_PER_CALL,
        "embodied_label": "MODELED",
        "sci_score_gco2_per_call": sci_rounded,
        "sci_functional_unit": "inference_call",
        "measurement_source": ("nvml/kepler" if meter_reachable and energy_joules is not None
                               else "none/meter_offline"),
        "methodology": "GSF_SCI_ISO_21031_2024",
        "note": note,
        "meter_reachable": meter_reachable,
        "timestamp_utc": _now_iso(),
    }


def build_sci_receipt_fields() -> dict:
    """Return ONLY the energy attestation fields to embed in a Khipu receipt
    payload BEFORE DSSE signing. All fields present; null when UNAVAILABLE.

    The receipt consumer (szl_governed_api, szl_energy_ledger) calls this
    and merges the result into the receipt body before signing.

    Schema follows DEV_CONSOLE_ENERGY.md §2.5 (the governal receipt pattern):
      energy_joules, carbon_gco2eq, grid_intensity_gco2_per_kwh,
      sci_score_gco2_per_call, measurement_source, methodology.
    """
    sci = build_sci()
    return {
        "energy_joules": sci["energy_joules"],
        "energy_kwh": sci["energy_kwh"],
        "carbon_gco2eq": sci["carbon_gco2eq"],
        "grid_intensity_gco2_per_kwh": sci["grid_intensity_gco2_per_kwh"],
        "sci_score_gco2_per_call": sci["sci_score_gco2_per_call"],
        "sci_functional_unit": "inference_call",
        "measurement_source": sci["measurement_source"],
        "grid_source": sci["grid_source"],
        "methodology": "GSF_SCI_ISO_21031_2024",
        "energy_label": sci["energy_label"],
        "grid_intensity_label": sci["grid_intensity_label"],
        "embodied_gco2eq_per_call": sci["embodied_gco2eq_per_call"],
        "embodied_label": "MODELED",
        "sci_label": sci["label"],
        "sci_note": sci["note"],
    }


def _h_sci(req: Request):
    return JSONResponse(build_sci())


def register(app, ns: str = "a11oy"):
    """Wire the live energy endpoints onto the app under /api/<ns>/v1/energy/*.

    Additive. Prefers FastAPI's add_api_route (so routes resolve BEFORE the SPA
    catch-all, matching the other szl_energy_* modules); falls back to a Starlette
    Route append for a bare Starlette app. Returns the list of mounted paths."""
    base = f"/api/{ns}/v1/energy"
    handlers = [
        (f"{base}/live", _h_live),
        (f"{base}/mesh", _h_mesh),
        (f"{base}/harvest", _h_harvest),
        (f"{base}/sci", _h_sci),   # GSF SCI ISO 21031:2024 endpoint
    ]
    add_api_route = getattr(app, "add_api_route", None)
    mounted = []
    for path, fn in handlers:
        try:
            if callable(add_api_route):
                app.add_api_route(path, fn, methods=["GET"])
            else:
                app.router.routes.append(Route(path, fn))
            mounted.append(path)
        except Exception:
            continue
    return mounted


# ---------------------------------------------------------------------------
# No-server self-test — proves parsing + honest labels, no live meter required.
# ---------------------------------------------------------------------------
def _selftest() -> dict:
    out: dict = {}

    # (a) Prometheus parse: per-GPU watts + cumulative joules; totals summed.
    sample = (
        "# HELP szl_gpu_power_watts GPU power draw.\n"
        "# TYPE szl_gpu_power_watts gauge\n"
        'szl_gpu_power_watts{gpu="0",name="RTX 4060 Ti"} 142.5\n'
        'szl_gpu_energy_joules{gpu="0",name="RTX 4060 Ti"} 78369.586\n'
        'szl_gpu_power_watts{gpu="1",name="RTX 5050"} 60.0\n'
        'szl_gpu_energy_joules{gpu="1",name="RTX 5050"} 1000.0\n'
        "szl_other_metric 5\n"
    )
    parsed = parse_meter_metrics(sample)
    assert len(parsed["gpus"]) == 2, parsed
    assert abs(parsed["total_watts"] - 202.5) < 1e-6, parsed
    assert abs(parsed["total_joules"] - 79369.586) < 1e-6, parsed
    out["prom_parse"] = True

    # (b) MEASURED live snapshot wiring (inject a reachable parsed snapshot).
    with _snap_lock:
        _snap_cache["data"] = {**parse_meter_metrics(sample), "reachable": True, "status": "ok"}
        _snap_cache["ts"] = time.time()
    live = build_live()
    assert live["label"] == LABEL_MEASURED and live["joules_label"] == LABEL_MEASURED, live
    assert live["total_watts"] == 202.5, live
    assert all(n["source"] == "NVML" and n["live"] is True for n in live["nodes"]), live
    out["live_measured"] = True

    # (c) UNAVAILABLE when the meter is offline — joules NOT fabricated.
    with _snap_lock:
        _snap_cache["data"] = None
        _snap_cache["ts"] = 0.0
    # Force a real fetch against an unroutable address so it fails fast/honestly.
    _prev = globals()["METER_URL"]
    try:
        globals()["METER_URL"] = "http://127.0.0.1:9"  # nothing listens here
        snap = meter_snapshot(force=True)
        assert snap["reachable"] is False, snap
        live2 = build_live()
        assert live2["label"] == LABEL_UNAVAILABLE and live2["total_joules"] is None, live2
        assert "NOT fabricated" in live2["note"], live2
    finally:
        globals()["METER_URL"] = _prev
    out["unavailable_honest"] = True

    # (d) Harvest: budget series + heuristic window labeled NOT a live feed; no free energy.
    harvest = build_harvest()
    assert "NOT a live tariff feed" in harvest["tariff_window"]["label"], harvest["tariff_window"]
    assert harvest["tariff_window"]["window"] in ("off-peak", "normal", "peak")
    assert "free-energy" in harvest["honesty"].lower() or "no free" in harvest["honesty"].lower()
    assert harvest["budget"]["available"] in (True, False)
    out["harvest_honest"] = True

    # (e) Mesh: honest empty-states; draw normalized or null, never fabricated.
    mesh = build_mesh()
    assert "nodes" in mesh and isinstance(mesh["nodes"], list)
    assert mesh["label"] in (LABEL_MEASURED, LABEL_UNAVAILABLE)
    out["mesh_shape"] = True

    # (f) Mesh per-node attribution by NVML engine name from the MERGED multi-meter map:
    # the laptop node ('betterwithage') pulls its OWN live watts/joules exactly like the
    # tower node ('omen'). When its engine is absent (meter2 down) it stays null —
    # UNAVAILABLE, never fabricated. This is the regression this fix guards.
    _lap = "Sovereign GPU 1 (laptop · RTX 5050 · Blackwell)"
    _tow = "Sovereign GPU 2 (tower · RTX 4060 Ti · anchor)"
    _prev_posture = globals()["govern_posture"]
    _prev_readings = globals()["_merged_engine_readings"]
    try:
        # Deterministic posture (no network) with both nodes' engine labels wired.
        globals()["govern_posture"] = lambda *a, **k: {
            "available": True, "live_count": 2, "nodes": [
                {"name": _tow, "role": "anchor", "gpu_model": "RTX 4060 Ti",
                 "exporter": "omen", "is_glm": False, "live": True},
                {"name": _lap, "role": "blackwell", "gpu_model": "RTX 5050",
                 "exporter": "betterwithage", "is_glm": False, "live": True},
            ]}
        # Reachable-but-empty single meter so the GPU-model fallback yields nothing
        # (proves attribution comes from the engine map, and null is honest when absent).
        with _snap_lock:
            _snap_cache["data"] = {"gpus": [], "total_watts": 0.0, "total_joules": None,
                                   "reachable": True, "status": "ok"}
            _snap_cache["ts"] = time.time()

        # Both engines present in the merged meters → both nodes MEASURED from their own engine.
        globals()["_merged_engine_readings"] = lambda: {
            "omen": {"watts": 13.53, "joules": 15896.0},
            "betterwithage": {"watts": 8.0, "joules": 37000.0},
        }
        m2 = build_mesh()
        by = {nd["name"]: nd for nd in m2["nodes"]}
        assert by[_lap]["watts"] == 8.0 and by[_lap]["joules"] == 37000.0, by[_lap]
        assert by[_lap]["joules_label"] == LABEL_MEASURED and by[_lap]["source"] == "NVML", by[_lap]
        assert by[_tow]["watts"] == 13.53 and by[_tow]["joules"] == 15896.0, by[_tow]

        # Laptop engine absent (meter2 unreachable) → null, NEVER fabricated; tower unaffected.
        globals()["_merged_engine_readings"] = lambda: {"omen": {"watts": 13.53, "joules": 15896.0}}
        m3 = build_mesh()
        by3 = {nd["name"]: nd for nd in m3["nodes"]}
        assert by3[_lap]["watts"] is None and by3[_lap]["joules"] is None, by3[_lap]
        assert by3[_lap]["joules_label"] == LABEL_UNAVAILABLE, by3[_lap]
        assert by3[_tow]["watts"] == 13.53, by3[_tow]
    finally:
        globals()["govern_posture"] = _prev_posture
        globals()["_merged_engine_readings"] = _prev_readings
        with _snap_lock:
            _snap_cache["data"] = None
            _snap_cache["ts"] = 0.0
    out["mesh_laptop_attribution"] = True

    out["ok"] = all(v is True for v in out.values())
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(_selftest(), indent=2))
