# SPDX-License-Identifier: Apache-2.0
"""Offline gates for the governed SZL-Nemo fine-tuning candidate."""

from __future__ import annotations

import importlib.util
import json
import os
from contextlib import nullcontext
from pathlib import Path
import socket
import subprocess
import sys
import types

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "model_release" / "szl-nemo" / "szl_nemo_finetune.py"
SPEC = importlib.util.spec_from_file_location("szl_nemo_finetune", RUNNER)
assert SPEC and SPEC.loader
nemo_train = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(nemo_train)


is_fast_path_available = True


class Linear4bit:
    pass


Linear4bit.__module__ = "bitsandbytes.nn.modules"


class FakeLoraProjection:
    def __init__(self, valid: bool = True):
        self.base_layer = Linear4bit()
        self.lora_A = {"default": object()} if valid else {}
        self.lora_B = {"default": object()} if valid else {}
        self.training = True


class NemotronHMamba2Mixer:
    def __init__(self, valid_lora: bool = True):
        self.out_proj = FakeLoraProjection(valid_lora)
        self.in_proj = types.SimpleNamespace(
            weight=types.SimpleNamespace(device=types.SimpleNamespace(type="cuda"))
        )
        self.training = True
        self.raise_during_cuda = False
        self.dispatch_observation = None

    def forward(self, *_args, **_kwargs):
        return "fused"

    def cuda_kernels_forward(self, *_args, **_kwargs):
        self.dispatch_observation = {
            "mixer_training": self.training,
            "projection_training": self.out_proj.training,
        }
        if self.raise_during_cuda:
            raise RuntimeError("fixture CUDA failure")
        return "decomposed-cuda"


class FakeQuantizedMambaModel:
    def __init__(self, mixer_count: int = 2, valid_lora: bool = True):
        self.config = types.SimpleNamespace(
            hybrid_override_pattern="M-M",
            use_mamba_kernels=True,
            chunk_size=256,
            mamba_num_heads=96,
            ssm_state_size=128,
        )
        self.mixers = [
            NemotronHMamba2Mixer(valid_lora=valid_lora)
            for _index in range(mixer_count)
        ]

    def named_modules(self):
        yield "", self
        for index, mixer in enumerate(self.mixers):
            yield f"base.layers.{index}.mixer", mixer


class FakePaddingTokenizer:
    def __init__(
        self,
        *,
        source_token: str = "<unk>",
        source_id: int = 0,
        pad_token: str | None = None,
        added_vocab: dict[str, int] | None = None,
    ) -> None:
        self.unk_token = source_token
        self.unk_token_id = source_id
        self._pad_token = pad_token
        self._tokens = {source_id: source_token}
        self._ids = {source_token: source_id}
        self._added_vocab = dict(added_vocab or {})
        self._length = 131072

    def __len__(self):
        return self._length

    @property
    def pad_token(self):
        return self._pad_token

    @pad_token.setter
    def pad_token(self, value):
        self._pad_token = value

    @property
    def pad_token_id(self):
        if self._pad_token is None:
            return None
        return self._ids.get(self._pad_token)

    def get_added_vocab(self):
        return dict(self._added_vocab)

    def convert_ids_to_tokens(self, value):
        return self._tokens.get(value)

    def convert_tokens_to_ids(self, value):
        return self._ids.get(value)


def compatibility_contract() -> dict:
    return {
        "base": {
            "required_files": [
                {
                    "path": "modeling_nemotron_h.py",
                    "sha256": nemo_train.sha256_file(Path(__file__)),
                }
            ]
        }
    }


def padding_contract() -> dict:
    return {
        "training": {
            "padding_policy": {
                "source": "PINNED_MODEL_AND_GENERATION_CONFIG",
                "token": "<unk>",
                "token_id": 0,
                "special_token_attribute": "unk_token",
                "vocabulary_mutation_allowed": False,
            }
        }
    }


def test_padding_admission_binds_pinned_special_token_without_vocab_mutation():
    tokenizer = FakePaddingTokenizer(added_vocab={"<SPECIAL_18>": 18})

    receipt = nemo_train.admit_padding_token(
        tokenizer, padding_contract(), "fixture"
    )

    assert tokenizer.pad_token == "<unk>"
    assert tokenizer.pad_token_id == 0
    assert receipt == {
        "state": "BOUND_PINNED_SPECIAL_TOKEN_NO_VOCAB_MUTATION",
        "phase": "fixture",
        "source": "PINNED_MODEL_AND_GENERATION_CONFIG",
        "special_token_attribute": "unk_token",
        "token": "<unk>",
        "token_id": 0,
        "pad_before": {"token": None, "token_id": None},
        "pad_after": {"token": "<unk>", "token_id": 0},
        "vocabulary_size_before": 131072,
        "vocabulary_size_after": 131072,
        "added_vocabulary_unchanged": True,
    }


def test_padding_admission_refuses_conflicting_or_unpinned_identity():
    with pytest.raises(nemo_train.GateRefused, match="conflicting padding identity"):
        nemo_train.admit_padding_token(
            FakePaddingTokenizer(pad_token="different"),
            padding_contract(),
            "fixture",
        )
    with pytest.raises(nemo_train.GateRefused, match="pinned padding token identity"):
        nemo_train.admit_padding_token(
            FakePaddingTokenizer(source_id=7), padding_contract(), "fixture"
        )


def test_model_and_generation_padding_must_match_admitted_token():
    padding = {"token": "<unk>", "token_id": 0}
    model = types.SimpleNamespace(
        config=types.SimpleNamespace(pad_token_id=0),
        generation_config=types.SimpleNamespace(pad_token_id=0),
    )

    receipt = nemo_train.verify_model_padding_binding(model, padding, "fixture")

    assert receipt["state"] == "CONSISTENT_PINNED_PADDING_IDS"
    assert receipt["model_config_pad_token_id"] == 0
    assert receipt["generation_config_pad_token_id"] == 0
    model.generation_config.pad_token_id = 2
    with pytest.raises(nemo_train.GateRefused, match="padding identity is inconsistent"):
        nemo_train.verify_model_padding_binding(model, padding, "fixture")


def test_curriculum_is_deterministic_rights_scoped_and_disjoint(tmp_path):
    first = nemo_train.build_curriculum(tmp_path / "first")
    second = nemo_train.build_curriculum(tmp_path / "second")

    assert first == second
    assert first["train"]["rows"] == 99
    assert first["eval"]["rows"] == 8
    assert first["shadow_eval"]["rows"] == 10
    assert first["eval"]["sha256"] == "caeb07c94929c24a47fd12f35cbc9021523308dc9fcc684bd444ffcf4a367b0d"
    assert first["evaluation_gate"] == "ORIGINAL_AND_SHADOW_MUST_BOTH_PASS"
    assert first["rights_basis"] == "PROJECT_AUTHORED_SCENARIOS"
    assert first["external_mutations"] == {
        "uploaded": False,
        "published": False,
        "deployed": False,
    }

    train = list(nemo_train.iter_jsonl(tmp_path / "first" / "train.jsonl"))
    evaluation = list(nemo_train.iter_jsonl(tmp_path / "first" / "eval.jsonl"))
    shadow = list(nemo_train.iter_jsonl(tmp_path / "first" / "shadow-eval.jsonl"))
    assert all(row["rights_basis"] == "PROJECT_AUTHORED_SCENARIOS" for row in train + evaluation + shadow)
    contrastive = [row for row in train if row["record_id"].startswith("train:contrastive:")]
    assert len(contrastive) == 75
    assert {row["behavior_class"] for row in contrastive} == {
        "IDENTITY_ATTRIBUTION",
        "BRAIN_PROVENANCE",
        "EXECUTION_BOUNDARY",
        "SIGNATURE_BOUNDARY",
        "CLAIM_SCOPE",
    }
    assert all(
        row["rights_admission"]["provenance"] == "INDEPENDENTLY_AUTHORED_FOR_NEMO_V2"
        and row["rights_admission"]["held_out_contamination"]
        == "NO_ORIGINAL_OR_SHADOW_EVAL_TEXT_COPIED"
        for row in contrastive
    )
    train_prompts = {row["messages"][1]["content"].casefold() for row in train}
    eval_prompts = {row["messages"][1]["content"].casefold() for row in evaluation}
    shadow_prompts = {row["messages"][1]["content"].casefold() for row in shadow}
    assert train_prompts.isdisjoint(eval_prompts)
    assert train_prompts.isdisjoint(shadow_prompts)
    assert eval_prompts.isdisjoint(shadow_prompts)


def test_original_evaluation_is_byte_frozen_while_shadow_is_distinct(tmp_path):
    manifest = nemo_train.build_curriculum(tmp_path)
    original = (tmp_path / "eval.jsonl").read_bytes()
    shadow = (tmp_path / "shadow-eval.jsonl").read_bytes()

    assert nemo_train.sha256_bytes(original) == "caeb07c94929c24a47fd12f35cbc9021523308dc9fcc684bd444ffcf4a367b0d"
    assert original == nemo_train.EVAL_PATH.read_bytes()
    assert original != shadow
    assert manifest["eval"]["sha256"] != manifest["shadow_eval"]["sha256"]


def test_contrastive_rights_or_behavior_coverage_cannot_be_relaxed():
    source = json.loads(nemo_train.SOURCE_PATH.read_text(encoding="utf-8"))
    contract = json.loads(nemo_train.CONTRACT_PATH.read_text(encoding="utf-8"))

    missing_rights = json.loads(json.dumps(source))
    missing_rights["contrastive_train_scenarios"][0]["rights_admission"]["provenance"] = "UNKNOWN"
    with pytest.raises(nemo_train.GateRefused, match="rights admission"):
        nemo_train.validate_source(missing_rights, contract)

    missing_class = json.loads(json.dumps(source))
    missing_class["contrastive_train_scenarios"] = [
        row for row in missing_class["contrastive_train_scenarios"]
        if row["behavior_class"] != "CLAIM_SCOPE"
    ]
    with pytest.raises(nemo_train.GateRefused, match="contract minimum|behavior coverage"):
        nemo_train.validate_source(missing_class, contract)


def test_v2_curriculum_source_validates_against_declared_schema():
    jsonschema = pytest.importorskip("jsonschema")
    source = json.loads(nemo_train.SOURCE_PATH.read_text(encoding="utf-8"))
    schema = json.loads(nemo_train.SCHEMA_PATH.read_text(encoding="utf-8"))

    jsonschema.Draft202012Validator(schema).validate(source)
    counts = {}
    for row in source["contrastive_train_scenarios"]:
        counts[row["behavior_class"]] = counts.get(row["behavior_class"], 0) + 1
    assert counts == {
        "IDENTITY_ATTRIBUTION": 5,
        "BRAIN_PROVENANCE": 5,
        "EXECUTION_BOUNDARY": 5,
        "SIGNATURE_BOUNDARY": 5,
        "CLAIM_SCOPE": 5,
    }


def test_completion_only_loss_masks_prompt_and_refuses_truncation():
    class FakeTokenizer:
        marker = [7, 8]

        def encode(self, value, add_special_tokens=False):
            assert add_special_tokens is False
            return list(self.marker)

        def __call__(self, value, add_special_tokens=False, truncation=False):
            assert add_special_tokens is False
            assert truncation is False
            suffix = [2, 3] if value == "normal" else list(range(20))
            return {"input_ids": [1, *self.marker, *suffix], "attention_mask": [1] * (3 + len(suffix))}

    class FakeCollator:
        def __init__(self, response_template, tokenizer, mlm):
            self.marker = response_template
            assert tokenizer is not None and mlm is False

        def __call__(self, features):
            labels = []
            for feature in features:
                ids = feature["input_ids"]
                offset = nemo_train._subsequence_offsets(ids, self.marker)[0] + len(self.marker)
                labels.append([-100] * offset + ids[offset:])
            return {"labels": labels}

    settings = {
        "loss_scope": "ASSISTANT_COMPLETION_ONLY",
        "assistant_response_template": "assistant-marker",
        "max_sequence_length": 8,
    }
    _, evidence = nemo_train.completion_only_training_setup(
        FakeTokenizer(), ["normal"], settings, FakeCollator
    )
    assert evidence["state"] == "PASS_ASSISTANT_COMPLETION_ONLY"
    assert evidence["masked_prompt_tokens"] == {"minimum": 3, "maximum": 3}
    assert evidence["supervised_completion_tokens"] == {"minimum": 2, "maximum": 2}
    assert evidence["truncated_rows"] == 0

    with pytest.raises(nemo_train.GateRefused, match="truncated"):
        nemo_train.completion_only_training_setup(
            FakeTokenizer(), ["too-long"], settings, FakeCollator
        )


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


def test_evaluation_resume_requires_exact_acknowledgements_before_artifact_admission(
    monkeypatch, tmp_path
):
    contract = json.loads(nemo_train.CONTRACT_PATH.read_text(encoding="utf-8"))
    monkeypatch.setattr(
        nemo_train,
        "admit_evaluation_resume",
        lambda *_args: (_ for _ in ()).throw(AssertionError("artifact admission ran")),
    )
    with pytest.raises(nemo_train.GateRefused, match="evaluation-only confirmation"):
        nemo_train.evaluate_saved_adapter(
            tmp_path / "base",
            tmp_path / "training",
            tmp_path / "evaluation.json",
            "WRONG",
            "WRONG",
        )
    with pytest.raises(nemo_train.GateRefused, match="license acknowledgement"):
        nemo_train.evaluate_saved_adapter(
            tmp_path / "base",
            tmp_path / "training",
            tmp_path / "evaluation.json",
            nemo_train.EVALUATION_CONFIRMATION,
            "WRONG",
        )


def test_evaluation_resume_binds_completed_training_adapter_base_and_holdouts(
    monkeypatch, tmp_path
):
    contract = json.loads(nemo_train.CONTRACT_PATH.read_text(encoding="utf-8"))
    output = tmp_path / "training"
    adapter = output / "adapter"
    receipts = output / "receipts"
    adapter.mkdir(parents=True)
    receipts.mkdir(parents=True)
    (adapter / "adapter_model.safetensors").write_bytes(b"adapter-v2")
    (adapter / "adapter_config.json").write_text("{}\n", encoding="utf-8")
    inventory = nemo_train._inventory(adapter)
    adapter_receipt = receipts / "adapter-files.json"
    nemo_train.atomic_json(
        adapter_receipt,
        {"schema_version": "szl.nemo.adapter-files.v1", "files": inventory},
    )
    base_files = [{"path": "pinned-base", "bytes": 1, "sha256": "0" * 64}]
    monkeypatch.setattr(nemo_train, "verify_base", lambda _snapshot: base_files)
    training_receipt = {
        "schema_version": "szl.nemo.training-receipt.v2",
        "contract_id": contract["contract_id"],
        "state": "FAILED_NOT_PROMOTED",
        "error_type": "GateRefused",
        "error": "training thermal ceiling exceeded",
        "global_steps": contract["training"]["max_steps"],
        "training_loss": 6.5,
        "training_completed_at_unix_ns": 2,
        "contract_sha256": nemo_train.sha256_file(nemo_train.CONTRACT_PATH),
        "curriculum_manifest_sha256": nemo_train.sha256_file(nemo_train.MANIFEST_PATH),
        "runner_sha256": "1" * 64,
        "source_control": {"state": "CLEAN_REVIEWED_COMMIT", "commit": "a" * 40},
        "adapter_files_sha256": nemo_train.sha256_file(adapter_receipt),
        "base_files_before": base_files,
        "curriculum_inputs_before": nemo_train.curriculum_input_identity(),
    }
    nemo_train.atomic_json(receipts / "training-receipt.json", training_receipt)

    admitted = nemo_train.admit_evaluation_resume(tmp_path / "base", output, contract)
    assert admitted["adapter_inventory"] == inventory
    assert admitted["origin_commit"] == "a" * 40
    assert admitted["training_receipt"]["global_steps"] == 96

    (adapter / "adapter_model.safetensors").write_bytes(b"mutated")
    with pytest.raises(nemo_train.GateRefused, match="adapter inventory changed"):
        nemo_train.admit_evaluation_resume(tmp_path / "base", output, contract)


def test_evaluation_runtime_guard_uses_same_ceiling_with_honest_scope(monkeypatch):
    contract = json.loads(nemo_train.CONTRACT_PATH.read_text(encoding="utf-8"))
    monkeypatch.setattr(
        nemo_train,
        "query_gpu",
        lambda: {
            "measured_at_unix_ns": 1,
            "gpu_name": "fixture",
            "memory_total_mib": 8192,
            "memory_used_mib": 4096,
            "memory_free_mib": 4096,
            "utilization_pct": 90,
            "temperature_c": 81,
        },
    )
    guard = nemo_train.RuntimeGuard(contract, thermal_scope="evaluation")
    guard._record("fixture")
    assert guard.maximum_temperature == contract["gpu_admission"]["maximum_training_temperature_c"]
    assert guard.reason == "evaluation thermal ceiling exceeded"
    assert guard.receipt()["thermal_scope"] == "evaluation"


def test_cli_evaluation_refusal_never_reports_training_started(monkeypatch, tmp_path, capsys):
    contract = json.loads(nemo_train.CONTRACT_PATH.read_text(encoding="utf-8"))
    monkeypatch.setattr(nemo_train, "training_mutex", lambda: nullcontext())
    monkeypatch.setattr(
        nemo_train, "fresh_hf_modules_cache", lambda: nullcontext({"state": "FIXTURE"})
    )
    monkeypatch.setattr(
        nemo_train,
        "evaluate_saved_adapter",
        lambda *_args: (_ for _ in ()).throw(nemo_train.GateRefused("fixture refusal")),
    )
    code = nemo_train.main(
        [
            "evaluate-adapter",
            "--base-snapshot",
            str(tmp_path / "base"),
            "--training-output",
            str(tmp_path / "training"),
            "--receipt",
            str(tmp_path / "evaluation.json"),
            "--confirmation",
            nemo_train.EVALUATION_CONFIRMATION,
            "--license-acknowledgement",
            contract["base"]["license_acknowledgement"],
        ]
    )
    assert code == 3
    payload = json.loads(capsys.readouterr().err)
    assert payload["effects"]["training_started"] == nemo_train.TRAINING_START_PROVEN_FALSE


def test_cli_refusal_preserves_receipt_proof_that_training_started(monkeypatch, tmp_path, capsys):
    contract = json.loads(nemo_train.CONTRACT_PATH.read_text(encoding="utf-8"))
    output = tmp_path / "run"

    def fail_after_start(_snapshot, observed_output, _confirmation, _ack, _cache):
        nemo_train.atomic_json(
            observed_output / "receipts" / "training-receipt.json",
            {
                "schema_version": "szl.nemo.training-receipt.v1",
                "state": "FAILED_NOT_PROMOTED",
                "training_started_at_unix_ns": 1,
                "promotion": "NOT_PROMOTED",
            },
        )
        raise nemo_train.GateRefused("post-start fixture refusal")

    monkeypatch.setattr(nemo_train, "training_mutex", lambda: nullcontext())
    monkeypatch.setattr(
        nemo_train, "fresh_hf_modules_cache", lambda: nullcontext({"state": "FIXTURE"})
    )
    monkeypatch.setattr(nemo_train, "train", fail_after_start)
    code = nemo_train.main(
        [
            "train",
            "--base-snapshot",
            str(tmp_path / "base"),
            "--output-dir",
            str(output),
            "--confirmation",
            contract["training"]["confirmation_phrase"],
            "--license-acknowledgement",
            contract["base"]["license_acknowledgement"],
        ]
    )
    assert code == 3
    payload = json.loads(capsys.readouterr().err)
    assert payload["effects"]["training_started"] == nemo_train.TRAINING_START_PROVEN_TRUE


def test_training_start_receipt_state_is_tri_state(tmp_path):
    output = tmp_path / "run"
    assert nemo_train.observed_training_started(output) == nemo_train.TRAINING_START_UNKNOWN
    nemo_train.atomic_json(
        output / "receipts" / "training-receipt.json",
        {"schema_version": "wrong", "training_started_at_unix_ns": 1},
    )
    assert nemo_train.observed_training_started(output) == nemo_train.TRAINING_START_UNKNOWN
    nemo_train.atomic_json(
        output / "receipts" / "training-receipt.json",
        {
            "schema_version": "szl.nemo.training-receipt.v1",
            "state": "RUNNING_NOT_PROMOTED",
        },
    )
    assert nemo_train.observed_training_started(output) == nemo_train.TRAINING_START_PROVEN_FALSE
    for state in (
        "TRAINING_STARTED_NOT_PROMOTED",
        "FAILED_NOT_PROMOTED",
        "CANDIDATE_PASS_NOT_PROMOTED",
    ):
        nemo_train.atomic_json(
            output / "receipts" / "training-receipt.json",
            {
                "schema_version": "szl.nemo.training-receipt.v1",
                "state": state,
            },
        )
        assert nemo_train.observed_training_started(output) == nemo_train.TRAINING_START_UNKNOWN


def test_dsse_verifier_is_pinned_in_clean_scope_and_dirty_scope_refuses(monkeypatch, tmp_path):
    contract = json.loads(nemo_train.CONTRACT_PATH.read_text(encoding="utf-8"))
    assert "szl_dsse.py" in contract["source_control"]["paths"]
    assert "szl_content_address.py" in contract["source_control"]["paths"]
    _module, identity = nemo_train._load_pinned_dsse(contract)
    assert identity == {
        "path": contract["dsse"]["verifier_path"],
        "sha256": contract["dsse"]["verifier_sha256"],
        "content_address_path": contract["dsse"]["content_address_path"],
        "content_address_sha256": contract["dsse"]["content_address_sha256"],
        "key_id": contract["dsse"]["key_id"],
        "public_key_fingerprint_sha256": contract["dsse"][
            "public_key_fingerprint_sha256"
        ],
    }

    git = tmp_path / "git"
    git.write_text("fixture", encoding="utf-8")
    monkeypatch.setenv(contract["source_control"]["git_executable_env"], str(git))

    def fake_run(command, **_kwargs):
        if "rev-parse" in command:
            return subprocess.CompletedProcess(command, 0, stdout="a" * 40 + "\n", stderr="")
        return subprocess.CompletedProcess(
            command, 0, stdout=" M szl_dsse.py\n", stderr=""
        )

    monkeypatch.setattr(nemo_train.subprocess, "run", fake_run)
    with pytest.raises(nemo_train.GateRefused, match="scope is dirty"):
        nemo_train.git_identity(contract)


def test_dsse_verifier_replacement_and_key_substitution_refuse():
    contract = json.loads(nemo_train.CONTRACT_PATH.read_text(encoding="utf-8"))
    replaced = json.loads(json.dumps(contract))
    replaced["dsse"]["verifier_sha256"] = "0" * 64
    with pytest.raises(nemo_train.GateRefused, match="source mismatch"):
        nemo_train._load_pinned_dsse(replaced)

    replaced_dependency = json.loads(json.dumps(contract))
    replaced_dependency["dsse"]["content_address_sha256"] = "0" * 64
    with pytest.raises(nemo_train.GateRefused, match="content-address dependency source mismatch"):
        nemo_train._load_pinned_dsse(replaced_dependency)

    wrong_key = json.loads(json.dumps(contract))
    wrong_key["dsse"]["public_key_fingerprint_sha256"] = "0" * 64
    with pytest.raises(nemo_train.GateRefused, match="key identity mismatch"):
        nemo_train._load_pinned_dsse(wrong_key)


def test_dsse_loader_uses_only_pinned_dependency_and_restores_ambient_module(
    monkeypatch,
):
    contract = json.loads(nemo_train.CONTRACT_PATH.read_text(encoding="utf-8"))
    ambient = types.ModuleType("szl_content_address")
    ambient.sha256_content_address = lambda *_args, **_kwargs: "ambient-not-pinned"
    monkeypatch.setitem(sys.modules, "szl_content_address", ambient)
    repo = nemo_train.REPO.resolve()
    monkeypatch.setattr(
        sys,
        "path",
        [
            entry
            for entry in sys.path
            if not entry or Path(entry).resolve() != repo
        ],
    )

    module, identity = nemo_train._load_pinned_dsse(contract)

    assert module.public_key_fingerprint() == identity[
        "public_key_fingerprint_sha256"
    ]
    assert module.sha256_content_address is not ambient.sha256_content_address
    assert sys.modules["szl_content_address"] is ambient


def test_capacity_probe_requires_both_acknowledgements_before_receipt_or_model_load(tmp_path):
    receipt = tmp_path / "capacity.json"
    with pytest.raises(nemo_train.GateRefused, match="capacity-probe confirmation"):
        nemo_train.capacity_probe(tmp_path / "base", receipt, "WRONG", "WRONG")
    assert not receipt.exists()

    contract = json.loads(nemo_train.CONTRACT_PATH.read_text(encoding="utf-8"))
    with pytest.raises(nemo_train.GateRefused, match="license acknowledgement"):
        nemo_train.capacity_probe(
            tmp_path / "base",
            receipt,
            contract["training"]["confirmation_phrase"],
            "WRONG",
        )
    assert not receipt.exists()


def test_low_vram_calibration_requires_distinct_acknowledgement_and_never_weakens_training_gate(tmp_path):
    receipt = tmp_path / "calibration.json"
    contract = json.loads(nemo_train.CONTRACT_PATH.read_text(encoding="utf-8"))
    with pytest.raises(nemo_train.GateRefused, match="low-VRAM calibration confirmation"):
        nemo_train.low_vram_calibration(
            tmp_path / "base",
            receipt,
            contract["training"]["confirmation_phrase"],
            contract["base"]["license_acknowledgement"],
        )
    assert not receipt.exists()
    assert contract["gpu_admission"]["minimum_free_memory_mib"] == 6656
    profile = contract["low_vram_calibration"]
    assert profile["gpu_admission"]["minimum_free_memory_claim"] == (
        "CALIBRATION_ATTEMPT_FLOOR_NOT_TRAINING_THRESHOLD"
    )
    assert profile["training_admission_effect"] == "NONE"
    assert profile["may_modify_canonical_gpu_admission"] is False
    assert profile["may_enqueue_training"] is False
    assert profile["adapter_write_allowed"] is False
    assert profile["upload_allowed"] is False
    assert profile["publish_allowed"] is False
    assert profile["promotion_allowed"] is False


def test_activation_offload_calibration_is_exact_shape_and_never_authorizes_training(
    monkeypatch, tmp_path
):
    contract = json.loads(nemo_train.CONTRACT_PATH.read_text(encoding="utf-8"))
    profile = contract["activation_offload_calibration"]
    assert profile["sequence_length"] == contract["training"]["max_sequence_length"] == 768
    assert profile["optimizer"] == contract["training"]["optimizer"]
    assert profile["mechanism"] == "torch.autograd.graph.save_on_cpu"
    assert profile["pin_memory"] is False
    assert profile["parameter_offload"] is False
    assert profile["optimizer_offload"] is False
    assert profile["adoption_requirements"]["minimum_measured_vram_headroom_mib"] == 384
    for right in (
        "may_modify_canonical_gpu_admission",
        "may_enqueue_training",
        "adapter_write_allowed",
        "upload_allowed",
        "publish_allowed",
        "promotion_allowed",
    ):
        assert profile[right] is False
    assert contract["gpu_admission"]["minimum_free_memory_mib"] == 6656

    observed = {}

    def fake_capacity(*args, **kwargs):
        observed["args"] = args
        observed["kwargs"] = kwargs
        return 17

    monkeypatch.setattr(nemo_train, "capacity_probe", fake_capacity)
    code = nemo_train.activation_offload_calibration(
        tmp_path / "base",
        tmp_path / "receipt.json",
        profile["confirmation_phrase"],
        contract["base"]["license_acknowledgement"],
        {"cache": "fresh"},
    )
    assert code == 17
    assert observed["kwargs"] == {"probe_kind": "activation_offload_calibration"}


def test_activation_offload_calibration_requires_its_own_ack_before_receipt(tmp_path):
    receipt = tmp_path / "offload.json"
    contract = json.loads(nemo_train.CONTRACT_PATH.read_text(encoding="utf-8"))
    with pytest.raises(
        nemo_train.GateRefused, match="activation-offload calibration confirmation"
    ):
        nemo_train.capacity_probe(
            tmp_path / "base",
            receipt,
            contract["training"]["confirmation_phrase"],
            contract["base"]["license_acknowledgement"],
            probe_kind="activation_offload_calibration",
        )
    assert not receipt.exists()


def test_unknown_capacity_probe_kind_refuses_before_receipt(tmp_path):
    receipt = tmp_path / "unknown.json"
    with pytest.raises(nemo_train.GateRefused, match="unknown capacity probe kind"):
        nemo_train.capacity_probe(
            tmp_path / "base",
            receipt,
            "anything",
            "anything",
            probe_kind="undeclared",
        )
    assert not receipt.exists()


def test_host_memory_sample_is_measured_or_explicitly_unknown():
    sample = nemo_train.host_memory_sample()
    assert sample["state"] in {
        "MEASURED_PROCFS",
        "UNKNOWN_PROCFS_UNAVAILABLE",
        "UNKNOWN_PROCFS_READ_FAILED",
        "UNKNOWN_PROCFS_FIELDS_MISSING",
    }
    if sample["state"] == "MEASURED_PROCFS":
        assert sample["rss_bytes"] > 0
        assert sample["peak_rss_bytes"] >= sample["rss_bytes"]


def test_capacity_and_calibration_receipts_are_append_only(tmp_path):
    receipt = tmp_path / "existing.json"
    receipt.write_text('{"sentinel":true}\n', encoding="utf-8")
    before = receipt.read_bytes()
    contract = json.loads(nemo_train.CONTRACT_PATH.read_text(encoding="utf-8"))
    with pytest.raises(nemo_train.GateRefused, match="evidence is append-only"):
        nemo_train.low_vram_calibration(
            tmp_path / "base",
            receipt,
            contract["low_vram_calibration"]["confirmation_phrase"],
            contract["base"]["license_acknowledgement"],
        )
    assert receipt.read_bytes() == before


def test_initial_receipt_claim_is_exclusive(tmp_path):
    receipt = tmp_path / "claim.json"
    nemo_train.create_json_once(receipt, {"owner": "first"})
    with pytest.raises(nemo_train.GateRefused, match="evidence is append-only"):
        nemo_train.create_json_once(receipt, {"owner": "second"})
    assert json.loads(receipt.read_text(encoding="utf-8")) == {"owner": "first"}


def test_low_vram_calibration_failure_persists_fail_closed_receipt(monkeypatch, tmp_path):
    receipt = tmp_path / "calibration-failed.json"
    contract = json.loads(nemo_train.CONTRACT_PATH.read_text(encoding="utf-8"))
    monkeypatch.setattr(
        nemo_train,
        "git_identity",
        lambda _contract: (_ for _ in ()).throw(RuntimeError("fixture failure")),
    )
    monkeypatch.setattr(
        nemo_train,
        "query_gpu",
        lambda: (_ for _ in ()).throw(RuntimeError("fixture GPU unavailable")),
    )

    with pytest.raises(RuntimeError, match="fixture failure"):
        nemo_train.low_vram_calibration(
            tmp_path / "base",
            receipt,
            contract["low_vram_calibration"]["confirmation_phrase"],
            contract["base"]["license_acknowledgement"],
        )

    failed = json.loads(receipt.read_text(encoding="utf-8"))
    assert failed["schema_version"] == contract["low_vram_calibration"]["receipt_schema_version"]
    assert failed["state"] == "FAILED_CALIBRATION_NOT_TRAINED_NOT_QUALIFIED_NOT_PROMOTED"
    assert failed["error_type"] == "RuntimeError"
    assert failed["training_started"] is False
    assert failed["effects"]["training_authorized"] is False
    assert failed["effects"]["queue_progression_allowed"] is False
    assert failed["effects"]["adapter_written"] is False
    assert failed["effects"]["uploaded"] is False
    assert failed["effects"]["published"] is False
    assert failed["effects"]["promoted"] is False
    assert failed["failure_evidence"]["completed_micro_steps"] == 0
    assert failed["failure_evidence"]["terminal_gpu_sample_error"] == "RuntimeError"


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


def test_preflight_refuses_undeclared_or_mislabelled_gpu_policy():
    contract = json.loads(nemo_train.CONTRACT_PATH.read_text(encoding="utf-8"))
    weakened = json.loads(json.dumps(contract["gpu_admission"]))
    weakened["minimum_free_memory_mib"] = 1
    receipt = nemo_train.preflight(
        None,
        check_gpu=True,
        probe=True,
        gpu_policy=weakened,
        gpu_check_id="GPU_ADMISSION",
    )
    assert receipt["state"] == "BLOCKED"
    assert receipt["checks"][0]["reason"] == (
        "GPU policy override is not the selected contract-declared profile"
    )

    receipt = nemo_train.preflight(
        None,
        check_gpu=True,
        probe=True,
        gpu_profile_key="low_vram_calibration",
        gpu_policy=contract["low_vram_calibration"]["gpu_admission"],
        gpu_check_id="GPU_ADMISSION",
    )
    assert receipt["state"] == "BLOCKED"
    assert "selected profile check identity" in receipt["checks"][0]["reason"]

    receipt = nemo_train.preflight(
        None,
        check_gpu=True,
        probe=True,
        gpu_profile_key="activation_offload_calibration",
        gpu_policy=contract["low_vram_calibration"]["gpu_admission"],
        gpu_check_id="GPU_ACTIVATION_OFFLOAD_CALIBRATION_ATTEMPT_FLOOR",
    )
    assert receipt["state"] == "BLOCKED"
    assert "selected contract-declared profile" in receipt["checks"][0]["reason"]

    receipt = nemo_train.preflight(None, check_gpu=True, probe=True, gpu_policy={})
    assert receipt["state"] == "BLOCKED"
    assert "selected contract-declared profile" in receipt["checks"][0]["reason"]


def test_python_network_guard_refuses_connections():
    with nemo_train.deny_python_network() as control:
        assert control["state"] == "PYTHON_SOCKET_DENIED"
        with pytest.raises(OSError, match="network denied"):
            socket.create_connection(("127.0.0.1", 9))


def test_shared_gpu_lease_publishes_owner_and_refuses_second_acquisition(tmp_path):
    assert nemo_train.SHARED_GPU_TRAINING_LEASE_DIR == (
        ROOT / "model_release" / "szl-forge" / "queue-state" / "gpu-training.lease"
    )
    lease_path = tmp_path / "gpu-training.lease"
    with nemo_train.training_mutex(lease_path):
        owner_path = lease_path / nemo_train.GPU_TRAINING_LEASE_OWNER
        assert owner_path.is_file()
        owner = json.loads(owner_path.read_text(encoding="utf-8"))
        assert owner["schema_version"] == "szl.gpu-training-lease-owner.v1"
        assert owner["pid"] == os.getpid()
        assert owner["arbitration"] == "ATOMIC_DIRECTORY_CREATION"
        assert owner["stale_policy"] == "OPERATOR_REVIEW_REQUIRED"
        assert owner["automatic_stale_deletion"] is False
        with pytest.raises(nemo_train.GateRefused, match="shared GPU lease"):
            with nemo_train.training_mutex(lease_path):
                pytest.fail("second training lease should not be acquired")
        assert json.loads(owner_path.read_text(encoding="utf-8"))["owner_token"] == owner["owner_token"]
    assert not lease_path.exists()


def test_base_verifier_binds_files_and_architecture(monkeypatch, tmp_path):
    config = {
        "model_type": "nemotron_h",
        "vocab_size": 131072,
        "architectures": ["NemotronHForCausalLM"],
        "auto_map": {
            "AutoConfig": "configuration_nemotron_h.NemotronHConfig",
            "AutoModelForCausalLM": "modeling_nemotron_h.NemotronHForCausalLM",
        },
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
            "auto_map": config["auto_map"],
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
    assert contract["release_state"] == "V1_EVALUATION_FAILED_V2_CORRECTION_DECLARED"
    assert contract["quality_claim"] == "NOT_ESTABLISHED"
    assert contract["base"]["trust_remote_code"] is True
    assert contract["base"]["remote_code_policy"] == "PINNED_OFFICIAL_NVIDIA_FILES_ONLY"
    required = {item["path"]: item for item in contract["base"]["required_files"]}
    assert required["configuration_nemotron_h.py"]["sha256"] == "07fa66e5b3da7e6a71c1a263e3dd68da11c8afa9178b47c49510ba628746fcff"
    assert required["modeling_nemotron_h.py"]["sha256"] == "ea982af0b805f181573f919ecb001d5bbc0153459923cf4b2f1ccae194e415a4"
    assert contract["runtime"]["operating_system_allowlist"] == ["Linux"]
    assert set(contract["runtime"]["module_required"]) == {"mamba_ssm", "causal_conv1d"}
    assert contract["training"]["capacity_probe_sequence_length"] == 768
    assert contract["training"]["capacity_probe_sequence_length"] == contract["training"]["max_sequence_length"]
    assert contract["training"]["loss_scope"] == "ASSISTANT_COMPLETION_ONLY"
    assert contract["training"]["require_untruncated_assistant_completion"] is True
    assert contract["curriculum"]["frozen_original_eval_sha256"] == "caeb07c94929c24a47fd12f35cbc9021523308dc9fcc684bd444ffcf4a367b0d"
    assert contract["evaluation"]["mandatory_sets"] == [
        "ORIGINAL_FROZEN",
        "SHADOW_PREREGISTERED",
    ]
    assert contract["evaluation"]["requires_both_sets_pass"] is True
    assert contract["runtime"]["torch_exact_allowlist"] == ["2.10.0+cu128"]
    assert contract["runtime"]["minimum_cuda_runtime"] == [12, 8]
    assert contract["runtime"]["package_exact"] == {
        "transformers": "4.48.3",
        "trl": "0.15.2",
        "peft": "0.14.0",
        "datasets": "3.2.0",
        "accelerate": "1.12.0",
        "bitsandbytes": "0.49.2",
        "mamba-ssm": "2.3.2.post1",
        "causal-conv1d": "1.6.2.post1",
        "tokenizers": "0.21.4",
        "huggingface-hub": "0.36.2",
    }
    assert contract["promotion"]["automatic"] is False
    assert contract["promotion"]["requires_signed_dsse"] is True
    assert contract["promotion"]["requires_transparency_log"] is True
    assert contract["external_mutations"] == {
        "upload": False,
        "publish": False,
        "deploy": False,
        "push": False,
    }


def test_native_windows_execution_lane_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(nemo_train.platform, "system", lambda: "Windows")

    with pytest.raises(nemo_train.GateRefused, match="native Windows"):
        nemo_train.verify_nemotron_execution_lane(tmp_path)


def test_missing_linux_mamba_module_fails_before_custom_code_load(monkeypatch, tmp_path):
    monkeypatch.setattr(nemo_train.platform, "system", lambda: "Linux")

    def missing(name):
        raise ModuleNotFoundError(name)

    monkeypatch.setattr(nemo_train.importlib, "import_module", missing)
    with pytest.raises(nemo_train.GateRefused, match="mamba_ssm"):
        nemo_train.verify_nemotron_execution_lane(tmp_path)


def test_loaded_dynamic_code_must_match_pinned_source_hashes(monkeypatch, tmp_path):
    import transformers
    import transformers.dynamic_module_utils

    auto_config = transformers.AutoConfig
    auto_tokenizer = transformers.AutoTokenizer
    generation_config = transformers.GenerationConfig
    original_import_module = nemo_train.importlib.import_module

    contract = json.loads(nemo_train.CONTRACT_PATH.read_text(encoding="utf-8"))
    for item in contract["base"]["required_files"]:
        if item["path"] in {"configuration_nemotron_h.py", "modeling_nemotron_h.py"}:
            (tmp_path / item["path"]).write_bytes(b"fixture")

    class FakeConfig:
        model_type = "nemotron_h"
        pad_token_id = 0

    class FakeGenerationConfig:
        pad_token_id = 0

    class NemotronHForCausalLM:
        pass

    monkeypatch.setattr(nemo_train.platform, "system", lambda: "Linux")
    def import_module(name, *args, **kwargs):
        if name in {"mamba_ssm", "causal_conv1d"}:
            return types.SimpleNamespace(__version__="fixture")
        return original_import_module(name, *args, **kwargs)

    monkeypatch.setattr(nemo_train.importlib, "import_module", import_module)
    monkeypatch.setattr(
        auto_config,
        "from_pretrained",
        lambda *_args, **_kwargs: FakeConfig(),
    )
    monkeypatch.setattr(
        auto_tokenizer,
        "from_pretrained",
        lambda *_args, **_kwargs: FakePaddingTokenizer(),
    )
    monkeypatch.setattr(
        generation_config,
        "from_pretrained",
        lambda *_args, **_kwargs: FakeGenerationConfig(),
    )
    monkeypatch.setattr(
        transformers.dynamic_module_utils,
        "get_class_from_dynamic_module",
        lambda *_args, **_kwargs: NemotronHForCausalLM,
    )

    with pytest.raises(nemo_train.GateRefused, match="loaded pinned NVIDIA code hash mismatch"):
        nemo_train.verify_nemotron_execution_lane(tmp_path)


def test_quantized_mamba_lora_forward_binds_reviewed_module_path_without_global_mutation():
    model = FakeQuantizedMambaModel()
    global_before = is_fast_path_available

    receipt = nemo_train.bind_quantized_mamba_lora_forward(
        model, compatibility_contract(), "fixture"
    )

    assert receipt["state"] == "BOUND_REVIEWED_DECOMPOSED_CUDA_FORWARD"
    assert receipt["expected_mixer_count"] == receipt["bound_mixer_count"] == 2
    assert receipt["config_use_mamba_kernels_before"] is True
    assert receipt["config_use_mamba_kernels_after"] is True
    assert model.config.use_mamba_kernels is True
    assert is_fast_path_available is global_before is True
    assert all(mixer.forward("fixture") == "decomposed-cuda" for mixer in model.mixers)
    assert all(mixer.training is True for mixer in model.mixers)
    assert all(
        mixer.dispatch_observation
        == {"mixer_training": False, "projection_training": True}
        for mixer in model.mixers
    )
    assert all(
        row["projection_base_class"].endswith(".Linear4bit")
        and row["lora_adapter_names"] == ["default"]
        and row["execution_device"] == "cuda"
        and row["combined_training_kernel_selected"] is False
        and row["projection_module_forward_preserved"] is True
        and row["module_global_fast_path_before"] is True
        and row["module_global_fast_path_after"] is True
        for row in receipt["modules"]
    )


def test_quantized_mamba_lora_forward_refuses_mixer_count_mismatch():
    model = FakeQuantizedMambaModel(mixer_count=1)

    with pytest.raises(nemo_train.GateRefused, match="Mamba mixer count mismatch"):
        nemo_train.bind_quantized_mamba_lora_forward(
            model, compatibility_contract(), "fixture"
        )


def test_quantized_mamba_lora_forward_refuses_incomplete_adapter_wrapper():
    model = FakeQuantizedMambaModel(valid_lora=False)

    with pytest.raises(nemo_train.GateRefused, match="LoRA adapter sets are incomplete"):
        nemo_train.bind_quantized_mamba_lora_forward(
            model, compatibility_contract(), "fixture"
        )


def test_quantized_mamba_lora_forward_refuses_missing_reviewed_forward():
    model = FakeQuantizedMambaModel()
    model.mixers[0].cuda_kernels_forward = None

    with pytest.raises(nemo_train.GateRefused, match="lacks reviewed cuda_kernels_forward"):
        nemo_train.bind_quantized_mamba_lora_forward(
            model, compatibility_contract(), "fixture"
        )


def test_decomposed_cuda_dispatch_restores_mixer_training_after_failure():
    model = FakeQuantizedMambaModel()
    nemo_train.bind_quantized_mamba_lora_forward(
        model, compatibility_contract(), "fixture"
    )
    model.mixers[0].raise_during_cuda = True

    with pytest.raises(RuntimeError, match="fixture CUDA failure"):
        model.mixers[0].forward("fixture")

    assert model.mixers[0].training is True
    assert model.mixers[0].out_proj.training is True


def test_naive_mamba_pairwise_memory_model_matches_measured_nine_gib_request():
    model = FakeQuantizedMambaModel()

    evidence = nemo_train.mamba_naive_pairwise_memory_model(
        model.config, batch_size=1, sequence_length=768
    )

    assert evidence["shape"] == [1, 3, 256, 256, 96, 128]
    assert evidence["bytes"] == 9 * 1024**3
    assert evidence["gib"] == 9.0
    assert evidence["padded_sequence_length"] == 768


def test_optimizer_and_checkpoint_attestations_are_fail_closed():
    tensor = types.SimpleNamespace(numel=lambda: 4, element_size=lambda: 2)
    optimizer = types.SimpleNamespace(state={"parameter": {"moment": tensor}})

    assert nemo_train.optimizer_state_inventory(optimizer) == {
        "state": "MEASURED_FROM_OPTIMIZER_STATE",
        "entry_count": 1,
        "tensor_count": 1,
        "tensor_bytes": 8,
    }
    assert nemo_train.gradient_checkpointing_evidence(
        types.SimpleNamespace(is_gradient_checkpointing=True), "fixture"
    )["use_reentrant"] is False
    with pytest.raises(nemo_train.GateRefused, match="gradient checkpointing is not active"):
        nemo_train.gradient_checkpointing_evidence(
            types.SimpleNamespace(is_gradient_checkpointing=False), "fixture"
        )


def test_capacity_and_training_bind_mamba_forward_only_after_peft_wrapping():
    runner = RUNNER.read_text(encoding="utf-8")
    tokenizer_load = runner.index("tokenizer = AutoTokenizer.from_pretrained", runner.index("def train("))
    padding_admission = runner.index(
        'tokenizer, contract, "training"', tokenizer_load
    )
    capacity_wrap = runner.index("model = get_peft_model(model, lora)")
    capacity_bind = runner.index(
        'model, contract, "capacity"', capacity_wrap
    )
    trainer_wrap = runner.index("trainer = SFTTrainer")
    training_bind = runner.index(
        'trainer.model, contract, "training"', trainer_wrap
    )
    training_start = runner.index(
        'receipt["state"] = "TRAINING_STARTED_NOT_PROMOTED"', trainer_wrap
    )

    assert tokenizer_load < padding_admission < trainer_wrap
    assert capacity_wrap < capacity_bind < trainer_wrap
    assert trainer_wrap < training_bind < training_start
    assert runner.count('gradient_checkpointing_kwargs={"use_reentrant": False}') >= 3
    assert '"packing": False' in runner
    assert '"optimizer_state_before_forward"' in runner
    assert '"forward_evidence"' in runner
    assert "pad_token_id=tokenizer.pad_token_id" in runner
    assert "pad_token_id=tokenizer.pad_token_id or" not in runner


def test_training_requires_linux_network_namespace(monkeypatch):
    monkeypatch.setattr(nemo_train.platform, "system", lambda: "Windows")
    with pytest.raises(nemo_train.GateRefused, match="Linux network namespace"):
        nemo_train.verify_linux_network_namespace()


def test_linux_network_namespace_uses_namespace_scoped_interface_measurement(
    monkeypatch, tmp_path
):
    route_path = tmp_path / "route"
    route_path.write_text("", encoding="utf-8")
    real_path = nemo_train.Path

    monkeypatch.setattr(nemo_train.platform, "system", lambda: "Linux")
    monkeypatch.setattr(nemo_train.socket, "if_nameindex", lambda: [(1, "lo")])
    monkeypatch.setattr(
        nemo_train,
        "Path",
        lambda value: route_path if value == "/proc/net/route" else real_path(value),
    )
    monkeypatch.setattr(nemo_train.os, "readlink", lambda _path: "net:[fixture]")

    evidence = nemo_train.verify_linux_network_namespace()

    assert evidence == {
        "state": "OS_NETWORK_NAMESPACE_DENIED",
        "interfaces": ["lo"],
        "default_route_count": 0,
        "interface_measurement_source": "socket.if_nameindex",
        "route_measurement_source": str(route_path),
        "namespace_link": "net:[fixture]",
    }


def test_linux_network_namespace_refuses_non_loopback_interface(monkeypatch, tmp_path):
    route_path = tmp_path / "route"
    route_path.write_text(
        "Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\n",
        encoding="utf-8",
    )
    real_path = nemo_train.Path

    monkeypatch.setattr(nemo_train.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        nemo_train.socket,
        "if_nameindex",
        lambda: [(1, "lo"), (2, "eth0")],
    )
    monkeypatch.setattr(
        nemo_train,
        "Path",
        lambda value: route_path if value == "/proc/net/route" else real_path(value),
    )

    with pytest.raises(nemo_train.GateRefused, match="network namespace is not isolated"):
        nemo_train.verify_linux_network_namespace()


def test_linux_network_namespace_refuses_malformed_route_evidence(monkeypatch, tmp_path):
    route_path = tmp_path / "route"
    route_path.write_text("not a Linux route table\n", encoding="utf-8")
    real_path = nemo_train.Path

    monkeypatch.setattr(nemo_train.platform, "system", lambda: "Linux")
    monkeypatch.setattr(nemo_train.socket, "if_nameindex", lambda: [(1, "lo")])
    monkeypatch.setattr(
        nemo_train,
        "Path",
        lambda value: route_path if value == "/proc/net/route" else real_path(value),
    )

    with pytest.raises(nemo_train.GateRefused, match="route evidence is invalid"):
        nemo_train.verify_linux_network_namespace()


def test_linux_network_namespace_refuses_unknown_namespace_identity(monkeypatch, tmp_path):
    route_path = tmp_path / "route"
    route_path.write_text("", encoding="utf-8")
    real_path = nemo_train.Path

    monkeypatch.setattr(nemo_train.platform, "system", lambda: "Linux")
    monkeypatch.setattr(nemo_train.socket, "if_nameindex", lambda: [(1, "lo")])
    monkeypatch.setattr(
        nemo_train,
        "Path",
        lambda value: route_path if value == "/proc/net/route" else real_path(value),
    )
    def unavailable_readlink(_path):
        raise OSError("unavailable")

    monkeypatch.setattr(nemo_train.os, "readlink", unavailable_readlink)

    with pytest.raises(nemo_train.GateRefused, match="identity cannot be measured"):
        nemo_train.verify_linux_network_namespace()


def test_historical_static_preflight_is_preserved_and_scoped():
    contract = json.loads(nemo_train.CONTRACT_PATH.read_text(encoding="utf-8"))
    lineage = contract["evidence_lineage"]
    path = ROOT / lineage["static_preflight_path"]
    receipt = json.loads(path.read_text(encoding="utf-8"))

    assert receipt["state"] == "PASS"
    assert all(check["id"] != "LINUX_MAMBA_EXECUTION_LANE" for check in receipt["checks"])
    assert nemo_train.sha256_canonical_lf(path) == lineage["static_preflight_canonical_lf_sha256"]
    assert lineage["scope"] == "STATIC_FILE_AND_LICENSE_INTEGRITY_ONLY"
    assert lineage["runtime_readiness_established"] is False


def test_wsl_import_receipt_is_hash_bound_and_never_claims_model_readiness():
    contract = json.loads(nemo_train.CONTRACT_PATH.read_text(encoding="utf-8"))
    lineage = contract["evidence_lineage"]
    path = ROOT / lineage["wsl_runtime_import_receipt_path"]
    receipt = json.loads(path.read_text(encoding="utf-8"))

    assert nemo_train.sha256_canonical_lf(path) == lineage["wsl_runtime_import_receipt_canonical_lf_sha256"]
    assert lineage["wsl_runtime_import_receipt_scope"] == "OS_NETWORK_ISOLATED_CONFIG_AND_CUSTOM_CLASS_IMPORT_NO_WEIGHTS"
    assert receipt["status"] == "PASS"
    assert receipt["network_namespace"]["interfaces"] == ["lo"]
    assert receipt["network_namespace"]["default_routes"] == []
    assert receipt["training_started"] is False
    assert receipt["effects"]["weights_loaded"] is False
    assert receipt["effects"]["model_instantiated"] is False


def test_setup_probe_and_contract_pin_the_same_training_runtime():
    contract = json.loads(nemo_train.CONTRACT_PATH.read_text(encoding="utf-8"))
    setup = (ROOT / "model_release" / "szl-nemo" / "setup_wsl_runtime.sh").read_text(encoding="utf-8")
    probe = (ROOT / "model_release" / "szl-nemo" / "wsl_runtime_probe.py").read_text(encoding="utf-8")

    assert "torch==2.10.0" in setup and '"2.10.0+cu128"' in probe
    for package, version in contract["runtime"]["package_exact"].items():
        distribution = package.replace("-", "_") if package in {"mamba-ssm", "causal-conv1d"} else package
        assert version in setup, f"setup does not pin {package}=={version}"
        assert f'"{package}": "{version}"' in probe, f"probe does not bind {distribution} {version}"


def test_legacy_powershell_queue_train_is_retired_and_status_is_read_only():
    queue = (ROOT / "model_release" / "szl-nemo" / "Invoke-SZLNemoFineTuneQueue.ps1").read_text(encoding="utf-8")
    refusal = queue.index("Legacy PowerShell queue-train is retired")
    status = queue.index("READ_ONLY_STATUS")
    assert refusal < status
    assert "szl_nemo_wsl_queue.py" in queue[refusal:status]
    assert "New-Item" not in queue
    assert "& $Python" not in queue
    assert "Set-Content" not in queue
    assert "WriteAllText" not in queue


def test_trl_lane_uses_the_pinned_048_api_and_capacity_is_network_isolated():
    runner = RUNNER.read_text(encoding="utf-8")
    launcher = (ROOT / "model_release" / "szl-nemo" / "run_wsl_governed.sh").read_text(encoding="utf-8")

    assert "max_seq_length=settings[\"max_sequence_length\"]" in runner
    assert "max_length=settings[\"max_sequence_length\"]" not in runner
    assert '"PASS_CAPACITY_ONLY_NOT_TRAINED_NOT_PROMOTED"' in runner
    assert '"capacity_optimization_step_started": False' in runner
    assert '"capacity_optimization_step_completed": False' in runner
    assert "loaded NVIDIA model source hash mismatch" in runner
    assert "fresh_hf_modules_cache" in runner
    assert '"curriculum_inputs_before"' in runner
    assert '"source_control_after"' in runner
    assert "from bitsandbytes.optim import PagedAdamW8bit" in runner
    assert "optimizer = PagedAdamW8bit" in runner
    assert 'padding="max_length"' in runner
    assert 'labels = labels.masked_fill(encoded["attention_mask"] == 0, -100)' in runner
    assert "torch.optim.AdamW" not in runner
    assert 'device_map="auto"' not in runner
    assert '"gradient_accumulation_micro_steps": accumulation' in runner
    assert "del optimizer, output" not in runner
    assert "failure_evidence" in runner
    assert "optimizer = None" in runner
    assert "torch_module.cuda.empty_cache()" in runner
    assert 'evaluate_set("ORIGINAL_FROZEN", original_rows, EVAL_PATH)' in runner
    assert 'evaluate_set("SHADOW_PREREGISTERED", shadow_rows, SHADOW_EVAL_PATH)' in runner
    assert "evaluate-adapter" in runner
    assert "EVALUATE_SZL_NEMO_GOVERNED_ADAPTER_V2" in runner
    assert 'thermal_scope="evaluation"' in runner
    assert "DataCollatorForCompletionOnlyLM" in runner
    assert "capacity-probe" in launcher
    assert "calibrate-vram" in launcher
    assert "--mode calibrate" in launcher
    assert "calibrate-activation-offload" in launcher
    assert "--mode activation-offload" in launcher
    assert '"$MODE" == "evaluate"' in launcher
    assert "evaluate-adapter" in launcher
    assert 'save_on_cpu(pin_memory=False, device_type="cuda")' in runner
    assert "unshare --user --map-root-user --net" in launcher


def test_gpu_inventory_helper_is_read_only_and_reports_the_fixed_gap():
    helper = (
        ROOT / "model_release" / "szl-nemo" / "Measure-SZLNemoGpuInventory.ps1"
    ).read_text(encoding="utf-8")
    folded = helper.casefold()
    assert "stop-process" not in folded
    assert "taskkill" not in folded
    assert "processes_stopped = $false" in folded
    assert "wddm_counter_reported_not_nvml_resident" in folded
    assert "minimum_free_memory_mib" in folded
    assert "evidence is append-only" in folded
    assert "[io.file]::move" in folded
    assert "move-item -force" not in folded
    assert "required_device_name" in folded
    assert "unknown_unavailable" in folded


def test_generated_curriculum_is_byte_deterministic_lf(tmp_path):
    nemo_train.build_curriculum(tmp_path)
    for name in ("train.jsonl", "eval.jsonl", "shadow-eval.jsonl", "curriculum-manifest.json"):
        assert b"\r" not in (tmp_path / name).read_bytes()


def test_dynamic_module_cache_is_fresh_process_unique_and_removed():
    with nemo_train.fresh_hf_modules_cache() as receipt:
        cache = Path(os.environ["HF_MODULES_CACHE"])
        assert cache.is_dir()
        assert list(cache.iterdir()) == []
        assert receipt["state"] == "FRESH_PROCESS_UNIQUE_CACHE"
    assert not cache.exists()
