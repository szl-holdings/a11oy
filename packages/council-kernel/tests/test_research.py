from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import unittest

from a11oy_council.research import (
    PromotionState,
    ReproductionState,
    ResearchArtifact,
    ResearchFoundry,
    ResearchSource,
    RightsStatus,
    SourceKind,
    artifact_bundle_digest,
    source_bundle_digest,
)


NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
CONTENT_HASH = hashlib.sha256(b"source-content").hexdigest()
REPRODUCER_HASH = hashlib.sha256(b"reproducer").hexdigest()
GIT_REVISION = "a" * 40


def source(
    *,
    source_id: str = "source-1",
    kind: SourceKind = SourceKind.GITHUB,
    revision: str = GIT_REVISION,
    rights: RightsStatus = RightsStatus.ALLOWED,
    license_expression: str | None = "Apache-2.0",
) -> ResearchSource:
    return ResearchSource(
        source_id=source_id,
        kind=kind,
        uri="https://example.invalid/source",
        immutable_revision=revision,
        content_sha256=CONTENT_HASH,
        retrieved_at=NOW,
        rights_status=rights,
        license_expression=license_expression,
    )


def artifact(
    *,
    artifact_id: str = "artifact-1",
    item_source: ResearchSource | None = None,
    reproduction: ReproductionState = ReproductionState.PASS,
    claims: tuple[str, ...] = ("bounded finding",),
    evidence: tuple[str, ...] = ("evidence://reproduction",),
) -> ResearchArtifact:
    return ResearchArtifact(
        artifact_id=artifact_id,
        source=item_source or source(),
        normalized_summary="Normalized source summary.",
        extracted_claims=claims,
        evidence_refs=evidence,
        reproduction_state=reproduction,
        reproducer_digest=(
            REPRODUCER_HASH if reproduction is ReproductionState.PASS else None
        ),
        limitations=("single-source result",),
    )


class ResearchSourceTests(unittest.TestCase):
    def test_git_sources_require_full_commit_hash(self) -> None:
        with self.assertRaises(ValueError):
            source(revision="abc123")

    def test_arxiv_sources_require_explicit_version(self) -> None:
        with self.assertRaises(ValueError):
            source(kind=SourceKind.ARXIV, revision="2406.04692")
        accepted = source(kind=SourceKind.ARXIV, revision="2406.04692v2")
        self.assertEqual(accepted.immutable_revision, "2406.04692v2")

    def test_source_bundle_digest_is_order_independent(self) -> None:
        first = source(source_id="a")
        second = source(source_id="b", revision="b" * 40)
        self.assertEqual(
            source_bundle_digest((first, second)),
            source_bundle_digest((second, first)),
        )


class ResearchFoundryTests(unittest.TestCase):
    def test_admission_is_always_quarantined(self) -> None:
        foundry = ResearchFoundry()
        disposition = foundry.admit(artifact())
        self.assertEqual(disposition.state, PromotionState.QUARANTINED)
        self.assertTrue(foundry.ledger.verify())
        self.assertEqual(len(foundry.ledger.entries), 1)

    def test_explicit_evaluation_can_make_artifact_eligible(self) -> None:
        foundry = ResearchFoundry()
        foundry.admit(artifact())
        disposition = foundry.evaluate_for_promotion("artifact-1")
        self.assertEqual(disposition.state, PromotionState.ELIGIBLE)
        self.assertTrue(any("gates passed" in reason for reason in disposition.reasons))
        self.assertTrue(foundry.ledger.verify())
        self.assertEqual(len(foundry.ledger.entries), 2)

    def test_unknown_rights_block_promotion(self) -> None:
        foundry = ResearchFoundry()
        foundry.admit(
            artifact(item_source=source(rights=RightsStatus.UNKNOWN))
        )
        disposition = foundry.evaluate_for_promotion("artifact-1")
        self.assertEqual(disposition.state, PromotionState.BLOCKED)
        self.assertTrue(any("rights" in reason for reason in disposition.reasons))

    def test_absent_license_blocks_promotion(self) -> None:
        foundry = ResearchFoundry()
        foundry.admit(
            artifact(item_source=source(license_expression=None))
        )
        disposition = foundry.evaluate_for_promotion("artifact-1")
        self.assertEqual(disposition.state, PromotionState.BLOCKED)
        self.assertTrue(any("license" in reason for reason in disposition.reasons))

    def test_missing_reproduction_blocks_promotion(self) -> None:
        foundry = ResearchFoundry()
        foundry.admit(artifact(reproduction=ReproductionState.NOT_RUN))
        disposition = foundry.evaluate_for_promotion("artifact-1")
        self.assertEqual(disposition.state, PromotionState.BLOCKED)
        self.assertTrue(any("reproduction" in reason for reason in disposition.reasons))

    def test_claim_and_evidence_gates_fail_closed(self) -> None:
        foundry = ResearchFoundry()
        foundry.admit(artifact(claims=(), evidence=()))
        disposition = foundry.evaluate_for_promotion("artifact-1")
        self.assertEqual(disposition.state, PromotionState.BLOCKED)
        self.assertTrue(any("evidence" in reason for reason in disposition.reasons))
        self.assertTrue(any("claims" in reason for reason in disposition.reasons))

    def test_artifact_id_cannot_be_rebound(self) -> None:
        foundry = ResearchFoundry()
        foundry.admit(artifact())
        other_source = source(source_id="source-2", revision="b" * 40)
        with self.assertRaises(ValueError):
            foundry.admit(artifact(item_source=other_source))

    def test_artifact_bundle_digest_is_order_independent(self) -> None:
        first = artifact(artifact_id="a")
        second = artifact(
            artifact_id="b",
            item_source=source(source_id="source-2", revision="b" * 40),
        )
        self.assertEqual(
            artifact_bundle_digest((first, second)),
            artifact_bundle_digest((second, first)),
        )


if __name__ == "__main__":
    unittest.main()
