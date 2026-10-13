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
