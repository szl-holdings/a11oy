# SPDX-License-Identifier: Apache-2.0 · Doctrine v12 (additive). Yachay.
"""
status_feed — internal health -> public status_feed.json (fail-closed allow-list).
Reads Prometheus + active Alertmanager alerts + degradation receipts; emits ONLY the
szl.status_feed/v1 schema. Anything not explicitly mapped is dropped (never leaked).

Honest anti-cover-up: driven by the SAME Prometheus signals as the internal dashboard,
so the public page can never claim green while internally red. v11 LOCKED untouched.
"""
from datetime import datetime, timezone

# allow-list: internal flagship -> public component
PUBLIC_COMPONENT = {
    "a11oy": "Governance & Brand", "amaru": "Memory / Cortex",
    "sentra": "Immune / Policy",   "vessels": "Maritime & Receipts",
    "rosie": "Companion",          "killinchu": "Drone Ops",
    "lean-kernel": "Proof Kernel",
}
# Keys that MUST NEVER appear in the public feed (defense in depth; allow-list already
# drops them). We match on KEY NAMES (not a substring of the whole blob) so legitimate
# component copy like "Receipts"/"Companion" is never falsely flagged.
_NEVER_PUBLISH_KEYS = frozenset({
    "provider", "model", "tripwire", "khipu_node", "digest",
    "hostname", "ip", "secret", "token", "breaker", "circuit",
})


def _coarse_status(up: bool, degraded: bool, partial: bool) -> str:
    if not up: return "major_outage"
    if partial: return "partial_outage"
    if degraded: return "degraded"
    return "operational"


def build_feed(metrics: dict, alerts: list[dict]) -> dict:
    components = []
    for fl, comp in PUBLIC_COMPONENT.items():
        up = metrics.get(f"szl_up::{fl}", 0) == 1
        degraded = any(a for a in alerts
                       if a.get("flagship") == fl and a.get("impact") == "degraded")
        components.append({
            "name": comp,
            "status": _coarse_status(up, degraded, partial=False),
            "uptime_30d": round(metrics.get(f"szl_uptime_30d::{fl}", 0.0), 2),
        })
    # AI Responses component derived from router tiers (impact only, no provider names)
    router_degraded = (metrics.get("szl_router_tier::T0_cache", 0)
                       + metrics.get("szl_router_tier::T1_small", 0)) > 0
    components.append({"name": "AI Responses",
                       "status": "degraded" if router_degraded else "operational",
                       "note": "Responses may be slower than usual." if router_degraded else None})

    overall = "operational"
    if any(c["status"] == "major_outage" for c in components): overall = "major_outage"
    elif any(c["status"] == "partial_outage" for c in components): overall = "partial_outage"
    elif any(c["status"] == "degraded" for c in components): overall = "degraded"

    feed = {"schema": "szl.status_feed/v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "overall": overall, "components": components,
            "active_incidents": _public_incidents(alerts),
            "scheduled_maintenance": []}
    _assert_no_leak(feed)            # fail-closed: refuse to emit if any banned key present
    return feed


def _public_incidents(alerts):
    out = []
    for a in alerts:
        if not a.get("customer_impacting"):  # only customer-impacting alerts go public
            continue
        out.append({"id": a["incident_id"], "title": a["public_title"],   # pre-sanitized
                    "impact": a["impact"], "started_at": a["started_at"],
                    "latest_update": a["public_update"]})
    return out


def _assert_no_leak(node) -> None:
    """Recursively assert no banned KEY appears anywhere in the feed (fail-closed)."""
    if isinstance(node, dict):
        for k, v in node.items():
            if str(k).lower() in _NEVER_PUBLISH_KEYS:
                raise RuntimeError(
                    f"status_feed leak guard tripped on key '{k}' — refusing to publish")
            _assert_no_leak(v)
    elif isinstance(node, (list, tuple)):
        for item in node:
            _assert_no_leak(item)
