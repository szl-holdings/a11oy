from __future__ import annotations

import importlib.util
import re
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

AUDIT_EQ = re.compile(r"^([A-Za-z0-9_.-]+)==([0-9][^#\s]*)$")
DOCKER_EQ = re.compile(r'"([A-Za-z0-9_.-]+)(?:\[[a-z]+\])?==([0-9][^"]*)"')


def overlapping_equality_pins(audit_text: str, docker_text: str) -> dict[str, tuple[str, str]]:
    """Return pkg -> (audit, docker) for equality pins present in both files."""
    audit_pins: dict[str, str] = {}
    for line in audit_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = AUDIT_EQ.fullmatch(stripped)
        if match is not None:
            audit_pins[match.group(1)] = match.group(2)
    docker_pins: dict[str, str] = {}
    for match in DOCKER_EQ.finditer(docker_text):
        docker_pins[match.group(1)] = match.group(2)
    return {
        name: (audit_pins[name], docker_pins[name])
        for name in sorted(set(audit_pins) & set(docker_pins))
    }


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


def test_overlapping_audit_and_dockerfile_equality_pins_match() -> None:
    pairs = overlapping_equality_pins(
        (ROOT / "requirements-audit.txt").read_text(encoding="utf-8"),
        (ROOT / "Dockerfile").read_text(encoding="utf-8"),
    )
    assert "huggingface_hub" in pairs
    assert "openai" in pairs
    drifted = {name: versions for name, versions in pairs.items() if versions[0] != versions[1]}
    assert drifted == {}, drifted


def test_historic_openai_audit_380_versus_runtime_243_is_synthetic_hold() -> None:
    """Former live openai audit pin is not an admitted successor and is not the runtime."""
    historic = overlapping_equality_pins(
        "openai==3.8.0\n",
        'RUN pip install "openai==2.43.0"\n',
    )
    assert historic["openai"] == ("3.8.0", "2.43.0")
    current = overlapping_equality_pins(
        (ROOT / "requirements-audit.txt").read_text(encoding="utf-8"),
        (ROOT / "Dockerfile").read_text(encoding="utf-8"),
    )
    assert current["openai"] == ("2.43.0", "2.43.0")
