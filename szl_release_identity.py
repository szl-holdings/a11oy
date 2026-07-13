"""Canonical, machine-readable A11oy release identity.

The software-version DOI is intentionally absent until an immutable GitHub
release is archived and Zenodo returns a resolvable record. Existing research
DOIs remain separately typed so a UI cannot present either as the new release.
"""

from __future__ import annotations

import os
import re
from typing import Any


SOFTWARE_NAME = "A11oy"
SOFTWARE_VERSION = "1.1.0"
CANONICAL_URL = "https://a-11-oy.com"
LEGACY_ALIAS = "https://a11oy.net"
REPOSITORY_URL = "https://github.com/szl-holdings/a11oy"
CONCEPT_DOI = "10.5281/zenodo.19944926"
FORMAL_ARTIFACT_DOI = "10.5281/zenodo.20434276"

_ZENODO_DOI_RE = re.compile(r"^10\.5281/zenodo\.\d+$")
_RELEASE_TAG_RE = re.compile(r"^v\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def _optional_release_value(name: str, pattern: re.Pattern[str]) -> str | None:
    value = os.getenv(name, "").strip()
    return value if value and pattern.fullmatch(value) else None


def release_identity() -> dict[str, Any]:
    """Return release identity without upgrading unverified state.

    ``A11OY_VERSION_DOI`` and ``A11OY_RELEASE_TAG`` are accepted only when both
    have valid syntax. Their presence means CONFIGURED, not independently
    VERIFIED; deployment or archive verification must establish resolution.
    """

    version_doi = _optional_release_value("A11OY_VERSION_DOI", _ZENODO_DOI_RE)
    release_tag = _optional_release_value("A11OY_RELEASE_TAG", _RELEASE_TAG_RE)
    configured = bool(version_doi and release_tag)
    release_url = f"{REPOSITORY_URL}/releases/tag/{release_tag}" if configured else f"{REPOSITORY_URL}/releases"

    return {
        "name": SOFTWARE_NAME,
        "version": SOFTWARE_VERSION,
        "release_state": "CONFIGURED_UNVERIFIED" if configured else "CANDIDATE",
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
                "status": "CONFIGURED_UNVERIFIED" if configured else "PENDING_ZENODO_READBACK",
            },
        },
        "honesty": {
            "configured_is_operational": False,
            "conjecture_promoted": False,
            "doi_invented": False,
        },
    }
