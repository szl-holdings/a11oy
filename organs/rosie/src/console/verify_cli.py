"""rosie.console.verify_cli — offline command-line DSSE receipt verifier.

The receipt verifier in :mod:`rosie.console.receipt_verifier` is the operator
console's interactive demo asset, but until now it could be reached solely
through the Gradio Space UI or by importing the library from Python. When the
hosted Space is unreachable (offline, rate-limited, or a 404 on a static
mirror), an operator had no command-line path to verify a receipt.

This CLI closes that gap. It reads a DSSE envelope from a file or stdin and
prints the verdict, using the same verification core that backs the UI. It
depends on the Python standard library alone and makes no network calls, so it
works fully offline.

Usage:
    python3 -m src.console.verify_cli RECEIPT.json
    cat RECEIPT.json | python3 -m src.console.verify_cli -
    python3 -m src.console.verify_cli --json RECEIPT.json   # machine-readable

Exit codes:
    0 — verdict VALID
    2 — verdict TAMPERED
    3 — verdict MALFORMED
    1 — usage / I/O error

SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import argparse
import json
import sys

from src.console.receipt_verifier import Verdict, verify_receipt_json

# Map each terminal verdict to a distinct process exit code so callers (CI,
# shell scripts) can branch without parsing stdout.
_EXIT_BY_VERDICT = {
    Verdict.VALID: 0,
    Verdict.TAMPERED: 2,
    Verdict.MALFORMED: 3,
}


def _read_input(source: str) -> str:
    """Return the envelope text from a path, or from stdin when source is '-'."""
    if source == "-":
        return sys.stdin.read()
    with open(source, encoding="utf-8") as handle:
        return handle.read()


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns the process exit code."""
    parser = argparse.ArgumentParser(
        prog="rosie-verify",
        description="Offline DSSE/PAE v1 receipt verifier (standard library, no network).",
    )
    parser.add_argument(
        "envelope",
        help="Path to a DSSE envelope JSON file, or '-' to read from stdin.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the result as a JSON object instead of human-readable text.",
    )
    args = parser.parse_args(argv)

    try:
        envelope_json = _read_input(args.envelope)
    except OSError as exc:
        print(f"error: could not read input: {exc}", file=sys.stderr)
        return 1

    result = verify_receipt_json(envelope_json)

    if args.json:
        print(json.dumps({
            "verdict": result.verdict.value,
            "ok": result.ok,
            "message": result.message,
            "keyid": result.keyid,
        }))
    else:
        print(f"{result.verdict.value.upper()}: {result.message}")
        if result.keyid:
            print(f"  keyid: {result.keyid}")

    return _EXIT_BY_VERDICT.get(result.verdict, 1)


if __name__ == "__main__":
    raise SystemExit(main())
