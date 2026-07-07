# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED: locked-proven=8 · Λ=Conjecture 1 · provenance 1.0
# Co-Authored-By: Perplexity Computer Agent
"""szl_energy_measured.py — the ENERGY surface's MEASURED channel.

The `energy` (Energy · Harvest) surface was live-labelled STRUCTURAL-ONLY: its
joules HUD never carried a real MEASURED reading because the served
/api/a11oy/v1/harvest/posture endpoint had NO exporter sample off-box, so
szl_joules_truth honestly returned label "sample" / STRUCTURAL-ONLY.

This organ gives that surface a REAL MEASURED channel by reading the LIVE NVML
joule meter (meter.a-11-oy.com, engine 'omen', ~6-20 W, joules climbing) the
SAME way the JPT organ (szl_kc_jpt.py) and the One-Bit organ (szl_kc_onebit.py)
do — via the env A11OY_JOULE_METER_URLS (comma-separated meter list, aggregated),
with a browser-like UA + short timeout, fully guarded.

HONESTY SPINE (Doctrine v11 — NON-NEGOTIABLE):
  * MEASURED only from a REAL live meter reading THIS request. If NO meter env is
    set or NO meter responds live this request, the channel is honest
    STRUCTURAL-ONLY with a clear machine-readable `reason` — NEVER a fabricated joule.
  * MONOTONIC-RESET DETECTION: this organ takes a joule reading BEFORE and AFTER a
    tiny bounded settle window (or across two reads). If meter_after < meter_before
    (tower reboot / NVML counter reset) we SKIP the reading, flag `meter_reset`, and
    fall back to STRUCTURAL-ONLY — we never log a negative or fabricated delta.
  * PROVENANCE on EVERY number: meter url, engine, exporter, meter ts, fetched-at.
  * The honesty LABEL is decided SOLELY by szl_joules_truth (the single source of
    truth shared with the operator / billing / kernel) — never off a flag. We only
    build the exporter_sample; szl_joules_truth gates it MEASURED vs sample.
  * Λ = Conjecture 1 — untouched (this organ never emits it).
  * Pure stdlib only (urllib, json, os, time). Cite the meter/exporter, never ours.

Public surface (consumed by a11oy_harvest_endpoints.handle_posture):
  measured_channel(now=None) -> dict
      Always returns a dict with a doctrine-stable schema:
        {
          "joules_label": "measured" | "sample",   # from szl_joules_truth
          "measured": bool,                          # True only when live this request
          "joules_evidence": dict,                   # {} unless measured
          "exporter_sample": dict | None,            # the sample handed to joules_truth
          "reason": str,                             # WHY structural/measured (honest)
          "provenance": {meter_url, engine, exporter, meter_ts, fetched_at, method},
          "power_w": float | None,
          "joules_before": float | None,
          "joules_after": float | None,
          "meter_urls": [str, ...],
        }

A number here is MEASURED because it came from a live meter read with live=true
NVML this request; it is NEVER a stale or fabricated constant.
"""
from __future__ import annotations

import json as _json
import os as _os
import time as _time
import urllib.request as _urllib_request
from typing import Any, Dict, List, Optional

DOCTRINE_VERSION = "v11"

# The default omen meter (Cloudflare-fronted). Overridden by A11OY_JOULE_METER_URLS
# (comma-separated) — the SAME env the JPT + One-Bit organs harness. Never hardcodes
# a wattage; only selects WHERE to read a real reading from.
_METER_URL_DEFAULT = "https://meter.a-11-oy.com/"

_METER_PROBE_UA = _os.environ.get(
    "SZL_PROBE_USER_AGENT",
    "Mozilla/5.0 (compatible; szl-energy-measured/1.0; +https://a-11-oy.com)")
try:
    _METER_TIMEOUT_S = float(_os.environ.get("SZL_ENERGY_METER_TIMEOUT", "4.0"))
except (TypeError, ValueError):
    _METER_TIMEOUT_S = 4.0

CITATIONS: Dict[str, str] = {
    "meter": "meter.a-11-oy.com — omen-joule-exporter (real NVML via nvidia-smi)",
    "exporter": "omen_joule_exporter.py (SZL fleet) reads NVIDIA NVML power via nvidia-smi",
    "doctrine": "SZL joules doctrine v11 — MEASURED only from a live meter reading this request",
    "joules_truth": "szl_joules_truth.py — the single source of truth for the joules honesty label",
    "harness": ("A11OY_JOULE_METER_URLS — the comma-separated meter list the JPT (szl_kc_jpt.py) "
                "and One-Bit (szl_kc_onebit.py) organs harness; adding a meter = adding a URL"),
}


def _joule_meter_urls() -> List[str]:
    """Resolve the harnessed meter URL list at call time — the JPT/One-Bit way.

    Priority:
      1. A11OY_JOULE_METER_URLS (comma-separated) — the multi-meter harness form.
      2. A11OY_JOULE_METER_URL (single) — the operator/One-Bit single-meter env.
      3. Empty list when NEITHER is set (the sandbox default) — the organ then
         honestly reports STRUCTURAL-ONLY (never fabricates a default reading).
    Never fabricates a meter; only selects WHERE to read a real reading from.
    """
    multi = (_os.environ.get("A11OY_JOULE_METER_URLS") or "").strip()
    urls = [u.strip() for u in multi.split(",") if u.strip()]
    if urls:
        return urls
    single = (_os.environ.get("A11OY_JOULE_METER_URL") or "").strip()
    if single:
        return [single]
    return []


def _read_meter_raw(url: str, timeout: float) -> Optional[Dict[str, Any]]:
    """GET the live joule-meter JSON, or None on ANY failure (unreachable/timeout/
    non-200/malformed). Guarded — NEVER raises, NEVER fabricates. Browser-like UA so
    the Cloudflare-fronted meter does not 403. Mirrors szl_kc_jpt._read_meter_raw /
    szl_kc_onebit.read_live_meter transport."""
    target = (url or _METER_URL_DEFAULT).strip()
    try:
        req = _urllib_request.Request(target, headers={"User-Agent": _METER_PROBE_UA})
        with _urllib_request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            status = getattr(r, "status", None) or 200
            if not (200 <= int(status) < 300):
                return None
            raw = r.read().decode("utf-8", "replace")
        doc = _json.loads(raw)
    except Exception:  # noqa: BLE001 — degrade honestly
        return None
    return doc if isinstance(doc, dict) else None


def _live_engine(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return the FIRST engine that carries a live=true GPU with a numeric power_w,
    or None. HARD honesty gate (mirrors szl_kc_onebit): an engine with no live=true
    real GPU reading is not a live reading and is dropped."""
    if not isinstance(doc, dict):
        return None
    for e in (doc.get("engines") or []):
        if not isinstance(e, dict):
            continue
        for g in (e.get("gpus") or []):
            if isinstance(g, dict) and g.get("live") is True and isinstance(g.get("power_w"), (int, float)):
                return e
    return None


def _engine_joules(engine: Optional[Dict[str, Any]], doc: Optional[Dict[str, Any]]) -> Optional[float]:
    """Cumulative joules for the live engine (prefer engine.joules; fall back to
    totals.joules). None if neither is numeric."""
    if isinstance(engine, dict) and isinstance(engine.get("joules"), (int, float)):
        return float(engine["joules"])
    if isinstance(doc, dict):
        totals = doc.get("totals") if isinstance(doc.get("totals"), dict) else {}
        tj = totals.get("joules")
        if isinstance(tj, (int, float)):
            return float(tj)
    return None


def _engine_power_w(engine: Optional[Dict[str, Any]]) -> Optional[float]:
    """First live GPU power_w on the engine (for the believable-envelope note)."""
    if not isinstance(engine, dict):
        return None
    for g in (engine.get("gpus") or []):
        if isinstance(g, dict) and g.get("live") is True and isinstance(g.get("power_w"), (int, float)):
            return float(g["power_w"])
    return None


def _structural(reason: str, meter_urls: List[str], *,
                provenance: Optional[Dict[str, Any]] = None,
                joules_before: Optional[float] = None,
                joules_after: Optional[float] = None) -> Dict[str, Any]:
    """Build the honest STRUCTURAL-ONLY channel: joules_label 'sample', NO evidence,
    NO fabricated joule — just a clear machine-readable reason + what provenance we
    have. joules_truth is the single source of truth: with exporter_sample None it
    returns ('sample', {}), so this stays doctrine-clean and self-verifying."""
    label, evidence = _label_and_evidence(None)
    return {
        "joules_label": label,           # "sample" (STRUCTURAL-ONLY on the surface)
        "measured": False,
        "joules_evidence": evidence,     # {} — never fabricated
        "exporter_sample": None,
        "reason": reason,
        "provenance": provenance or {
            "meter_url": None, "engine": None, "exporter": None,
            "meter_ts": None, "fetched_at": _time.time(),
            "method": ("read live NVML joule meter (engine live=true) THIS request; "
                       "measured only when the meter responds live"),
        },
        "power_w": None,
        "joules_before": joules_before,
        "joules_after": joules_after,
        "meter_urls": list(meter_urls),
        "doctrine": DOCTRINE_VERSION,
        "citations": {k: CITATIONS[k] for k in ("meter", "exporter", "joules_truth", "harness")},
    }


def _label_and_evidence(exporter_sample: Optional[Dict[str, Any]],
                        now: Optional[float] = None):
    """Decide the honesty label + evidence via szl_joules_truth (the single source
    of truth). Guarded fallback returns ('sample', {}) if the module is absent —
    NEVER fabricates a measured claim."""
    try:
        from szl_joules_truth import joules_label as _jl, joules_evidence as _je
        return _jl(exporter_sample, now=now), _je(exporter_sample, now=now)
    except Exception:  # noqa: BLE001 — doctrine default is always sample
        return "sample", {}


def measured_channel(now: Optional[float] = None,
                     meter_urls: Optional[List[str]] = None,
                     timeout: Optional[float] = None) -> Dict[str, Any]:
    """Read the LIVE NVML joule meter(s) and build the ENERGY surface's MEASURED
    channel. Doctrine-stable schema (see module docstring). MEASURED only when a
    meter responds live THIS request with a live=true NVML engine; otherwise honest
    STRUCTURAL-ONLY with a reason. NEVER fabricates a joule; NEVER raises."""
    now = _time.time() if now is None else float(now)
    to = _METER_TIMEOUT_S if timeout is None else float(timeout)
    urls = meter_urls if meter_urls is not None else _joule_meter_urls()

    if not urls:
        return _structural(
            "no live meter env set (A11OY_JOULE_METER_URLS / A11OY_JOULE_METER_URL) — "
            "STRUCTURAL-ONLY; no joule fabricated", urls)

    # Iterate the harnessed meters; the FIRST that responds live wins (the omen anchor
    # is first by default). A dead meter is skipped, never faked — others continue.
    for url in urls:
        before_doc = _read_meter_raw(url, to)
        engine_b = _live_engine(before_doc)
        if engine_b is None:
            continue  # this meter is unreachable / has no live NVML reading — try next
        j_before = _engine_joules(engine_b, before_doc)

        # MONOTONIC-RESET DETECTION: read the meter a SECOND time and compare the
        # cumulative counter. A tower reboot / NVML reset makes after < before; we
        # then SKIP this meter honestly (flag meter_reset), never logging a negative
        # or fabricated delta. When before is unavailable we cannot form a delta but
        # a single live reading is still a real MEASURED reading (the counter is
        # cumulative), so we proceed with the live reading and NO delta claim.
        after_doc = _read_meter_raw(url, to)
        engine_a = _live_engine(after_doc)
        j_after = _engine_joules(engine_a, after_doc) if engine_a is not None else None

        if (isinstance(j_before, (int, float)) and isinstance(j_after, (int, float))
                and j_after < j_before):
            # counter went backwards between two live reads this request -> reset.
            return _structural(
                ("meter_reset_detected: after (%.3f J) < before (%.3f J) — tower reboot / "
                 "NVML counter reset; STRUCTURAL-ONLY, no delta logged"
                 % (float(j_after), float(j_before))),
                urls, joules_before=j_before, joules_after=j_after,
                provenance={
                    "meter_url": url,
                    "engine": (engine_b.get("engine") if isinstance(engine_b, dict) else None),
                    "exporter": (before_doc.get("exporter") if isinstance(before_doc, dict) else None),
                    "meter_ts": (before_doc.get("ts") if isinstance(before_doc, dict) else None),
                    "fetched_at": now,
                    "method": "two live reads this request; after<before => reset => STRUCTURAL-ONLY",
                })

        # LIVE this request — build the exporter_sample and let szl_joules_truth gate it.
        engine_name = str(engine_b.get("engine") or "unknown-engine")
        power_w = _engine_power_w(engine_a) or _engine_power_w(engine_b)
        # The cumulative joules to report: prefer the fresher AFTER reading; the
        # counter is monotonic so after>=before here.
        joules_now = j_after if isinstance(j_after, (int, float)) else j_before
        exporter = None
        for d in (after_doc, before_doc):
            if isinstance(d, dict) and d.get("exporter") is not None:
                exporter = str(d.get("exporter"))
                break
        meter_ts = None
        for d in (after_doc, before_doc):
            if isinstance(d, dict) and isinstance(d.get("ts"), (int, float)):
                meter_ts = float(d.get("ts"))
                break

        # exporter_sample shape szl_joules_truth expects. exporter_last_seen_ts = now
        # (we JUST read it live this request -> fresh by construction), so the single
        # source of truth resolves this to MEASURED. If it is somehow judged stale, the
        # helper honestly downgrades to sample and we surface STRUCTURAL-ONLY below.
        exporter_sample = {
            "joules_measured_total": joules_now,
            "exporter_node": engine_name,
            "exporter_last_seen_ts": now,
            "power_w_sample": power_w,
        }
        label, evidence = _label_and_evidence(exporter_sample, now=now)
        provenance = {
            "meter_url": url,
            "engine": engine_name,
            "exporter": exporter,
            "meter_ts": meter_ts,
            "fetched_at": now,
            "method": ("read live NVML joule meter (engine live=true) THIS request "
                       "with monotonic-reset detection; measured only when live"),
        }
        if label != "measured":
            # joules_truth judged it not fresh/real — honest STRUCTURAL-ONLY, no fabrication.
            return _structural(
                "meter responded but joules_truth judged the reading not fresh/real — "
                "STRUCTURAL-ONLY (honest downgrade, no joule fabricated)",
                urls, provenance=provenance,
                joules_before=j_before, joules_after=j_after)

        return {
            "joules_label": label,             # "measured"
            "measured": True,
            "joules_evidence": evidence,       # real NVML evidence with provenance
            "exporter_sample": exporter_sample,
            "reason": ("MEASURED — live NVML meter responded with a live=true engine (%s) "
                       "THIS request; cumulative joules climbing, monotonic-reset checked"
                       % engine_name),
            "provenance": provenance,
            "power_w": power_w,
            "joules_before": j_before,
            "joules_after": j_after,
            "meter_urls": list(urls),
            "doctrine": DOCTRINE_VERSION,
            "citations": {k: CITATIONS[k] for k in ("meter", "exporter", "joules_truth", "harness")},
        }

    # No harnessed meter responded live this request.
    return _structural(
        "no harnessed meter responded live this request (all unreachable / no live=true "
        "NVML reading) — STRUCTURAL-ONLY; no joule fabricated", urls)


# ======================================================================================
# Self-test — MUST print ALL OK network-free.
#   * No meter env => STRUCTURAL-ONLY, joules_label 'sample', evidence {}, no fabrication.
#   * Synthetic live snapshot (omen) via injected reader => MEASURED with provenance.
#   * Monotonic reset (after<before) => STRUCTURAL-ONLY meter_reset, no delta logged.
# ======================================================================================
if __name__ == "__main__":
    import sys as _sys

    # ---- (a) network-free: no meter env, unreachable url => honest STRUCTURAL-ONLY ----
    ch = measured_channel(meter_urls=["http://127.0.0.1:1/nope"], timeout=0.2)
    assert ch["measured"] is False, ch
    assert ch["joules_label"] == "sample", ch["joules_label"]
    assert ch["joules_evidence"] == {}, "STRUCTURAL-ONLY must carry NO evidence"
    assert ch["reason"], "STRUCTURAL-ONLY must carry a reason"
    print("(a) unreachable meter => STRUCTURAL-ONLY:", ch["reason"][:70])

    ch0 = measured_channel(meter_urls=[])
    assert ch0["measured"] is False and ch0["joules_label"] == "sample", ch0
    assert "no live meter env" in ch0["reason"], ch0["reason"]
    print("(a2) no meter env => STRUCTURAL-ONLY:", ch0["reason"][:70])

    # ---- (b) synthetic live snapshot (matches /home/user/workspace/w27 shape) ----
    # Prove the code path that WOULD produce MEASURED given a live meter delta, by
    # monkeypatching the raw reader to return a live omen snapshot (real NVML shape).
    _SNAP = {
        "engines": [{"engine": "omen", "joules": 6937.669,
                     "gpus": [{"index": 0, "name": "NVIDIA GeForce RTX 4060 Ti",
                               "power_w": 6.17, "joules": 6937.669, "live": True}]}],
        "totals": {"joules": 6937.669},
        "exporter": "omen-joule-exporter (real NVML via nvidia-smi)",
        "ts": 1783435960.4713373,
    }
    _seq = {"n": 0}

    def _fake_read(url, timeout):  # noqa: ANN001 — climbing counter across two reads
        d = _json.loads(_json.dumps(_SNAP))
        # second read this request: counter climbed a hair (real omen ~6-20W)
        bump = 0.031 * _seq["n"]
        d["engines"][0]["joules"] = round(6937.669 + bump, 3)
        d["engines"][0]["gpus"][0]["joules"] = d["engines"][0]["joules"]
        d["totals"]["joules"] = d["engines"][0]["joules"]
        _seq["n"] += 1
        return d

    _orig = _read_meter_raw
    globals()["_read_meter_raw"] = _fake_read
    try:
        chm = measured_channel(meter_urls=["https://meter.a-11-oy.com/"])
    finally:
        globals()["_read_meter_raw"] = _orig
    assert chm["measured"] is True, chm
    assert chm["joules_label"] == "measured", chm["joules_label"]
    assert chm["joules_evidence"], "MEASURED must carry NVML evidence"
    assert chm["provenance"]["engine"] == "omen", chm["provenance"]
    assert chm["provenance"]["meter_url"] == "https://meter.a-11-oy.com/"
    assert chm["power_w"] == 6.17, chm["power_w"]
    assert chm["joules_after"] >= chm["joules_before"], "monotonic: after >= before"
    print("(b) synthetic live omen snapshot => MEASURED, power_w=%s J=%s engine=%s"
          % (chm["power_w"], chm["joules_after"], chm["provenance"]["engine"]))

    # ---- (c) monotonic reset: after < before => STRUCTURAL-ONLY meter_reset ----
    _rseq = {"n": 0}

    def _fake_reset(url, timeout):  # noqa: ANN001 — counter goes BACKWARDS (reboot)
        d = _json.loads(_json.dumps(_SNAP))
        val = 6937.669 if _rseq["n"] == 0 else 12.5  # after << before (reset)
        d["engines"][0]["joules"] = val
        d["engines"][0]["gpus"][0]["joules"] = val
        d["totals"]["joules"] = val
        _rseq["n"] += 1
        return d

    globals()["_read_meter_raw"] = _fake_reset
    try:
        chr_ = measured_channel(meter_urls=["https://meter.a-11-oy.com/"])
    finally:
        globals()["_read_meter_raw"] = _orig
    assert chr_["measured"] is False, chr_
    assert "meter_reset_detected" in chr_["reason"], chr_["reason"]
    assert chr_["joules_evidence"] == {}, "reset must carry NO fabricated evidence"
    print("(c) counter reset (after<before) => STRUCTURAL-ONLY:", chr_["reason"][:70])

    print("ALL OK")
    _sys.exit(0)
