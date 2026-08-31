"""Tests for provenance-native agent responses."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from verifiable_ai import Claim, Label, ProvenanceResponse  # noqa: E402


def test_backed_response_emits():
    r = ProvenanceResponse(
        "Burgers rel-L2 was 0.644 over 3 seeds.",
        [Claim("burgers_rel_l2", Label.MEASURED, value=0.644, evidence={"seeds": 3})],
    )
    assert r.ok
    payload = r.emit()
    assert payload["verifiable"] is True
    assert payload["claims"][0]["label"] == "MEASURED"


def test_unbacked_claim_is_refused():
    r = ProvenanceResponse(
        "Our model beats everyone.",
        [Claim("win_rate", Label.MEASURED, value=0.99)],  # no evidence
    )
    assert not r.ok
    with pytest.raises(ValueError):
        r.emit()


def test_abstention_response_is_honest():
    r = ProvenanceResponse(
        "We have not benchmarked energy use.",
        [Claim("energy_j", Label.NOT_MEASURED)],
    )
    assert r.ok
    assert r.emit()["claims"][0]["value"] is None
