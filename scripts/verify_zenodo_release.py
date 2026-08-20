#!/usr/bin/env python3
"""Verify the public Zenodo record for an immutable A11oy release.

This script is deliberately fail-closed.  It will only write the local
readback receipt when the public Zenodo API agrees on the exact software
version, release tag, DOI, title, and source repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SOFTWARE_VERSION = "1.1.0"
EXPECTED_TAG = f"v{SOFTWARE_VERSION}"
REPOSITORY_URL = "https://github.com/szl-holdings/a11oy"
RESERVED_DOIS = {
    "10.5281/zenodo.19944926",
    "10.5281/zenodo.20434276",
}
DOI_RE = re.compile(r"^10\.5281/zenodo\.(\d+)$")
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class VerificationError(ValueError):
    """The public record does not prove the requested release identity."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def validate_record(record: Any, requested_doi: str, release_tag: str) -> dict[str, Any]:
    """Validate a decoded Zenodo API record and return a readback receipt."""

    match = DOI_RE.fullmatch(requested_doi)
    if not match or requested_doi in RESERVED_DOIS:
        raise VerificationError("DOI is not a distinct Zenodo software-version DOI")
    if release_tag != EXPECTED_TAG:
        raise VerificationError(f"release tag must be exactly {EXPECTED_TAG}")
    if not isinstance(record, dict):
        raise VerificationError("Zenodo response is not an object")

    public_doi = str(record.get("doi") or "").strip()
    if public_doi != requested_doi:
        raise VerificationError("Zenodo top-level DOI does not match the requested DOI")

    pids = record.get("pids")
    if isinstance(pids, dict) and isinstance(pids.get("doi"), dict):
        pid_doi = str(pids["doi"].get("identifier") or "").strip()
        if pid_doi and pid_doi != requested_doi:
            raise VerificationError("Zenodo PID DOI conflicts with the requested DOI")

    metadata = record.get("metadata")
    if not isinstance(metadata, dict):
        raise VerificationError("Zenodo metadata is missing")
    if str(metadata.get("version") or "").strip() != SOFTWARE_VERSION:
        raise VerificationError(f"Zenodo version must be exactly {SOFTWARE_VERSION}")
    if "a11oy" not in str(metadata.get("title") or "").casefold():
        raise VerificationError("Zenodo title does not identify A11oy")

    related = metadata.get("related_identifiers")
    if not isinstance(related, list):
        raise VerificationError("Zenodo related identifiers are missing")
    identifiers = {
        str(item.get("identifier") or "").rstrip("/")
        for item in related
        if isinstance(item, dict)
    }
    if not any(value == REPOSITORY_URL or value.startswith(f"{REPOSITORY_URL}/") for value in identifiers):
        raise VerificationError("Zenodo record is not linked to the A11oy source repository")

    digest = hashlib.sha256(_canonical_bytes(record)).hexdigest()
    return {
        "status": "VERIFIED",
        "software_version": SOFTWARE_VERSION,
        "release_tag": release_tag,
        "doi": requested_doi,
        "doi_url": f"https://doi.org/{requested_doi}",
        "record_url": f"https://zenodo.org/records/{match.group(1)}",
        "verified_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "verification_source": "zenodo-public-api",
        "metadata_sha256": digest,
    }


def fetch_record(requested_doi: str, *, timeout_seconds: float = 20.0) -> Any:
    match = DOI_RE.fullmatch(requested_doi)
    if not match or requested_doi in RESERVED_DOIS:
        raise VerificationError("DOI is not a distinct Zenodo software-version DOI")
    request = urllib.request.Request(
        f"https://zenodo.org/api/records/{match.group(1)}",
        headers={
            "Accept": "application/json",
            "User-Agent": "a11oy-release-readback/1.1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise VerificationError("Zenodo response exceeds the bounded read limit")
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError("Zenodo response is not valid UTF-8 JSON") from exc


def write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--doi", required=True)
    parser.add_argument("--tag", default=EXPECTED_TAG)
    parser.add_argument("--write", type=Path, default=Path("zenodo-readback.json"))
    args = parser.parse_args()

    record = fetch_record(args.doi)
    receipt = validate_record(record, args.doi, args.tag)
    write_receipt(args.write, receipt)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
