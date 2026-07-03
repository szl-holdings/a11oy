"""szl_joules_truth.py — SINGLE SOURCE OF TRUTH for the joules honesty label.

Doctrine v11 (the whole point of this module):

    joules may read "measured" ONLY when a REAL on-box NVML exporter sample is
    present AND fresh. In every other case the honest label is "sample".

The cross-module bug this fixes: several surfaces stamped joules_label="measured"
off a bare boolean (e.g. ``metered_onbox``) or off a forwarded string label, with
NO actual exporter reading behind it. That fabricates a "measured" claim. This
module is the ONLY place allowed to decide the label, so the answer is consistent
and self-verifying everywhere.

Two pure, deterministic helpers:

    joules_label(exporter_sample)    -> "measured" | "sample"
    joules_evidence(exporter_sample) -> dict (evidence iff measured, else {})

NEVER fabricate a measured value. If we cannot prove a fresh real exporter sample,
we return "sample" and an empty / honestly-null evidence dict.

An ``exporter_sample`` is whatever real NVML-exporter signal a module has, e.g.::

    {
        "joules_measured_total": 1234.5,   # cumulative joules from the exporter
        "exporter_node": "rig-0",          # which box produced it
        "exporter_last_seen_ts": 1718000000.0,  # epoch seconds of the reading
        "power_w_sample": 210.0,           # optional instantaneous watts
    }

If that dict is missing, malformed, lacks a real numeric reading, or is older than
the freshness window, the label is "sample". Sovereign / own-metal only: there is
no remote-trust path — a label string a caller hands us is NEVER trusted on its own.
"""
from __future__ import annotations

import time
from typing import Any, Mapping, Optional

# ---------------------------------------------------------------------------
# Doctrine constants. These are fixed honesty labels + the freshness floor.
# ---------------------------------------------------------------------------
DOCTRINE = "v11"
MEASURED = "measured"   # ONLY with a fresh, real on-box NVML exporter sample
SAMPLE = "sample"       # the honest default — off-box / no real meter / stale

# A real exporter reading older than this many seconds is treated as stale and
# DOWNGRADED to "sample". Doctrine: a measurement we cannot currently observe is
# not a measurement we may claim right now. 30.0s is the CANONICAL operator value,
# shared with szl_energy_operator.MAX_NVML_AGE_S, joule_billing.MAX_NVML_AGE_S, and
# the published kernel szl-energy-attest/energy_core FRESHNESS_WINDOW_S.
FRESHNESS_WINDOW_S = 30.0


def _coerce_float(value: Any) -> Optional[float]:
    """Best-effort numeric coercion. Returns None for anything non-finite/None."""
    if value is None or isinstance(value, bool):  # bool is an int — reject it
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):  # NaN / inf are not readings
        return None
    return f


def _is_fresh(last_seen_ts: Optional[float], now: float) -> bool:
    """True iff the reading timestamp is within the freshness window of ``now``.

    A reading from the FUTURE (clock skew / fabrication) is rejected as not fresh:
    we accept only ts in (now - window, now + small_skew].
    """
    if last_seen_ts is None:
        return False
    age = now - last_seen_ts
    # Reject far-future timestamps (allow tiny clock skew of 1s).
    if age < -1.0:
        return False
    return age <= FRESHNESS_WINDOW_S


def _real_measured_total(sample: Mapping[str, Any]) -> Optional[float]:
    """Extract the real cumulative joules reading, or None if absent/invalid."""
    return _coerce_float(sample.get("joules_measured_total"))


def is_real_fresh_sample(exporter_sample: Any, now: Optional[float] = None) -> bool:
    """Pure predicate: does ``exporter_sample`` prove a fresh real NVML reading?

    Requires ALL of:
      - a mapping
      - a finite numeric ``joules_measured_total`` (a real reading, not a flag)
      - an ``exporter_last_seen_ts`` within FRESHNESS_WINDOW_S of now
    """
    if not isinstance(exporter_sample, Mapping):
        return False
    total = _real_measured_total(exporter_sample)
    if total is None:
        return False
    now = time.time() if now is None else now
    ts = _coerce_float(exporter_sample.get("exporter_last_seen_ts"))
    return _is_fresh(ts, now)


def joules_label(exporter_sample: Any, now: Optional[float] = None) -> str:
    """Return "measured" ONLY with a fresh real exporter sample, else "sample".

    Pure + deterministic for a given (exporter_sample, now). NEVER trusts a bare
    boolean flag or a forwarded label string — only a real NVML reading + ts.
    """
    return MEASURED if is_real_fresh_sample(exporter_sample, now=now) else SAMPLE


def joules_evidence(exporter_sample: Any, now: Optional[float] = None) -> dict:
    """Self-verifying evidence dict.

    When (and only when) the label is "measured", returns the real reading fields::

        {joules_measured_total, exporter_node, exporter_last_seen_ts, power_w_sample}

    Otherwise returns an HONEST empty dict — never a fabricated number. The caller
    can attach this next to joules_label so the label is verifiable from the body.
    """
    if not is_real_fresh_sample(exporter_sample, now=now):
        return {}
    # Safe: is_real_fresh_sample guarantees a Mapping with a numeric total + ts.
    return {
        "joules_measured_total": _real_measured_total(exporter_sample),
        "exporter_node": exporter_sample.get("exporter_node"),
        "exporter_last_seen_ts": _coerce_float(exporter_sample.get("exporter_last_seen_ts")),
        "power_w_sample": _coerce_float(exporter_sample.get("power_w_sample")),
    }


def labeled_joules(exporter_sample: Any, now: Optional[float] = None) -> dict:
    """Convenience: one call returns BOTH the honest label and its evidence.

    Returns ``{"joules_label": <label>, "joules_evidence": <dict>}`` so a surface
    can splat it into a response body and the label is self-verifying.
    """
    return {
        "joules_label": joules_label(exporter_sample, now=now),
        "joules_evidence": joules_evidence(exporter_sample, now=now),
    }
