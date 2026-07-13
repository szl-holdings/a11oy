from __future__ import annotations

import json

import pytest

from scripts.verify_zenodo_release import VerificationError, validate_record, write_receipt


DOI = "10.5281/zenodo.21234567"


def _record() -> dict:
    return {
        "id": 21234567,
        "doi": DOI,
        "pids": {"doi": {"identifier": DOI}},
        "metadata": {
            "title": "A11oy: governed AI execution fabric",
            "version": "1.1.0",
            "related_identifiers": [
                {"identifier": "https://github.com/szl-holdings/a11oy", "relation": "isDerivedFrom"}
            ],
        },
    }


def test_validate_record_emits_verified_distinct_receipt():
    receipt = validate_record(_record(), DOI, "v1.1.0")
    assert receipt["status"] == "VERIFIED"
    assert receipt["doi"] == DOI
    assert receipt["release_tag"] == "v1.1.0"
    assert len(receipt["metadata_sha256"]) == 64


@pytest.mark.parametrize(
    ("mutation", "doi", "tag"),
    [
        (lambda value: value, "10.5281/zenodo.19944926", "v1.1.0"),
        (lambda value: value, DOI, "latest"),
        (lambda value: value["metadata"].__setitem__("version", "1.0.0"), DOI, "v1.1.0"),
        (lambda value: value["metadata"].__setitem__("title", "Unrelated software"), DOI, "v1.1.0"),
        (lambda value: value["metadata"].__setitem__("related_identifiers", []), DOI, "v1.1.0"),
    ],
)
def test_validate_record_rejects_wrong_or_unrelated_identity(mutation, doi, tag):
    record = _record()
    mutation(record)
    with pytest.raises(VerificationError):
        validate_record(record, doi, tag)


def test_write_receipt_is_parseable(tmp_path):
    receipt = validate_record(_record(), DOI, "v1.1.0")
    target = tmp_path / "zenodo-readback.json"
    write_receipt(target, receipt)
    assert json.loads(target.read_text(encoding="utf-8")) == receipt
