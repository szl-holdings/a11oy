# SPDX-License-Identifier: Apache-2.0
"""Offline gates for the governed SZL-Nemo fine-tuning candidate."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import socket

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "model_release" / "szl-nemo" / "szl_nemo_finetune.py"
SPEC = importlib.util.spec_from_file_location("szl_nemo_finetune", RUNNER)
assert SPEC and SPEC.loader
nemo_train = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(nemo_train)


def test_curriculum_is_deterministic_rights_scoped_and_disjoint(tmp_path):
    first = nemo_train.build_curriculum(tmp_path / "first")
    second = nemo_train.build_curriculum(tmp_path / "second")

    assert first == second
    assert first["train"]["rows"] == 24
    assert first["eval"]["rows"] == 8
    assert first["rights_basis"] == "PROJECT_AUTHORED_SCENARIOS"
    assert first["external_mutations"] == {
        "uploaded": False,
        "published": False,
        "deployed": False,
    }

    train = list(nemo_train.iter_jsonl(tmp_path / "first" / "train.jsonl"))
    evaluation = list(nemo_train.iter_jsonl(tmp_path / "first" / "eval.jsonl"))
    assert all(row["rights_basis"] == "PROJECT_AUTHORED_SCENARIOS" for row in train + evaluation)
    train_prompts = {row["messages"][1]["content"].casefold() for row in train}
    eval_prompts = {row["messages"][1]["content"].casefold() for row in evaluation}
    assert train_prompts.isdisjoint(eval_prompts)


def test_preflight_refuses_absent_base_without_starting_training():
    result = nemo_train.preflight(None)

    assert result["state"] == "BLOCKED"
    assert result["effects"] == {
        "training_started": False,
        "uploaded": False,
        "published": False,
        "deployed": False,
    }
    assert "base snapshot" in result["checks"][-1]["reason"]


def test_fetch_requires_exact_confirmation_before_hub_import(tmp_path):
    with pytest.raises(nemo_train.GateRefused, match="exact base-fetch confirmation"):
        nemo_train.fetch_base(tmp_path / "base", "WRONG")


def test_train_requires_confirmation_and_license_ack_before_gpu_or_model_load(tmp_path):
    with pytest.raises(nemo_train.GateRefused, match="exact training confirmation"):
        nemo_train.train(tmp_path / "base", tmp_path / "out", "WRONG", "WRONG")

    contract = json.loads(nemo_train.CONTRACT_PATH.read_text(encoding="utf-8"))
    with pytest.raises(nemo_train.GateRefused, match="license acknowledgement"):
        nemo_train.train(
            tmp_path / "base",
            tmp_path / "out",
            contract["training"]["confirmation_phrase"],
            "WRONG",
        )


def test_gpu_gate_is_fixed_and_fail_closed(monkeypatch):
    sample = {
        "measured_at_unix_ns": 1,
        "gpu_name": "NVIDIA GeForce RTX 5050 Laptop GPU",
        "memory_total_mib": 8151,
        "memory_used_mib": 3000,
        "memory_free_mib": 5151,
        "utilization_pct": 1,
        "temperature_c": 55,
    }
    monkeypatch.setattr(nemo_train, "query_gpu", lambda: dict(sample))
    policy = json.loads(nemo_train.CONTRACT_PATH.read_text(encoding="utf-8"))["gpu_admission"]

    with pytest.raises(nemo_train.GPUAdmissionRefused) as exc:
        nemo_train.sample_gpu(policy, 3, 0)
    assert exc.value.samples == [sample]
    assert policy["thresholds_may_be_weakened"] is False
    assert policy["processes_may_be_stopped_automatically"] is False


def test_python_network_guard_refuses_connections():
    with nemo_train.deny_python_network() as control:
        assert control["state"] == "PYTHON_SOCKET_DENIED"
        with pytest.raises(OSError, match="network denied"):
            socket.create_connection(("127.0.0.1", 9))


def test_base_verifier_binds_files_and_architecture(monkeypatch, tmp_path):
    config = {
        "model_type": "nemotron_h",
        "vocab_size": 131072,
        "architectures": ["NemotronHForCausalLM"],
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    weight_path = tmp_path / "model.safetensors"
    weight_path.write_bytes(b"fixture-weight")

    original_load = nemo_train.load_object
    fixture_contract = {
        "base": {
            "model_type": "nemotron_h",
            "vocab_size": 131072,
            "architecture": "NemotronHForCausalLM",
            "required_files": [
                {
                    "path": "config.json",
                    "bytes": config_path.stat().st_size,
                    "git_blob_sha1": nemo_train.git_blob_sha1(config_path),
                },
                {
                    "path": "model.safetensors",
                    "bytes": weight_path.stat().st_size,
                    "sha256": nemo_train.sha256_file(weight_path),
                },
            ],
        }
    }

    def fake_load(path):
        if Path(path) == nemo_train.CONTRACT_PATH:
            return fixture_contract
        return original_load(path)

    monkeypatch.setattr(nemo_train, "load_object", fake_load)
    observed = nemo_train.verify_base(tmp_path)
    assert {item["path"] for item in observed} == {"config.json", "model.safetensors"}

    config["vocab_size"] = 151936
    config_path.write_text(json.dumps(config), encoding="utf-8")
    fixture_contract["base"]["required_files"][0].update(
        bytes=config_path.stat().st_size,
        git_blob_sha1=nemo_train.git_blob_sha1(config_path),
    )
    with pytest.raises(nemo_train.GateRefused, match="architecture identity"):
        nemo_train.verify_base(tmp_path)


def test_held_out_evaluation_enforces_required_and_forbidden_terms():
    expected = {
        "required_terms": ["UNKNOWN", "receipt"],
        "forbidden_terms": ["measured throughput is"],
    }
    assert nemo_train._evaluate_output("UNKNOWN without a receipt.", expected)["state"] == "PASS"
    failed = nemo_train._evaluate_output("Measured throughput is 9000.", expected)
    assert failed["state"] == "FAIL"
    assert failed["present_forbidden_terms"] == ["measured throughput is"]


def test_contract_never_allows_automatic_promotion_or_external_release():
    contract = json.loads(nemo_train.CONTRACT_PATH.read_text(encoding="utf-8"))
    assert contract["release_state"] == "EXECUTABLE_CANDIDATE_NOT_TRAINED"
    assert contract["quality_claim"] == "NOT_ESTABLISHED"
    assert contract["promotion"]["automatic"] is False
    assert contract["promotion"]["requires_signed_dsse"] is True
    assert contract["promotion"]["requires_transparency_log"] is True
    assert contract["external_mutations"] == {
        "upload": False,
        "publish": False,
        "deploy": False,
        "push": False,
    }
