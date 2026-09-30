"""SOW membrane retrieve-or-abstain contract.

Additive to brain capabilities. Does not change capabilities_total,
overall_status, or the wired:4 register receipt.

Signed-off-by: Lutar, Stephen P. <stephenlutar2@gmail.com>
"""

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("starlette.testclient")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import szl_brain_capabilities as bc  # noqa: E402


def test_empty_membrane_abstains_every_station():
    body = bc.retrieve_membrane()
    assert body["miss"] == "ABSTAIN"
    assert body["overall"] == "ABSTAIN"
    assert body["certified_production_ready"] is False
    assert body["hickok_untouched"] is True
    assert body["locked_formula_count"] == 8
    assert body["china_oss"] == "REPORTED"
    assert body["blocked_at"] == "SOW"
    assert body["admitted"] == []
    for station in bc.STATION_IDS:
        row = body["membrane"][station]
        assert row["state"] == "ABSTAIN"
        assert row["handle"] is None


def test_retrieve_never_invents_an_id_from_blank_or_unknown_keys():
    body = bc.retrieve_membrane({"SOW": "  ", "NOT_A_STATION": "invented"})
    assert body["membrane"]["SOW"]["state"] == "ABSTAIN"
    assert "NOT_A_STATION" not in body["membrane"]
    assert body["overall"] == "ABSTAIN"


def test_handles_admit_in_station_order_and_block_at_first_miss():
    partial = bc.retrieve_membrane({"SOW": "sow_northwind_p1"})
    assert partial["membrane"]["SOW"]["state"] == "HANDLE"
    assert partial["membrane"]["SOW"]["handle"] == "sow_northwind_p1"
    assert partial["blocked_at"] == "STAFF"
    assert partial["overall"] == "ABSTAIN"

    full = bc.retrieve_membrane(
        {
            "SOW": "sow_atlas_cutover",
            "STAFF": "roster_atlas",
            "EXCEPTION": "exc_atlas_none",
            "INVOICE": "inv-4502",
        }
    )
    assert full["overall"] == "ADMIT"
    assert full["blocked_at"] is None
    assert full["admitted"] == list(bc.STATION_IDS)


def test_manifest_stays_partial_and_gains_membrane_pointer():
    manifest = bc.build_manifest("a11oy")
    assert manifest["overall_status"] == "PARTIALLY OPERATIONAL"
    assert manifest["summary"]["capabilities_total"] == len(manifest["capabilities"])
    assert manifest["certified_production_ready"] is False
    assert manifest["hickok_untouched"] is True
    assert manifest["miss"] == "ABSTAIN"
    assert manifest["membrane_route"] == "/api/a11oy/v1/brain/membrane"
    assert manifest["membrane"]["INVOICE"]["state"] == "ABSTAIN"


def test_membrane_route_registers_without_changing_wired_receipt():
    app = FastAPI()
    status = bc.register(app, ns="a11oy")
    assert status == "brain-capabilities-wired:4"

    with TestClient(app) as client:
        empty = client.get("/api/a11oy/v1/brain/membrane")
        admitted = client.get(
            "/api/a11oy/v1/brain/membrane",
            params={
                "sow": "sow_atlas_cutover",
                "staff": "roster_atlas",
                "exception": "exc_atlas_none",
                "invoice": "inv-4502",
            },
        )
        capabilities = client.get("/api/a11oy/v1/brain/capabilities")

    assert empty.status_code == 200
    assert empty.json()["overall"] == "ABSTAIN"
    assert admitted.status_code == 200
    assert admitted.json()["overall"] == "ADMIT"
    assert capabilities.json()["summary"]["capabilities_total"] == 8
    assert capabilities.json()["overall_status"] == "PARTIALLY OPERATIONAL"
