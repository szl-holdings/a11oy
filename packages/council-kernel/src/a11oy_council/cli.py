"""File-driven CLI for deterministic Council commitments and evaluation."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

from .kernel import (
    Assessment,
    CapabilityGrant,
    Commitment,
    CouncilKernel,
    CouncilPolicy,
    Decision,
    HashChainLedger,
    LedgerIntegrityError,
    MemberIdentity,
    Proposal,
    Reveal,
    RiskClass,
    Role,
    canonical_json,
    make_commitment,
)


def _read_json(path: str) -> Mapping[str, Any]:
    if path == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(path).read_text(encoding="utf-8")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("input document must be a JSON object")
    return value


def _datetime(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("datetime values must contain an offset")
    return parsed


def _member(raw: Mapping[str, Any]) -> MemberIdentity:
    return MemberIdentity(
        member_id=str(raw["member_id"]),
        role=Role(str(raw["role"])),
        operator_id=str(raw["operator_id"]),
        key_id=str(raw["key_id"]),
        model_lineage=str(raw["model_lineage"]),
        implementation_id=str(raw["implementation_id"]),
        provider_id=str(raw["provider_id"]),
        retrieval_path=str(raw["retrieval_path"]),
        evidence_domain=str(raw["evidence_domain"]),
        trust_domain=str(raw["trust_domain"]),
    )


def _assessment(raw: Mapping[str, Any]) -> Assessment:
    return Assessment(
        recommendation=Decision(str(raw["recommendation"])),
        confidence=float(raw["confidence"]),
        claims=tuple(str(value) for value in raw.get("claims", ())),
        evidence=tuple(str(value) for value in raw.get("evidence", ())),
        objections=tuple(str(value) for value in raw.get("objections", ())),
        veto=bool(raw.get("veto", False)),
    )


def _proposal(raw: Mapping[str, Any]) -> Proposal:
    metadata_raw = raw.get("metadata", {})
    if not isinstance(metadata_raw, dict):
        raise ValueError("proposal metadata must be an object")
    return Proposal(
        proposal_id=str(raw["proposal_id"]),
        action=str(raw["action"]),
        target=str(raw["target"]),
        capability=str(raw["capability"]),
        risk_class=RiskClass(str(raw["risk_class"])),
        estimated_cost_microunits=int(raw["estimated_cost_microunits"]),
        evidence_requirements=tuple(
            str(value) for value in raw.get("evidence_requirements", ())
        ),
        metadata=tuple(sorted((str(key), str(value)) for key, value in metadata_raw.items())),
    )


def _grant(raw: Mapping[str, Any]) -> CapabilityGrant:
    return CapabilityGrant(
        grant_id=str(raw["grant_id"]),
        subject=str(raw["subject"]),
        capabilities=tuple(str(value) for value in raw["capabilities"]),
        actions=tuple(str(value) for value in raw["actions"]),
        exact_targets=tuple(str(value) for value in raw["exact_targets"]),
        budget_microunits=int(raw["budget_microunits"]),
        expires_at=_datetime(str(raw["expires_at"])),
        revoked=bool(raw.get("revoked", False)),
    )


def _policy(raw: Mapping[str, Any] | None) -> CouncilPolicy:
    if raw is None:
        return CouncilPolicy()
    return CouncilPolicy(
        required_roles=frozenset(Role(str(value)) for value in raw.get("required_roles", [
            Role.AUTHORITY.value,
            Role.SENTINEL.value,
            Role.VERIFIER.value,
            Role.VALUE.value,
        ])),
        minimum_effective_size=float(raw.get("minimum_effective_size", 2.5)),
        act_score_threshold=float(raw.get("act_score_threshold", 0.67)),
        minimum_evidence_per_member=int(raw.get("minimum_evidence_per_member", 1)),
        maximum_autonomous_risk=Risk(str(raw.get("maximum_autonomous_risk", "B"))),
    )


# Kept as a separate alias to make invalid policy values fail at the parser boundary.
Risk = RiskClass


def command_commit(document: Mapping[str, Any]) -> Mapping[str, Any]:
    identity_raw = document["member"]
    assessment_raw = document["assessment"]
    if not isinstance(identity_raw, dict) or not isinstance(assessment_raw, dict):
        raise ValueError("member and assessment must be objects")
    identity = _member(identity_raw)
    value = _assessment(assessment_raw)
    commitment = make_commitment(identity, value, str(document["nonce"]))
    return {"member_id": commitment.member_id, "digest": commitment.digest}


def command_evaluate(document: Mapping[str, Any]) -> Mapping[str, Any]:
    proposal_raw = document["proposal"]
    reveal_values = document["reveals"]
    grant_values = document["grants"]
    if not isinstance(proposal_raw, dict):
        raise ValueError("proposal must be an object")
    if not isinstance(reveal_values, list) or not isinstance(grant_values, list):
        raise ValueError("reveals and grants must be arrays")

    parsed_reveals: list[Reveal] = []
    for item in reveal_values:
        if not isinstance(item, dict):
            raise ValueError("each reveal must be an object")
        member_raw = item["member"]
        assessment_raw = item["assessment"]
        commitment_raw = item["commitment"]
        if not all(isinstance(value, dict) for value in (member_raw, assessment_raw, commitment_raw)):
            raise ValueError("reveal member, assessment, and commitment must be objects")
        parsed_reveals.append(
            Reveal(
                member=_member(member_raw),
                assessment=_assessment(assessment_raw),
                nonce=str(item["nonce"]),
                commitment=Commitment(
                    member_id=str(commitment_raw["member_id"]),
                    digest=str(commitment_raw["digest"]),
                ),
            )
        )

    parsed_grants = []
    for item in grant_values:
        if not isinstance(item, dict):
            raise ValueError("each grant must be an object")
        parsed_grants.append(_grant(item))

    policy_raw = document.get("policy")
    if policy_raw is not None and not isinstance(policy_raw, dict):
        raise ValueError("policy must be an object")
    spent_raw = document.get("spent_by_grant", {})
    if not isinstance(spent_raw, dict):
        raise ValueError("spent_by_grant must be an object")

    record = CouncilKernel(_policy(policy_raw)).evaluate(
        _proposal(proposal_raw),
        tuple(parsed_reveals),
        tuple(parsed_grants),
        now=_datetime(str(document["now"])),
        spent_by_grant={str(key): int(value) for key, value in spent_raw.items()},
    )
    return record.canonical_dict()


def command_verify_ledger(path: str) -> Mapping[str, Any]:
    ledger = HashChainLedger(path)
    entries = ledger.entries
    return {
        "valid": ledger.verify(),
        "entries": len(entries),
        "head": entries[-1].entry_hash if entries else HashChainLedger.GENESIS_HASH,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="a11oy-council")
    subparsers = parser.add_subparsers(dest="command", required=True)

    commit_parser = subparsers.add_parser("commit", help="create an assessment commitment")
    commit_parser.add_argument("input", help="JSON file or - for stdin")

    evaluate_parser = subparsers.add_parser("evaluate", help="compile a Council decision")
    evaluate_parser.add_argument("input", help="JSON file or - for stdin")

    ledger_parser = subparsers.add_parser("verify-ledger", help="verify a Council JSONL ledger")
    ledger_parser.add_argument("path", help="ledger path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "commit":
            result = command_commit(_read_json(args.input))
        elif args.command == "evaluate":
            result = command_evaluate(_read_json(args.input))
        else:
            result = command_verify_ledger(args.path)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, LedgerIntegrityError) as exc:
        print(canonical_json({"error": str(exc), "status": "BLOCKED"}), file=sys.stderr)
        return 2

    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
