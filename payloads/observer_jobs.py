#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Observer and geo-command jobs for a11oy + killinchu surfaces.

These are job rails, not SKUs and not extra organs.
Estate observer domains (a11oy surface):
  coverage, connectivity, cognitive, executive, impact
Field geo-command jobs (killinchu surface):
  locate, correlate, sense, evidence, hold
Public field engage_admissible stays 0. No public effector.
"""
from __future__ import annotations

from typing import Any

OBSERVER_DOMAINS = (
    "coverage",
    "connectivity",
    "cognitive",
    "executive",
    "impact",
)

GEO_JOBS = (
    "locate",
    "correlate",
    "sense",
    "evidence",
    "hold",
)

_COVERAGE = ("inventory", "snapshot", "census", "space count", "model count", "dataset")
_CONNECT = ("connect", "bind", "mirror", "twin", "github", "hugging face", "align")
_COGNITIVE = ("measure", "yuyay", "axis", "lambda", "conjecture", "vector", "pack")
_EXEC = ("admit", "deny", "policy", "gate", "receipt", "merge", "cosign", "tally")
_IMPACT = ("field", "track", "observe", "evidence", "impact", "killinchu")

_LOCATE = ("locate", "where", "geo", "lat", "lon", "coordinate", "place")
_CORRELATE = ("correlate", "join", "cross", "match fixture", "same track")
_EVIDENCE = ("evidence", "receipt", "witness", "proof origin")
_HOLD = ("hold", "do not engage", "stand down", "sense only")


def route_observer(intent: str) -> str:
    t = intent.lower()
    hits = {
        "coverage": sum(1 for w in _COVERAGE if w in t),
        "connectivity": sum(1 for w in _CONNECT if w in t),
        "cognitive": sum(1 for w in _COGNITIVE if w in t),
        "executive": sum(1 for w in _EXEC if w in t),
        "impact": sum(1 for w in _IMPACT if w in t),
    }
    best = max(hits.values())
    if best == 0:
        return "executive"
    for domain in OBSERVER_DOMAINS:
        if hits[domain] == best:
            return domain
    return "executive"


def route_geo(intent: str) -> str:
    t = intent.lower()
    if any(w in t for w in _HOLD) or "engage" in t:
        return "hold"
    if any(w in t for w in _LOCATE):
        return "locate"
    if any(w in t for w in _CORRELATE):
        return "correlate"
    if any(w in t for w in _EVIDENCE):
        return "evidence"
    return "sense"


def attach(*, intent: str, surface: str, engage_admissible: float) -> dict[str, Any]:
    surface = surface if surface in {"estate", "field"} else "estate"
    body: dict[str, Any] = {
        "surface": surface,
        "observer_domain": route_observer(intent),
        "observer_domains": list(OBSERVER_DOMAINS),
        "sku": False,
        "organ": "a11oy" if surface == "estate" else "killinchu",
        "jev_allow_alone": False,
    }
    if surface == "field":
        body["geo_job"] = route_geo(intent)
        body["geo_jobs"] = list(GEO_JOBS)
        body["engage_admissible"] = 0.0
        body["public_effector"] = False
        _ = engage_admissible
    return body
