# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 — Fabric / Tawantin / Auto-review honest SUMMARY surfaces.
"""
szl_fabric_surface.py — honest /status summaries for the Governed Distributed
Compute Fabric (user-visible names "Fabric" + "Tawantin") and the Governed
Auto-review autonomy layer.

WHY THIS MODULE EXISTS
----------------------
The /fabric and /tawantin PAGES are live (200) and the /autoreview page is live,
but a page-vs-api sweep found NO honest `/api/a11oy/v1/{tawantin,fabric}/status`
summary endpoint (404) and NO `/api/a11oy/v1/autoreview/status` (the autoreview
module registers classify/policy/metrics/dial/recent but not /status).

The REAL data already exists and is LIVE elsewhere — we do NOT duplicate it and
we NEVER fabricate node/joule data:
  * compute fabric nodes / reachability / sovereignty:
        GET /api/a11oy/v1/compute-pool-hardened   (szl_backend_hardening, LIVE)
  * MEASURED joules / node compute state:
        GET /api/a11oy/v1/energy/operator/status   (szl_energy_operator, LIVE)
  * signed energy-provenance chain head:
        GET /api/a11oy/v1/energy/provenance         (szl_energy_provenance, LIVE)
  * governed auto-review classifier + calibration + dial:
        GET /api/a11oy/v1/autoreview/{metrics,dial,policy}  (a11oy_autoreview, LIVE)

This module mounts honest SUMMARY endpoints that AGGREGATE those live sources
(short internal HTTP self-call against 127.0.0.1, cached/cheap) and report ONLY
what the sources truly say:
  GET /api/a11oy/v1/tawantin/status  — fabric summary (Quechua name "Tawantin").
  GET /api/a11oy/v1/fabric/status     — SAME honest summary (canonical "Fabric").
  GET /api/a11oy/v1/autoreview/status — honest summary over the real autoreview
                                        substance (calibration MEASURED, dial,
                                        block-rate ROADMAP until real runs land).

HONESTY (doctrine v11)
----------------------
  * Summaries reflect TRUE live state. If a source is unreachable this sweep, the
    summary says so (sources_reachable=false) and the affected fields read
    UNKNOWN — never a fabricated green.
  * nodes_reachable / sovereign_count / joules are PASSED THROUGH from the real
    sources, never re-probed, never invented here.
  * MEASURED joules only (the billable figure from the on-box NVML exporter);
    SAMPLE energy is reported separately and labelled, never billable.
  * Khipu receipt OPTIONAL — the underlying sources already sign (energy
    provenance chain + per-source receipts); this summary cites the signed
    provenance head rather than minting a duplicate node-data receipt.
  * locked = EXACTLY 8 {F1,F4,F7,F11,F12,F18,F19,F22} @ c7c0ba17 (add nothing);
    Λ = Conjecture 1; Khipu = Conjecture 2; trust never 100%; effectors
    SIMULATED; HORIZONTAL scale only (NEVER a fused-VRAM claim); orbital =
    ROADMAP; NO user-visible codenames; never commit a key.

Stdlib only (urllib for the internal self-call). Additive; try/except-guarded by
the caller; registered BEFORE the SPA catch-all. `from __future__ import
annotations` + module-level FastAPI imports so `request: Request` resolves.
"""
from __future__ import annotations

import datetime
import json
import os
import time
import urllib.request
from typing import Any, Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

# ---------------------------------------------------------------------------
# Identity + doctrine constants (honest, never a codename).
# ---------------------------------------------------------------------------
_FABRIC_NAME = "Fabric (Tawantin) — Governed Distributed Compute Fabric"
_AUTOREVIEW_NAME = "Governed Auto-review"
_LOCKED_PROVEN = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]  # EXACTLY 8
_KERNEL_COMMIT = "c7c0ba17"

# Internal self-base: the SAME process serves these sibling endpoints, so a short
# loopback call returns the already-cached live payloads cheaply. Env-overridable.
_SELF_PORT = os.environ.get("PORT", "7860")
_SELF_BASE = os.environ.get("SZL_SELF_BASE_URL", f"http://127.0.0.1:{_SELF_PORT}")
_SELF_TIMEOUT = float(os.environ.get("SZL_FABRIC_SELF_TIMEOUT", "6.0"))

_COMPUTE_POOL_PATH = "/api/a11oy/v1/compute-pool-hardened"
_ENERGY_OP_PATH = "/api/a11oy/v1/energy/operator/status"
_ENERGY_PROV_PATH = "/api/a11oy/v1/energy/provenance"
_AR_METRICS_PATH = "/api/a11oy/v1/autoreview/metrics"
_AR_DIAL_PATH = "/api/a11oy/v1/autoreview/dial"
_AR_POLICY_PATH = "/api/a11oy/v1/autoreview/policy"

_HONESTY = {
    "lambda": "Conjecture 1 (NOT a theorem)",
    "khipu": "Conjecture 2",
    "trust_ceiling": "never 100%",
    "effectors": "simulated",
    "scale_model": "HORIZONTAL only — independent nodes; NO fused/pooled VRAM is ever claimed",
    "orbital": "ROADMAP",
    "fabricated_data": False,
    "key_committed": False,
}


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _gov(payload: dict, status: str = "REAL", **extra) -> dict:
    """Governed envelope — byte-compatible with serve.py's gov_envelope contract
    ({status, citations, fetchedAt, doctrine}). Reproduced inline so this module
    never imports the heavy serve module at request time."""
    out = dict(payload)
    st = str(status or "REAL").upper()
    if st not in ("REAL", "DEMO", "DEGRADED"):
        st = "DEGRADED"
    out["status"] = st
    if out.get("citations") is None:
        out["citations"] = []
    out["fetchedAt"] = _now_iso()
    out.setdefault("doctrine", "v11")
    for k, v in extra.items():
        out[k] = v
    return out


def _self_get(path: str, timeout: Optional[float] = None) -> Optional[dict]:
    """Short loopback GET of a sibling live endpoint. Returns parsed JSON or None
    (None == source unreachable THIS sweep; the caller degrades honestly, never
    fabricates). Pure stdlib, no new dep."""
    url = _SELF_BASE + path
    try:
        req = urllib.request.Request(url, headers={"accept": "application/json",
                                                    "user-agent": "szl-fabric-summary/1"})
        with urllib.request.urlopen(req, timeout=timeout or _SELF_TIMEOUT) as resp:
            raw = resp.read()
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else {"_list": data}
    except Exception:  # noqa: BLE001 — any failure => honest "source unreachable"
        return None


# ---------------------------------------------------------------------------
# Fabric / Tawantin honest summary — aggregate the live sources, NEVER duplicate
# or fabricate node/joule data. nodes/sovereign/joules are PASSED THROUGH.
# ---------------------------------------------------------------------------
def _fabric_summary() -> dict:
    pool = _self_get(_COMPUTE_POOL_PATH)
    energy = _self_get(_ENERGY_OP_PATH)
    prov = _self_get(_ENERGY_PROV_PATH)

    pool_ok = isinstance(pool, dict) and "nodes" in pool
    energy_ok = isinstance(energy, dict) and "joules_measured_total" in energy
    prov_ok = isinstance(prov, dict) and "verify" in prov

    # --- node reachability + sovereignty: PASS THROUGH from compute-pool only ---
    if pool_ok:
        counts = pool.get("counts", {}) or {}
        nodes = pool.get("nodes", []) or []
        nodes_total = counts.get("nodes_total", len(nodes))
        nodes_reachable = counts.get("nodes_reachable",
                                     sum(1 for n in nodes if n.get("reachable")))
        gpu_nodes_reachable = counts.get("gpu_nodes_reachable")
        sovereign_count = sum(1 for n in nodes if n.get("sovereign"))
        sovereign_reachable = sum(1 for n in nodes
                                  if n.get("sovereign") and n.get("reachable"))
        node_brief = [
            {"name": n.get("name"), "kind": n.get("kind"),
             "reachable": n.get("reachable"), "sovereign": n.get("sovereign"),
             "detail": n.get("detail")}
            for n in nodes
        ]
        pool_cached_at = pool.get("cached_at")
    else:
        nodes_total = nodes_reachable = gpu_nodes_reachable = None
        sovereign_count = sovereign_reachable = None
        node_brief = []
        pool_cached_at = None

    # --- MEASURED joules: PASS THROUGH from the energy operator only ---
    if energy_ok:
        joules_measured_total = energy.get("joules_measured_total")
        joules_measured_label = energy.get("joules_measured_label", "MEASURED")
        joules_sample_total = energy.get("joules_sample_total")
        joules_sample_label = energy.get("joules_sample_label", "SAMPLE")
        nodes_computing = energy.get("nodes_computing", [])
        operator_running = energy.get("running")
        exporter_node = energy.get("exporter_node")
        jobs_done = energy.get("jobs_done")
    else:
        joules_measured_total = None
        joules_measured_label = "UNKNOWN — energy operator unreachable this sweep"
        joules_sample_total = None
        joules_sample_label = "UNKNOWN"
        nodes_computing = []
        operator_running = None
        exporter_node = None
        jobs_done = None

    # --- signed-receipt head: cite the energy-provenance chain (already signed) ---
    if prov_ok:
        verify = prov.get("verify", {}) or {}
        signed_head = {
            "source": "energy-provenance chain (hash-linked + Bekenstein gate)",
            "head_hash": prov.get("head_hash", "") or verify.get("head_hash", ""),
            "chain_length": prov.get("length", verify.get("length")),
            "links_intact": verify.get("links_intact"),
            "verified_ok": verify.get("ok"),
            "kind": "Conjecture 2 (Khipu/provenance: tamper-EVIDENT, not tamper-proof)",
        }
    else:
        signed_head = {
            "source": "energy-provenance chain",
            "head_hash": "UNKNOWN — provenance source unreachable this sweep",
            "verified_ok": None,
            "kind": "Conjecture 2",
        }

    sources_reachable = bool(pool_ok and energy_ok)
    status = "REAL" if sources_reachable else "DEGRADED"

    payload = {
        "ok": True,
        "service": "fabric",
        "surface_names": ["Fabric", "Tawantin"],
        "organ": _FABRIC_NAME,
        "kind": "Governed Distributed Compute Fabric (honest SUMMARY over live sources)",
        "role": "horizontal multi-node governed compute — independent nodes, NOT a fused pool",
        "summary": {
            "nodes_total": nodes_total,
            "nodes_reachable": nodes_reachable,
            "gpu_nodes_reachable": gpu_nodes_reachable,
            "sovereign_count": sovereign_count,
            "sovereign_reachable": sovereign_reachable,
            "joules_measured_total": joules_measured_total,
            "joules_measured_label": joules_measured_label,
            "joules_sample_total": joules_sample_total,
            "joules_sample_label": joules_sample_label,
            "operator_running": operator_running,
            "nodes_computing": nodes_computing,
            "jobs_done": jobs_done,
            "exporter_node": exporter_node,
            "signed_receipt_head": signed_head,
        },
        "nodes": node_brief,
        "sources": {
            "compute_pool": {"path": _COMPUTE_POOL_PATH, "reachable": pool_ok,
                             "cached_at": pool_cached_at,
                             "note": "node identity / reachability / sovereignty (LIVE)"},
            "energy_operator": {"path": _ENERGY_OP_PATH, "reachable": energy_ok,
                                "note": "MEASURED joules via on-box NVML exporter (LIVE)"},
            "energy_provenance": {"path": _ENERGY_PROV_PATH, "reachable": prov_ok,
                                  "note": "signed hash-linked provenance chain head (LIVE)"},
        },
        "sources_reachable": sources_reachable,
        "honesty": dict(_HONESTY, **{
            "summary_only": "This endpoint AGGREGATES the live sources above. It "
                            "duplicates NO node data and fabricates NO joule/node "
                            "value — every figure is passed through from its real "
                            "source, or UNKNOWN when that source is unreachable.",
            "scale": "HORIZONTAL scale only — independent nodes. There is NO fused/"
                     "pooled VRAM claim anywhere in this fabric.",
            "joules": "joules_measured_total is the SUM of fresh (<30s) per-job "
                      "MEASURED NVML deltas — the only billable figure. SAMPLE "
                      "energy is tracked separately and is never billable.",
            "khipu_receipt": "OPTIONAL here — the underlying energy-provenance + "
                             "per-source receipts already sign. This summary CITES "
                             "the signed provenance head rather than minting a "
                             "duplicate node-data receipt.",
        }),
        "locked_proven": {
            "set": _LOCKED_PROVEN, "count": len(_LOCKED_PROVEN),
            "kernel_commit": _KERNEL_COMMIT,
            "note": "EXACTLY 8 locked-proven; this summary adds nothing to the set.",
        },
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    return _gov(payload, status=status)


# ---------------------------------------------------------------------------
# Auto-review honest summary — over the REAL governed auto-review substance.
# Calibration is MEASURED (LIVE); decision-rate metrics are ROADMAP until real
# runs are logged. NEVER faked.
# ---------------------------------------------------------------------------
def _autoreview_summary() -> dict:
    metrics = _self_get(_AR_METRICS_PATH)
    dial = _self_get(_AR_DIAL_PATH)
    policy = _self_get(_AR_POLICY_PATH)

    metrics_ok = isinstance(metrics, dict)
    dial_ok = isinstance(dial, dict)
    policy_ok = isinstance(policy, dict)

    # --- calibration: MEASURED, passed through from the live metrics source ---
    calib = (metrics.get("calibration") if metrics_ok else None) or {}
    calib_status = calib.get("status")  # "measured" when real predictions exist
    calibration_live = calib_status == "measured"

    # --- decision rates: MEASURED when real decisions logged, else ROADMAP ---
    decisions_logged = metrics.get("decisions_logged") if metrics_ok else None
    rate_status = metrics.get("rate_status") if metrics_ok else None
    rates_live = bool(decisions_logged) if decisions_logged is not None else False

    dial_levels = dial.get("levels", []) if dial_ok else []
    default_level = None
    for lvl in dial_levels:
        if isinstance(lvl, dict) and "default" in str(lvl.get("label", "")).lower():
            default_level = lvl.get("level")

    automated_gate = metrics.get("automated_response_gate") if metrics_ok else None

    # The classifier itself is REAL + LIVE (deterministic intent-relative scorer,
    # policy-as-code, signed DSSE verdicts). The fast-model wiring is ROADMAP.
    sources_reachable = bool(metrics_ok and dial_ok)
    status = "REAL" if sources_reachable else "DEGRADED"

    payload = {
        "ok": True,
        "service": "autoreview",
        "organ": _AUTOREVIEW_NAME,
        "kind": "Governed + signed + standards-mapped Auto-review autonomy layer "
                "(honest SUMMARY over the live classifier/calibration/dial sources)",
        "classifier": {
            "kind": "fast deterministic intent-relative rule+feature scorer (HEURISTIC)",
            "live": True,
            "label": "LIVE — the classifier + policy-as-code + signed DSSE verdict "
                     "path are real and served (classify/gated-run/policy/metrics).",
            "production_fast_model": "sovereign GPU/router fast model (RTX role-split) "
                                     "— ROADMAP (labelled, not wired).",
        },
        "calibration": {
            "live": calibration_live,
            "label": "LIVE — MEASURED ECE/Brier" if calibration_live
                     else "ROADMAP — no measured calibration yet",
            "model": calib.get("model"),
            "n": calib.get("n"),
            "ece": calib.get("ece"),
            "brier": calib.get("brier"),
            "accuracy": calib.get("accuracy"),
            "ece_gate_threshold": calib.get("ece_gate_threshold"),
            "note": "ECE/Brier over the last N verified predictions; ECE<0.05 gates "
                    "automated responses. MEASURED, never faked.",
        },
        "decision_rates": {
            "live": rates_live,
            "label": "LIVE — MEASURED from the rolling decision log" if rates_live
                     else "ROADMAP — no real decisions logged yet (rates are null, never faked)",
            "decisions_logged": decisions_logged,
            "block_rate": metrics.get("block_rate") if metrics_ok else None,
            "interrupt_rate": metrics.get("interrupt_rate") if metrics_ok else None,
            "escalate_rate": metrics.get("escalate_rate") if metrics_ok else None,
            "rate_status": rate_status,
            "honest_note": "Block/interrupt/escalate rates are MEASURED from the local "
                           "rolling decision log, or ROADMAP (null) when no real runs "
                           "exist yet. We never borrow another vendor's published number.",
        },
        "autonomy_dial": {
            "live": dial_ok,
            "levels": len(dial_levels),
            "default_level": default_level,
            "label": "LIVE — autonomy is a DIAL (L0..L5), not a switch",
        },
        "policy_as_code": {
            "live": policy_ok,
            "label": "LIVE — OPA/Rego rules mapped to OSCAL control IDs + NIST AI RMF "
                     "MANAGE subcategories" if policy_ok else "ROADMAP",
        },
        "automated_response_gate": automated_gate,
        "sources": {
            "metrics": {"path": _AR_METRICS_PATH, "reachable": metrics_ok},
            "dial": {"path": _AR_DIAL_PATH, "reachable": dial_ok},
            "policy": {"path": _AR_POLICY_PATH, "reachable": policy_ok},
        },
        "sources_reachable": sources_reachable,
        "honesty": dict(_HONESTY, **{
            "verdict_signing": "Auto-review verdicts are signed into DSSE receipts "
                               "(reuses the host's real ECDSA-P256 signer) — tamper-"
                               "EVIDENT, not tamper-proof.",
            "summary_only": "This endpoint summarizes the live autoreview sources; it "
                            "fabricates no metric. Decision rates stay ROADMAP/null "
                            "until real runs are logged.",
            "borrow": "Pattern honestly borrowed-and-evolved from Cursor's Auto-review "
                      "(autonomy as a dial). We MEASURE our own numbers; we do not "
                      "borrow theirs.",
        }),
        "locked_proven": {
            "set": _LOCKED_PROVEN, "count": len(_LOCKED_PROVEN),
            "kernel_commit": _KERNEL_COMMIT,
            "note": "EXACTLY 8 locked-proven; this summary adds nothing to the set.",
        },
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    return _gov(payload, status=status)


def _healthz(service: str, organ: str) -> dict:
    return {"status": "ok", "service": service, "organ": organ, "doctrine": "v11"}


# ---------------------------------------------------------------------------
# Registration — dual-register under /api/{ns}/v1/* AND /v1/*. add_api_route,
# mirroring szl_immune. Registered BEFORE the SPA catch-all so these JSON routes
# win ordering. Module-level Request/JSONResponse imports keep annotations valid.
# ---------------------------------------------------------------------------
def register(app, ns: str = "a11oy") -> dict:
    # NOTE: the summaries make blocking loopback self-calls to sibling endpoints.
    # We run them in a threadpool so the (single-worker) event loop stays FREE to
    # serve those nested requests — a synchronous self-call directly inside the
    # async handler would starve the loop and the nested request would time out
    # (the summary would then wrongly degrade to UNKNOWN).
    async def _h_tawantin_status():  # noqa: ANN202
        return JSONResponse(await run_in_threadpool(_fabric_summary))

    async def _h_fabric_status():  # noqa: ANN202
        return JSONResponse(await run_in_threadpool(_fabric_summary))

    async def _h_autoreview_status():  # noqa: ANN202
        return JSONResponse(await run_in_threadpool(_autoreview_summary))

    async def _h_tawantin_healthz():  # noqa: ANN202
        return JSONResponse(_healthz("tawantin", _FABRIC_NAME))

    async def _h_fabric_healthz():  # noqa: ANN202
        return JSONResponse(_healthz("fabric", _FABRIC_NAME))

    routes: list[str] = []
    for base in (f"/api/{ns}/v1", "/v1"):
        app.add_api_route(f"{base}/tawantin/status", _h_tawantin_status,
                          methods=["GET"], include_in_schema=True)
        app.add_api_route(f"{base}/tawantin/healthz", _h_tawantin_healthz,
                          methods=["GET"], include_in_schema=True)
        app.add_api_route(f"{base}/fabric/status", _h_fabric_status,
                          methods=["GET"], include_in_schema=True)
        app.add_api_route(f"{base}/fabric/healthz", _h_fabric_healthz,
                          methods=["GET"], include_in_schema=True)
        app.add_api_route(f"{base}/autoreview/status", _h_autoreview_status,
                          methods=["GET"], include_in_schema=True)
        routes.extend([f"{base}/tawantin/status", f"{base}/tawantin/healthz",
                       f"{base}/fabric/status", f"{base}/fabric/healthz",
                       f"{base}/autoreview/status"])

    print(f"[{ns}] szl_fabric_surface routes registered "
          f"(Fabric/Tawantin + Auto-review honest summaries, {len(routes)} routes)",
          flush=True)
    return {"ok": True, "ns": ns, "organ": _FABRIC_NAME, "routes": routes}


# ---------------------------------------------------------------------------
# No-server self-test — proves the aggregation/honesty logic with mocked sources
# (no HTTP, no live deps). Validates: pass-through, honest degradation, no
# codename leak, no fused-VRAM claim.
# ---------------------------------------------------------------------------
def _selftest() -> dict:
    import unittest.mock as mock
    out: dict = {}

    fake_pool = {
        "counts": {"nodes_total": 7, "nodes_reachable": 4, "gpu_nodes_reachable": 0},
        "nodes": [
            {"name": "hetzner-box-cpu", "kind": "cpu", "reachable": True,
             "sovereign": True, "detail": "self"},
            {"name": "rtx-betterwithage", "kind": "sovereign-gpu", "reachable": False,
             "sovereign": True, "detail": "timeout"},
            {"name": "groq", "kind": "hosted-inference", "reachable": True,
             "sovereign": False, "detail": "tcp reachable"},
        ],
        "cached_at": "2026-06-16T05:00:00Z",
    }
    fake_energy = {
        "joules_measured_total": 0.0, "joules_measured_label": "MEASURED",
        "joules_sample_total": 0.0, "joules_sample_label": "SAMPLE",
        "running": False, "nodes_computing": [], "jobs_done": 0,
        "exporter_node": "betterwithage",
    }
    fake_prov = {"head_hash": "abc123", "length": 3,
                 "verify": {"ok": True, "links_intact": True, "length": 3,
                            "head_hash": "abc123"}}
    fake_metrics = {
        "decisions_logged": 0, "block_rate": None, "interrupt_rate": None,
        "rate_status": "ROADMAP — no real decisions logged yet",
        "calibration": {"model": "a11oy-autoreview-classifier", "n": 24,
                        "status": "measured", "ece": 0.03875, "brier": 0.002017,
                        "accuracy": 1.0, "ece_gate_threshold": 0.05},
        "automated_response_gate": {"allow": True},
    }
    fake_dial = {"levels": [{"level": i, "label": f"L{i}"} for i in range(6)]}
    fake_dial["levels"][3]["label"] = "L3 — Governed (default)"
    fake_policy = {"rules": []}

    def _route(path, timeout=None):
        return {
            _COMPUTE_POOL_PATH: fake_pool, _ENERGY_OP_PATH: fake_energy,
            _ENERGY_PROV_PATH: fake_prov, _AR_METRICS_PATH: fake_metrics,
            _AR_DIAL_PATH: fake_dial, _AR_POLICY_PATH: fake_policy,
        }.get(path)

    with mock.patch(__name__ + "._self_get", side_effect=_route):
        fab = _fabric_summary()
        ar = _autoreview_summary()

    # Pass-through correctness (no fabrication, no invention).
    assert fab["status"] == "REAL", fab
    assert fab["summary"]["nodes_total"] == 7, fab
    assert fab["summary"]["nodes_reachable"] == 4, fab
    assert fab["summary"]["sovereign_count"] == 2, fab
    assert fab["summary"]["sovereign_reachable"] == 1, fab
    assert fab["summary"]["joules_measured_total"] == 0.0, fab
    assert fab["summary"]["signed_receipt_head"]["head_hash"] == "abc123", fab
    out["fabric_passthrough"] = True

    # Auto-review: calibration MEASURED live, rates ROADMAP.
    assert ar["calibration"]["live"] is True, ar
    assert ar["calibration"]["ece"] == 0.03875, ar
    assert ar["decision_rates"]["live"] is False, ar
    assert ar["autonomy_dial"]["default_level"] == 3, ar
    out["autoreview_labels"] = True

    # Honest degradation when a source is unreachable.
    with mock.patch(__name__ + "._self_get", side_effect=lambda p, timeout=None: None):
        fab_d = _fabric_summary()
        ar_d = _autoreview_summary()
    assert fab_d["status"] == "DEGRADED", fab_d
    assert fab_d["sources_reachable"] is False, fab_d
    assert fab_d["summary"]["nodes_total"] is None, fab_d
    assert ar_d["status"] == "DEGRADED", ar_d
    out["honest_degradation"] = True

    # No codename leak; no fused-VRAM claim.
    served = json.dumps([fab, ar, fab_d, ar_d]).lower()
    for bad in ("sentra", "amaru", "rosie", "jarvis"):
        assert bad not in served, f"codename leak: {bad}"
    # The ONLY mentions of fused/pooled VRAM must be honest NEGATIONS (we deny it).
    assert "horizontal" in served, "missing horizontal-scale honesty"
    assert ("no fused" in served and "not a fused pool" in served), \
        "fused-VRAM must appear only as an explicit denial"
    # No POSITIVE fused-VRAM claim (e.g. 'fused vram', 'pooled vram' without 'no').
    assert "fused vram" not in served, "positive fused-VRAM claim leaked"
    out["no_codename_no_fused_vram"] = True

    return out


if __name__ == "__main__":
    print(json.dumps(_selftest(), indent=2))
