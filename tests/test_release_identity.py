from __future__ import annotations

import json
from pathlib import Path

import szl_release_identity as release


ROOT = Path(__file__).resolve().parents[1]


def test_release_identity_keeps_existing_and_version_dois_distinct(monkeypatch):
    monkeypatch.delenv("A11OY_VERSION_DOI", raising=False)
    monkeypatch.delenv("A11OY_RELEASE_TAG", raising=False)

    payload = release.release_identity()

    assert payload["release_state"] == "CANDIDATE"
    assert payload["doi"]["concept"]["value"] == "10.5281/zenodo.19944926"
    assert payload["doi"]["formal_artifacts"]["value"] == "10.5281/zenodo.20434276"
    assert payload["doi"]["software_version"] == {
        "value": None,
        "url": None,
        "status": "PENDING_ZENODO_READBACK",
    }
    assert payload["honesty"]["doi_invented"] is False


def test_release_identity_rejects_malformed_external_values(monkeypatch):
    monkeypatch.setenv("A11OY_VERSION_DOI", "10.0000/not-real")
    monkeypatch.setenv("A11OY_RELEASE_TAG", "latest")

    payload = release.release_identity()

    assert payload["release_state"] == "CANDIDATE"
    assert payload["release_tag"] is None
    assert payload["doi"]["software_version"]["value"] is None


def test_release_identity_accepts_only_paired_syntactic_configuration(monkeypatch):
    monkeypatch.setenv("A11OY_VERSION_DOI", "10.5281/zenodo.21234567")
    monkeypatch.setenv("A11OY_RELEASE_TAG", "v1.1.0")

    payload = release.release_identity()

    assert payload["release_state"] == "CONFIGURED_UNVERIFIED"
    assert payload["release_tag"] == "v1.1.0"
    assert payload["doi"]["software_version"]["status"] == "CONFIGURED_UNVERIFIED"
    assert payload["release_url"].endswith("/releases/tag/v1.1.0")


def test_zenodo_metadata_and_company_page_tag_both_domains_and_existing_dois():
    zenodo = json.loads((ROOT / ".zenodo.json").read_text(encoding="utf-8"))
    company = (ROOT / "pages" / "company.html").read_text(encoding="utf-8")

    assert zenodo["version"] == release.SOFTWARE_VERSION
    assert zenodo["license"] == "Apache-2.0"
    identifiers = {item["identifier"] for item in zenodo["related_identifiers"]}
    assert release.CONCEPT_DOI in identifiers
    assert release.FORMAL_ARTIFACT_DOI in identifiers
    assert release.CANONICAL_URL in identifiers

    for value in (
        release.CANONICAL_URL,
        release.LEGACY_ALIAS,
        release.CONCEPT_DOI,
        release.FORMAL_ARTIFACT_DOI,
        release.REPOSITORY_URL,
    ):
        assert value in company

    assert "PENDING_ZENODO_READBACK" not in company
    assert "No placeholder is presented as a DOI" in company
