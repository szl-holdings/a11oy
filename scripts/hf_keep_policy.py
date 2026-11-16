#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Dependency-free parser for the governed Hugging Face keep-list subset."""
from __future__ import annotations

from pathlib import Path
import re


KEEPER_ID = re.compile(
    r"^(?P<quote>[\"']?)(?P<id>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)(?P=quote)$"
)


class KeepPolicyError(RuntimeError):
    """Raised when the canonical keep-list subset cannot be read safely."""


def load_keep_ids(path: Path) -> list[str]:
    """Return only top-level ``keep`` IDs, rejecting unsupported YAML syntax."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise KeepPolicyError(f"cannot load canonical keep policy: {exc}") from exc

    try:
        start = lines.index("keep:") + 1
    except ValueError as exc:
        raise KeepPolicyError(
            "canonical keep policy has no top-level keep section"
        ) from exc

    identifiers: list[str] = []
    metadata_keys: set[str] = set()
    metadata_list = False
    for line in lines[start:]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line.startswith(" "):
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*:.*", line):
                break
            raise KeepPolicyError(
                "canonical keep policy contains unexpected top-level syntax"
            )
        if not line.startswith("  -"):
            # Metadata is a sibling mapping, not an arbitrary indented scalar.
            # A list is admitted only directly under an empty metadata field.
            field = re.fullmatch(
                r"    (?P<key>[A-Za-z_][A-Za-z0-9_-]*):(?: (?P<value>.*))?",
                line,
            )
            if field is not None and identifiers:
                key = field.group("key")
                if key == "id" or key in metadata_keys:
                    raise KeepPolicyError(
                        "canonical keep policy contains duplicate keeper metadata"
                    )
                metadata_keys.add(key)
                value = field.group("value")
                metadata_list = value is None or not value.strip()
                continue
            if metadata_list and re.fullmatch(
                r"      - [A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?", line
            ):
                continue
            raise KeepPolicyError(
                "canonical keep policy contains unsupported keeper continuation"
            )
        if not line.startswith("  - id: "):
            raise KeepPolicyError(
                "canonical keep policy contains an unrecognized keeper item"
            )
        raw_identifier = line.removeprefix("  - id: ").strip()
        match = KEEPER_ID.fullmatch(raw_identifier)
        if match is None:
            raise KeepPolicyError(
                "canonical keep policy contains an invalid keeper id"
            )
        identifiers.append(match.group("id"))
        metadata_keys.clear()
        metadata_list = False

    if not identifiers:
        raise KeepPolicyError("canonical keep policy has no keeper ids")
    if len(identifiers) != len(set(identifiers)):
        raise KeepPolicyError("canonical governed keep-set contains duplicates")
    return sorted(identifiers, key=str.casefold)

def load_inventory_pending_public_holds(path: Path) -> list[str]:
    """Read the single existing pending decision, without extending the keep-set.

    This bounded representation deliberately admits only the recorded Constellation
    hold. Another ID, state or historical source requires a separate source review.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise KeepPolicyError("canonical pending-public-hold policy unavailable") from exc
    headers = [
        i for i, line in enumerate(lines)
        if re.match(r"^\s*(?:\?\s*)?['\"]?inventory_pending_public_holds['\"]?\s*(?::|$)", line)
    ]
    if len(headers) != 1 or lines[headers[0]] != "inventory_pending_public_holds:":
        raise KeepPolicyError("canonical pending-public-hold section missing or malformed")
    body = []
    for line in lines[headers[0] + 1:]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*:.*", line):
                break
            raise KeepPolicyError("unsupported pending-public-hold continuation")
        body.append(line)
    if body != [
        "  - id: SZLHOLDINGS/szl-constellation",
        "    state: OWNER_VISIBILITY_DECISION_PENDING",
        "    source: static/shared/public-estate-contract.v1.json#/foldExecution/2026-11-15-batch2/held",
    ]:
        raise KeepPolicyError("unsupported pending-public-hold identity, state or source")
    return ["SZLHOLDINGS/szl-constellation"]
