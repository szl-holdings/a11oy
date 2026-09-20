#!/usr/bin/env python3
"""Python twin of anatomy.supplychain Rego. Same ALLOW/REVIEW/BLOCK contract."""
from __future__ import annotations

import argparse
import json
import re
from typing import Any

SHA256_RE = re.compile(r"^[a-fA-F0-9]{64}$")
STATEMENT_V1 = "https://in-toto.io/Statement/v1"
SLSA_PREFIX = "https://slsa.dev/provenance/"


def _obj(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def evaluate(payload: dict[str, Any]) -> dict[str, Any]:
    statement = _obj(payload.get("statement"))
    verification = _obj(payload.get("verification"))
    predicate = _obj(statement.get("predicate"))
    builder = _obj(_obj(predicate.get("runDetails")).get("builder"))
    build_definition = _obj(predicate.get("buildDefinition"))
    valid_statement_type = statement.get("_type") == STATEMENT_V1
    subjects = statement.get("subject") if isinstance(statement.get("subject"), list) else []
    valid_subject_digest = any(
        SHA256_RE.match(str(_obj(_obj(subject).get("digest")).get("sha256", "")))
        for subject in subjects
        if isinstance(subject, dict)
    )
    is_slsa = str(statement.get("predicateType") or "").startswith(SLSA_PREFIX)
    verified = verification.get("verified") is True
    deny: list[str] = []
    review: list[str] = []
    if not valid_statement_type:
        deny.append("statement type is not in-toto Statement/v1")
    if not valid_subject_digest:
        deny.append("no subject has a valid SHA-256 digest")
    if is_slsa and not build_definition:
        deny.append("SLSA provenance is missing buildDefinition")
    if is_slsa and not str(builder.get("id") or ""):
        deny.append("SLSA provenance is missing runDetails.builder.id")
    if valid_statement_type and not is_slsa:
        review.append("predicate is not SLSA provenance")
    if valid_statement_type and not verified:
        review.append("cryptographic verification has not been proven")
    outcome = "BLOCK" if deny else ("REVIEW" if review else "ALLOW")
    return {
        "outcome": outcome,
        "deny": sorted(deny),
        "review": sorted(review),
        "verified": verified,
        "slsa": is_slsa,
        "evaluator": "python-twin",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    with open(args.input, encoding="utf-8") as handle:
        payload = json.load(handle)
    print(json.dumps(evaluate(payload), indent=2))


if __name__ == "__main__":
    main()
