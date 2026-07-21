#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Deterministically freeze the raw Brain ledger without admitting its content.

The snapshot is an integrity and accounting artifact.  It grants no rights,
privacy clearance, proof credit, training eligibility, or model promotion.  A
row remains quarantined until the separate row-admission gate verifies every
required evidence envelope.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import pathlib
from typing import Any, Iterable, Mapping, Sequence


SNAPSHOT_SCHEMA = "szl.brain-raw-snapshot.v1"
EXPECTED_LEDGER_SCHEMA = "szl.m1-brain-ingest-decision/v1"
MAX_LEDGER_BYTES = 64 * 1024 * 1024
MAX_ROWS = 20_000
_LEAF_DOMAIN = b"szl.brain.raw-row.v1\x00"
_NODE_DOMAIN = b"szl.brain.merkle-node.v1\x00"


class SnapshotError(RuntimeError):
    """The raw ledger cannot be frozen without ambiguity."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _merkle_root(leaves: Iterable[bytes]) -> str:
    level = [hashlib.sha256(_LEAF_DOMAIN + leaf).digest() for leaf in leaves]
    if not level:
        return hashlib.sha256(_NODE_DOMAIN).hexdigest()
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [
            hashlib.sha256(_NODE_DOMAIN + level[index] + level[index + 1]).digest()
            for index in range(0, len(level), 2)
        ]
    return level[0].hex()


def _string_counter(rows: Sequence[Mapping[str, Any]], getter: Any) -> dict[str, int]:
    counter: collections.Counter[str] = collections.Counter()
    for row in rows:
        value = getter(row)
        counter[value if isinstance(value, str) and value else "UNKNOWN"] += 1
    return dict(sorted(counter.items()))


def load_ledger(path: pathlib.Path | str) -> list[dict[str, Any]]:
    ledger_path = pathlib.Path(path)
    if not ledger_path.is_file():
        raise SnapshotError("LEDGER_UNAVAILABLE")
    size = ledger_path.stat().st_size
    if size <= 0 or size > MAX_LEDGER_BYTES:
        raise SnapshotError("LEDGER_SIZE_OUT_OF_BOUNDS")
    rows: list[dict[str, Any]] = []
    with ledger_path.open("r", encoding="utf-8", newline="") as stream:
        for line_number, raw_line in enumerate(stream, start=1):
            if not raw_line.strip():
                raise SnapshotError(f"LEDGER_BLANK_LINE:{line_number}")
            if len(rows) >= MAX_ROWS:
                raise SnapshotError("LEDGER_ROW_LIMIT_EXCEEDED")
            try:
                row = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise SnapshotError(f"LEDGER_JSON_INVALID:{line_number}") from exc
            if not isinstance(row, dict):
                raise SnapshotError(f"LEDGER_ROW_NOT_OBJECT:{line_number}")
            if row.get("schema") != EXPECTED_LEDGER_SCHEMA:
                raise SnapshotError(f"LEDGER_SCHEMA_MISMATCH:{line_number}")
            node_id = row.get("node_id")
            content_sha = row.get("canonical_text_sha256")
            content = row.get("canonical_text")
            if not isinstance(node_id, str) or not node_id:
                raise SnapshotError(f"LEDGER_NODE_ID_INVALID:{line_number}")
            if (
                not isinstance(content, str)
                or not isinstance(content_sha, str)
                or len(content_sha) != 64
                or sha256_bytes(content.encode("utf-8")) != content_sha
            ):
                raise SnapshotError(f"LEDGER_CONTENT_BINDING_INVALID:{line_number}")
            rows.append(row)
    node_ids = [row["node_id"] for row in rows]
    if len(node_ids) != len(set(node_ids)):
        raise SnapshotError("LEDGER_DUPLICATE_NODE_ID")
    return rows


def build_snapshot(path: pathlib.Path | str) -> dict[str, Any]:
    ledger_path = pathlib.Path(path)
    rows = load_ledger(ledger_path)
    canonical_rows = [canonical_bytes(row) for row in rows]
    content_hashes = [str(row["canonical_text_sha256"]) for row in rows]
    safety = _string_counter(rows, lambda row: row.get("safety_decision"))
    training = _string_counter(rows, lambda row: row.get("training_decision"))
    body: dict[str, Any] = {
        "schema_version": SNAPSHOT_SCHEMA,
        "source": {
            "path": ledger_path.as_posix(),
            "schema": EXPECTED_LEDGER_SCHEMA,
            "bytes": ledger_path.stat().st_size,
            "sha256": sha256_file(ledger_path),
        },
        "integrity": {
            "row_canonicalization": "SORTED_COMPACT_JSON_UTF8_V1",
            "leaf_domain": _LEAF_DOMAIN[:-1].decode("ascii"),
            "node_domain": _NODE_DOMAIN[:-1].decode("ascii"),
            "odd_leaf_rule": "DUPLICATE_LAST",
            "merkle_root_sha256": _merkle_root(canonical_rows),
        },
        "counts": {
            "rows": len(rows),
            "unique_node_ids": len(rows),
            "distinct_content_sha256": len(set(content_hashes)),
            "duplicate_content_rows": len(rows) - len(set(content_hashes)),
            "person_rows": sum(row.get("kind") == "person" for row in rows),
            "training_eligible_rows": sum(
                row.get("training_eligible") is True for row in rows
            ),
        },
        "facets": {
            "kind": _string_counter(rows, lambda row: row.get("kind")),
            "source_family": _string_counter(rows, lambda row: row.get("source_family")),
            "source": _string_counter(
                rows,
                lambda row: (row.get("provenance") or {}).get("source")
                if isinstance(row.get("provenance"), Mapping)
                else None,
            ),
            "license_state": _string_counter(
                rows,
                lambda row: (row.get("license") or {}).get("state")
                if isinstance(row.get("license"), Mapping)
                else None,
            ),
            "freshness_state": _string_counter(
                rows,
                lambda row: (row.get("freshness") or {}).get("state")
                if isinstance(row.get("freshness"), Mapping)
                else None,
            ),
            "safety_decision": safety,
            "training_decision": training,
        },
        "claims_boundary": {
            "rights_established": False,
            "privacy_clearance_established": False,
            "training_authorized": False,
            "training_triggered": False,
            "model_promotion_allowed": False,
            "proof_credit": 0,
        },
    }
    body["snapshot_sha256"] = sha256_bytes(canonical_bytes(body))
    return body


def write_snapshot(snapshot: Mapping[str, Any], output: pathlib.Path | str) -> None:
    output_path = pathlib.Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8", newline="\n")
    temporary.replace(output_path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    snapshot = build_snapshot(args.ledger)
    write_snapshot(snapshot, args.output)
    print(json.dumps({
        "snapshot_sha256": snapshot["snapshot_sha256"],
        "rows": snapshot["counts"]["rows"],
        "merkle_root_sha256": snapshot["integrity"]["merkle_root_sha256"],
        "training_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
