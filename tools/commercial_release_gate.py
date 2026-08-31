#!/usr/bin/env python3
"""commercial_release_gate.py — the commercial truth gate (round-10 master payload).

Wired into szl-holdings/a11oy under this name because tools/release_gate.py
already exists in this repository as the round-5 operational/audit release
gate (referenced by .github/workflows/release.yml). The two gates check
different things and both run. Gate logic is byte-identical to the round-10
payload's tools/release_gate.py; only this docstring, the usage line, and
the --apply demotion-note string were adapted.

Reads COMMERCIAL_LEDGER.yaml and claims-ledger.yaml from the repo root and
enforces the funding discipline (CANON sections 3 and 8):

  COMMERCIAL_LEDGER
    - every row with blocks_raise: true must carry state UNKNOWN with an
      auditable evidence trail (an explanation of why it is unknown /
      what would verify it, or attached artifacts). A raise-blocking row
      that is not UNKNOWN-with-evidence fails this gate. Note: VERIFIED
      with supporting evidence is the earned end state and passes; what
      fails is UNVERIFIED assertion, incomplete metadata, or a blocking
      row quietly marked non-blocking.
    - On a fresh scaffold all 24 rows are UNKNOWN with non-blocking
      guideline text only, so FIRST RUN FAILS. That is the intended
      Week 1 output: the company has 24 open questions, zero of them
      answered, and the gate says so.

  claims-ledger
    - every claim in state VERIFIED must have at least one evidence entry
      with status: supports. With --apply, claims that fail this test are
      auto-demoted to UNKNOWN in place (Zero-Bandaid Law), and the gate
      exits non-zero to mark that demotion happened. Without --apply the
      file is not touched and the gate fails.

Usage: python3 tools/commercial_release_gate.py [--root .] [--apply]
Exit 0 = all gates green, 1 = blocking findings, 2 = tool error.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

EXIT_GREEN = 0
EXIT_BLOCKING = 1
EXIT_ERROR = 2

MIN_SUPPORTING_EVIDENCE = 1


def _load_miniyaml():
    module_path = Path(__file__).resolve().parent / "szl_miniyaml.py"
    spec = importlib.util.spec_from_file_location("szl_miniyaml", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_commercial_ledger(doc: dict) -> list[str]:
    findings: list[str] = []
    rows = doc.get("rows")
    if not isinstance(rows, list) or not rows:
        return ["COMMERCIAL_LEDGER.yaml: no rows found (an empty ledger is an oversight)"]
    seen_ids: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            findings.append(f"row {index}: not a mapping")
            continue
        row_id = row.get("id", f"row-{index}")
        if row_id in seen_ids:
            findings.append(f"{row_id}: duplicate row id")
        seen_ids.add(row_id)
        state = row.get("state")
        blocks = row.get("blocks_raise")
        evidence = row.get("evidence")
        has_supporting = isinstance(evidence, list) and any(
            isinstance(e, dict) and e.get("status") == "supports" for e in evidence
        )
        if state not in {"VERIFIED", "UNKNOWN", "UNAVAILABLE"}:
            findings.append(f"{row_id}: state {state!r} is not a declared truth state")
        if blocks is True:
            if state == "UNKNOWN" and not row.get("why_unknown"):
                findings.append(
                    f"{row_id}: raise-blocking row is UNKNOWN without a why_unknown "
                    "explanation (UNKNOWN is an audited state, not a blank)"
                )
            if state == "UNAVAILABLE":
                findings.append(
                    f"{row_id}: raise-blocking row is UNAVAILABLE — retrieval blocker "
                    "must be resolved or re-scoped before a raise"
                )
            if state == "VERIFIED" and not has_supporting:
                findings.append(
                    f"{row_id}: raise-blocking row claims VERIFIED without supporting "
                    "evidence (Zero-Bandaid Law)"
                )
            if state in {"UNKNOWN", "UNAVAILABLE"}:
                findings.append(
                    f"{row_id}: raise blocked — state {state} "
                    f"(reason: {row.get('why_unknown', 'none recorded')})"
                )
        elif blocks is not False:
            findings.append(f"{row_id}: blocks_raise is not an explicit boolean")
    return findings


def check_claims_ledger(doc: dict) -> tuple[list[str], list[str]]:
    """Return (blocking findings, demotable claim ids)."""
    findings: list[str] = []
    demotable: list[str] = []
    claims = doc.get("claims")
    if not isinstance(claims, list) or not claims:
        return ["claims-ledger.yaml: no claims found (an empty ledger is an oversight)"], []
    for claim in claims:
        if not isinstance(claim, dict):
            findings.append("claims-ledger.yaml: a claim entry is not a mapping")
            continue
        cid = claim.get("id", "<no id>")
        state = claim.get("state")
        if state not in {"VERIFIED", "UNKNOWN", "UNAVAILABLE"}:
            findings.append(f"{cid}: state {state!r} is not a declared truth state")
            demotable.append(cid)
            continue
        evidence = claim.get("evidence") or []
        supporting = [
            e
            for e in evidence
            if isinstance(e, dict) and e.get("status") == "supports"
        ]
        if state == "VERIFIED" and len(supporting) < MIN_SUPPORTING_EVIDENCE:
            findings.append(
                f"{cid}: VERIFIED without supporting evidence — auto-demote to UNKNOWN"
            )
            demotable.append(cid)
    return findings, demotable


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".", help="repo root containing the ledgers")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="rewrite claims-ledger.yaml demoting unsupported VERIFIED claims to UNKNOWN",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    miniyaml = _load_miniyaml()
    exit_code = EXIT_GREEN
    demoted: list[str] = []

    commercial_path = root / "COMMERCIAL_LEDGER.yaml"
    if not commercial_path.is_file():
        print("release_gate ERROR: COMMERCIAL_LEDGER.yaml not found", file=sys.stderr)
        return EXIT_ERROR
    commercial = miniyaml.load(commercial_path.read_text(encoding="utf-8"))
    commercial_findings = check_commercial_ledger(commercial)
    unknown_blocks = sum(1 for f in commercial_findings if "raise blocked" in f)

    claims_path = root / "claims-ledger.yaml"
    if not claims_path.is_file():
        print("release_gate ERROR: claims-ledger.yaml not found", file=sys.stderr)
        return EXIT_ERROR
    claims_doc = miniyaml.load(claims_path.read_text(encoding="utf-8"))
    claims_findings, demotable = check_claims_ledger(claims_doc)
    if claims_findings and args.apply and demotable:
        ids = set(demotable)
        for claim in claims_doc["claims"]:
            if isinstance(claim, dict) and claim.get("id") in ids:
                claim["state"] = "UNKNOWN"
                note = claim.get("demotion_note")
                claim["demotion_note"] = (
                    (note + " | ") if note else ""
                ) + "auto-demoted by tools/commercial_release_gate.py (Zero-Bandaid Law)"
        claims_path.write_text(miniyaml.dump(claims_doc), encoding="utf-8")
        demoted = sorted(ids)

    if commercial_findings or claims_findings:
        exit_code = EXIT_BLOCKING

    print("release_gate report")
    print(f"  COMMERCIAL_LEDGER rows checked: {len(commercial.get('rows', []))}")
    print(f"  raise-blocking rows still UNKNOWN/UNAVAILABLE: {unknown_blocks}")
    for finding in commercial_findings:
        print(f"    {finding}")
    print(f"  claims checked: {len(claims_doc.get('claims', []))}")
    for finding in claims_findings:
        print(f"    {finding}")
    if demoted:
        print(f"  auto-demoted to UNKNOWN (file rewritten): {', '.join(demoted)}")
    if exit_code == EXIT_GREEN:
        print("release_gate: PASS — every raise-blocking row is VERIFIED with evidence")
    else:
        print("release_gate: FAIL — a raise today would rest on unverified claims")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
