from __future__ import annotations

import ast
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
RUNTIME_EQ = re.compile(r"^([A-Za-z0-9_.-]+)(?:\[[a-z]+\])?==([0-9][^#\s]*)$")

CLOSURE_SPEC = importlib.util.spec_from_file_location(
    "audit_closure_check", ROOT / "scripts" / "audit_closure_check.py"
)
assert CLOSURE_SPEC and CLOSURE_SPEC.loader
CLOSURE = importlib.util.module_from_spec(CLOSURE_SPEC)
sys.modules[CLOSURE_SPEC.name] = CLOSURE
CLOSURE_SPEC.loader.exec_module(CLOSURE)


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


def test_historic_133_grouped_bump_is_synthetic_hold() -> None:
    """Equal audit/image pins cannot admit an unqualified recovery SDK."""
    result = MODULE.evaluate_runtime_alignment(
        audit_text="huggingface_hub==1.33.0",
        docker_text='RUN pip install "huggingface_hub==1.33.0"',
    )
    assert result["aligned"] is False
    assert result["disposition"] == "HOLD"
    for key in ("productionAuthorized", "automaticPromotionAuthorized",
                "hubPublicationAuthorized", "sandboxJobCreationAuthorized"):
        assert result[key] is False


def test_managed_storage_sdk_matches_the_admitted_runtime_contract() -> None:
    """Read the literal without loading provider or database implementations."""
    tree = ast.parse((ROOT / "gdw_durable_storage.py").read_text(encoding="utf-8"))
    values = [
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "SDK_VERSION"
                for target in node.targets)
    ]
    assert values == [MODULE.HF_HUB_VERSION]


def _runtime_equality_pins(text: str) -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = RUNTIME_EQ.fullmatch(stripped)
        assert match is not None, f"runtime requirement is not an exact pin: {stripped!r}"
        pins[match.group(1)] = match.group(2)
    return pins


def test_audit_closure_is_exactly_the_runtime_install_set() -> None:
    """The audit closure includes the file the image installs; nothing is copied."""
    runtime = _runtime_equality_pins(MODULE.runtime_install_text(ROOT))
    audit_closure = MODULE._expand_includes(ROOT, "requirements-audit.txt")
    audit_pins: dict[str, str] = {}
    for line in audit_closure.splitlines():
        match = RUNTIME_EQ.fullmatch(line.strip())
        if match is not None:
            audit_pins[match.group(1)] = match.group(2)
    assert "huggingface_hub" in runtime
    assert "openai" in runtime
    assert {name: audit_pins.get(name) for name in runtime} == runtime
    assert CLOSURE.check(ROOT) == []


def test_dockerfile_carries_no_inline_runtime_pins() -> None:
    docker_pins = {m.group(1) for m in DOCKER_EQ.finditer((ROOT / "Dockerfile").read_text(encoding="utf-8"))}
    runtime = _runtime_equality_pins((ROOT / "requirements-runtime.txt").read_text(encoding="utf-8"))
    assert docker_pins & set(runtime) == set()


def _closure_tree(tmp_path: Path, *, runtime: str, audit: str, docker: str) -> Path:
    (tmp_path / "requirements-runtime.txt").write_text(runtime, encoding="utf-8")
    (tmp_path / "requirements-audit.txt").write_text(audit, encoding="utf-8")
    (tmp_path / "Dockerfile").write_text(docker, encoding="utf-8")
    return tmp_path


GOOD_DOCKER = (
    "FROM python:3.14-slim\n"
    "COPY requirements-runtime.txt /tmp/requirements-runtime.txt\n"
    "RUN pip install --no-cache-dir -r /tmp/requirements-runtime.txt\n"
)
GOOD_RUNTIME = "uvicorn[standard]==0.52.4\nhuggingface_hub==1.31.0\nopenai==2.43.0\n"
GOOD_AUDIT = "-r requirements-runtime.txt\nsigstore==4.5.0\n"


def test_closure_check_accepts_the_single_source_shape(tmp_path: Path) -> None:
    root = _closure_tree(tmp_path, runtime=GOOD_RUNTIME, audit=GOOD_AUDIT, docker=GOOD_DOCKER)
    assert CLOSURE.check(root) == []
    assert MODULE.evaluate_repository(root)["aligned"] is True


def test_closure_check_refuses_a_copied_audit_pin(tmp_path: Path) -> None:
    """The #2306/#2307 failure: a bump lands in the audit file but not the image."""
    root = _closure_tree(
        tmp_path, runtime=GOOD_RUNTIME, audit=GOOD_AUDIT + "openai==3.8.0\n", docker=GOOD_DOCKER
    )
    errors = CLOSURE.check(root)
    assert any("runtime pin openai is copied" in e for e in errors), errors


def test_closure_check_refuses_an_inline_dockerfile_pin(tmp_path: Path) -> None:
    """The #2315 failure: runtime pins edited inline in the Dockerfile RUN line."""
    docker = GOOD_DOCKER + 'RUN pip install --no-cache-dir "huggingface_hub==1.32.0"\n'
    root = _closure_tree(tmp_path, runtime=GOOD_RUNTIME, audit=GOOD_AUDIT, docker=docker)
    errors = CLOSURE.check(root)
    assert any("huggingface_hub is re-listed inline" in e for e in errors), errors


def test_closure_check_refuses_missing_include_and_ranges(tmp_path: Path) -> None:
    root = _closure_tree(
        tmp_path,
        runtime=GOOD_RUNTIME + "numpy>=2.5\n",
        audit="sigstore==4.5.0\n",
        docker=GOOD_DOCKER,
    )
    errors = CLOSURE.check(root)
    assert any("must include '-r requirements-runtime.txt'" in e for e in errors), errors
    assert any("'numpy>=2.5' is not an exact == pin" in e for e in errors), errors


def test_closure_check_refuses_an_image_that_does_not_install_the_runtime_file(tmp_path: Path) -> None:
    docker = "FROM python:3.14-slim\nCOPY requirements-runtime.txt /tmp/requirements-runtime.txt\n"
    root = _closure_tree(tmp_path, runtime=GOOD_RUNTIME, audit=GOOD_AUDIT, docker=docker)
    assert any("RUN pip install --no-cache-dir -r" in e for e in CLOSURE.check(root))
    try:
        MODULE.evaluate_repository(root)
    except MODULE.ContractError:
        pass
    else:
        raise AssertionError("an image that does not install the runtime file was evaluated as aligned")


def test_historic_openai_audit_380_versus_runtime_243_is_synthetic_hold() -> None:
    """Former live openai audit pin is not an admitted successor and is not the runtime."""
    historic = overlapping_equality_pins(
        "openai==3.8.0\n",
        'RUN pip install "openai==2.43.0"\n',
    )
    assert historic["openai"] == ("3.8.0", "2.43.0")
    runtime = _runtime_equality_pins(MODULE.runtime_install_text(ROOT))
    assert runtime["openai"] == "2.43.0"
    assert runtime["huggingface_hub"] == MODULE.HF_HUB_VERSION


def test_audited_report_must_contain_every_runtime_pin(tmp_path: Path) -> None:
    """A -r include the auditor skipped (or resolved to another version) fails closed."""
    import json

    root = _closure_tree(tmp_path, runtime=GOOD_RUNTIME, audit=GOOD_AUDIT, docker=GOOD_DOCKER)
    complete = tmp_path / "complete.json"
    complete.write_text(json.dumps({"dependencies": [
        {"name": "uvicorn", "version": "0.52.4", "vulns": []},
        {"name": "huggingface-hub", "version": "1.31.0", "vulns": []},
        {"name": "openai", "version": "2.43.0", "vulns": []},
        {"name": "sigstore", "version": "4.5.0", "vulns": []},
    ], "fixes": []}), encoding="utf-8")
    assert CLOSURE.check_audited(root, complete) == []

    skipped = tmp_path / "skipped.json"
    skipped.write_text(json.dumps({"dependencies": [
        {"name": "sigstore", "version": "4.5.0", "vulns": []},
        {"name": "openai", "version": "3.8.0", "vulns": []},
    ], "fixes": []}), encoding="utf-8")
    errors = CLOSURE.check_audited(root, skipped)
    assert any("did not audit runtime pin huggingface-hub" in e for e in errors), errors
    assert any("audited openai==3.8.0, runtime pins 2.43.0" in e for e in errors), errors
