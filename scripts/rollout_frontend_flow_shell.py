#!/usr/bin/env python3
"""Inject the local SZL Flow Shell into the live A11oy HTML surfaces.

The patch is deliberately source-native and idempotent. It changes no API,
receipt, signer, policy, or DNS behavior. Assets live under console/assets,
which the production Dockerfile already copies wholesale to /app/static and
serves at /assets/*.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STYLE = '<link rel="stylesheet" href="/assets/szl-flow.css" data-szl-flow-asset="style" />'
SCRIPT = '<script src="/assets/szl-flow.js" defer data-szl-flow-asset="script"></script>'
STATE = ROOT / "docs" / "frontend-flow-shell-state.json"

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
EXCLUDE_PARTS = {"node_modules", "vendor", "archive", "archives", "fixtures", ".git"}


def candidates() -> list[Path]:
    found: set[Path] = set()
    for rel in EXACT:
        path = ROOT / rel
        if path.is_file():
            found.add(path)
    for pattern in GLOBS:
        for path in ROOT.glob(pattern):
            if path.is_file() and not (set(path.relative_to(ROOT).parts) & EXCLUDE_PARTS):
                found.add(path)
    return sorted(found)


def inject(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if "data-szl-flow-opt-out" in text:
        return "opt-out"
    if "</head>" not in text.lower() or "</body>" not in text.lower():
        return "not-document"

    style_count = text.count('data-szl-flow-asset="style"')
    script_count = text.count('data-szl-flow-asset="script"')
    if style_count > 1 or script_count > 1:
        raise RuntimeError(f"duplicate flow-shell marker in {path.relative_to(ROOT)}")

    changed = False
    if style_count == 0:
        index = text.lower().rfind("</head>")
        text = text[:index] + "  " + STYLE + "\n" + text[index:]
        changed = True
    if script_count == 0:
        index = text.lower().rfind("</body>")
        text = text[:index] + "  " + SCRIPT + "\n" + text[index:]
        changed = True

    if changed:
        path.write_text(text, encoding="utf-8", newline="\n")
        return "injected"
    return "present"


def update_state(changed: list[str], examined: int) -> None:
    payload = json.loads(STATE.read_text(encoding="utf-8"))
    payload["state"] = "ROLLED_OUT"
    payload["examined_documents"] = examined
    payload["injected_documents"] = changed
    STATE.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify that every candidate is already injected")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    rows = []
    changed: list[str] = []
    for path in candidates():
        rel = path.relative_to(ROOT).as_posix()
        result = inject(path) if not args.check else (
            "present" if STYLE in path.read_text(encoding="utf-8") and SCRIPT in path.read_text(encoding="utf-8") else "missing"
        )
        rows.append({"path": rel, "result": result})
        if result == "injected":
            changed.append(rel)

    if not rows:
        raise SystemExit("no live HTML candidates were found")
    root_row = next((row for row in rows if row["path"] == "a11oy_landing.html"), None)
    if not root_row or root_row["result"] in {"missing", "not-document", "opt-out"}:
        raise SystemExit("the product front door is not flow-shell bound")
    if args.check and any(row["result"] == "missing" for row in rows):
        missing = [row["path"] for row in rows if row["result"] == "missing"]
        raise SystemExit("missing flow shell: " + ", ".join(missing))
    if not args.check:
        update_state(changed, len(rows))

    report = {
        "schema": "szl.frontend-flow-shell-rollout/v1",
        "mode": "CHECK" if args.check else "APPLY",
        "examined": len(rows),
        "changed": len(changed),
        "rows": rows,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
