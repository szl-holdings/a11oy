# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""
szl_engine_status — the UNIFIED STATUS API for the agentic-GPU organism.

ONE read-only endpoint, GET /api/a11oy/v1/engine/status, aggregates the WHOLE
living body into a single honest JSON the 3D hologram (F1) and every dashboard
read from:

    {
      mind:    {sovereign, posture, inference, gpu, base_url}   # from /code/healthz
      organs:  {brain, heart, blood, immune, skeleton, nervous} # each {reachable, status}
      energy:  {window, source, joules{value,label}, within_bound}   # from the budget
      swarm:   {nodes, served_by}                               # if available
      doctrine:{lambda:"Conjecture 1", locked:8, half_state:"forbidden"}
    }

HONESTY (Doctrine v11), enforced by construction:
  - NEVER fabricate a status. Every sub-probe runs with a timeout and degrades to
    {"reachable": false, "status": "unreachable", "error": ...}. A missing organ
    is reported as down — never bluffed green.
  - sovereign:true ONLY when /code/healthz says so. If the MIND probe fails or is
    silent, sovereign is false. We never infer sovereignty from any other signal.
  - joules carry an explicit label: "measured" ONLY when the budget feed reports a
    real metered figure; otherwise "sample"/"estimate". No greenwashing.
  - Λ = Conjecture 1 is stated in the payload (the skeleton's killer formula is
    intentionally a conjecture — we say so); locked-8 untouched; half_state forbidden.
  - No key, open-weight, pure-stdlib aggregation. The probes are read-only GETs.

The endpoint is additive and try/except-guarded in serve.py, registered BEFORE the
SPA catch-all. If httpx/FastAPI are absent at import time the module still parses
and the self-test (which injects a fake fetcher) runs on pure stdlib.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

# Single source of truth for the joules honesty label. Wrapped so a missing/broken
# import can NEVER take down the status aggregator — we degrade to honest "sample".
try:
    from szl_joules_truth import (
        joules_label as _joules_truth_label,
        joules_evidence as _joules_truth_evidence,
    )
except Exception:  # pragma: no cover - defensive: doctrine default is always sample
    def _joules_truth_label(_exporter_sample, now=None):  # type: ignore
        return "sample"
    def _joules_truth_evidence(_exporter_sample, now=None):  # type: ignore
        return {}

# ---------------------------------------------------------------------------
# Doctrine block — constant, stamped on every response.
# ---------------------------------------------------------------------------
DOCTRINE: dict[str, Any] = {
    "lambda": "Conjecture 1",          # the Λ-uniqueness killer formula is a CONJECTURE, said plainly
    "locked": 8,                       # the locked-8 round9 organ formulas, untouched
    "half_state": "forbidden",         # claiming sovereign while a non-sovereign router served = forbidden
    "version": "v11",                  # doctrine LOCK version — matches DOCTRINE="v11" (szl_be_hardening) and /honest
}

# ---------------------------------------------------------------------------
# Organ map — each organ -> the live read-only endpoint that proves it.
# Paths are relative to the Space root; the in-process probe prepends the base.
# (BRAIN/SKELETON/NERVOUS live on amaru; HEART/BLOOD/IMMUNE on sentra; the a11oy
# Space proxies organ paths, so a single base reaches them honestly. A probe that
# 404s/refuses is reported reachable:false — never faked.)
# ---------------------------------------------------------------------------
# FIX 2: Remapped from retired amaru/sentra endpoints to a11oy-native LIVE
# equivalents (verified 2026-06-30: all 6 return HTTP 200 on the live Space).
# Old targets (/api/amaru/*, /api/sentra/*) are RETIRED and caused organs_healthy=0
# even when the system was healthy — the dashboard was showing a corpse.
ORGAN_ENDPOINTS: dict[str, str] = {
    "brain":    "/api/a11oy/v1/formulas",          # BrainBeliefUpdate — formula registry (was /api/amaru/v1/formulas)
    "heart":    "/api/lake/v1/health",             # HeartReceiptSigma — lake ledger health (was /api/amaru/receipts)
    "blood":    "/api/a11oy/v1/govern/health",     # BloodDSSEMerkle — DSSE governance health (was /api/sentra/khipu/ledger)
    "immune":   "/api/a11oy/v1/honest",            # ImmuneNeymanPearson — honesty/gate status (was /api/sentra/v1/gates)
    "skeleton": "/api/a11oy/v1/materials/health",  # SkeletonLambdaSpine — materials/Lean health (was /api/amaru/v1/math/lean/theorems)
    "nervous":  "/api/a11oy/v1/e8/verify",         # NervousShannonAlarm — E8 verification (was /api/amaru/overwatch/snapshot)
}

MIND_ENDPOINT = "/code/healthz"
ENERGY_ENDPOINT = "/api/a11oy/v1/energy/budget"
SWARM_ENDPOINT = "/api/a11oy/v1/swarm/status"

DEFAULT_TIMEOUT = 3.0

# Brief result cache: engine/status fans out concurrently with a per-probe timeout
# (good), but it RE-PROBED the whole organism on EVERY request — a slow organ taxed
# every caller (~2.3s observed). We cache the last REAL aggregate for STATUS_CACHE_TTL
# seconds so repeat requests are served instantly; the payload carries cached_at so
# the caller sees how fresh it is. HONEST: only ever caches a real aggregate output;
# reachability still reflects the most recent real probe sweep, never fabricated.
STATUS_CACHE_TTL = 20.0
# (value, stored_at_monotonic) — module-level, shared across requests.
_STATUS_CACHE: "dict[str, tuple[dict, float]]" = {}

# A Fetcher is an async callable (path, timeout) -> (status_code, parsed_json|None).
# The serve.py path wires the live httpx client; the self-test injects a fake one.
Fetcher = Callable[[str, float], Awaitable["tuple[int, Any]"]]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _probe(fetch: Fetcher, path: str, timeout: float) -> dict[str, Any]:
    """One honest probe. NEVER raises; NEVER fabricates a green status.

    Returns {reachable, status, ...}. reachable is True ONLY on a real 2xx with a
    body we could read. Any error/timeout/non-2xx -> reachable:false + the reason.
    """
    try:
        code, body = await fetch(path, timeout)
    except Exception as exc:  # timeout, connect-refused, anything — degrade honestly
        return {"reachable": False, "status": "unreachable", "error": repr(exc)[:200], "endpoint": path}
    if not (200 <= int(code) < 300):
        return {"reachable": False, "status": f"http_{code}", "endpoint": path}
    return {"reachable": True, "status": "ok", "http": int(code), "body": body, "endpoint": path}


def _mind_from_healthz(probe: dict[str, Any], base_url: str) -> dict[str, Any]:
    """Project /code/healthz into the MIND block. sovereign:true ONLY if healthz says so."""
    mind: dict[str, Any] = {
        "sovereign": False,          # default-false: never sovereign unless the MIND proves it
        "posture": "unknown",
        "inference": {"reachable": probe.get("reachable", False)},
        "gpu": None,
        "base_url": base_url,
        "reachable": probe.get("reachable", False),
    }
    if not probe.get("reachable"):
        mind["status"] = probe.get("status", "unreachable")
        return mind
    body = probe.get("body") or {}
    if isinstance(body, dict):
        # sovereign comes ONLY from the MIND's own report; coerce to a real bool.
        mind["sovereign"] = bool(body.get("sovereign", False))
        mind["posture"] = body.get("posture", body.get("status", "ok"))
        mind["gpu"] = body.get("gpu")
        infer = body.get("inference")
        if infer is not None:
            mind["inference"] = infer
        else:
            mind["inference"] = {"reachable": True}
    mind["status"] = "ok"
    return mind


def _energy_from_budget(probe: dict[str, Any]) -> dict[str, Any]:
    """Project the budget feed into the ENERGY block with an honest joules label."""
    energy: dict[str, Any] = {
        "reachable": probe.get("reachable", False),
        "window": None,
        "source": None,
        "joules": {"value": None, "label": "unknown"},
        "within_bound": None,
    }
    if not probe.get("reachable"):
        energy["status"] = probe.get("status", "unreachable")
        return energy
    body = probe.get("body") or {}
    if isinstance(body, dict):
        energy["window"] = body.get("window")
        energy["source"] = body.get("source")
        energy["within_bound"] = body.get("within_bound")
        # joules honesty: the label is decided by the SINGLE SOURCE OF TRUTH
        # (szl_joules_truth) — "measured" ONLY when the budget feed carries a REAL,
        # FRESH on-box NVML exporter sample. A forwarded label STRING is NO LONGER
        # trusted on its own (that was the honesty bug): a feed saying
        # joules_label="measured" with no real exporter reading now degrades to
        # "sample". The feed must supply an actual exporter_sample/joules_evidence.
        exporter_sample = body.get("exporter_sample") or body.get("joules_evidence")
        truth_label = _joules_truth_label(exporter_sample)
        if truth_label == "measured":
            label = "measured"
        else:
            # Preserve the honest finer-grained distinction between estimate/sample
            # for non-measured feeds, but NEVER upgrade to measured here.
            raw_label = str(body.get("joules_label", body.get("label", "sample"))).lower()
            label = "estimate" if raw_label in ("estimate", "est") else "sample"
        energy["joules"] = {
            "value": body.get("joules"),
            "label": label,
            # self-verifying: real exporter evidence iff measured, else empty.
            "evidence": _joules_truth_evidence(exporter_sample),
        }
    energy["status"] = "ok"
    return energy


def _swarm_from_probe(probe: dict[str, Any]) -> dict[str, Any]:
    """Project the swarm feed if available. Absent/unreachable -> reachable:false."""
    swarm: dict[str, Any] = {"reachable": probe.get("reachable", False), "nodes": None, "served_by": None}
    if not probe.get("reachable"):
        st = probe.get("status", "unavailable")
        # A 404 means no swarm mesh is *served* on this Space (single-node deploy).
        # That is an honest "standalone" state, not a fault — report it as such
        # (reachable stays False; nothing fabricated) so dashboards render a neutral
        # chip instead of a scary red http_404.
        if st == "http_404":
            swarm["status"] = "standalone"
            swarm["detail"] = "no swarm mesh on this Space (single-node)"
        else:
            swarm["status"] = st
        return swarm
    body = probe.get("body") or {}
    if isinstance(body, dict):
        swarm["nodes"] = body.get("nodes", body.get("registered"))
        swarm["served_by"] = body.get("served_by")
    swarm["status"] = "ok"
    return swarm


async def aggregate_status(fetch: Fetcher, base_url: str = "", timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Aggregate the WHOLE organism into one honest payload.

    Every sub-probe is independent and honest-degrading: one organ down does NOT
    take the aggregate down — it shows up as {reachable:false}. The MIND, energy,
    and swarm probes run concurrently with the 6 organ probes.
    """
    organ_names = list(ORGAN_ENDPOINTS)
    coros = (
        [_probe(fetch, MIND_ENDPOINT, timeout)]
        + [_probe(fetch, ORGAN_ENDPOINTS[name], timeout) for name in organ_names]
        + [_probe(fetch, ENERGY_ENDPOINT, timeout)]
        + [_probe(fetch, SWARM_ENDPOINT, timeout)]
    )
    results = await asyncio.gather(*coros)

    mind_probe = results[0]
    organ_probes = results[1:1 + len(organ_names)]
    energy_probe = results[1 + len(organ_names)]
    swarm_probe = results[2 + len(organ_names)]

    organs: dict[str, Any] = {}
    for name, pr in zip(organ_names, organ_probes):
        # Dashboards want {reachable, status}; keep the endpoint for debuggability,
        # drop the raw body to keep the aggregate lean and non-fabricating.
        organs[name] = {
            "reachable": pr.get("reachable", False),
            "status": pr.get("status", "unreachable"),
            "endpoint": pr.get("endpoint"),
        }

    mind = _mind_from_healthz(mind_probe, base_url)
    healthy = sum(1 for o in organs.values() if o["reachable"])

    return {
        "schema": "szl.engine_status/v1",
        "ts_utc": _now(),
        "mind": mind,
        "organs": organs,
        "organs_healthy": healthy,
        "organs_total": len(organs),
        "energy": _energy_from_budget(energy_probe),
        "swarm": _swarm_from_probe(swarm_probe),
        "doctrine": dict(DOCTRINE),
        "honesty": (
            "Every sub-status is a live read-only probe; unreachable organs report "
            "reachable:false (never bluffed green). sovereign:true ONLY from /code/healthz. "
            "joules.label is 'measured' only on a real metered figure, else sample/estimate. "
            "Λ=Conjecture 1; locked-8 untouched; half-state forbidden. No key; open-weight."
        ),
    }


# ---------------------------------------------------------------------------
# serve.py wiring — additive, try/except-guarded, BEFORE the SPA catch-all.
# ---------------------------------------------------------------------------
def _make_httpx_fetcher(http_client: Any, base_url: str) -> Fetcher:
    """Build a real fetcher over the app's shared httpx.AsyncClient."""
    async def _fetch(path: str, timeout: float) -> "tuple[int, Any]":
        resp = await http_client.get(f"{base_url}{path}", timeout=timeout)
        try:
            body: Any = resp.json()
        except Exception:
            body = None
        return resp.status_code, body
    return _fetch


def _make_asgi_fetcher(app: Any) -> "Fetcher | None":
    """Build an IN-PROCESS fetcher that calls the ASGI app directly (no network).

    Root cause of the chronic organs=0/6: the HF Space sandbox FIREWALLS outbound
    HTTP to both the public hostname AND the 127.0.0.1 loopback, so any self-HTTP
    probe fails even though every organ endpoint is healthy. Calling the ASGI app
    in-process via httpx.ASGITransport routes the probe through the same FastAPI
    app object with ZERO network — always reachable in-container. This is the
    reliable primary probe path; the loopback httpx client remains a fallback.
    """
    try:
        import httpx as _httpx  # local import keeps module import-safe
        transport = _httpx.ASGITransport(app=app)
    except Exception:
        return None

    async def _fetch(path: str, timeout: float) -> "tuple[int, Any]":
        async with _httpx.AsyncClient(
            transport=transport, base_url="http://asgi.local"
        ) as ac:
            resp = await ac.get(path, timeout=timeout)
        try:
            body: Any = resp.json()
        except Exception:
            body = None
        return resp.status_code, body
    return _fetch


def register(app, ns: str = "a11oy", http_client: Any = None, base_url: str = "") -> list[str]:
    """ADDITIVE: attach GET /api/{ns}/v1/engine/status. Never replaces a route.

    http_client — the app's shared httpx.AsyncClient (if None, resolved lazily from
                  serve.py's module global so registration order doesn't matter).
    base_url    — origin the organ paths are probed against; "" = same-origin loopback,
                  which is correct since the a11oy Space serves/proxies all organ paths.
    """
    from fastapi.responses import JSONResponse  # local import: keeps module import-safe

    paths: list[str] = []

    @app.get(f"/api/{ns}/v1/engine/status")
    async def _engine_status():  # noqa: ANN202
        import os as _os
        import time as _time
        # Fast path: a fresh cached aggregate -> serve WITHOUT re-probing the organism.
        ent = _STATUS_CACHE.get("_")
        if ent is not None and (_time.monotonic() - ent[1]) < STATUS_CACHE_TTL:
            return JSONResponse(ent[0])

        # Resolve effective base_url: an empty base_url means same-origin loopback.
        # Resolution priority: explicit override > local loopback. HF Space sandboxes FIREWALL outbound calls to their own
        # PUBLIC hostname (SPACE_HOST), so probing https://<space>.hf.space from
        # inside the container always times out -> organs read 0/6 even when healthy.
        # The reliable in-container path is the loopback 127.0.0.1:PORT, so prefer it.
        _eff_base = base_url
        if not _eff_base:
            _eff_base = _os.environ.get("SZL_ENGINE_STATUS_BASE", "")
        if not _eff_base:
            # Local loopback FIRST — works inside the HF sandbox.
            _eff_base = f"http://127.0.0.1:{_os.environ.get('PORT', '7860')}"
        # NOTE: SPACE_HOST (public hostname) is intentionally NOT used as a probe
        # target; outbound-to-self is blocked in the HF sandbox. Set
        # SZL_ENGINE_STATUS_BASE only if running behind a reachable reverse proxy.

        # PRIMARY: in-process ASGI probe (no network) — the only path that works
        # inside the HF sandbox, which firewalls BOTH public-host and loopback HTTP.
        fetcher = _make_asgi_fetcher(app)
        eff_base_for_probe = _eff_base
        if fetcher is not None:
            eff_base_for_probe = ""  # ASGI fetcher takes bare paths; no base needed.
        else:
            # FALLBACK: shared httpx client over loopback (works outside the sandbox).
            client = http_client
            if client is None:
                try:
                    import serve as _serve  # type: ignore
                    client = getattr(_serve, "_http_client", None)
                except Exception:
                    client = None
            if client is None:
                async def _dead(_p: str, _t: float):
                    raise RuntimeError("no transport available for in-process organ probes")
                fetcher = _dead
            else:
                fetcher = _make_httpx_fetcher(client, _eff_base)
        payload = await aggregate_status(fetcher, base_url=eff_base_for_probe)
        # Stamp freshness + store the REAL aggregate for the brief TTL window.
        if isinstance(payload, dict):
            payload = {**payload, "cached_at": _now(), "cache_ttl_s": STATUS_CACHE_TTL}
            _STATUS_CACHE["_"] = (payload, _time.monotonic())
        return JSONResponse(payload)

    paths.append(f"/api/{ns}/v1/engine/status")
    return paths


# ---------------------------------------------------------------------------
# Self-test — pure stdlib, no network, no FastAPI/httpx needed. Injects a fake
# fetcher. Verifies: full aggregate; one organ down -> honest reachable:false;
# sovereign ONLY when the mind says so; joules label honesty. Prints {ok:true}.
# ---------------------------------------------------------------------------
def _selftest() -> dict[str, Any]:
    checks: list[tuple[str, bool]] = []

    def chk(name: str, cond: bool) -> None:
        checks.append((name, bool(cond)))

    def run(coro):  # one fresh event loop per scenario; forward-compatible
        return asyncio.run(coro)

    # ---- Scenario A: everything healthy, MIND sovereign, joules MEASURED ----
    def make_fetch(table: dict[str, "tuple[int, Any]"], dead: set[str] | None = None) -> Fetcher:
        dead = dead or set()

        async def _fetch(path: str, timeout: float) -> "tuple[int, Any]":
            if path in dead:
                raise TimeoutError(f"simulated timeout probing {path}")
            if path not in table:
                return 404, None
            return table[path]
        return _fetch

    full_table: dict[str, "tuple[int, Any]"] = {
        MIND_ENDPOINT: (200, {"sovereign": True, "posture": "green",
                              "inference": {"reachable": True, "model": "qwen"},
                              "gpu": {"name": "RTX 5000", "util": 0.4}}),
        ENERGY_ENDPOINT: (200, {"window": "off-peak", "source": "nvml",
                                "joules": 1234.5, "joules_label": "measured", "within_bound": True,
                                # A REAL, FRESH on-box NVML exporter sample backs the
                                # "measured" claim — without this the label degrades to
                                # "sample" (the honesty fix). ts is now() => fresh.
                                "exporter_sample": {
                                    "joules_measured_total": 1234.5,
                                    "exporter_node": "rig-0",
                                    "exporter_last_seen_ts": __import__("time").time(),
                                    "power_w_sample": 210.0,
                                }}),
        SWARM_ENDPOINT: (200, {"nodes": 4, "served_by": "anchor"}),
    }
    for ep in ORGAN_ENDPOINTS.values():
        full_table[ep] = (200, {"ok": True})

    a = run(
        aggregate_status(make_fetch(full_table), base_url="http://127.0.0.1:7860")
    )
    chk("A_schema", a["schema"] == "szl.engine_status/v1")
    chk("A_mind_sovereign_true", a["mind"]["sovereign"] is True)
    chk("A_mind_posture_green", a["mind"]["posture"] == "green")
    chk("A_mind_base_url", a["mind"]["base_url"] == "http://127.0.0.1:7860")
    chk("A_all_6_organs_present", set(a["organs"]) == set(ORGAN_ENDPOINTS))
    chk("A_all_organs_reachable", all(o["reachable"] for o in a["organs"].values()))
    chk("A_organs_healthy_6", a["organs_healthy"] == 6 and a["organs_total"] == 6)
    chk("A_energy_measured", a["energy"]["joules"]["label"] == "measured")
    chk("A_energy_value", a["energy"]["joules"]["value"] == 1234.5)
    # self-verifying: a measured label MUST carry real exporter evidence.
    chk("A_energy_evidence_present", bool(a["energy"]["joules"].get("evidence")))
    chk("A_energy_evidence_node", a["energy"]["joules"]["evidence"].get("exporter_node") == "rig-0")
    chk("A_energy_within_bound", a["energy"]["within_bound"] is True)
    chk("A_swarm_served_by", a["swarm"]["served_by"] == "anchor" and a["swarm"]["nodes"] == 4)
    chk("A_doctrine_lambda", a["doctrine"]["lambda"] == "Conjecture 1")
    chk("A_doctrine_locked8", a["doctrine"]["locked"] == 8)
    chk("A_doctrine_halfstate", a["doctrine"]["half_state"] == "forbidden")

    # ---- Scenario B: ONE organ (immune) down -> honest reachable:false, rest fine ----
    b = run(
        aggregate_status(make_fetch(full_table, dead={ORGAN_ENDPOINTS["immune"]}))
    )
    chk("B_immune_unreachable", b["organs"]["immune"]["reachable"] is False)
    chk("B_immune_status_labeled", b["organs"]["immune"]["status"] == "unreachable")
    chk("B_others_still_reachable", b["organs"]["brain"]["reachable"] is True
        and b["organs"]["heart"]["reachable"] is True)
    chk("B_healthy_count_5", b["organs_healthy"] == 5)
    chk("B_aggregate_did_not_fail", b["schema"] == "szl.engine_status/v1")

    # ---- Scenario C: MIND down -> sovereign MUST be false (never fabricated) ----
    no_mind = dict(full_table)
    del no_mind[MIND_ENDPOINT]
    c = run(aggregate_status(make_fetch(no_mind)))
    chk("C_mind_unreachable", c["mind"]["reachable"] is False)
    chk("C_sovereign_false_when_mind_down", c["mind"]["sovereign"] is False)

    # ---- Scenario D: MIND reachable but reports sovereign:false -> stays false ----
    d_table = dict(full_table)
    d_table[MIND_ENDPOINT] = (200, {"sovereign": False, "posture": "degraded"})
    d = run(aggregate_status(make_fetch(d_table)))
    chk("D_sovereign_honest_false", d["mind"]["sovereign"] is False)
    chk("D_mind_reachable_true", d["mind"]["reachable"] is True)

    # ---- Scenario E: budget feed without a measured label -> joules labeled sample ----
    e_table = dict(full_table)
    e_table[ENERGY_ENDPOINT] = (200, {"window": "peak", "source": "off-peak-clock", "joules": 99.0})
    e = run(aggregate_status(make_fetch(e_table)))
    chk("E_joules_sample_default", e["energy"]["joules"]["label"] == "sample")

    # ---- Scenario H: feed CLAIMS "measured" but ships NO real exporter sample ----
    # This is the cross-module honesty bug: a bare label string must NOT be trusted.
    # The single source of truth degrades it to "sample" with empty evidence.
    h_table = dict(full_table)
    h_table[ENERGY_ENDPOINT] = (200, {"window": "off-peak", "source": "claims-nvml",
                                      "joules": 777.0, "joules_label": "measured"})
    h = run(aggregate_status(make_fetch(h_table)))
    chk("H_unbacked_measured_downgraded", h["energy"]["joules"]["label"] == "sample")
    chk("H_no_fabricated_evidence", h["energy"]["joules"].get("evidence") == {})

    # ---- Scenario I: feed ships a STALE exporter sample -> downgraded to sample ----
    i_table = dict(full_table)
    i_table[ENERGY_ENDPOINT] = (200, {"window": "off-peak", "source": "nvml", "joules": 555.0,
                                      "joules_label": "measured",
                                      "exporter_sample": {"joules_measured_total": 555.0,
                                                          "exporter_node": "rig-1",
                                                          "exporter_last_seen_ts": 1.0}})
    i = run(aggregate_status(make_fetch(i_table)))
    chk("I_stale_sample_downgraded", i["energy"]["joules"]["label"] == "sample")

    # ---- Scenario F: swarm absent -> reachable:false, never invented ----
    no_swarm = dict(full_table)
    del no_swarm[SWARM_ENDPOINT]
    f = run(aggregate_status(make_fetch(no_swarm)))
    chk("F_swarm_unreachable", f["swarm"]["reachable"] is False)
    chk("F_swarm_served_by_none", f["swarm"]["served_by"] is None)

    # ---- Scenario G: TOTAL outage (dead fetcher) -> nothing fabricated green ----
    async def _dead(_p: str, _t: float):
        raise ConnectionRefusedError("simulated full outage")
    g = run(aggregate_status(_dead))
    chk("G_mind_down", g["mind"]["reachable"] is False and g["mind"]["sovereign"] is False)
    chk("G_no_organ_reachable", g["organs_healthy"] == 0)
    chk("G_energy_down", g["energy"]["reachable"] is False)
    chk("G_doctrine_still_present", g["doctrine"]["lambda"] == "Conjecture 1")

    ok = all(passed for _, passed in checks)
    return {
        "ok": ok,
        "checks": len(checks),
        "failed": [name for name, passed in checks if not passed],
        "sample_full": {
            "mind_sovereign": a["mind"]["sovereign"],
            "organs_healthy": a["organs_healthy"],
            "energy_label": a["energy"]["joules"]["label"],
            "swarm_served_by": a["swarm"]["served_by"],
        },
        "doctrine": dict(DOCTRINE),
    }


if __name__ == "__main__":
    print(json.dumps(_selftest(), indent=2))
