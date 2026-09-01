#!/usr/bin/env python3
"""Repair the product Flow Shell boundary without mutating canonical shared sources."""
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROLLOUT = ROOT / "scripts" / "rollout_frontend_flow_shell.py"
TEST = ROOT / "tests" / "test_product_flow_source_boundary.py"
STYLE = '<link rel="stylesheet" href="/assets/szl-flow.css" data-szl-flow-asset="style" />'
SCRIPT = '<script src="/assets/szl-flow.js" defer data-szl-flow-asset="script"></script>'


def source_controlled_documents() -> list[Path]:
    paths = {ROOT / "pages" / "integrations.html"}
    paths.update(ROOT.glob("spaces/*/index.html"))
    return sorted(path for path in paths if path.is_file())


def strip_product_only_tags(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for tag in (STYLE, SCRIPT):
        text = re.sub(
            rf"^[ \t]*{re.escape(tag)}[ \t]*\r?\n?",
            "",
            text,
            flags=re.MULTILINE,
        )
    if 'data-szl-flow-asset="style"' in text or 'data-szl-flow-asset="script"' in text:
        raise SystemExit(f"unrecognized Flow Shell marker remains in {path.relative_to(ROOT)}")
    path.write_text(text, encoding="utf-8", newline="\n")


def write_rollout() -> None:
    ROLLOUT.write_text('''#!/usr/bin/env python3
"""Bind the local SZL Flow Shell to A11oy-owned product HTML surfaces.

Shared and vendored documents remain byte-identical to their canonical owners.
The integrations route receives the product shell at response time; standalone
Hugging Face Space sources are outside the A11oy product-origin asset boundary.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STYLE = '<link rel="stylesheet" href="/assets/szl-flow.css" data-szl-flow-asset="style" />'
SCRIPT = '<script src="/assets/szl-flow.js" defer data-szl-flow-asset="script"></script>'
STYLE_MARKER = 'data-szl-flow-asset="style"'
SCRIPT_MARKER = 'data-szl-flow-asset="script"'
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
)
SOURCE_CONTROLLED_EXACT = ("pages/integrations.html",)
SOURCE_CONTROLLED_GLOBS = ("spaces/*/index.html",)
EXCLUDE_PARTS = {"node_modules", "vendor", "archive", "archives", "fixtures", ".git"}


def _collect(exact: tuple[str, ...], globs: tuple[str, ...]) -> list[Path]:
    found: set[Path] = set()
    for rel in exact:
        path = ROOT / rel
        if path.is_file():
            found.add(path)
    for pattern in globs:
        for path in ROOT.glob(pattern):
            if path.is_file() and not (set(path.relative_to(ROOT).parts) & EXCLUDE_PARTS):
                found.add(path)
    return sorted(found)


def source_controlled_candidates() -> list[Path]:
    return _collect(SOURCE_CONTROLLED_EXACT, SOURCE_CONTROLLED_GLOBS)


def candidates() -> list[Path]:
    controlled = set(source_controlled_candidates())
    return [path for path in _collect(EXACT, GLOBS) if path not in controlled]


def marker_counts(text: str) -> tuple[int, int]:
    return text.count(STYLE_MARKER), text.count(SCRIPT_MARKER)


def inject(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if "data-szl-flow-opt-out" in text:
        return "opt-out"
    if "</head>" not in text.lower() or "</body>" not in text.lower():
        return "not-document"

    style_count, script_count = marker_counts(text)
    if style_count > 1 or script_count > 1:
        raise RuntimeError(f"duplicate Flow Shell marker in {path.relative_to(ROOT)}")
    if style_count == 1 and text.count(STYLE) != 1:
        raise RuntimeError(f"non-canonical Flow Shell style tag in {path.relative_to(ROOT)}")
    if script_count == 1 and text.count(SCRIPT) != 1:
        raise RuntimeError(f"non-canonical Flow Shell script tag in {path.relative_to(ROOT)}")

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


def check_result(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    style_count, script_count = marker_counts(text)
    if style_count > 1 or script_count > 1:
        return "duplicate"
    if text.count(STYLE) == 1 and text.count(SCRIPT) == 1:
        return "present"
    return "missing"


def update_state(bound: list[str], examined: int, source_controlled: list[str]) -> None:
    payload = json.loads(STATE.read_text(encoding="utf-8"))
    payload["state"] = "ROLLED_OUT"
    payload["examined_documents"] = examined
    payload["bound_documents"] = len(bound)
    payload["injected_documents"] = sorted(bound)
    payload["source_controlled_documents"] = sorted(source_controlled)
    STATE.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    controlled_rows = []
    for path in source_controlled_candidates():
        rel = path.relative_to(ROOT).as_posix()
        style_count, script_count = marker_counts(path.read_text(encoding="utf-8"))
        controlled_rows.append({
            "path": rel,
            "result": "clean" if style_count == 0 and script_count == 0 else "source-drift",
        })
    drifted = [row["path"] for row in controlled_rows if row["result"] != "clean"]
    if drifted:
        raise SystemExit("product-only tags mutated source-controlled documents: " + ", ".join(drifted))

    rows = []
    changed: list[str] = []
    bound: list[str] = []
    for path in candidates():
        rel = path.relative_to(ROOT).as_posix()
        result = check_result(path) if args.check else inject(path)
        rows.append({"path": rel, "result": result})
        if result == "injected":
            changed.append(rel)
        if result in {"injected", "present"}:
            bound.append(rel)

    if not rows:
        raise SystemExit("no A11oy-owned product HTML candidates were found")
    root_row = next((row for row in rows if row["path"] == "a11oy_landing.html"), None)
    if not root_row or root_row["result"] not in {"injected", "present"}:
        raise SystemExit("the product front door is not Flow Shell bound")
    if args.check:
        failures = [row["path"] for row in rows if row["result"] != "present"]
        if failures:
            raise SystemExit("invalid or missing Flow Shell: " + ", ".join(failures))
    else:
        controlled = [row["path"] for row in controlled_rows]
        update_state(bound, len(rows) + len(controlled_rows), controlled)

    report = {
        "schema": "szl.frontend-flow-shell-rollout/v2",
        "mode": "CHECK" if args.check else "APPLY",
        "examined": len(rows) + len(controlled_rows),
        "bound": len(bound),
        "changed": len(changed),
        "source_controlled": len(controlled_rows),
        "rows": rows,
        "source_controlled_rows": controlled_rows,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
''', encoding="utf-8", newline="\n")
    ROLLOUT.chmod(0o755)


def write_test() -> None:
    TEST.write_text('''#!/usr/bin/env python3
"""Regression checks for product-only versus canonical Flow Shell ownership."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "docs" / "frontend-flow-shell-state.json"
ROLLOUT = ROOT / "scripts" / "rollout_frontend_flow_shell.py"
MODULE = ROOT / "szl_connectors_serve.py"
STYLE_MARKER = 'data-szl-flow-asset="style"'
SCRIPT_MARKER = 'data-szl-flow-asset="script"'


class ProductFlowSourceBoundaryContract(unittest.TestCase):
    def setUp(self) -> None:
        self.state = json.loads(STATE.read_text(encoding="utf-8"))

    def test_source_controlled_documents_are_unmodified(self) -> None:
        controlled = set(self.state.get("source_controlled_documents", []))
        self.assertIn("pages/integrations.html", controlled)
        spaces = {
            path.relative_to(ROOT).as_posix()
            for path in ROOT.glob("spaces/*/index.html")
            if path.is_file()
        }
        self.assertTrue(spaces)
        self.assertTrue(spaces.issubset(controlled))
        for rel in sorted(controlled):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn(STYLE_MARKER, text, rel)
            self.assertNotIn(SCRIPT_MARKER, text, rel)

    def test_recorded_product_documents_are_bound_once(self) -> None:
        bound = self.state.get("injected_documents", [])
        self.assertEqual(self.state.get("bound_documents"), len(bound))
        self.assertEqual(len(bound), len(set(bound)))
        for rel in bound:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertEqual(text.count(STYLE_MARKER), 1, rel)
            self.assertEqual(text.count(SCRIPT_MARKER), 1, rel)

    def test_integrations_binding_is_runtime_and_namespace_scoped(self) -> None:
        source = MODULE.read_text(encoding="utf-8")
        self.assertIn('if ns == "a11oy":', source)
        self.assertIn("_with_a11oy_flow_shell", source)
        self.assertIn('return HTMLResponse(page, media_type="text/html")', source)
        self.assertIn('return FileResponse(f, media_type="text/html")', source)

    def test_rollout_declares_canonical_source_boundaries(self) -> None:
        source = ROLLOUT.read_text(encoding="utf-8")
        self.assertIn('SOURCE_CONTROLLED_EXACT = ("pages/integrations.html",)', source)
        self.assertIn('SOURCE_CONTROLLED_GLOBS = ("spaces/*/index.html",)', source)
        self.assertNotIn('    "spaces/*/index.html",\n)', source.split("GLOBS = (", 1)[1].split(")", 1)[0])


if __name__ == "__main__":
    unittest.main()
''', encoding="utf-8", newline="\n")


def main() -> int:
    controlled = source_controlled_documents()
    if not controlled:
        raise SystemExit("no source-controlled documents found")
    for path in controlled:
        strip_product_only_tags(path)
    write_rollout()
    write_test()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
