from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from a11oy_council import Assessment, Decision, HashChainLedger, MemberIdentity, Role, make_commitment
from a11oy_council.cli import command_commit, command_evaluate, command_verify_ledger, main


NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
EVIDENCE = "evidence://required"


def member(role: Role, suffix: str) -> MemberIdentity:
    return MemberIdentity(
        member_id=f"member-{suffix}",
        role=role,
        operator_id=f"operator-{suffix}",
        key_id=f"key-{suffix}",
        model_lineage=f"lineage-{suffix}",
        implementation_id=f"implementation-{suffix}",
        provider_id=f"provider-{suffix}",
        retrieval_path=f"retrieval-{suffix}",
        evidence_domain=f"evidence-{suffix}",
        trust_domain=f"trust-{suffix}",
    )


def value() -> Assessment:
    return Assessment(
        recommendation=Decision.ACT,
        confidence=0.9,
        claims=("bounded claim",),
        evidence=(EVIDENCE,),
    )


def reveal_document(identity: MemberIdentity, item: Assessment, nonce: str) -> dict[str, object]:
    commitment = make_commitment(identity, item, nonce)
    return {
        "member": identity.canonical_dict(),
        "assessment": item.canonical_dict(),
        "nonce": nonce,
        "commitment": {
            "member_id": commitment.member_id,
            "digest": commitment.digest,
        },
    }


class CliTests(unittest.TestCase):
    def test_commit_command_returns_matching_digest(self) -> None:
        identity = member(Role.AUTHORITY, "authority")
        item = value()
        document = {
            "member": identity.canonical_dict(),
            "assessment": item.canonical_dict(),
            "nonce": "nonce-authority-123456",
        }
        result = command_commit(document)
        expected = make_commitment(identity, item, document["nonce"])
        self.assertEqual(result["member_id"], identity.member_id)
        self.assertEqual(result["digest"], expected.digest)

    def test_evaluate_command_compiles_act(self) -> None:
        identities = (
            member(Role.AUTHORITY, "authority"),
            member(Role.SENTINEL, "sentinel"),
            member(Role.VERIFIER, "verifier"),
            member(Role.VALUE, "value"),
        )
        reveals = [
            reveal_document(identity, value(), f"nonce-{index}-123456")
            for index, identity in enumerate(identities)
        ]
        document = {
            "proposal": {
                "proposal_id": "proposal-1",
                "action": "apply_patch",
                "target": "repo://szl-holdings/a11oy",
                "capability": "source.write",
                "risk_class": "B",
                "estimated_cost_microunits": 100,
                "evidence_requirements": [EVIDENCE],
                "metadata": {},
            },
            "reveals": reveals,
            "grants": [
                {
                    "grant_id": "grant-1",
                    "subject": "council-alpha",
                    "capabilities": ["source.write"],
                    "actions": ["apply_patch"],
                    "exact_targets": ["repo://szl-holdings/a11oy"],
                    "budget_microunits": 1_000,
                    "expires_at": (NOW + timedelta(days=1)).isoformat(),
                    "revoked": False,
                }
            ],
            "spent_by_grant": {},
            "now": NOW.isoformat(),
        }
        result = command_evaluate(document)
        self.assertEqual(result["decision"], "ACT")
        self.assertEqual(result["grant_id"], "grant-1")
        self.assertEqual(len(result["decision_digest"]), 64)

    def test_verify_ledger_command_reports_head(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "council.jsonl"
            ledger = HashChainLedger(path)
            entry = ledger.append("decision", {"decision": "ACT"})
            result = command_verify_ledger(str(path))
            self.assertTrue(result["valid"])
            self.assertEqual(result["entries"], 1)
            self.assertEqual(result["head"], entry.entry_hash)

    def test_main_fails_closed_for_invalid_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text("[]", encoding="utf-8")
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = main(["commit", str(path)])
            self.assertEqual(result, 2)
            self.assertEqual(stdout.getvalue(), "")
            error = json.loads(stderr.getvalue())
            self.assertEqual(error["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
