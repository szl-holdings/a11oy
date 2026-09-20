#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import pathlib
import sys
from typing import Any

UTC = dt.timezone.utc
SKIP = {".git", "node_modules", ".venv", "venv", "dist", "__pycache__"}
PATTERNS = ("*.intoto.json", "*.intoto.jsonl", "*attestation*.json", "*provenance*.json")

ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from evaluate_supply_chain import evaluate  # noqa: E402


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def decode_statement(value: Any) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    if not isinstance(value, dict):
        return None, {}
    verification = value.get("verification") if isinstance(value.get("verification"), dict) else {}
    if value.get("_type") == "https://in-toto.io/Statement/v1":
        return value, verification
    if "payload" in value and "payloadType" in value:
        try:
            statement = json.loads(base64.b64decode(value["payload"]))
            verification = {
                **verification,
                "envelopePresent": True,
                "signatureCount": len(value.get("signatures") or []),
                "verified": bool(verification.get("verified", False)),
            }
            return statement, verification
        except Exception:
            return None, verification
    for key in ("statement", "attestation"):
        candidate = value.get(key)
        if isinstance(candidate, dict):
            return decode_statement(candidate)
    return None, verification


def objects_from_file(path: pathlib.Path) -> list[Any]:
    text = path.read_text(encoding="utf-8", errors="strict")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    value = json.loads(text)
    return value if isinstance(value, list) else [value]


def discover(root: pathlib.Path, evidence_dir: pathlib.Path) -> list[pathlib.Path]:
    paths: set[pathlib.Path] = set()
    for base in {evidence_dir, root}:
        if not base.exists():
            continue
        for pattern in PATTERNS:
            for path in base.rglob(pattern):
                if any(part in SKIP for part in path.parts):
                    continue
                if "public/data/ledger.json" in path.as_posix():
                    continue
                paths.add(path.resolve())
    return sorted(paths)


def build(root: pathlib.Path, evidence_dir: pathlib.Path, output: pathlib.Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    previous_hash = "0" * 64
    for path in discover(root, evidence_dir):
        rel = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
        try:
            values = objects_from_file(path)
        except Exception as exc:
            base = {
                "source": rel,
                "ingestError": str(exc),
                "policy": {"outcome": "BLOCK", "deny": ["attestation file could not be parsed"], "review": []},
                "previousHash": previous_hash,
            }
            base["recordHash"] = digest(base)
            previous_hash = base["recordHash"]
            records.append(base)
            continue
        for index, value in enumerate(values):
            statement, verification = decode_statement(value)
            if statement is None:
                base = {
                    "source": rel,
                    "sourceIndex": index,
                    "ingestError": "No in-toto Statement/v1 could be extracted",
                    "policy": {"outcome": "BLOCK", "deny": ["no statement extracted"], "review": []},
                    "previousHash": previous_hash,
                }
            else:
                decision = evaluate({"statement": statement, "verification": verification})
                predicate = statement.get("predicate") if isinstance(statement.get("predicate"), dict) else {}
                builder = (predicate.get("runDetails") or {}).get("builder") if isinstance(predicate.get("runDetails"), dict) else {}
                base = {
                    "source": rel,
                    "sourceIndex": index,
                    "statementDigest": digest(statement),
                    "statementType": statement.get("_type"),
                    "predicateType": statement.get("predicateType"),
                    "subjects": statement.get("subject") or [],
                    "builderId": (builder or {}).get("id") if isinstance(builder, dict) else None,
                    "verification": verification,
                    "policy": decision,
                    "previousHash": previous_hash,
                }
            base["recordHash"] = digest(base)
            previous_hash = base["recordHash"]
            records.append(base)
    counts = {"ALLOW": 0, "REVIEW": 0, "BLOCK": 0}
    for record in records:
        outcome = (record.get("policy") or {}).get("outcome", "BLOCK")
        counts[outcome] = counts.get(outcome, 0) + 1
    ledger = {
        "schema": "szl.anatomy.ledger.v1",
        "generatedAt": dt.datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "recordCount": len(records),
        "outcomes": counts,
        "chainRoot": previous_hash if records else None,
        "records": records,
        "disclosure": (
            "recordHash/previousHash provides tamper evidence only. "
            "Cryptographic verification is true only with explicit verifier output. "
            "DSSE envelope presence is not verification."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    return ledger


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--evidence-dir", default="anatomy-ledger/evidence")
    parser.add_argument("--output", default="anatomy-ledger/public/data/ledger.json")
    args = parser.parse_args()
    root = pathlib.Path(args.root).resolve()
    ledger = build(root, (root / args.evidence_dir).resolve(), (root / args.output).resolve())
    print(json.dumps({"recordCount": ledger["recordCount"], "outcomes": ledger["outcomes"], "chainRoot": ledger["chainRoot"]}, indent=2))


if __name__ == "__main__":
    main()
