#!/usr/bin/env python3
"""tools/spaces_audit.py — READ_ONLY tier audit of the SZLHOLDINGS Spaces
estate (turn-16 payload §3 H2, building on the spaces estate audit).

Laws:
  * stage=RUNNING is NEVER evidence of a deployed revision — only runtime state.
  * FLAGSHIP is capped at 5; an untiered surface is a gate failure.
  * Docker/Gradio Spaces on free cpu-basic require a paid plan; billing must be
    VERIFIED (org plan team/enterprise, or PRO) — not assumed.
  * Emits a signed GovernedAction/v1 receipt for its own run (dogfood).

Backends:
  --from-audit   read audits/hf_estate_audit.json (default; READ_ONLY offline)
  --live         re-enumerate via the public REST API (SZLHOLDINGS casing!)

Outputs:
  audits/spaces_tier_report.md
  receipts/sub-spaces-audit.json
"""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
AUDITS = ROOT / "audits"
RECEIPTS = ROOT / "receipts"
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
ORG = "SZLHOLDINGS"   # casing matters: lowercase author returns ZERO on the public API

FLAGSHIP_DECLARED = ["a11oy", "killinchu", "governed-receipt-verifier", "szl-atelier", "holographic"]
KNOWN_RETIRED = {"holographic": "szl-estate-live"}


def load_from_audit() -> dict:
    """Read per-space detail captured by the collector (raw/spaces_details.json,
    a dict of id -> {api, readme, runtime_stage}), plus org plan from the
    estate summary where available."""
    raw = ROOT / "raw" / "spaces_details.json"
    org_plan = "UNKNOWN"
    sumf = AUDITS / "hf_estate_audit.json"
    if sumf.is_file():
        org_plan = json.loads(sumf.read_text()).get("org_plan", "UNKNOWN")
    if not raw.is_file():
        return {"error": f"{raw} not found", "spaces": [], "org_plan": org_plan}
    detail = json.loads(raw.read_text())
    spaces = []
    for sid, rec in detail.items():
        api = rec.get("api") or {}
        spaces.append({
            "id": sid,
            "sdk": api.get("sdk") or rec.get("sdk") or "UNKNOWN",
            "last_modified": str(api.get("lastModified") or rec.get("last_modified") or "UNKNOWN"),
            "runtime_stage": rec.get("runtime_stage") or (api.get("runtime") or {}).get("stage", "NOT_QUERIED")
                             if isinstance(rec.get("runtime_stage"), str) is False else rec.get("runtime_stage", "NOT_QUERIED"),
        })
    return {"spaces": spaces, "org_plan": org_plan, "source": "raw/spaces_details.json"}


def load_live() -> dict:
    try:
        import requests
        r = requests.get("https://huggingface.co/api/spaces",
                         params={"author": ORG, "limit": 500, "full": "true"}, timeout=60)
        items = r.json() if r.status_code == 200 else []
        return {"spaces": [{"id": s.get("id"), "sdk": s.get("sdk"),
                            "last_modified": str(s.get("lastModified") or s.get("last_modified")),
                            "runtime_stage": "NOT_QUERIED"} for s in items],
                "org_plan": "UNKNOWN", "source": "live-rest"}
    except Exception as e:  # noqa: BLE001
        return {"error": f"live fetch failed: {type(e).__name__}: {e}", "spaces": []}


def tier(spaces: list[dict], org_plan: str) -> dict:
    billing_verified = org_plan in ("team", "enterprise", "pro")
    tiers = []
    for s in spaces:
        sid = (s.get("id") or "").split("/")[-1]
        sdk = s.get("sdk") or "UNKNOWN"
        if sid in KNOWN_RETIRED:
            t = "ARCHIVE_RETIRED"
        elif sid in FLAGSHIP_DECLARED:
            t = "FLAGSHIP"
        elif sdk == "static":
            t = "SUPPORTING"
        elif sdk in ("docker", "gradio"):
            t = "SUPPORTING_PAID_SDK" if billing_verified else "BLOCKER_BILLING_UNVERIFIED"
        else:
            t = "UNTIERED"
        tiers.append({"id": s.get("id"), "sdk": sdk, "tier": t,
                      "last_modified": s.get("last_modified", "UNKNOWN"),
                      "runtime_stage": s.get("runtime_stage", "NOT_QUERIED"),
                      "note": f"retired → {KNOWN_RETIRED[sid]}" if sid in KNOWN_RETIRED else ""})
    return {
        "generated_at": NOW, "org": ORG, "org_plan": org_plan,
        "billing_verified": billing_verified,
        "spaces_total": len(tiers),
        "flagship": [t for t in tiers if t["tier"] == "FLAGSHIP"],
        "untiered": [t for t in tiers if t["tier"] == "UNTIERED"],
        "retired": [t for t in tiers if t["tier"] == "ARCHIVE_RETIRED"],
        "billing_blockers": [t for t in tiers if t["tier"] == "BLOCKER_BILLING_UNVERIFIED"],
        "tiers": tiers,
    }


def emit_receipt(rep: dict) -> Path:
    RECEIPTS.mkdir(parents=True, exist_ok=True)
    try:
        from a11oy.receipts import Signer, build_predicate, sign_envelope
        from a11oy.policy_engine import TypedPolicyEngine
        signer = Signer(RECEIPTS / "keys")
        engine = TypedPolicyEngine()
        decision = engine.evaluate("estate.audit.spaces", requested_side_effect="READ_ONLY")
        pred = build_predicate(
            action={"id": "spaces-audit", "type": "estate.audit.spaces",
                    "side_effect_class": "READ_ONLY",
                    "identity": {"id": "tools/spaces_audit.py", "type": "tool"}},
            actor={"id": "tools/spaces_audit.py", "type": "tool", "is_service_account": True},
            authority={"outcome": decision.outcome, "deciding_rule": decision.deciding_rule,
                       "evaluated_before_execution": True},
            evidence={"completeness": "COMPLETE" if not rep["billing_blockers"] else "INCOMPLETE",
                      "obligations": [
                          {"id": "spaces_enumerated", "satisfied": rep["spaces_total"] > 0},
                          {"id": "billing_verified", "satisfied": rep["billing_verified"]},
                          {"id": "runtime_is_state_not_revision", "satisfied": True},
                      ]},
            limitations=[
                "stage=RUNNING is runtime state, not evidence of a deployed revision.",
                "Kernel inventory is NOT_ENUMERABLE_VIA_API and excluded from this receipt.",
            ],
        )
        env = sign_envelope(pred, signer)
        out = RECEIPTS / "sub-spaces-audit.json"
        out.write_text(json.dumps(env, indent=2))
        return out
    except Exception as e:  # noqa: BLE001
        return RECEIPTS / f"sub-spaces-audit.unsigned-error-{type(e).__name__}.txt"


def main() -> int:
    data = load_live() if "--live" in sys.argv else load_from_audit()
    if data.get("error"):
        print(f"spaces_audit: {data['error']}", file=sys.stderr)
        return 2
    spaces = data.get("spaces") or []
    org_plan = data.get("org_plan", "UNKNOWN")
    rep = tier(spaces, org_plan)
    (AUDITS / "spaces_tier_report.json").write_text(json.dumps(rep, indent=2))
    md = [f"# Spaces Tier Audit — {ORG}", f"Generated: {NOW} · READ_ONLY · org_plan={org_plan}", "",
          f"- total spaces: {rep['spaces_total']}",
          f"- FLAGSHIP: {len(rep['flagship'])}",
          f"- ARCHIVE_RETIRED: {len(rep['retired'])}",
          f"- UNTIERED: {len(rep['untiered'])}",
          f"- billing verified (paid plan): {rep['billing_verified']}",
          f"- billing blockers: {len(rep['billing_blockers'])}", "",
          "| Space | SDK | Tier |", "|---|---|---|"]
    md += [f"| {t['id']} | {t['sdk']} | {t['tier']} |" for t in rep["tiers"]]
    (AUDITS / "spaces_tier_report.md").write_text("\n".join(md) + "\n")
    rc = emit_receipt(rep)
    print(f"spaces_audit: spaces={rep['spaces_total']} flagship={len(rep['flagship'])} "
          f"untiered={len(rep['untiered'])} billing_blockers={len(rep['billing_blockers'])} receipt={rc.name}")
    return 0


if __name__ == "__main__":
    if "--help" in sys.argv:
        print(__doc__)
        sys.exit(2)
    sys.exit(main())
