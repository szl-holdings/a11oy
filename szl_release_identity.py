"""Canonical, machine-readable A11oy release identity.

The software-version DOI is intentionally absent until an immutable GitHub
release is archived and Zenodo returns a resolvable record. Existing research
DOIs remain separately typed so a UI cannot present either as the new release.
"""

from __future__ import annotations

import os
import re
import json
from pathlib import Path
from typing import Any


SOFTWARE_NAME = "A11oy"
SOFTWARE_VERSION = "1.1.0"
CANONICAL_URL = "https://a-11-oy.com"
LEGACY_ALIAS = "https://a11oy.net"
REPOSITORY_URL = "https://github.com/szl-holdings/a11oy"
CONCEPT_DOI = "10.5281/zenodo.19944926"
FORMAL_ARTIFACT_DOI = "10.5281/zenodo.20434276"

_ZENODO_DOI_RE = re.compile(r"^10\.5281/zenodo\.\d+$")
_EXPECTED_RELEASE_TAG = f"v{SOFTWARE_VERSION}"
_READBACK_PATH = Path(__file__).with_name("zenodo-readback.json")


def _configured_version_doi() -> str | None:
    value = os.getenv("A11OY_VERSION_DOI", "").strip()
    if not value or not _ZENODO_DOI_RE.fullmatch(value):
        return None
    if value in {CONCEPT_DOI, FORMAL_ARTIFACT_DOI}:
        return None
    return value


def _configured_release_tag() -> str | None:
    value = os.getenv("A11OY_RELEASE_TAG", "").strip()
    return value if value == _EXPECTED_RELEASE_TAG else None


def _verified_readback() -> dict[str, Any] | None:
    try:
        payload = json.loads(_READBACK_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(payload, dict) or payload.get("status") != "VERIFIED":
        return None
    if payload.get("software_version") != SOFTWARE_VERSION:
        return None
    if payload.get("release_tag") != _EXPECTED_RELEASE_TAG:
        return None
    doi = str(payload.get("doi") or "")
    if not _ZENODO_DOI_RE.fullmatch(doi) or doi in {CONCEPT_DOI, FORMAL_ARTIFACT_DOI}:
        return None
    if not str(payload.get("metadata_sha256") or ""):
        return None
    return payload


def release_identity() -> dict[str, Any]:
    """Return release identity without upgrading unverified state.

    ``A11OY_VERSION_DOI`` and ``A11OY_RELEASE_TAG`` are accepted only when both
    have valid syntax. Their presence means CONFIGURED, not independently
    VERIFIED; deployment or archive verification must establish resolution.
    """

    readback = _verified_readback()
    version_doi = str(readback["doi"]) if readback else _configured_version_doi()
    release_tag = str(readback["release_tag"]) if readback else _configured_release_tag()
    configured = bool(version_doi and release_tag)
    verified = bool(readback)
    release_url = f"{REPOSITORY_URL}/releases/tag/{release_tag}" if configured else f"{REPOSITORY_URL}/releases"

    return {
        "name": SOFTWARE_NAME,
        "version": SOFTWARE_VERSION,
        "expected_release_tag": _EXPECTED_RELEASE_TAG,
        "release_state": "VERIFIED" if verified else ("CONFIGURED_UNVERIFIED" if configured else "CANDIDATE"),
        "release_tag": release_tag,
        "release_url": release_url,
        "surfaces": {
            "canonical": CANONICAL_URL,
            "legacy_alias": LEGACY_ALIAS,
            "legacy_alias_policy": "PERMANENT_REDIRECT_TO_CANONICAL",
            "repository": REPOSITORY_URL,
        },
        "doi": {
            "concept": {
                "value": CONCEPT_DOI,
                "url": f"https://doi.org/{CONCEPT_DOI}",
                "role": "ASSOCIATED_RESEARCH_PROGRAM",
            },
            "formal_artifacts": {
                "value": FORMAL_ARTIFACT_DOI,
                "url": f"https://doi.org/{FORMAL_ARTIFACT_DOI}",
                "role": "EXISTING_FORMAL_ARTIFACT_RECORD",
            },
            "software_version": {
                "value": version_doi,
                "url": f"https://doi.org/{version_doi}" if version_doi else None,
                "status": "VERIFIED" if verified else ("CONFIGURED_UNVERIFIED" if configured else "PENDING_ZENODO_READBACK"),
                "readback": readback,
            },
        },
        "honesty": {
            "configured_is_operational": False,
            "conjecture_promoted": False,
            "doi_invented": False,
        },
    }
