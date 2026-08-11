from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .profile import TokenizerProfile
from .tokenizer import EncodedDocument


@dataclass(frozen=True)
class SemanticGateResult:
    state: str
    promotable: bool
    checks: dict[str, bool]
    mismatches: tuple[dict, ...]

    def record(self) -> dict:
        return {
            "state": self.state,
            "promotable": self.promotable,
            "checks": dict(self.checks),
            "mismatches": [dict(item) for item in self.mismatches],
        }


def semantic_equivalence(
    *,
    oracle_profile: TokenizerProfile,
    candidate_profile: TokenizerProfile,
    oracle_documents: Iterable[EncodedDocument],
    candidate_documents: Iterable[EncodedDocument],
) -> SemanticGateResult:
    oracle = tuple(oracle_documents)
    candidate = tuple(candidate_documents)
    mismatches: list[dict] = []

    checks = {
        "profile_tokenizer_id": oracle_profile.tokenizer_id
        == candidate_profile.tokenizer_id,
        "profile_revision": oracle_profile.tokenizer_revision
        == candidate_profile.tokenizer_revision,
        "profile_family": oracle_profile.family == candidate_profile.family,
        "profile_normalization": oracle_profile.normalization
        == candidate_profile.normalization,
        "profile_special_tokens": dict(oracle_profile.special_tokens)
        == dict(candidate_profile.special_tokens),
        "profile_added_tokens": tuple(sorted(oracle_profile.added_tokens))
        == tuple(sorted(candidate_profile.added_tokens)),
        "profile_pre_tokenizer": oracle_profile.pre_tokenizer
        == candidate_profile.pre_tokenizer,
        "profile_post_processor": oracle_profile.post_processor
        == candidate_profile.post_processor,
        "document_count": len(oracle) == len(candidate),
    }

    for index, (expected, observed) in enumerate(zip(oracle, candidate)):
        if expected.token_ids != observed.token_ids:
            mismatches.append(
                {
                    "document_index": index,
                    "field": "token_ids",
                    "oracle": list(expected.token_ids),
                    "candidate": list(observed.token_ids),
                }
            )
        if expected.offsets != observed.offsets:
            mismatches.append(
                {
                    "document_index": index,
                    "field": "offsets",
                    "oracle": [list(item) for item in expected.offsets],
                    "candidate": [list(item) for item in observed.offsets],
                }
            )

    checks["token_ids"] = not any(
        item["field"] == "token_ids" for item in mismatches
    )
    checks["offsets"] = not any(item["field"] == "offsets" for item in mismatches)
    promotable = all(checks.values()) and not mismatches
    return SemanticGateResult(
        state="VERIFIED" if promotable else "FAILED",
        promotable=promotable,
        checks=checks,
        mismatches=tuple(mismatches),
    )
