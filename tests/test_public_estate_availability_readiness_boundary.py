# SPDX-License-Identifier: Apache-2.0
"""Regression guard for public-estate availability versus readiness semantics."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "governance" / "public-estate.v1.json"


def test_killinchu_fail_closed_readiness_is_not_an_availability_requirement() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    killinchu = next(
        row for row in manifest["public_products"] if row["id"] == "killinchu"
    )

    # The canonical Killinchu publisher verifies /api/defend/readyz separately and
    # intentionally requires HTTP 503 while production authorization is held.
    # Availability/SLO probes must therefore use the live product and status/source
    # surfaces, not reinterpret that honest readiness refusal as a product outage.
    assert "/api/defend/readyz" not in killinchu["required_paths"]
    assert "/api/killinchu/healthz" in killinchu["required_paths"]
    assert "/api/defend/status" in killinchu["required_paths"]
    assert "/api/defend/source" in killinchu["required_paths"]
