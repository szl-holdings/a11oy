#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Successor identity is exact; historical evidence cannot grant authority."""
from pathlib import Path
import ast
import pytest

from scripts import hf_hub_131_source_contract as historical
from scripts import hf_hub_133_source_contract as successor

ROOT = Path(__file__).resolve().parents[1]


def test_exact_successor_upstream_provenance_and_separate_history():
    assert successor.HF_HUB_VERSION == "1.33.0"
    assert successor.HF_HUB_RELEASE_COMMIT == "9eeace5e467939b8f6af6ff280a134bc7c22802f"
    assert successor.HF_HUB_TAG_OBJECT == "a93d85c0e6e0f35c29c33e60cb1e1ca9d60a1692"
    assert successor.HF_HUB_WHEEL_SHA256 == "04e434b06e100eddbce9a6e817d72693a7884b10a79bd67ab48080d5c07eb899"
    assert successor.HF_HUB_TAG_SIGNATURE_VERIFIED is False
    assert successor.HF_HUB_TAG_SIGNATURE_REASON == "unsigned"
    assert historical.HF_HUB_VERSION == "1.31.0"
    assert historical.HF_HUB_RELEASE_COMMIT == "495b17c8529614759ae0f1ccf1ebe9a61c148b7c"


def test_successor_source_alignment_grants_no_operational_authority():
    result = successor.evaluate_repository(ROOT)
    assert result["aligned"] is True
    assert result["disposition"] == "EVALUATION"
    assert result["auditPin"] == result["runtimePin"] == "1.33.0"
    assert all(result[name] is False for name in (
        "productionAuthorized", "automaticPromotionAuthorized", "hubPublicationAuthorized",
        "sandboxJobCreationAuthorized"))
    assert "forgeEvaluationMerge" not in result


@pytest.mark.parametrize("audit,runtime", [("1.31.0", "1.31.0"), ("1.31.0", "1.33.0"),
                                           ("1.33.0", "1.31.0"), ("1.34.0", "1.34.0")])
def test_equal_pins_or_historical_qualification_cannot_admit_another_sdk(audit, runtime):
    result = successor.evaluate_runtime_alignment(
        audit_text=f"huggingface_hub=={audit}", docker_text=f"huggingface_hub=={runtime}")
    assert result["aligned"] is False
    assert result["disposition"] == "HOLD"


def test_managed_control_and_same_interpreter_worker_share_exact_sdk():
    def literal(path, name):
        tree = ast.parse((ROOT / path).read_text())
        return [ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)]
    assert literal("gdw_durable_storage.py", "SDK_VERSION") == ["1.33.0"]
    # load_admitted_head uses sys.executable for the storage worker, so the
    # actual control interpreter cannot retain a different exact SDK.
    assert literal("scripts/configure_hf_gdw_runtime.py", "MANAGED_SDK_VERSION") == ["1.33.0"]
    workflow = (ROOT / ".github/workflows/hf-sync.yml").read_text()
    assert workflow.count('"huggingface_hub==1.33.0"') == 2
    # The independent vertical-only client remains separate from these workers.
    assert workflow.count('"huggingface_hub==1.31.0"') == 1
    assert '"huggingface_hub==1.33.0"' in (ROOT / ".github/workflows/restart-drill.yml").read_text()


@pytest.mark.parametrize("pin", ["", "hf-xet>=1.6.0,<2.0.0", "hf-xet==1.6.0", "hf-xet==1.8.0", "hf-xet==1.7.0\nhf-xet==1.8.0"])
def test_native_transport_missing_range_or_drift_never_qualifies(pin):
    good = "huggingface_hub==1.33.0\nhf-xet==1.7.0"
    bad = "huggingface_hub==1.33.0\n" + pin
    for audit, runtime in ((good, bad), (bad, good)):
        result = successor.evaluate_runtime_alignment(audit_text=audit, docker_text=runtime)
        assert result["aligned"] is False
        assert result["disposition"] == "HOLD"
        assert result["productionAuthorized"] is False


def test_exact_native_transport_matches_the_qualified_offline_closure():
    result = successor.evaluate_repository(ROOT)
    assert result["auditTransportPin"] == result["runtimeTransportPin"] == "1.7.0"
    assert result["requiredTransportVersion"] == "1.7.0"
    assert result["nativeTransportAligned"] is True
    assert result["aligned"] is True
    assert result["hubPublicationAuthorized"] is False


@pytest.mark.parametrize("path", [".github/workflows/hf-sync.yml", ".github/workflows/restart-drill.yml", ".github/workflows/gdw-artifact-readonly-triage.yml"])
def test_each_successor_control_install_retains_qualified_native_transport(path):
    text = (ROOT / path).read_text(encoding="utf-8")
    assert text.count("huggingface_hub==1.33.0") > 0
    assert text.count("hf-xet==1.7.0") == text.count("huggingface_hub==1.33.0")


@pytest.mark.parametrize("path", ["scripts/hf_hub_133_source_contract.py", "tests/test_hf_hub_133_source_contract.py", "docs/CODEX_HF_HUB_133_RUNTIME_ALIGNMENT.md"])
def test_successor_files_include_required_license_and_rights_header(path):
    header = "\n".join((ROOT / path).read_text(encoding="utf-8").splitlines()[:4])
    assert "SPDX-License-Identifier: Apache-2.0" in header
    assert "(c) 2026 Lutar, Stephen P. - SZL Holdings" in header
    if path.endswith(".py"):
        assert header.startswith("#!/usr/bin/env python3\n")


def test_historical_runtime_document_does_not_describe_old_pins_as_current():
    text = (ROOT / "docs/CODEX_HF_HUB_131_RUNTIME_ALIGNMENT.md").read_text(encoding="utf-8")
    for stale in ("Source pins on this branch converge", "This branch repairs", "This restores `huggingface_hub==1.31.0`", "runtime pins now live"):
        assert stale not in text
    assert "Historical record" in text
    assert "CODEX_HF_HUB_133_RUNTIME_ALIGNMENT.md" in text
