#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

SPEC_PATH = Path(__file__).resolve().parents[1] / "config" / "a11oy-frontdoor" / "PATCH_SPEC.json"


class PatchError(RuntimeError):
    pass


def load_spec() -> dict:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def apply_text(text: str, spec: dict) -> tuple[str, list[dict]]:
    results: list[dict] = []
    for item in spec["replacements"]:
        old, new, name = item["old"], item["new"], item["name"]
        old_count = text.count(old)
        new_count = text.count(new)
        if new_count == 1:
            results.append({"name": name, "state": "ALREADY_APPLIED"})
        elif old_count == 1:
            text = text.replace(old, new, 1)
            results.append({"name": name, "state": "APPLIED"})
        else:
            raise PatchError(
                f"{name}: expected one old anchor or one new anchor; "
                f"old={old_count} new={new_count}"
            )
    return text, results


def validate_truth(text: str) -> list[str]:
    errors: list[str] = []
    banned = [
        "Every answer arrives with a signed receipt",
        "every governed decision is sealed into a signed, hash-chained receipt",
        "signed receipts travel the vessels",
        ">Signed receipts</div>",
        "const pass = v >= 0.90",
        "pass?'≥ floor':'below floor'",
        "snapshot observed 2026-07-16",
        '<div class="estate-cell"><b>15</b><span>Models</span></div>',
        '<div class="estate-cell"><b>24</b><span>Datasets</span></div>',
        '<div class="estate-cell"><b>26</b><span>Spaces</span></div>',
        '<div class="estate-cell"><b>22</b><span>Collections</span></div>',
    ]
    for token in banned:
        if token in text:
            errors.append("banned token remains: " + token)

    required = [
        "proves its receipt state",
        "signer state",
        "verification passes",
        'grayChip(relation + " · CONJECTURE")',
        "Receipt records · signer state separate",
        "min-height:44px",
        "overflow-wrap:anywhere",
        "The front door no longer hardcodes organization totals",
    ]
    for token in required:
        if token not in text:
            errors.append("required token missing: " + token)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    spec = load_spec()
    original = args.path.read_text(encoding="utf-8")
    try:
        patched, results = apply_text(original, spec)
    except PatchError as exc:
        print(json.dumps({"status": "BLOCKED_DRIFT", "error": str(exc)}, indent=2))
        return 2

    errors = validate_truth(patched)
    if errors:
        print(json.dumps({"status": "FAIL", "errors": errors, "results": results}, indent=2))
        return 1

    pending = [item["name"] for item in results if item["state"] == "APPLIED"]
    if args.check and pending:
        print(
            json.dumps(
                {
                    "status": "FAIL_UNAPPLIED",
                    "target": str(args.path),
                    "pending_replacements": pending,
                    "results": results,
                },
                indent=2,
            )
        )
        return 1

    if not args.check:
        out = args.output or args.path
        out.write_text(patched, encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "PASS",
                "target": str(args.path),
                "output": str(args.output or args.path),
                "results": results,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
