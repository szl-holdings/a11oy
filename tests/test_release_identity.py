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
        "readback": None,
    }
    assert payload["honesty"]["doi_invented"] is False


def test_release_identity_rejects_malformed_external_values(monkeypatch):
    monkeypatch.setenv("A11OY_VERSION_DOI", "10.0000/not-real")
    monkeypatch.setenv("A11OY_RELEASE_TAG", "latest")

    payload = release.release_identity()

    assert payload["release_state"] == "CANDIDATE"
    assert payload["release_tag"] is None
    assert payload["doi"]["software_version"]["value"] is None


def test_release_identity_rejects_wrong_version_tag_and_existing_research_dois(monkeypatch):
    monkeypatch.setenv("A11OY_RELEASE_TAG", "v9.9.9")
    monkeypatch.setenv("A11OY_VERSION_DOI", release.CONCEPT_DOI)
    payload = release.release_identity()
    assert payload["release_state"] == "CANDIDATE"
    assert payload["release_tag"] is None
    assert payload["doi"]["software_version"]["value"] is None

    monkeypatch.setenv("A11OY_RELEASE_TAG", "v1.1.0")
    monkeypatch.setenv("A11OY_VERSION_DOI", release.FORMAL_ARTIFACT_DOI)
    payload = release.release_identity()
    assert payload["release_state"] == "CANDIDATE"
    assert payload["doi"]["software_version"]["value"] is None


def test_release_identity_accepts_only_paired_syntactic_configuration(monkeypatch):
    monkeypatch.setenv("A11OY_VERSION_DOI", "10.5281/zenodo.21234567")
    monkeypatch.setenv("A11OY_RELEASE_TAG", "v1.1.0")

    payload = release.release_identity()

    assert payload["release_state"] == "CONFIGURED_UNVERIFIED"
    assert payload["release_tag"] == "v1.1.0"
    assert payload["doi"]["software_version"]["status"] == "CONFIGURED_UNVERIFIED"
    assert payload["release_url"].endswith("/releases/tag/v1.1.0")


def test_pending_readback_does_not_upgrade_release(monkeypatch, tmp_path):
    readback = tmp_path / "zenodo-readback.json"
    readback.write_text(
        json.dumps({"status": "PENDING_ZENODO_READBACK", "doi": None}),
        encoding="utf-8",
    )
    monkeypatch.setattr(release, "_READBACK_PATH", readback)
    monkeypatch.delenv("A11OY_VERSION_DOI", raising=False)
    monkeypatch.delenv("A11OY_RELEASE_TAG", raising=False)
    assert release.release_identity()["release_state"] == "CANDIDATE"


def test_verified_readback_is_the_only_verified_release_state(monkeypatch, tmp_path):
    readback = tmp_path / "zenodo-readback.json"
    readback.write_text(
        json.dumps(
            {
                "status": "VERIFIED",
                "software_version": "1.1.0",
                "release_tag": "v1.1.0",
                "doi": "10.5281/zenodo.21234567",
                "metadata_sha256": "a" * 64,
                "verification_source": "zenodo-public-api",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release, "_READBACK_PATH", readback)
    payload = release.release_identity()
    assert payload["release_state"] == "VERIFIED"
    assert payload["doi"]["software_version"]["value"] == "10.5281/zenodo.21234567"
    assert payload["doi"]["software_version"]["readback"]["verification_source"] == "zenodo-public-api"


def test_wrong_version_or_reserved_readback_is_ignored(monkeypatch, tmp_path):
    readback = tmp_path / "zenodo-readback.json"
    readback.write_text(
        json.dumps(
            {
                "status": "VERIFIED",
                "software_version": "9.9.9",
                "release_tag": "v1.1.0",
                "doi": release.CONCEPT_DOI,
                "metadata_sha256": "b" * 64,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release, "_READBACK_PATH", readback)
    monkeypatch.delenv("A11OY_VERSION_DOI", raising=False)
    monkeypatch.delenv("A11OY_RELEASE_TAG", raising=False)
    assert release.release_identity()["release_state"] == "CANDIDATE"


def test_zenodo_metadata_and_company_page_tag_both_domains_and_existing_dois():
    zenodo = json.loads((ROOT / ".zenodo.json").read_text(encoding="utf-8"))
    company = (ROOT / "pages" / "company.html").read_text(encoding="utf-8")

    assert zenodo["version"] == release.SOFTWARE_VERSION
    assert zenodo["license"] == "Apache-2.0"
    identifiers = {item["identifier"] for item in zenodo["related_identifiers"]}
    assert release.CONCEPT_DOI in identifiers
    assert release.FORMAL_ARTIFACT_DOI in identifiers
    assert release.REPOSITORY_URL in identifiers

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
    assert 'id="software-release-card"' in company
    assert "release.release_state !== 'VERIFIED'" in company
    assert "a11oy:software-version-doi" in company


def test_live_version_route_uses_canonical_release_identity(monkeypatch):
    monkeypatch.delenv("A11OY_VERSION_DOI", raising=False)
    monkeypatch.delenv("A11OY_RELEASE_TAG", raising=False)
    monkeypatch.delenv("SZL_GIT_SHA", raising=False)

    from fastapi.testclient import TestClient
    import serve

    with TestClient(serve.app) as client:
        response = client.get("/api/a11oy/v1/version")

    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == release.SOFTWARE_VERSION
    assert payload["release_state"] == "CANDIDATE"
    assert payload["git_sha"] == "UNKNOWN"
    assert payload["surfaces"]["canonical"] == release.CANONICAL_URL
    assert payload["surfaces"]["legacy_alias"] == release.LEGACY_ALIAS
    assert payload["doi"]["software_version"]["status"] == "PENDING_ZENODO_READBACK"
    assert payload["verify"]["release_assets_status"] == "PENDING_RELEASE"
