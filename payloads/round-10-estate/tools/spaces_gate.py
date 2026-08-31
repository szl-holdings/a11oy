#!/usr/bin/env python3
"""tools/spaces_gate.py — CI gate over the spaces tier audit.

Fails (exit 1) if ANY of:
  * an UNTIERED space exists
  * a BLOCKER_BILLING_UNVERIFIED space exists (Docker/Gradio with unverified billing)
  * a KNOWN_RETIRED space is still listed as a flagship (org-card drift)
  * flagship count exceeds the 5-cap
Exit 0 only when the estate is fully tiered, within cap, and billing-verified.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "audits" / "spaces_tier_report.json"
FLAGSHIP_CAP = 5
FLAGSHIP_DECLARED = {"a11oy", "killinchu", "governed-receipt-verifier", "szl-atelier", "holographic"}


def main() -> int:
    if not REPORT.is_file():
        print(f"spaces_gate: {REPORT} not found — run tools/spaces_audit.py first", file=sys.stderr)
        return 2
    rep = json.loads(REPORT.read_text())
    failures: list[str] = []

    if rep["untiered"]:
        failures.append(f"{len(rep['untiered'])} UNTIERED spaces: "
                        + ", ".join(t["id"] for t in rep["untiered"][:6]))
    if rep["billing_blockers"]:
        failures.append(f"{len(rep['billing_blockers'])} Docker/Gradio spaces with UNVERIFIED billing: "
                        + ", ".join(t["id"] for t in rep["billing_blockers"][:6]))
    retired_ids = {t["id"].split("/")[-1] for t in rep["retired"]}
    drift = retired_ids & FLAGSHIP_DECLARED
    if drift:
        failures.append(f"org-card drift: retired space(s) still in flagship list: {', '.join(sorted(drift))}")
    if len(rep["flagship"]) > FLAGSHIP_CAP:
        failures.append(f"flagship count {len(rep['flagship'])} exceeds cap {FLAGSHIP_CAP}")

    print(f"spaces_gate: {rep['spaces_total']} spaces, flagship={len(rep['flagship'])}, "
          f"billing_verified={rep['billing_verified']}")
    if failures:
        print("spaces_gate: FAIL —")
        for f in failures:
            print(f"  {f}")
        return 1
    print("spaces_gate: PASS — estate fully tiered, billing verified, no org-card drift")
    return 0


if __name__ == "__main__":
    sys.exit(main() if not ("--help" in sys.argv) else (print(__doc__) or 2))
