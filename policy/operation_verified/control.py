# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Finite policy model and cryptographically bound authorization receipts.

The issuer owns an injected ECDSA private key. Workers receive only a public key,
so an execution worker cannot mint its own authorization.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_TRACE = re.compile(r"^[0-9a-f]{32}$")
_PRINCIPAL = re.compile(r"^(agent|human|workload):[A-Za-z0-9][A-Za-z0-9._:/-]{2,127}$")
_ALLOWED_ACTIONS = frozenset(
    {
        "deploy.staging",
        "deploy.production",
        "secret.rotate",
        "identity.change",
        "policy.change",
        "database.migrate",
        "traffic.change",
        "ruleset.change",
        "admission.change",
        "model.promote",
        "benchmark.publish",
        "claim.upgrade",
        "infrastructure.destroy",
    }
)
_HIGH_RISK = _ALLOWED_ACTIONS - {"deploy.staging"}
_STATES = (
    "PROPOSED",
    "SCHEMA_VALIDATED",
    "POLICY_EVALUATED",
    "APPROVAL_REQUIRED",
    "AUTHORIZED",
    "REJECTED",
    "EXECUTING",
    "VERIFIED",
    "COMMITTED",
    "DEPLOYED",
    "OBSERVED",
    "CLOSED",
    "ROLLED_BACK",
)
_TRANSITIONS = {
    "PROPOSED": {"SCHEMA_VALIDATED", "REJECTED"},
    "SCHEMA_VALIDATED": {"POLICY_EVALUATED", "REJECTED"},
    "POLICY_EVALUATED": {"APPROVAL_REQUIRED", "AUTHORIZED", "REJECTED"},
    "APPROVAL_REQUIRED": {"AUTHORIZED", "REJECTED"},
    "AUTHORIZED": {"EXECUTING", "REJECTED"},
    "EXECUTING": {"VERIFIED", "ROLLED_BACK"},
    "VERIFIED": {"COMMITTED", "ROLLED_BACK"},
    "COMMITTED": {"DEPLOYED", "CLOSED", "ROLLED_BACK"},
    "DEPLOYED": {"OBSERVED", "ROLLED_BACK"},
    "OBSERVED": {"CLOSED", "ROLLED_BACK"},
    "REJECTED": {"CLOSED"},
    "CLOSED": set(),
    "ROLLED_BACK": {"CLOSED"},
}


class AuthorizationError(ValueError):
    """A fail-closed validation or authorization failure."""


class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise AuthorizationError("timestamp must include an offset")
    return parsed.astimezone(timezone.utc)


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def canonical_digest(value: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64url(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def validate_request(request: Mapping[str, Any], now: datetime) -> None:
    required = {
        "request_id",
        "trace_id",
        "principal",
        "action_type",
        "target",
        "source_commit",
        "artifact_digest",
        "requested_transition",
        "preconditions",
        "test_receipts",
        "provenance_receipt",
        "security_receipts",
        "blast_radius",
        "rollback",
        "human_approvals",
        "expires_at",
    }
    unknown = set(request) - required
    missing = required - set(request)
    if missing or unknown:
        raise AuthorizationError(f"request shape invalid; missing={sorted(missing)}, unknown={sorted(unknown)}")
    if request["action_type"] not in _ALLOWED_ACTIONS:
        raise AuthorizationError("unsupported action type")
    if not _TRACE.fullmatch(str(request["trace_id"])):
        raise AuthorizationError("malformed trace id")
    if not _PRINCIPAL.fullmatch(str(request["principal"])):
        raise AuthorizationError("malformed principal")
    if not _SHA.fullmatch(str(request["source_commit"])):
        raise AuthorizationError("source commit must be immutable")
    if not _DIGEST.fullmatch(str(request["artifact_digest"])):
        raise AuthorizationError("artifact digest must be immutable")
    target = str(request["target"])
    if "@sha256:" not in target or not _DIGEST.fullmatch("sha256:" + target.rsplit("@sha256:", 1)[1]):
        raise AuthorizationError("target must be an immutable digest reference")
    if _utc(str(request["expires_at"])) <= now.astimezone(timezone.utc):
        raise AuthorizationError("request expired")
    transition = request["requested_transition"]
    if not isinstance(transition, Mapping) or set(transition) != {"from", "to"}:
        raise AuthorizationError("transition shape invalid")


@dataclass(frozen=True)
class PolicyEvaluator:
    """Finite runtime model corresponding to the Lean T1/T2 boundary."""

    allowed_principals: frozenset[str]
    policy_version: str
    formal_artifact_digest: str
    revoked_principals: frozenset[str] = frozenset()
    revoked_policy_versions: frozenset[str] = frozenset()

    def decide(self, request: Mapping[str, Any], now: datetime) -> tuple[Decision, str]:
        try:
            validate_request(request, now)
        except AuthorizationError as exc:
            return Decision.DENY, str(exc)
        principal = str(request["principal"])
        if principal not in self.allowed_principals:
            return Decision.DENY, "no matching authorization rule"
        if principal in self.revoked_principals or self.policy_version in self.revoked_policy_versions:
            return Decision.DENY, "principal or policy is revoked"
        to_environment = str(request["requested_transition"]["to"])
        if to_environment not in {"staging", "production"}:
            return Decision.DENY, "target environment is not executable"
        if request["action_type"] in _HIGH_RISK and not request["human_approvals"]:
            return Decision.DENY, "valid human approval required"
        if to_environment == "production":
            if not request["provenance_receipt"]:
                return Decision.DENY, "accepted provenance required"
            rollback = request["rollback"]
            if not isinstance(rollback, Mapping) or not _DIGEST.fullmatch(str(rollback.get("target_digest", ""))):
                return Decision.DENY, "immutable rollback target required"
        return Decision.ALLOW, "matching authorization rule"


class AppendOnlyLifecycle:
    """Append-only transition log with explicit allowed edges."""

    def __init__(self, request_id: str):
        self._events: list[dict[str, str]] = []
        self.request_id = request_id

    @property
    def events(self) -> tuple[Mapping[str, str], ...]:
        return tuple(dict(event) for event in self._events)

    def append(self, state: str, at: str) -> None:
        if state not in _STATES:
            raise AuthorizationError("unknown lifecycle state")
        if not self._events:
            if state != "PROPOSED":
                raise AuthorizationError("lifecycle must begin at PROPOSED")
        elif state not in _TRANSITIONS[self._events[-1]["state"]]:
            raise AuthorizationError(f"invalid lifecycle transition to {state}")
        _utc(at)
        self._events.append({"request_id": self.request_id, "state": state, "at": at})


class ReceiptIssuer:
    """Authorization service; the only component that accepts a private key."""

    def __init__(self, private_key: ec.EllipticCurvePrivateKey, evaluator: PolicyEvaluator):
        if not isinstance(private_key, ec.EllipticCurvePrivateKey):
            raise TypeError("an ECDSA private key is required")
        self._key = private_key
        self._evaluator = evaluator

    def issue(self, request: Mapping[str, Any], now: datetime) -> dict[str, str]:
        decision, reason = self._evaluator.decide(request, now)
        if decision is not Decision.ALLOW:
            raise AuthorizationError(f"DENY: {reason}")
        expires = _utc(str(request["expires_at"]))
        issued = now.astimezone(timezone.utc)
        environment = str(request["requested_transition"]["to"])
        unsigned = {
            "decision": "ALLOW",
            "request_digest": canonical_digest(request),
            "policy_version": self._evaluator.policy_version,
            "formal_artifact_digest": self._evaluator.formal_artifact_digest,
            "principal": str(request["principal"]),
            "target_digest": str(request["artifact_digest"]),
            "environment": environment,
            "issued_at": issued.isoformat().replace("+00:00", "Z"),
            "expires_at": expires.isoformat().replace("+00:00", "Z"),
            "trace_id": str(request["trace_id"]),
        }
        signature = self._key.sign(_canonical(unsigned), ec.ECDSA(hashes.SHA256()))
        return {**unsigned, "signature": _b64url(signature)}


class WorkerVerifier:
    """Execution-side verifier. It intentionally has no signing capability."""

    def __init__(self, public_key: ec.EllipticCurvePublicKey):
        if not isinstance(public_key, ec.EllipticCurvePublicKey):
            raise TypeError("an ECDSA public key is required")
        self._key = public_key

    def authorize(
        self,
        receipt: Mapping[str, Any],
        request: Mapping[str, Any],
        *,
        expected_environment: str,
        expected_principal: str,
        expected_target_digest: str,
        expected_policy_version: str,
        revoked_principals: Iterable[str] = (),
        revoked_policy_versions: Iterable[str] = (),
        now: datetime,
    ) -> bool:
        fields = {
            "decision",
            "request_digest",
            "policy_version",
            "formal_artifact_digest",
            "principal",
            "target_digest",
            "environment",
            "issued_at",
            "expires_at",
            "trace_id",
            "signature",
        }
        if set(receipt) != fields or receipt.get("decision") != "ALLOW":
            raise AuthorizationError("receipt shape or decision invalid")
        if receipt["request_digest"] != canonical_digest(request):
            raise AuthorizationError("request digest mismatch")
        expected = {
            "environment": expected_environment,
            "principal": expected_principal,
            "target_digest": expected_target_digest,
            "policy_version": expected_policy_version,
        }
        for key, value in expected.items():
            if receipt[key] != value:
                raise AuthorizationError(f"{key} binding mismatch")
        if receipt["principal"] in set(revoked_principals) or receipt["policy_version"] in set(revoked_policy_versions):
            raise AuthorizationError("receipt binding revoked")
        if _utc(str(receipt["expires_at"])) <= now.astimezone(timezone.utc):
            raise AuthorizationError("receipt expired")
        unsigned = {key: receipt[key] for key in fields - {"signature"}}
        try:
            self._key.verify(_unb64url(str(receipt["signature"])), _canonical(unsigned), ec.ECDSA(hashes.SHA256()))
        except (InvalidSignature, ValueError) as exc:
            raise AuthorizationError("receipt signature invalid") from exc
        return True
