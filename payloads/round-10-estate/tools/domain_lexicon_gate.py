#!/usr/bin/env python3
"""tools/domain_lexicon_gate.py — CI gate over the domain parity audit.

Fails (exit 1) if any PUBLIC surface (a-11-oy.com / a11oy.net) carries a
banned canonical-lexicon term. Runs the live audit first so the gate always
reflects current production copy — not a stale snapshot.

Exit 0 only when both domains are lexicon-clean.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "audits" / "domain_parity_report.json"


def main() -> int:
    # Always re-run the live audit so the gate reflects production NOW.
    subprocess.run([sys.executable, str(ROOT / "tools" / "domain_parity_audit.py"), "--report"],
                   capture_output=True, text=True, cwd=ROOT)
    if not REPORT.is_file():
        print("domain_lexicon_gate: audit report missing", file=sys.stderr)
        return 2
    data = json.loads(REPORT.read_text())
    findings = data.get("lexicon_findings", [])
    reachable = sum(1 for d in data.get("domains", []) if d.get("reachable"))
    print(f"domain_lexicon_gate: reachable={reachable}/2, lexicon_findings={len(findings)}")
    if findings:
        print("domain_lexicon_gate: FAIL — banned canonical-lexicon terms on public surfaces:")
        for f in findings:
            print(f"  {f['domain']}{f['route']}: {', '.join(f['terms'])}")
        print("Fix the copy, re-run. Public surfaces must be lexicon-clean.")
        return 1
    print("domain_lexicon_gate: PASS — both public domains lexicon-clean")
    return 0


if __name__ == "__main__":
    sys.exit(main() if not ("--help" in sys.argv) else (print(__doc__) or 2))
