#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Compare the web package's workspace dependencies with tracked package manifests."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB_PACKAGE = ROOT / "web" / "package.json"
OUTPUT = ROOT / "audit" / "web-workspace-dependency-gap.json"
IGNORED_PARTS = {"node_modules", ".git", ".lake", "dist", "build"}


def main() -> int:
    manifests: dict[str, str] = {}
    for path in ROOT.rglob("package.json"):
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        try:
            package = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        name = package.get("name")
        if isinstance(name, str):
            manifests[name] = path.relative_to(ROOT).as_posix()

    web = json.loads(WEB_PACKAGE.read_text(encoding="utf-8"))
    requested: dict[str, str] = {}
    for section in ("dependencies", "devDependencies", "optionalDependencies"):
        for name, spec in web.get(section, {}).items():
            if isinstance(spec, str) and spec.startswith("workspace:"):
                requested[name] = section
    resolved = {
        name: {"section": section, "manifest": manifests[name]}
        for name, section in requested.items()
        if name in manifests
    }
    missing = {
        name: {"section": section, "reason": "no tracked package manifest"}
        for name, section in requested.items()
        if name not in manifests
    }
    result = {
        "generated_at": dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "label": "FAILED" if missing else "MEASURED",
        "scope": "web/package.json workspace protocol dependencies",
        "requested": len(requested),
        "resolved": len(resolved),
        "missing": len(missing),
        "resolved_packages": resolved,
        "missing_packages": missing,
        "conclusion": (
            "The broader web package cannot be installed from this repository alone."
            if missing
            else "All web workspace dependencies have tracked manifests."
        ),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2))
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
