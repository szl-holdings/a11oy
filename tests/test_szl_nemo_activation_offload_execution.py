# SPDX-License-Identifier: Apache-2.0
"""No-GPU execution tests for the SZL-Nemo activation-offload experiment."""

from __future__ import annotations

from contextlib import nullcontext
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import types

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "model_release" / "szl-nemo" / "szl_nemo_finetune.py"
LAUNCHER = ROOT / "model_release" / "szl-nemo" / "run_wsl_governed.sh"
SPEC = importlib.util.spec_from_file_location(
    "szl_nemo_activation_offload_execution", RUNNER
)
assert SPEC and SPEC.loader
nemo_train = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(nemo_train)


class _FakeTensor:
    def __init__(self, *, shape: tuple[int, ...] = (1, 768), value: float = 1.0):
        self.shape = shape
        self.value = value
        self.device = types.SimpleNamespace(type="cuda")

    def to(self, _device):
        return self

    def clone(self):
        return self

    def masked_fill(self, _mask, _value):
        return self

    def detach(self):
        return self

    def cpu(self):
        return self

    def float(self):
        return self

    def pow(self, _exponent):
        return self

    def sum(self):
        return self

    def all(self):
        return self

    def item(self):
        return self.value

    def __eq__(self, _other):
        return self

    def __float__(self):
        return float(self.value)


class _FakeParameter:
    def __init__(self, *, requires_grad: bool):
        self.requires_grad = requires_grad
        self.grad = None
        self.device = types.SimpleNamespace(type="cuda")

    def numel(self):
        return 32


class _FakeLoss(_FakeTensor):
    def __init__(self, state: dict[str, object], trainable: _FakeParameter):
        super().__init__(shape=(), value=0.25)
        self._state = state
        self._trainable = trainable
        self._hook = None

    def __truediv__(self, _divisor):
        return self

    def backward(self):
        assert self._state["offload_context_active"] is True
        if self._hook is not None:
            self._hook(_FakeTensor(shape=(), value=1.0))
        self._state["backward_inside_offload_context"] = True
        self._trainable.grad = _FakeTensor(shape=(32,), value=1.0)

    def register_hook(self, hook):
        self._hook = hook
        return types.SimpleNamespace(remove=lambda: setattr(self, "_hook", None))


class _FakeModel:
    def __init__(self, state: dict[str, object]):
        self._state = state
        self._trainable = _FakeParameter(requires_grad=True)
        self._frozen = _FakeParameter(requires_grad=False)
        self.config = types.SimpleNamespace(use_cache=True)

    def parameters(self):
        return iter((self._trainable, self._frozen))

    def train(self):
        self._state["model_train_called"] = True

    def __call__(self, **_kwargs):
        self._state["forward_called"] = True
        return types.SimpleNamespace(loss=_FakeLoss(self._state, self._trainable))


class _FakeTokenizer:
    pad_token_id = 0
    eos_token_id = 1

    def apply_chat_template(self, _messages, **_kwargs):
        return "fixture"

    def __call__(self, _text, **_kwargs):
        return {
            "input_ids": _FakeTensor(shape=(1, 768)),
            "attention_mask": _FakeTensor(shape=(1, 768)),
        }


class _FakeRuntimeGuard:
    def __init__(self, *_args, **_kwargs):
        self._state = "RUNNING"

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False

    def check(self, _stage):
        return None

    def finalize(self):
        self._state = "PASS"

    def finalize_failure(self):
        self._state = "FAILED"

    def receipt(self):
        return {"state": self._state, "fixture": True}


def _install_fake_frameworks(monkeypatch, state: dict[str, object]) -> None:
    class SaveOnCpu:
        def __init__(self, *, pin_memory: bool, device_type: str):
            assert pin_memory is False
            assert device_type == "cuda"

        def __enter__(self):
            state["save_on_cpu_entered"] = int(state["save_on_cpu_entered"]) + 1
            state["offload_context_active"] = True
            return self

        def __exit__(self, _exc_type, _exc, _traceback):
            state["offload_context_active"] = False
            state["save_on_cpu_exited"] = int(state["save_on_cpu_exited"]) + 1
            return False

    class FakeCuda:
        @staticmethod
        def is_bf16_supported():
            return True

        @staticmethod
        def reset_peak_memory_stats():
            return None

        @staticmethod
        def memory_allocated():
            return 101

        @staticmethod
        def memory_reserved():
            return 202

        @staticmethod
        def max_memory_allocated():
            return 303

        @staticmethod
        def max_memory_reserved():
            return 404

        @staticmethod
        def synchronize():
            return None

        @staticmethod
        def empty_cache():
            state["empty_cache_called"] = True

    torch = types.ModuleType("torch")
    torch.bfloat16 = "torch.bfloat16"
    torch.float16 = "torch.float16"
    torch.cuda = FakeCuda()
    torch.autograd = types.SimpleNamespace(
        graph=types.SimpleNamespace(save_on_cpu=SaveOnCpu)
    )
    torch.isfinite = lambda _tensor: _FakeTensor(shape=(), value=1.0)

    model = _FakeModel(state)

    class AutoModelForCausalLM:
        @staticmethod
        def from_pretrained(*_args, **_kwargs):
            return model

    class AutoTokenizer:
        @staticmethod
        def from_pretrained(*_args, **_kwargs):
            return _FakeTokenizer()

    transformers = types.ModuleType("transformers")
    transformers.AutoModelForCausalLM = AutoModelForCausalLM
    transformers.AutoTokenizer = AutoTokenizer
    transformers.BitsAndBytesConfig = lambda **kwargs: types.SimpleNamespace(**kwargs)

    peft = types.ModuleType("peft")
    peft.LoraConfig = lambda **kwargs: types.SimpleNamespace(**kwargs)
    peft.prepare_model_for_kbit_training = lambda observed, **_kwargs: observed
    peft.get_peft_model = lambda observed, _config: observed

    class PagedAdamW8bit:
        def __init__(self, _parameters, *, lr: float):
            state["optimizer_learning_rate"] = lr

        def zero_grad(self, *, set_to_none: bool):
            assert set_to_none is True

        def step(self):
            state["optimizer_step_called"] = True

    bitsandbytes = types.ModuleType("bitsandbytes")
    bitsandbytes_optim = types.ModuleType("bitsandbytes.optim")
    bitsandbytes_optim.PagedAdamW8bit = PagedAdamW8bit
    bitsandbytes.optim = bitsandbytes_optim

    for name, module in {
        "torch": torch,
        "transformers": transformers,
        "peft": peft,
        "bitsandbytes": bitsandbytes,
        "bitsandbytes.optim": bitsandbytes_optim,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)


def _prepare_mocked_probe(
    monkeypatch,
    *,
    host_memory_states: list[str],
) -> tuple[dict[str, object], dict[str, object]]:
    state: dict[str, object] = {
        "save_on_cpu_entered": 0,
        "save_on_cpu_exited": 0,
        "offload_context_active": False,
        "backward_inside_offload_context": False,
        "model_train_called": False,
        "forward_called": False,
        "optimizer_step_called": False,
        "empty_cache_called": False,
    }
    _install_fake_frameworks(monkeypatch, state)
    contract = json.loads(nemo_train.CONTRACT_PATH.read_text(encoding="utf-8"))
    identity = {"commit": "fixture", "scope": "clean"}
    base_files = [{"path": "model.safetensors", "sha256": "fixture"}]
    curriculum = {"train": "fixture"}

    monkeypatch.setattr(nemo_train, "git_identity", lambda _contract: dict(identity))
    monkeypatch.setattr(
        nemo_train,
        "preflight",
        lambda _snapshot, **kwargs: {
            "state": "PASS",
            "selected_profile": kwargs["gpu_profile_key"],
        },
    )
    monkeypatch.setattr(nemo_train, "verify_base", lambda _snapshot: list(base_files))
    monkeypatch.setattr(
        nemo_train, "curriculum_input_identity", lambda: dict(curriculum)
    )
    monkeypatch.setattr(
        nemo_train,
        "iter_jsonl",
        lambda _path: iter(
            [
                {
                    "record_id": "fixture-record",
                    "messages": [{"role": "user", "content": "fixture"}],
                }
            ]
        ),
    )
    monkeypatch.setattr(
        nemo_train,
        "verify_linux_network_namespace",
        lambda: {"state": "PASS", "interfaces": ["lo"]},
    )
    monkeypatch.setattr(nemo_train, "RuntimeGuard", _FakeRuntimeGuard)
    monkeypatch.setattr(
        nemo_train,
        "offline_framework_environment",
        lambda: nullcontext({"state": "OFFLINE_FIXTURE"}),
    )
    monkeypatch.setattr(
        nemo_train,
        "deny_python_network",
        lambda: nullcontext({"state": "NETWORK_DENIED_FIXTURE"}),
    )
    monkeypatch.setattr(
        nemo_train, "verify_runtime", lambda _torch: {"state": "PINNED_FIXTURE"}
    )
    monkeypatch.setattr(
        nemo_train,
        "verify_loaded_model_source",
        lambda _model, _contract, _mode: "NemotronHForCausalLMFixture",
    )
    pending_host_states = list(host_memory_states)

    def fake_host_memory_sample():
        observed_state = (
            pending_host_states.pop(0)
            if pending_host_states
            else host_memory_states[-1]
        )
        if observed_state != "MEASURED_PROCFS":
            return {"state": observed_state}
        return {
            "state": "MEASURED_PROCFS",
            "measured_at_unix_ns": 1,
            "rss_bytes": 1_000_000,
            "peak_rss_bytes": 2_000_000,
            "mem_available_bytes": 8 * 1024 * 1024 * 1024,
        }

    monkeypatch.setattr(nemo_train, "host_memory_sample", fake_host_memory_sample)
    monkeypatch.setattr(
        nemo_train,
        "query_gpu",
        lambda: {
            "gpu_name": contract["runtime"]["required_device_name"],
            "memory_total_mib": 8151,
            "memory_used_mib": 2151,
            "memory_free_mib": 6000,
            "utilization_pct": 1,
            "temperature_c": 55,
        },
    )
    return state, contract


def _run_activation_probe(monkeypatch, tmp_path, *, host_memory_states: list[str]):
    state, contract = _prepare_mocked_probe(
        monkeypatch, host_memory_states=host_memory_states
    )
    profile = contract["activation_offload_calibration"]
    receipt_path = tmp_path / "activation-offload-receipt.json"
    result = nemo_train.capacity_probe(
        tmp_path / "base",
        receipt_path,
        profile["confirmation_phrase"],
        contract["base"]["license_acknowledgement"],
        {"state": "FRESH_FIXTURE"},
        probe_kind="activation_offload_calibration",
    )
    return result, json.loads(receipt_path.read_text(encoding="utf-8")), state


def test_mocked_activation_offload_executes_backward_inside_context_and_receipts_it(
    monkeypatch, tmp_path
):
    result, receipt, state = _run_activation_probe(
        monkeypatch,
        tmp_path,
        host_memory_states=["MEASURED_PROCFS"] * 6,
    )

    assert result == 0
    assert state["save_on_cpu_entered"] == 1
    assert state["save_on_cpu_exited"] == 1
    assert state["backward_inside_offload_context"] is True
    assert state["offload_context_active"] is False
    assert state["optimizer_step_called"] is True
    assert receipt["state"] == (
        "PASS_ACTIVATION_OFFLOAD_CALIBRATION_ONLY_"
        "NOT_TRAINED_NOT_QUALIFIED_NOT_PROMOTED"
    )
    offload = receipt["activation_offload"]
    assert offload["enabled"] is True
    assert offload["mechanism"] == "torch.autograd.graph.save_on_cpu"
    assert offload["pin_memory"] is False
    assert offload["saved_tensor_transfer_bytes"] == {
        "state": "UNKNOWN_NO_STABLE_PUBLIC_COUNTER"
    }
    assert offload["claim_scope"] == "API_ACTIVE_PLUS_EMPIRICAL_PEAK_ONLY"
    assert offload["parameter_offload"] is False
    assert offload["optimizer_offload"] is False
    assert offload["training_admission_effect"] == "NONE"
    assert offload["context_entered"] is True
    assert offload["context_exited"] is True
    assert offload["backward_completed_inside_context"] is True
    assert offload["host_ram_admission"]["state"] == "PASS"
    assert receipt["probe"]["sequence_tokens"] == 768
    assert receipt["probe"]["sequence_limit"] == 768
    assert receipt["probe"]["activation_offload"] == {"enabled": True}
    assert all(
        sample["state"] == "MEASURED_PROCFS"
        for sample in receipt["probe"]["host_memory_samples"]
    )
    assert receipt["probe"]["gradient_receipt"] == {
        "trainable_gradient_tensors": 1,
        "finite_gradient_tensors": 1,
        "all_trainable_gradients_finite": True,
        "frozen_parameters_with_gradients": 0,
        "l2_norm": 1.0,
    }
    assert receipt["effects"]["capacity_optimization_step_completed"] is True
    assert receipt["effects"]["canonical_capacity_satisfied"] is False
    assert receipt["effects"]["queue_progression_allowed"] is False
    assert receipt["effects"]["training_authorized"] is False
    assert receipt["adoption_assessment"]["state"] == "NOT_EVALUATED"
    assert receipt["adoption_assessment"]["reason"] == (
        "EMPIRICAL_PREDICATE_PASSED_INDEPENDENT_REVIEW_REQUIRED"
    )
    assert receipt["adoption_assessment"]["empirical_predicate"]["state"] == "PASS"
    assert receipt["adoption_assessment"]["training_authority"] is False


@pytest.mark.parametrize(
    "unknown_state",
    [
        "UNKNOWN_PROCFS_UNAVAILABLE",
        "UNKNOWN_PROCFS_READ_FAILED",
        "UNKNOWN_PROCFS_FIELDS_MISSING",
    ],
)
def test_activation_offload_refuses_unknown_host_memory_before_model_or_context(
    monkeypatch, tmp_path, unknown_state
):
    with pytest.raises(
        nemo_train.GateRefused,
        match="activation-offload host-RAM evidence is UNKNOWN",
    ):
        _run_activation_probe(
            monkeypatch, tmp_path, host_memory_states=[unknown_state]
        )

    receipt = json.loads(
        (tmp_path / "activation-offload-receipt.json").read_text(encoding="utf-8")
    )
    assert receipt["state"] == (
        "FAILED_ACTIVATION_OFFLOAD_CALIBRATION_"
        "NOT_TRAINED_NOT_QUALIFIED_NOT_PROMOTED"
    )
    evidence = receipt["failure_evidence"]
    assert evidence["completed_micro_steps"] == 0
    assert evidence["activation_offload"].get("context_entered") is not True
    assert evidence["activation_offload"].get("context_exited") is not True
    assert all(
        sample["state"] == unknown_state
        for sample in evidence["host_memory_samples"]
    )
    assert receipt["effects"]["canonical_capacity_satisfied"] is False
    assert receipt["effects"]["queue_progression_allowed"] is False
    assert receipt["effects"]["training_authorized"] is False


@pytest.mark.parametrize(
    ("minimum_free_mib", "finite_loss", "finite_gradients", "tokens", "expected"),
    [
        (384, True, True, 768, "PASS"),
        (383, True, True, 768, "FAIL"),
        (384, False, True, 768, "FAIL"),
        (384, True, False, 768, "FAIL"),
        (384, True, True, 767, "FAIL"),
    ],
)
def test_real_384_mib_adoption_evaluator_is_conjunctive_and_never_automatic(
    minimum_free_mib, finite_loss, finite_gradients, tokens, expected
):
    contract = json.loads(nemo_train.CONTRACT_PATH.read_text(encoding="utf-8"))
    profile = contract["activation_offload_calibration"]
    requirements = profile["adoption_requirements"]
    samples = [
        {
            "stage": stage,
            "state": "MEASURED_NVIDIA_SMI",
            "gpu_name": contract["runtime"]["required_device_name"],
            "memory_free_mib": minimum_free_mib,
        }
        for stage in requirements["required_vram_headroom_phases"]
    ]
    assessment = nemo_train.evaluate_activation_offload_adoption(
        samples,
        requirements,
        tokens,
        finite_loss,
        finite_gradients,
    )

    assert requirements["minimum_measured_vram_headroom_mib"] == 384
    assert assessment["empirical_predicate"]["state"] == expected
    assert assessment["state"] == ("NOT_EVALUATED" if expected == "PASS" else "FAIL")
    if expected == "PASS":
        assert assessment["reason"] == (
            "EMPIRICAL_PREDICATE_PASSED_INDEPENDENT_REVIEW_REQUIRED"
        )
        assert assessment["independent_review"] == {
            "required": True,
            "state": "NOT_EVALUATED",
        }
    assert assessment["training_authority"] is False
    assert assessment["queue_progression_allowed"] is False
    assert assessment["canonical_gpu_threshold_changed"] is False
    assert profile["training_admission_effect"] == (
        "NONE_UNTIL_SEPARATE_CANONICAL_PROFILE_ADOPTION"
    )
    assert profile["may_modify_canonical_gpu_admission"] is False
    assert profile["may_enqueue_training"] is False
    assert contract["gpu_admission"]["minimum_free_memory_mib"] == 6656


def test_real_adoption_evaluator_keeps_missing_or_unknown_phases_not_evaluated():
    contract = json.loads(nemo_train.CONTRACT_PATH.read_text(encoding="utf-8"))
    requirements = contract["activation_offload_calibration"]["adoption_requirements"]
    samples = [
        {
            "stage": stage,
            "state": (
                "UNKNOWN_GPU_QUERY_FAILED"
                if stage == requirements["required_vram_headroom_phases"][-1]
                else "MEASURED_NVIDIA_SMI"
            ),
            "gpu_name": contract["runtime"]["required_device_name"],
            "memory_free_mib": 6000,
        }
        for stage in requirements["required_vram_headroom_phases"]
    ]

    assessment = nemo_train.evaluate_activation_offload_adoption(
        samples, requirements, 768, True, True
    )
    assert assessment["state"] == "NOT_EVALUATED"
    assert assessment["reason"] == "PHYSICAL_VRAM_EVIDENCE_INCOMPLETE_OR_UNKNOWN"
    assert assessment["empirical_predicate"]["state"] == "NOT_EVALUATED"
    assert assessment["empirical_predicate"]["unknown_phases"] == [
        requirements["required_vram_headroom_phases"][-1]
    ]
    assert assessment["training_authority"] is False


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8", newline="\n")
    path.chmod(0o755)


@pytest.mark.skipif(os.name != "posix", reason="launcher execution requires POSIX")
def test_launcher_routes_activation_offload_without_falling_through_to_train(tmp_path):
    if shutil.which("bash") is None:
        pytest.skip("bash is unavailable")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log_path = tmp_path / "python-argv.jsonl"
    fake_python = fake_bin / "python"
    _write_executable(
        fake_python,
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "with open(os.environ['SZL_TEST_ARGV_LOG'], 'a', encoding='utf-8') as stream:\n"
        "    stream.write(json.dumps(sys.argv[1:]) + '\\n')\n",
    )
    _write_executable(fake_bin / "uname", "#!/usr/bin/env bash\necho Linux\n")
    _write_executable(
        fake_bin / "unshare",
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "if [[ \"${*: -1}\" == \"true\" ]]; then exit 0; fi\n"
        "while (($#)) && [[ \"$1\" != \"--\" ]]; do shift; done\n"
        "shift\n"
        "exec \"$@\"\n",
    )
    base = tmp_path / "base"
    base.mkdir()
    receipt = tmp_path / "receipt.json"
    preflight_receipt = tmp_path / "preflight.json"
    environment = dict(os.environ)
    environment.update(
        {
            "PATH": f"{fake_bin}{os.pathsep}{environment['PATH']}",
            "SZL_NEMO_PYTHON": str(fake_python),
            "SZL_TEST_ARGV_LOG": str(log_path),
        }
    )

    completed = subprocess.run(
        [
            "bash",
            str(LAUNCHER),
            "--base-snapshot",
            str(base),
            "--mode",
            "activation-offload",
            "--receipt",
            str(receipt),
            "--preflight-receipt",
            str(preflight_receipt),
            "--confirmation",
            "CALIBRATE_SZL_NEMO_ACTIVATION_OFFLOAD_V1",
            "--license-acknowledgement",
            "fixture-license-ack",
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    invocations = [
        json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [arguments[1] for arguments in invocations] == [
        "build",
        "preflight",
        "calibrate-activation-offload",
    ]
    activation_argv = invocations[-1]
    assert activation_argv[activation_argv.index("--base-snapshot") + 1] == str(base)
    assert activation_argv[activation_argv.index("--receipt") + 1] == str(receipt)
    assert "train" not in (arguments[1] for arguments in invocations)
