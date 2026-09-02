#!/usr/bin/env python3
"""Bind A11oy Holo-Constellation v2 to source-owned HTML surfaces.

This controller is local, deterministic, and idempotent. It adds only the two
first-party assets required by the shared holographic experience. It does not
change APIs, policy, receipt verification, claims, model behavior, DNS, or
third-party configuration.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STYLE = '<link rel="stylesheet" href="/assets/szl-holo-v2.css" data-szl-holo-asset="style-v2" />'
SCRIPT = '<script src="/assets/szl-holo-v2.js" defer data-szl-holo-asset="script-v2"></script>'
STATE = ROOT / "docs" / "holographic-experience-v2" / "rollout-state.json"

EXACT = (
    "a11oy_landing.html",
    "govern_showcase.html",
    "cathedral_genius.html",
    "console/index.html",
)
GLOBS = (
    "pages/*.html",
    "web/*.html",
    "console/static/viz/**/index.html",
    "spaces/*/index.html",
)
EXCLUDED_PARTS = {
    ".git",
    "node_modules",
    "vendor",
    "archive",
    "archives",
    "fixtures",
    "coverage",
    "dist",
}


def documents() -> list[Path]:
    found: set[Path] = set()
    for relative in EXACT:
        path = ROOT / relative
        if path.is_file():
            found.add(path)
    for pattern in GLOBS:
        for path in ROOT.glob(pattern):
            if not path.is_file():
                continue
            parts = set(path.relative_to(ROOT).parts)
            if not parts.intersection(EXCLUDED_PARTS):
                found.add(path)
    return sorted(found)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def is_bound(text: str) -> bool:
    return STYLE in text and SCRIPT in text


def bind(path: Path) -> str:
    text = _read(path)
    relative = path.relative_to(ROOT).as_posix()
    if "data-szl-holo-disabled" in text:
        return "opt-out"
    if "</head>" not in text.lower() or "</body>" not in text.lower():
        return "not-document"

    style_count = text.count('data-szl-holo-asset="style-v2"')
    script_count = text.count('data-szl-holo-asset="script-v2"')
    if style_count > 1 or script_count > 1:
        raise RuntimeError(f"duplicate Holo-Constellation marker in {relative}")

    changed = False
    if style_count == 0:
        offset = text.lower().rfind("</head>")
        text = text[:offset] + "  " + STYLE + "\n" + text[offset:]
        changed = True
    if script_count == 0:
        offset = text.lower().rfind("</body>")
        text = text[:offset] + "  " + SCRIPT + "\n" + text[offset:]
        changed = True

    if changed:
        path.write_text(text, encoding="utf-8", newline="\n")
        return "bound"
    return "present"


def update_state(rows: list[dict[str, str]]) -> None:
    state = json.loads(STATE.read_text(encoding="utf-8"))
    state["state"] = "ROLLED_OUT"
    state["bindings"] = [
        row["path"]
        for row in rows
        if row["result"] in {"bound", "present"}
    ]
    state["examined_documents"] = len(rows)
    state["bound_documents"] = len(state["bindings"])
    state["opt_out_documents"] = [
        row["path"] for row in rows if row["result"] == "opt-out"
    ]
    STATE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(*, check: bool) -> dict[str, object]:
    rows: list[dict[str, str]] = []
    for path in documents():
        relative = path.relative_to(ROOT).as_posix()
        if check:
            result = "present" if is_bound(_read(path)) else "missing"
        else:
            result = bind(path)
        rows.append({"path": relative, "result": result})

    if not rows:
        raise RuntimeError("no source-owned HTML surfaces were discovered")

    root = next((row for row in rows if row["path"] == "a11oy_landing.html"), None)
    if root is None or root["result"] in {"missing", "not-document", "opt-out"}:
        raise RuntimeError("a11oy_landing.html is not bound to Holo-Constellation v2")

    missing = [row["path"] for row in rows if row["result"] == "missing"]
    if check and missing:
        raise RuntimeError("missing Holo-Constellation v2 binding: " + ", ".join(missing))

    if not check:
        update_state(rows)

    return {
        "schema": "szl.holographic-experience-rollout/v2",
        "mode": "CHECK" if check else "APPLY",
        "examined": len(rows),
        "changed": sum(row["result"] == "bound" for row in rows),
        "present": sum(row["result"] == "present" for row in rows),
        "opt_out": sum(row["result"] == "opt-out" for row in rows),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    report = run(check=args.check)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
