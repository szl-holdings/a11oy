"""Adversarial review fixtures (Payload A / S2 execution, 2026-08-31).

Builds a fully VALID signed receipt using the demo backend, plus the
matching verifier. Every attack test mutates a copy of this envelope and
asserts the verifier does NOT output a passing verdict.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from a11oy.schemas import (
    Actor,
    Completeness,
    EvidenceItem,
    GovernedActionPredicate,
    GovernedActionReceipt,
    HumanApproval,
    ObservationWindow,
    PolicyDecisionRecord,
    RedactionCommitment,
    SideEffectClass,
    TIME_PROOF_UNAVAILABLE,
)
from a11oy.signing import DemoEd25519Backend
from a11oy.verifier import OfflineVerifier

SECRET_PLAINTEXT = b"database password hunter2 was visible in the log line"
SALT = os.urandom(32)


def build_valid_receipt() -> tuple[dict, str]:
    """Return (receipt_dict, expected_commitment_id)."""
    now = datetime.now(timezone.utc)
    commitment = RedactionCommitment.create(
        "rc-1", "predicate.evidence[0].uri", SECRET_PLAINTEXT, SALT
    )
    predicate = GovernedActionPredicate(
        action_id="act-adversarial-0001",
        actor=Actor(actor_id="u-stephen", display_name="Stephen Lutar"),
        action_type="deploy.patch",
        side_effect_class=SideEffectClass.REVERSIBLE,
        evidence=[
            EvidenceItem(
                evidence_id="ev-1",
                kind="test_log",
                sha256=hashlib.sha256(b"pytest: 59 passed").hexdigest(),
                description="test run output",
            ),
            EvidenceItem(
                evidence_id="ev-2",
                kind="review_thread",
                sha256=hashlib.sha256(b"approved in PR review").hexdigest(),
            ),
        ],
        completeness=Completeness.COMPLETE,
        redaction_commitments=[commitment],
        rfc3161_token=TIME_PROOF_UNAVAILABLE,
        ntp_synced=False,
    )
    receipt = GovernedActionReceipt(
        receipt_id="rcpt-adversarial-0001",
        predicate=predicate,
        decision=PolicyDecisionRecord(
            decision="ALLOW",
            reason="allowed by first matching rule deploy-allow",
            first_match_rule="deploy-allow",
            matched_rules=["deploy-allow"],
            evidence_obligations=["test_log"],
            effective_side_effect_class=SideEffectClass.REVERSIBLE,
            requires_human_approval=False,
        ),
        human_approval=None,
        observation_window=ObservationWindow(
            start=now, end=now + timedelta(minutes=30)
        ),
        retention_days=180,
        issued_at=now,
        generator="a11oy-adversarial-review/1.0",
    )
    return receipt.model_dump(mode="json"), commitment.commitment_id


@pytest.fixture()
def signed_envelope():
    receipt_dict, _ = build_valid_receipt()
    backend = DemoEd25519Backend()
    envelope = backend.sign(receipt_dict)
    verifier = OfflineVerifier({backend.keyid: backend.public_key_raw})
    return {
        "envelope": envelope,
        "verifier": verifier,
        "receipt_dict": receipt_dict,
        "keyid": backend.keyid,
    }


def decode_payload(envelope: dict) -> dict:
    return json.loads(base64.b64decode(envelope["payload"]).decode("utf-8"))


def reencode_payload(envelope: dict, receipt_dict: dict) -> dict:
    """Mutate the payload bytes WITHOUT re-signing (attacker has no key)."""
    env = copy.deepcopy(envelope)
    env["payload"] = base64.b64encode(
        json.dumps(receipt_dict, sort_keys=True, separators=(",", ":")).encode()
    ).decode("ascii")
    return env
