#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

USES = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)\s*(?:#.*)?$")
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def verify(root: Path) -> dict[str, object]:
    findings: list[dict[str, object]] = []
    action_count = 0
    for path in sorted(root.rglob("*.yml")) + sorted(root.rglob("*.yaml")):
        if not path.is_file() or path.is_symlink():
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            match = USES.match(line)
            if not match:
                continue
            reference = match.group(1)
            # Local actions are source-bound by the repository checkout.
            if reference.startswith("./"):
                continue
            action_count += 1
            if "@" not in reference:
                findings.append({"path": str(path), "line": line_no, "reference": reference, "reason": "MISSING_REF"})
                continue
            _, ref = reference.rsplit("@", 1)
            if not FULL_SHA.fullmatch(ref):
                findings.append({"path": str(path), "line": line_no, "reference": reference, "reason": "NOT_FULL_COMMIT_SHA"})
    return {
        "schema": "szl.github-action-pin-verification/v1",
        "status": "PASS" if not findings else "FAIL",
        "action_reference_count": action_count,
        "finding_count": len(findings),
        "findings": findings,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    report = verify(args.root.resolve())
    text = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
