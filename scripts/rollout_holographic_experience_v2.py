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
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STYLE = '<link rel="stylesheet" href="/assets/szl-holo-v2.css" data-szl-holo-asset="style-v2" />'
SCRIPT = '<script src="/assets/szl-holo-v2.js" defer data-szl-holo-asset="script-v2"></script>'
STYLE_MARKER = 'data-szl-holo-asset="style-v2"'
SCRIPT_MARKER = 'data-szl-holo-asset="script-v2"'
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
SOURCE_MANAGED = {
    "pages/integrations.html",
    "spaces/sda/index.html",
}


def source_managed(path: Path) -> bool:
    """Return True for files whose bytes are controlled by another source repository."""
    return path.relative_to(ROOT).as_posix() in SOURCE_MANAGED


def documents() -> list[Path]:
    found: set[Path] = set()
    for relative in EXACT:
        path = ROOT / relative
        if path.is_file() and not source_managed(path):
            found.add(path)
    for pattern in GLOBS:
        for path in ROOT.glob(pattern):
            if not path.is_file():
                continue
            parts = set(path.relative_to(ROOT).parts)
            if not parts.intersection(EXCLUDED_PARTS) and not source_managed(path):
                found.add(path)
    return sorted(found)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class _AssetBindingParser(HTMLParser):
    """Count markers and validate that each URL belongs to its marked element."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.style_markers = 0
        self.script_markers = 0
        self.style_bindings = 0
        self.script_bindings = 0

    def _observe(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name.lower(): value or "" for name, value in attrs}
        if tag.lower() == "link" and values.get("data-szl-holo-asset") == "style-v2":
            self.style_markers += 1
            if values.get("href") == "/assets/szl-holo-v2.css":
                self.style_bindings += 1
        if tag.lower() == "script" and values.get("data-szl-holo-asset") == "script-v2":
            self.script_markers += 1
            if values.get("src") == "/assets/szl-holo-v2.js":
                self.script_bindings += 1

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._observe(tag, attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._observe(tag, attrs)


def binding_state(text: str) -> _AssetBindingParser:
    parser = _AssetBindingParser()
    parser.feed(text)
    parser.close()
    return parser


def is_bound(text: str) -> bool:
    """Require each exact local URL on the same element as its unique marker."""
    state = binding_state(text)
    return (
        state.style_markers == state.style_bindings == 1
        and state.script_markers == state.script_bindings == 1
    )


def bind(path: Path) -> str:
    text = _read(path)
    relative = path.relative_to(ROOT).as_posix()
    if source_managed(path):
        return "source-managed"
    if "data-szl-holo-disabled" in text:
        return "opt-out"
    if "</head>" not in text.lower() or "</body>" not in text.lower():
        return "not-document"

    state = binding_state(text)
    style_count = state.style_markers
    script_count = state.script_markers
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
    if not is_bound(text):
        raise RuntimeError(f"invalid Holo-Constellation binding in {relative}")
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
    state["source_managed_documents"] = sorted(SOURCE_MANAGED)
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
        "source_managed": sorted(SOURCE_MANAGED),
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
