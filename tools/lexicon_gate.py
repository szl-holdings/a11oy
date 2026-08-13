#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Round-5 lexicon and legacy-name gate.

This gate blocks stale product-surface naming from surviving in public-facing
sources after the doctrine reset.

It is intentionally strict and fails closed:

- Any hit on legacy names causes a hard fail.
- Failures are always written into an evidence artifact with line-level details.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = ROOT / "audit"
DEFAULT_REPORT = AUDIT_DIR / "frontier-lexicon-gate.json"
LANDING = ROOT / "a11oy_landing.html"
PAGES_DIR = ROOT / "pages"

SCAN_DEFAULT_ROOTS = [
    LANDING,
    ROOT / "govern_showcase.html",
    ROOT / "cathedral.html",
    ROOT / "cathedral_genius.html",
    ROOT / "pages_console.html",
    ROOT / "index.html",
    ROOT / "agent.html",
    ROOT / "a11oy_code_ide.html",
    ROOT / "live_wires.html",
] + [path for path in sorted(PAGES_DIR.glob("*.html"))]

_KNOWN_EXTS = {
    ".html",
}



BANNED_PATTERNS: dict[str, str] = {
    "kora": r"\bKORA\b",
    "lumina": r"\bLUMINA\b",
    "paragon": r"\bPARAGON\b",
    "lyte": r"\bLyte\b",
    "governed_inference": r"Governed\s+Inference",
    "governed_inference_title": r"GOVERNED\s+INFERENCE",
}


ALLOWED_EXTS = _KNOWN_EXTS
SKIP_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    "vendor",
    "audit",
    "artifacts",
    "tmp",
    ".pytest_cache",
}


@dataclass
class Hit:
    token: str
    path: str
    line: int
    line_text: str


def _iter_candidates(base_paths: list[Path]) -> list[Path]:
    discovered: list[Path] = []
    for base in base_paths:
        if not base.exists():
            continue
        if base.is_file():
            discovered.append(base)
            continue
        try:
            for path in base.rglob("*"):
                if not path.is_file():
                    continue
                if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
                    continue
                if path.suffix.lower() not in ALLOWED_EXTS and not path.suffix == "":
                    continue
                discovered.append(path)
        except OSError as exc:
            discovered.append(base)
    return sorted(set(discovered))


def _read_lines(path: Path) -> tuple[list[str], str | None]:
    try:
        return path.read_text(encoding="utf-8").splitlines(), None
    except UnicodeDecodeError:
        return [], f"{path}: Unicode decode error"
    except OSError as exc:
        return [], f"{path}: {exc}"


def run_lexicon_gate(scan_paths: list[Path]) -> list[Hit]:
    patterns = {
        name: re.compile(expr, flags=re.IGNORECASE)
        for name, expr in BANNED_PATTERNS.items()
    }
    hits: list[Hit] = []
    for path in scan_paths:
        lines, read_error = _read_lines(path)
        if read_error:
            hits.append(
                Hit(
                    token="unreadable_file",
                    path=str(path.relative_to(ROOT)),
                    line=0,
                    line_text=read_error,
                )
            )
            continue
        if not lines:
            continue
        for idx, line in enumerate(lines, start=1):
            for name, pattern in patterns.items():
                if pattern.search(line):
                    hits.append(
                        Hit(
                            token=name,
                            path=str(path.relative_to(ROOT)),
                            line=idx,
                            line_text=line.strip(),
                        )
                    )
    return hits


def _build_report(hits: list[Hit]) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "kind": "szl-lexicon-gate",
        "status": "PASS" if not hits else "FAIL",
        "hitCount": len(hits),
        "hits": [
            {
                "token": hit.token,
                "path": hit.path,
                "line": hit.line,
                "lineText": hit.line_text,
            }
            for hit in hits
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Round-5 lexicon gate")
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero when the gate fails",
    )
    parser.add_argument(
        "--paths",
        nargs="*",
        default=[],
        help="optional explicit scan paths (defaults to landing + docs + scripts + tools)",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT,
        help="write machine-readable report JSON",
    )
    args = parser.parse_args()

    scan_roots = (
        [Path(p).expanduser() for p in args.paths]
        if args.paths
        else SCAN_DEFAULT_ROOTS
    )
    hits = run_lexicon_gate(scan_roots)
    report = _build_report(hits)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 1 if args.check and hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
