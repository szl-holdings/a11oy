#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Build an unsigned evidence snapshot; intake JSON never confers authority."""

from __future__ import annotations

import argparse
import base64
import binascii
import datetime as dt
import hashlib
import json
import os
import pathlib
import sys
from typing import Any

UTC = dt.timezone.utc
SKIP = {".git", "node_modules", ".venv", "venv", "dist", "__pycache__"}
MAX_FILE_BYTES = 1024 * 1024
MAX_FILES = 256
MAX_RECORDS = 2000
MAX_TOTAL_BYTES = 32 * 1024 * 1024
ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from evaluate_supply_chain import evaluate
from verify_release import VerifiedEvidence, proof_metadata, verify_artifact


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _bounded_shape(value: Any) -> None:
    pending = [(value, 0)]
    nodes = 0
    while pending:
        node, depth = pending.pop()
        nodes += 1
        if depth > 64 or nodes > 100000:
            raise ValueError("JSON nesting or node limit exceeded")
        if isinstance(node, dict):
            pending.extend((item, depth + 1) for item in node.values())
        elif isinstance(node, list):
            pending.extend((item, depth + 1) for item in node)


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("Non-finite JSON number")


def strict_json(raw: str | bytes) -> Any:
    if len(raw.encode("utf-8") if isinstance(raw, str) else raw) > MAX_FILE_BYTES:
        raise ValueError("JSON input exceeds size limit")
    value = json.loads(
        raw, object_pairs_hook=_strict_object, parse_constant=_reject_constant
    )
    _bounded_shape(value)
    return value


def decode_statement(value: Any) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Decode structure only; signature counts and input flags prove nothing."""
    verification: dict[str, Any] = {"verified": False, "source": "untrusted-input"}
    try:
        _bounded_shape(value)
        if len(canonical(value)) > MAX_FILE_BYTES:
            return None, verification
        for _ in range(8):
            if not isinstance(value, dict):
                return None, verification
            if value.get("_type") == "https://in-toto.io/Statement/v1":
                return value, verification
            if "payload" in value or "payloadType" in value:
                if value.get(
                    "payloadType"
                ) != "application/vnd.in-toto+json" or not isinstance(
                    value.get("payload"), str
                ):
                    return None, verification
                signatures = value.get("signatures")
                if not isinstance(signatures, list) or not all(
                    isinstance(sig, dict) for sig in signatures
                ):
                    return None, verification
                verification.update(
                    envelopePresent=True, signatureCount=len(signatures)
                )
                value = strict_json(base64.b64decode(value["payload"], validate=True))
                continue
            if isinstance(value.get("statement"), dict):
                value = value["statement"]
            elif isinstance(value.get("attestation"), dict):
                value = value["attestation"]
            else:
                return None, verification
    except (ValueError, TypeError, RecursionError, binascii.Error, UnicodeError):
        pass
    return None, verification


def objects_from_file(path: pathlib.Path) -> list[Any]:
    with path.open("rb") as handle:
        raw = handle.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError("Evidence file exceeds size limit")
    if path.suffix == ".jsonl":
        values = [strict_json(line) for line in raw.splitlines() if line.strip()]
    else:
        value = strict_json(raw)
        values = value if isinstance(value, list) else [value]
    if len(values) > MAX_RECORDS:
        raise ValueError("Evidence record limit exceeded")
    return values


def discover(root: pathlib.Path, evidence_dir: pathlib.Path) -> list[pathlib.Path]:
    """Only scan explicit intake, never unrelated repository files or symlinks."""
    evidence_dir = evidence_dir.resolve()
    if not evidence_dir.exists():
        return []
    paths = []
    total_bytes = 0
    for base, dirs, files in os.walk(evidence_dir, followlinks=False):
        dirs[:] = sorted(
            d
            for d in dirs
            if d not in SKIP and not (pathlib.Path(base) / d).is_symlink()
        )
        for name in sorted(files):
            path = pathlib.Path(base) / name
            if path.suffix not in {".json", ".jsonl"}:
                continue
            if path.is_symlink() or not path.resolve().is_relative_to(evidence_dir):
                raise ValueError("Evidence intake contains an external link")
            paths.append(path)
            total_bytes += path.stat().st_size
            if len(paths) > MAX_FILES or total_bytes > MAX_TOTAL_BYTES:
                raise ValueError("Evidence intake exceeds file or byte limits")
    return sorted(paths)


def _blocked(message: str) -> dict[str, Any]:
    return {
        "outcome": "BLOCK",
        "deny": [message],
        "review": [],
        "verified": False,
        "evaluator": "ingest-validation",
        "policyEvaluated": False,
        "evaluationOnly": True,
    }


def build(
    root: pathlib.Path,
    evidence_dir: pathlib.Path,
    output: pathlib.Path,
    *,
    opa: str | pathlib.Path | None = None,
    verified_evidence: list[VerifiedEvidence] | None = None,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    previous_hash = "0" * 64

    def append(record):
        nonlocal previous_hash
        if len(records) >= MAX_RECORDS:
            raise ValueError("Ledger record limit exceeded")
        record["previousHash"] = previous_hash
        record["recordHash"] = digest(record)
        previous_hash = record["recordHash"]
        records.append(record)

    def statement_record(source, index, statement, verification, proof=None):
        predicate = (
            statement.get("predicate")
            if isinstance(statement.get("predicate"), dict)
            else {}
        )
        run_details = (
            predicate.get("runDetails")
            if isinstance(predicate.get("runDetails"), dict)
            else {}
        )
        builder = (
            run_details.get("builder")
            if isinstance(run_details.get("builder"), dict)
            else {}
        )
        return {
            "source": source,
            "sourceIndex": index,
            "statement": statement,
            "statementDigest": digest(statement),
            "statementType": statement.get("_type"),
            "predicateType": statement.get("predicateType"),
            "subjects": statement.get("subject")
            if isinstance(statement.get("subject"), list)
            else [],
            "builderId": builder.get("id"),
            "verification": verification,
            "policy": evaluate({"statement": statement}, opa=opa, proof=proof),
        }

    for path in discover(root, evidence_dir):
        if path.resolve() == output.resolve():
            continue
        source = path.relative_to(evidence_dir).as_posix()
        try:
            values = objects_from_file(path)
        except (OSError, ValueError, RecursionError, UnicodeError) as exc:
            append(
                {
                    "source": source,
                    "ingestError": type(exc).__name__,
                    "policy": _blocked(
                        "attestation file could not be parsed within bounds"
                    ),
                }
            )
            continue
        for index, value in enumerate(values):
            statement, verification = decode_statement(value)
            if statement is None:
                append(
                    {
                        "source": source,
                        "sourceIndex": index,
                        "ingestError": "No valid statement extracted",
                        "policy": _blocked("no in-toto statement extracted"),
                    }
                )
            else:
                append(statement_record(source, index, statement, verification))
    for index, proof in enumerate(verified_evidence or []):
        if type(proof) is not VerifiedEvidence:
            raise ValueError(
                "Verified evidence must come directly from verify_artifact"
            )
        statement = proof.statement
        verification = proof_metadata(proof, statement)
        if verification.get("verified") is not True:
            raise ValueError("Invalid process-local verifier evidence")
        append(
            statement_record(
                "in-process-gh-attestation-verify",
                index,
                statement,
                verification,
                proof,
            )
        )
    counts = {"ALLOW": 0, "REVIEW": 0, "BLOCK": 0}
    for record in records:
        counts[record["policy"]["outcome"]] += 1
    ledger = {
        "schema": "szl.anatomy.ledger.v1",
        "generatedAt": dt.datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "recordCount": len(records),
        "outcomes": counts,
        "chainRoot": previous_hash if records else None,
        "records": records,
        "signatureStatus": "UNSIGNED",
        "externalAnchor": None,
        "disclosure": "Unsigned snapshot chain; internal consistency is not an independent trust anchor. Stored verification reports must be reverified before use as authority.",
    }
    if not validate_chain(ledger)["valid"]:
        raise ValueError("Generated ledger exceeds integrity or structural bounds")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(ledger, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    temporary.replace(output)
    return ledger


def validate_chain(ledger: Any) -> dict[str, Any]:
    """Recompute snapshot linkage and summary; never authenticate saved claims."""
    errors: list[str] = []
    result = {"valid": False, "errors": errors, "recordCount": 0, "anchored": False}
    if not isinstance(ledger, dict) or ledger.get("schema") != "szl.anatomy.ledger.v1":
        errors.append("Unsupported ledger schema")
        return result
    records = ledger.get("records")
    if not isinstance(records, list) or len(records) > MAX_RECORDS:
        errors.append("Ledger records are missing or exceed bounds")
        return result
    result["recordCount"] = len(records)
    previous = "0" * 64
    counts = {"ALLOW": 0, "REVIEW": 0, "BLOCK": 0}
    try:
        _bounded_shape(ledger)
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                errors.append(f"Record {index} is not an object")
                continue
            if record.get("previousHash") != previous:
                errors.append(f"Record {index} previousHash mismatch")
            content = {
                key: value for key, value in record.items() if key != "recordHash"
            }
            observed = digest(content)
            if record.get("recordHash") != observed:
                errors.append(f"Record {index} hash mismatch")
            previous = observed
            if "statement" in record and record.get("statementDigest") != digest(
                record["statement"]
            ):
                errors.append(f"Record {index} statement digest mismatch")
            policy = record.get("policy")
            outcome = policy.get("outcome") if isinstance(policy, dict) else None
            if not isinstance(outcome, str) or outcome not in counts:
                errors.append(f"Record {index} invalid outcome")
            else:
                counts[outcome] += 1
        if type(ledger.get("recordCount")) is not int or ledger["recordCount"] != len(
            records
        ):
            errors.append("recordCount mismatch")
        outcomes = ledger.get("outcomes")
        if (
            not isinstance(outcomes, dict)
            or set(outcomes) != set(counts)
            or any(
                type(outcomes.get(k)) is not int or outcomes[k] != v
                for k, v in counts.items()
            )
        ):
            errors.append("Outcome counts mismatch")
        if ledger.get("chainRoot") != (previous if records else None):
            errors.append("chainRoot mismatch")
    except (TypeError, ValueError, RecursionError):
        errors.append("Ledger contains invalid or excessive JSON")
    result["valid"] = not errors
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--evidence-dir", default="anatomy-ledger/evidence")
    parser.add_argument("--output", default="anatomy-ledger/public/data/ledger.json")
    parser.add_argument("--opa")
    parser.add_argument("--artifact")
    parser.add_argument("--repo")
    parser.add_argument("--workflow")
    parser.add_argument("--ref")
    parser.add_argument("--source-revision")
    parser.add_argument("--gh", default="gh")
    args = parser.parse_args()
    proofs = None
    if args.artifact:
        if not all((args.repo, args.workflow, args.ref)):
            parser.error("--artifact requires --repo, --workflow and --ref")
        proofs = verify_artifact(
            pathlib.Path(args.artifact),
            args.repo,
            args.workflow,
            args.ref,
            gh=args.gh,
            source_revision=args.source_revision,
        )
    root = pathlib.Path(args.root).resolve()
    ledger = build(
        root,
        (root / args.evidence_dir).resolve(),
        (root / args.output).resolve(),
        opa=args.opa,
        verified_evidence=proofs,
    )
    print(
        json.dumps(
            {
                "recordCount": ledger["recordCount"],
                "outcomes": ledger["outcomes"],
                "chainRoot": ledger["chainRoot"],
                "chainIntegrity": validate_chain(ledger),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
