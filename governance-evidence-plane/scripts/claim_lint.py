#!/usr/bin/env python3
# Claim linter for evidence claims.
# Fails on novelty overclaim and required field omissions.

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


FORBIDDEN_PATTERNS = [
    r"\bfirst\b",
    r"\bnew\b.*\balgorithm\b",
    r"\binvent(?:ed|s|ing)\b",
    r"\bsuperior\b",
    rf"\b{'b'}reakthrough\b",
]

REQUIRED = {"claim_id", "model", "policy", "evidence_schema", "test_obligation", "expires_at_utc"}


def parse_claim(text: str) -> dict:
    if text.lstrip().startswith("{"):
        return json.loads(text)
    # Very small fallback for JSON-like claim text; require json for deterministic behavior.
    raise ValueError("claim_lint.py expects JSON claim format in this bootstrap package")


def lint(claim: dict) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED - set(claim)
    if missing:
        errors.append(f"missing required keys: {', '.join(sorted(missing))}")
    text = json.dumps(claim).lower()
    for pat in FORBIDDEN_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            errors.append(f"novelty overclaim pattern: {pat}")
    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python claim_lint.py <claim.json>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8")
    claim = parse_claim(text)
    errors = lint(claim)
    if errors:
        print("claim_bad:")
        for msg in errors:
            print(f" - {msg}")
        return 1
    print(f"claim_ok: {claim.get('claim_id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
