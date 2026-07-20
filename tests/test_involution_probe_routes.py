"""Live route contract for the EvidenceOS involution probe."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

import szl_involution_probe as probe


def _client():
    app = FastAPI()
    probe.register(app)
    return TestClient(app)


def test_info_is_live_but_does_not_claim_measurement_or_write():
    response = _client().get("/api/a11oy/v1/evidenceos/involution/info")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["service_state"] == "LIVE"
    assert body["writes"] == 0
    assert body["effectors"] == 0
    assert body["labels"]["computed_observation"] == "MODELED"


def test_evaluate_runs_real_bounded_decomposition():
    response = _client().post("/api/a11oy/v1/evidenceos/involution/evaluate", json={
        "pair_id": "brain-retriever-pair-1",
        "left_observation": [1.0, 2.0, 4.0, 8.0],
        "transformed_observation": [2.0, 1.0, 8.0, 4.0],
        "permutation": [1, 0, 3, 2],
    })
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["verdict"] == "DECOMPOSED"
    assert body["closure"]["pair_reconstruction_residual_linf"] == 0.0
    assert body["digests"]["signed"] is False


def test_invalid_input_fails_closed_and_large_body_is_rejected():
    bad = _client().post("/api/a11oy/v1/evidenceos/involution/evaluate", json={
        "pair_id": "bad",
        "left_observation": [1, 2],
        "transformed_observation": [1, 2],
        "permutation": [1, 1],
    })
    assert bad.status_code == 422
    assert bad.json()["verdict"] == "REFUSED"
    assert bad.json()["refusal"]["code"] == "PERMUTATION_NOT_BIJECTIVE"

    large = _client().post(
        "/api/a11oy/v1/evidenceos/involution/evaluate",
        data=b'{"padding":"' + (b"x" * 200_001) + b'"}',
        headers={"content-type": "application/json"},
    )
    assert large.status_code == 413
