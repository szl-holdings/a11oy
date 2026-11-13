#!/usr/bin/env python3
"""Every Khipu 1.5B mention on the vertical cards carries its non-promotion status.

Source: docs/model-inference-support.json (publication_eligible=false; recorded
abstention 2/6 remains the release blocker) and docs/FRONTIER_MODEL_ADOPTION_WAVE26.md.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUALIFIER = "Khipu 1.5B (not promoted · abstention 2/6)"


def card_section() -> str:
    text = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")
    start = text.index('id="vertical-bodies"')
    end = text.index("<!-- ====================== FLAGSHIPS", start)
    return text[start:end]


def test_khipu_model_route_is_qualified_on_every_card() -> None:
    section = card_section()
    mentions = [m.start() for m in re.finditer(r"Khipu 1\.5B", section)]
    assert mentions, "cards must still disclose the Khipu model route"
    for pos in mentions:
        assert section.startswith(QUALIFIER, pos), section[pos : pos + 60]
