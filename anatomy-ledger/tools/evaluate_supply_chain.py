#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Audit untrusted evidence with optional OPA and process-local verifier proof.

JSON input cannot confer verification. The Python structural checker is an
advisory fallback, not a Rego interpreter, and can never return ALLOW.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from verify_release import proof_metadata

SHA256_RE = re.compile(r"^[a-fA-F0-9]{64}$")
STATEMENT_V1 = "https://in-toto.io/Statement/v1"
SLSA_V1 = "https://slsa.dev/provenance/v1"
MAX_INPUT_BYTES = 1024 * 1024
POLICY = ROOT.parent / "policy" / "rego" / "supply_chain.rego"


def _obj(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _structural(statement: Any) -> tuple[list[str], list[str], bool]:
    statement = _obj(statement)
    deny, review = [], []
    if statement.get("_type") != STATEMENT_V1:
        deny.append("statement type is not in-toto Statement/v1")
    subjects = statement.get("subject")
    valid_subjects = isinstance(subjects, list) and 1 <= len(subjects) <= 1000
    if valid_subjects:
        for subject in subjects:
            subject = _obj(subject)
            sha = _obj(subject.get("digest")).get("sha256")
            if (
                not isinstance(subject.get("name"), str)
                or not subject["name"]
                or not isinstance(sha, str)
                or not SHA256_RE.fullmatch(sha)
            ):
                valid_subjects = False
                break
    if not valid_subjects:
        deny.append("every subject must have a name and valid SHA-256 digest")
    predicate_type = statement.get("predicateType")
    if not isinstance(predicate_type, str) or not predicate_type:
        deny.append("predicateType must be a nonempty string")
    if not isinstance(statement.get("predicate"), dict):
        deny.append("predicate must be an object")
    is_slsa = predicate_type == SLSA_V1
    predicate = _obj(statement.get("predicate"))
    if is_slsa:
        definition = _obj(predicate.get("buildDefinition"))
        build_type = definition.get("buildType")
        if not isinstance(build_type, str) or not build_type:
            deny.append("SLSA provenance is missing buildDefinition.buildType")
        builder_id = _obj(_obj(predicate.get("runDetails")).get("builder")).get("id")
        if not isinstance(builder_id, str) or not builder_id:
            deny.append("SLSA provenance is missing runDetails.builder.id")
    else:
        review.append("predicate is not supported SLSA provenance/v1")
    return deny, review, is_slsa


def evaluate(
    payload: Any, *, opa: str | pathlib.Path | None = None, proof: Any = None
) -> dict[str, Any]:
    """Evaluate JSON; only fresh VerifiedEvidence supplies authority.

    Rego's verification object is a trusted internal projection produced here.
    It is never copied from payload, including for CLI and HTTP callers.
    """
    statement = _obj(payload).get("statement")
    deny, review, is_slsa = _structural(statement)
    verification = proof_metadata(proof, statement)
    verified = verification.get("verified") is True
    if not verified:
        review.append("cryptographic verification has not been proven")
    base = {
        "outcome": "BLOCK" if deny else "REVIEW",
        "deny": sorted(deny),
        "review": sorted(review),
        "verified": verified,
        "slsa": is_slsa,
        "evaluator": "python-structural-advisory",
        "policyEvaluated": False,
        "evaluationOnly": True,
    }
    try:
        serialized = json.dumps(
            {"statement": statement, "verification": verification}, allow_nan=False
        )
        if len(serialized.encode("utf-8")) > MAX_INPUT_BYTES:
            raise ValueError("input too large")
    except (TypeError, ValueError, RecursionError):
        base.update(
            outcome="BLOCK", deny=["evidence exceeds bounds or is not strict JSON"]
        )
        return base
    if opa is None:
        base["review"] = sorted(
            set(base["review"] + ["OPA unavailable; policy not evaluated"])
        )
        return base
    try:
        result = subprocess.run(
            [
                str(opa),
                "eval",
                "--format=json",
                "--stdin-input",
                "--data",
                str(POLICY),
                "data.anatomy.supplychain.decision",
            ],
            input=serialized,
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
        if (
            result.returncode != 0
            or len(result.stdout.encode("utf-8")) > MAX_INPUT_BYTES
        ):
            raise ValueError("OPA process failed or exceeded output bounds")
        parsed = json.loads(result.stdout)
        decision = parsed["result"][0]["expressions"][0]["value"]
        if not isinstance(decision, dict) or decision.get("outcome") not in {
            "ALLOW",
            "REVIEW",
            "BLOCK",
        }:
            raise ValueError("OPA decision is undefined or malformed")
        if any(
            not isinstance(decision.get(key), list)
            or not all(isinstance(x, str) for x in decision[key])
            for key in ("deny", "review")
        ):
            raise ValueError("OPA reasons are malformed")
        if (
            decision.get("verified") is not verified
            or decision.get("slsa") is not is_slsa
        ):
            raise ValueError("OPA facts differ from verified input")
        if decision["outcome"] == "ALLOW" and (deny or review or not verified):
            raise ValueError("OPA attempted to allow invalid or unverified evidence")
        if deny and decision["outcome"] != "BLOCK":
            raise ValueError("OPA did not block malformed evidence")
        decision.update(evaluator="opa", policyEvaluated=True, evaluationOnly=True)
        return decision
    except (
        OSError,
        subprocess.TimeoutExpired,
        ValueError,
        KeyError,
        IndexError,
        TypeError,
        RecursionError,
    ):
        base.update(
            outcome="BLOCK",
            deny=sorted(
                set(deny + ["OPA evaluation failed or returned an invalid decision"])
            ),
            evaluator="opa-error",
            policyEvaluated=False,
        )
        return base


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--opa")
    args = parser.parse_args()
    with open(args.input, "rb") as handle:
        raw = handle.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise SystemExit("Evidence exceeds size limit")
    print(json.dumps(evaluate(json.loads(raw), opa=args.opa), indent=2))


if __name__ == "__main__":
    main()
