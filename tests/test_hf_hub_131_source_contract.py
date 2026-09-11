from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "hf_hub_131_source_contract", ROOT / "scripts" / "hf_hub_131_source_contract.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_exact_upstream_release_is_fixed_and_unsigned_tag_is_honest() -> None:
    assert MODULE.HF_HUB_VERSION == "1.31.0"
    assert MODULE.HF_HUB_RELEASE_COMMIT == "495b17c8529614759ae0f1ccf1ebe9a61c148b7c"
    assert MODULE.HF_HUB_TAG_OBJECT == "32ccc9ee57f3b3546165de105b4a0d8eba1b7446"
    assert MODULE.HF_HUB_TAG_SIGNATURE_VERIFIED is False
    assert MODULE.HF_HUB_TAG_SIGNATURE_REASON == "unsigned"
    assert MODULE.FORGE_EVALUATION_MERGE == "74a8a07ced6c6b8697b31b7d0e482c4241d55880"


def test_revision_authority_includes_repository_identity() -> None:
    sha = "a" * 40
    first = MODULE.RevisionBinding("SZLHOLDINGS/a11oy", "space", "main", sha)
    same = MODULE.RevisionBinding("SZLHOLDINGS/a11oy", "space", "main", sha)
    other_repo = MODULE.RevisionBinding("SZLHOLDINGS/lyte", "space", "main", sha)
    other_type = MODULE.RevisionBinding("SZLHOLDINGS/a11oy", "dataset", "main", sha)
    assert first.same_authority(same) is True
    assert first.same_authority(other_repo) is False
    assert first.same_authority(other_type) is False


def test_moving_revision_cannot_become_resolved_authority() -> None:
    try:
        MODULE.RevisionBinding("SZLHOLDINGS/a11oy", "space", "main", "main")
    except MODULE.ContractError:
        pass
    else:
        raise AssertionError("moving revision was accepted as resolved authority")


def test_upstream_eligibility_and_sandbox_labels_do_not_grant_authority() -> None:
    assert MODULE.serving_authorized(
        upstream_eligible=True,
        szl_allowlisted=False,
        evaluation_passed=True,
        policy_passed=True,
    ) is False
    assert MODULE.sandbox_job_authorized(labels_valid=True, explicit_job_authority=False) is False
    assert MODULE.sandbox_job_authorized(labels_valid=False, explicit_job_authority=True) is True


def test_historic_129_130_mismatch_remains_synthetic_hold() -> None:
    """Preserve the former live drift as a negative fixture, not the desired pin."""
    result = MODULE.evaluate_runtime_alignment(
        audit_text="huggingface_hub==1.30.0",
        docker_text='RUN pip install "huggingface_hub==1.29.0"',
    )
    assert result["auditPin"] == "1.30.0"
    assert result["runtimePin"] == "1.29.0"
    assert result["requiredVersion"] == "1.31.0"
    assert result["aligned"] is False
    assert result["disposition"] == "HOLD"
    assert result["productionAuthorized"] is False
    assert result["automaticPromotionAuthorized"] is False
    assert result["hubPublicationAuthorized"] is False
    assert result["sandboxJobCreationAuthorized"] is False


def test_current_repository_canonical_pins_match_admitted_131() -> None:
    result = MODULE.evaluate_repository(ROOT)
    assert result["auditPin"] == "1.31.0"
    assert result["runtimePin"] == "1.31.0"
    assert result["requiredVersion"] == "1.31.0"
    assert result["aligned"] is True
    assert result["disposition"] == "EVALUATION"
    assert result["productionAuthorized"] is False
    assert result["automaticPromotionAuthorized"] is False
    assert result["hubPublicationAuthorized"] is False
    assert result["sandboxJobCreationAuthorized"] is False


def test_synthetic_131_alignment_still_only_reaches_evaluation() -> None:
    result = MODULE.evaluate_runtime_alignment(
        audit_text="huggingface_hub==1.31.0",
        docker_text='RUN pip install "huggingface_hub==1.31.0"',
    )
    assert result["aligned"] is True
    assert result["disposition"] == "EVALUATION"
    assert result["productionAuthorized"] is False
    assert result["automaticPromotionAuthorized"] is False
