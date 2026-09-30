# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Software lab admission stays independent of the theorem registry."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

import a11oy_experimental_tier as tier


def test_software_lab_manifest_preserves_proof_and_admission_boundaries():
    app = FastAPI()
    tier.register(app)
    response = TestClient(app).get("/api/a11oy/v1/experimental/index")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    data = response.json()
    assert data["doctrine"]["locked_count"] == 8
    assert data["doctrine"]["locked_proven"] == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
    assert data["total_experimental_items"] == len(data["frontier_five"]) + data["wave910"]["count"] + len(data["founder_gated"])
    lab, = data["software_labs"]
    assert data["software_lab_count"] == 1
    assert lab["promotion_status"] == "HOLD"
    assert lab["production_admitted"] is False
    assert lab["locked_formula_member"] is False
    assert lab["runtime_contract"]["model_loaded"] is False
    assert lab["runtime_observation"] == "NOT_PROBED"
    page = (Path(__file__).resolve().parents[1] / "a11oy_landing.html").read_text(encoding="utf-8")
    assert f'href="{lab["demo_url"]}"' in page
    assert f'href="{lab["space_url"]}"' in page
    assert f'href="{lab["readiness_url"]}"' in page


def test_mutating_manifest_does_not_change_future_admission_contract():
    data = tier.handle_experimental_index()
    data["software_labs"][0]["production_admitted"] = True
    data["software_labs"][0]["runtime_contract"]["model_loaded"] = True
    lab = tier.handle_experimental_index()["software_labs"][0]
    assert lab["production_admitted"] is False
    assert lab["runtime_contract"]["model_loaded"] is False
