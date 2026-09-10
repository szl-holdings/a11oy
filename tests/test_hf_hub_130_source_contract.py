from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "hf_hub_130_source_contract", ROOT / "scripts" / "hf_hub_130_source_contract.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_exact_upstream_release_is_fixed() -> None:
    assert MODULE.HF_HUB_130_VERSION == "1.30.0"
    assert MODULE.HF_HUB_130_RELEASE_COMMIT == "48ef2781c2c4c2247431c97efcd5487e89d42732"
    assert MODULE.HF_HUB_130_TAG_OBJECT == "103720584dcc9865259dc5165f1a42e0bdea15d5"


def test_revision_authority_includes_repository_identity() -> None:
    sha = "a" * 40
    first = MODULE.RevisionBinding("SZLHOLDINGS/a11oy", "space", "main", sha)
    same = MODULE.RevisionBinding("SZLHOLDINGS/a11oy", "space", "main", sha)
    different_repo = MODULE.RevisionBinding("SZLHOLDINGS/lyte", "space", "main", sha)
    different_type = MODULE.RevisionBinding("SZLHOLDINGS/a11oy", "dataset", "main", sha)
    assert first.same_authority(same) is True
    assert first.same_authority(different_repo) is False
    assert first.same_authority(different_type) is False


def test_invalid_revision_cannot_become_authority() -> None:
    try:
        MODULE.RevisionBinding("SZLHOLDINGS/a11oy", "space", "main", "main")
    except MODULE.ContractError:
        pass
    else:
        raise AssertionError("moving revision was accepted as resolved authority")


def test_upstream_chat_eligibility_never_authorizes_route() -> None:
    assert MODULE.serving_authorized(
        upstream_chat_eligible=True,
        szl_allowlisted=False,
        evaluation_passed=True,
        policy_passed=True,
    ) is False
    assert MODULE.serving_authorized(
        upstream_chat_eligible=True,
        szl_allowlisted=True,
        evaluation_passed=False,
        policy_passed=True,
    ) is False
    assert MODULE.serving_authorized(
        upstream_chat_eligible=False,
        szl_allowlisted=True,
        evaluation_passed=True,
        policy_passed=True,
    ) is True


def test_current_repository_drift_is_reported_as_hold() -> None:
    result = MODULE.evaluate_repository(ROOT)
    assert result["auditPin"] == "1.30.0"
    assert result["runtimePin"] == "1.29.0"
    assert result["aligned"] is False
    assert result["disposition"] == "HOLD"
    assert result["productionAuthorized"] is False
    assert result["automaticPromotionAuthorized"] is False


def test_synthetic_aligned_state_still_does_not_pre_authorize_production() -> None:
    result = MODULE.evaluate_runtime_alignment(
        audit_text="huggingface_hub==1.30.0",
        docker_text='RUN pip install "huggingface_hub==1.30.0"',
    )
    assert result["aligned"] is True
    assert result["disposition"] == "EVALUATION"
    assert result["productionAuthorized"] is False
    assert result["automaticPromotionAuthorized"] is False
