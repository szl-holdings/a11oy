#!/usr/bin/env python3
"""tools/raise_gate.py — commercial-ledger CI gate.

The round-10 innovation: commercial facts sit under the SAME CI law as
technical claims. Every UNKNOWN row sets blocks_raise=True and fails the
gate. No model, agent, or founder narrative may invent a row — the value
must come from a bank statement, a signed contract, or a named human.

Exit codes:
  0 = every commercial fact has a real value
  1 = one or more UNKNOWN rows (Series A claim blocked)
  2 = usage / parse error
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path.cwd()
    ledger = root / "ledgers" / "COMMERCIAL_LEDGER.yaml"
    if not ledger.is_file():
        print(f"raise_gate: {ledger} not found", file=sys.stderr)
        return 2

    data = yaml.safe_load(ledger.read_text())
    rows = data.get("rows", []) if isinstance(data, dict) else []
    unknown = [r for r in rows if r.get("value") is None]
    known = [r for r in rows if r.get("value") is not None]

    print(f"raise_gate: {len(rows)} commercial facts — {len(known)} known, {len(unknown)} UNKNOWN")
    if unknown:
        print(f"raise_gate: FAIL — {len(unknown)} UNKNOWN row(s), each blocks a Series A claim:")
        for r in unknown:
            print(f"  {r['id']}: {r['fact']} = UNKNOWN")
        print()
        print("No payload can fill these in. They come from bank statements,")
        print("signed contracts, named humans, and counsel — not from a model.")
        return 1
    print("raise_gate: PASS — all commercial facts have real values")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
