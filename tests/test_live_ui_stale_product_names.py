#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Live UI must not present retired product names as current products.

KORA / LUMINA / PARAGON stay banned in tools/lexicon_gate.py. Docs that say
'do not use KORA' are allowed. Λ = Conjecture 1.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB_SRC = ROOT / "web" / "src"
LEXICON = ROOT / "tools" / "lexicon_gate.py"
ECOSYSTEM = ROOT / "docs" / "ECOSYSTEM.md"

STALE = re.compile(r"\b(KORA|LUMINA|PARAGON)\b")
SKIP_PARTS = {"node_modules", "dist", "build"}


def _live_files() -> list[Path]:
    out: list[Path] = []
    for path in WEB_SRC.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        if path.suffix.lower() not in {".ts", ".tsx", ".js", ".jsx"}:
            continue
        out.append(path)
    return out


def test_lexicon_gate_bans_are_intact() -> None:
    text = LEXICON.read_text(encoding="utf-8")
    assert r'"kora": r"\bKORA\b"' in text
    assert r'"lumina": r"\bLUMINA\b"' in text
    assert r'"paragon": r"\bPARAGON\b"' in text


def test_docs_may_say_do_not_use_retired_names() -> None:
    text = ECOSYSTEM.read_text(encoding="utf-8")
    assert "do not use" in text.lower() or "retired/stale" in text
    assert "KORA" in text


def test_live_web_src_does_not_name_kora_lumina_paragon() -> None:
    hits: list[str] = []
    for path in _live_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if STALE.search(line):
                rel = path.relative_to(ROOT)
                hits.append(f"{rel}:{lineno}:{line.strip()}")
    assert hits == [], "retired product names in live UI:\n" + "\n".join(hits)


