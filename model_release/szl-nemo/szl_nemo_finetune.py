#!/usr/bin/env python3
"""Governed, fail-closed SZL-Nemo QLoRA candidate pipeline.

``fetch-base`` is the only network-capable command and pins the public NVIDIA
snapshot to the exact revision in ``training-contract.json``.  ``build``,
``preflight``, and ``train`` are local-only.  Training never uploads, publishes,
deploys, stops another process, weakens a GPU threshold, or promotes itself.
"""

from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
import gc
import hashlib
import importlib
import importlib.metadata
import inspect
import json
import math
import os
import platform
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from typing import Any, Iterable
import uuid


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CONTRACT_PATH = HERE / "training-contract.json"
SOURCE_PATH = HERE / "curriculum-source.json"
SCHEMA_PATH = HERE / "curriculum-source.schema.json"
GENERATED = HERE / "generated"
MANIFEST_PATH = GENERATED / "curriculum-manifest.json"
TRAIN_PATH = GENERATED / "train.jsonl"
EVAL_PATH = GENERATED / "eval.jsonl"
SYSTEM_PROMPT = (
    "You are an SZL-Nemo governed-adapter candidate built on NVIDIA Nemotron 3 "
    "Nano 4B. Preserve upstream attribution and license lineage. Distinguish "
    "MEASURED, REPORTED, and UNKNOWN. Never invent evidence, execution, proof, "
    "signatures, receipts, or model quality. Brain retrieval and formulas remain "
    "external evidence planes unless separately admitted."
)
FETCH_CONFIRMATION = "FETCH_SZL_NEMO_BASE_dfaf35de3e30f1867dd8dbc38a7fc9fb52d3914f"
PAYLOAD_TYPE = "application/vnd.szl.nemo-training+json"
SHARED_GPU_TRAINING_LEASE_DIR = REPO / "model_release" / "szl-forge" / "queue-state" / "gpu-training.lease"
GPU_TRAINING_LEASE_OWNER = "owner.json"


class GateRefused(RuntimeError):
    pass


class GPUAdmissionRefused(GateRefused):
    def __init__(self, reason: str, samples: list[dict[str, Any]]) -> None:
        super().__init__(reason)
        self.samples = samples


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_canonical_lf(path: Path) -> str:
    return sha256_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n"))


def git_blob_sha1(path: Path) -> str:
    size = path.stat().st_size
    digest = hashlib.sha1()
    digest.update(f"blob {size}\0".encode("ascii"))
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GateRefused(f"{path} is not a JSON object")
    return value


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def atomic_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("".join(canonical_json(row) + "\n" for row in rows))
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise GateRefused(f"{path}:{line_number} is not an object")
        yield value


def _validate_contract_assets(contract: dict[str, Any]) -> None:
    curriculum = contract["curriculum"]
    for path, expected in (
        (SOURCE_PATH, curriculum["source_sha256"]),
        (SCHEMA_PATH, curriculum["schema_sha256"]),
    ):
        if not path.is_file() or sha256_file(path) != expected:
            raise GateRefused(f"pinned curriculum asset mismatch: {path.name}")
    evidence = contract.get("evidence_lineage", {})
    evidence_assets = (
        (
            REPO / str(evidence.get("static_preflight_path", "")),
            evidence.get("static_preflight_canonical_lf_sha256"),
        ),
        (
            REPO / str(evidence.get("pinned_code_static_review_path", "")),
            evidence.get("pinned_code_static_review_canonical_lf_sha256"),
        ),
        (
            REPO / str(evidence.get("wsl_runtime_import_receipt_path", "")),
            evidence.get("wsl_runtime_import_receipt_canonical_lf_sha256"),
        ),
    )
    for path, expected in evidence_assets:
        if not isinstance(expected, str) or len(expected) != 64:
            raise GateRefused("pinned evidence lineage hash is invalid")
        if not path.is_file() or sha256_canonical_lf(path) != expected:
            raise GateRefused(f"pinned evidence lineage mismatch: {path.name}")


def validate_source(source: dict[str, Any], contract: dict[str, Any]) -> None:
    expected = {"schema_version", "owner", "license", "rights_basis", "profile_id", "notice", "train_scenarios", "eval_scenarios"}
    if set(source) != expected:
        raise GateRefused("curriculum source has unknown or missing fields")
    if source["schema_version"] != "szl.nemo.curriculum-source.v1":
        raise GateRefused("unsupported curriculum source schema")
    if (source["owner"], source["license"], source["rights_basis"], source["profile_id"]) != (
        "SZL Holdings", "Apache-2.0", "PROJECT_AUTHORED_SCENARIOS", "SZL-Nemo-Governed-v1"
    ):
        raise GateRefused("curriculum rights declaration is not admitted")
    if not isinstance(source["notice"], str) or not source["notice"].strip():
        raise GateRefused("curriculum notice is absent")
    train = source["train_scenarios"]
    evaluation = source["eval_scenarios"]
    if not isinstance(train, list) or len(train) * 3 < contract["curriculum"]["minimum_train_rows"]:
        raise GateRefused("training scenarios are below the contract minimum")
    if not isinstance(evaluation, list) or len(evaluation) < contract["curriculum"]["minimum_eval_rows"]:
        raise GateRefused("evaluation scenarios are below the contract minimum")
    ids: set[str] = set()
    prompts: set[str] = set()
    for split, scenarios in (("train", train), ("eval", evaluation)):
        for item in scenarios:
            keys = {"id", "prompt", "response"} if split == "train" else {"id", "prompt", "required_terms", "forbidden_terms"}
            if not isinstance(item, dict) or set(item) != keys:
                raise GateRefused(f"{split} scenario has unknown or missing fields")
            if not all(isinstance(item[key], str) and item[key].strip() for key in ("id", "prompt")):
                raise GateRefused(f"{split} scenario identity or prompt is invalid")
            if item["id"] in ids or item["prompt"].casefold() in prompts:
                raise GateRefused("curriculum ids and prompts must be unique across splits")
            ids.add(item["id"])
            prompts.add(item["prompt"].casefold())
            if split == "train" and (not isinstance(item["response"], str) or not item["response"].strip()):
                raise GateRefused("training response is invalid")
            if split == "eval":
                for key in ("required_terms", "forbidden_terms"):
                    terms = item[key]
                    if not isinstance(terms, list) or (key == "required_terms" and not terms) or any(not isinstance(term, str) or not term for term in terms):
                        raise GateRefused(f"evaluation {key} is invalid")


def _curriculum_rows(source: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    variants = (
        "Answer directly and preserve evidence boundaries: ",
        "Respond concisely under the honesty doctrine: ",
        "Give the governed answer without speculation: ",
    )
    train: list[dict[str, Any]] = []
    for scenario in source["train_scenarios"]:
        for index, prefix in enumerate(variants, 1):
            train.append({
                "schema_version": "szl.nemo.curriculum-record.v1",
                "record_id": f"train:{scenario['id']}:{index}",
                "split": "TRAIN",
                "rights_basis": "PROJECT_AUTHORED_SCENARIOS",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prefix + scenario["prompt"]},
                    {"role": "assistant", "content": scenario["response"]},
                ],
            })
    evaluation = [{
        "schema_version": "szl.nemo.eval-record.v1",
        "record_id": f"eval:{scenario['id']}",
        "split": "EVAL",
        "rights_basis": "PROJECT_AUTHORED_SCENARIOS",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": scenario["prompt"]},
        ],
        "expected": {"required_terms": scenario["required_terms"], "forbidden_terms": scenario["forbidden_terms"]},
    } for scenario in source["eval_scenarios"]]
    return train, evaluation


def build_curriculum(output: Path = GENERATED) -> dict[str, Any]:
    contract = load_object(CONTRACT_PATH)
    _validate_contract_assets(contract)
    source = load_object(SOURCE_PATH)
    validate_source(source, contract)
    train, evaluation = _curriculum_rows(source)
    train_path, eval_path = output / "train.jsonl", output / "eval.jsonl"
    atomic_jsonl(train_path, train)
    atomic_jsonl(eval_path, evaluation)
    manifest = {
        "schema_version": "szl.nemo.curriculum-manifest.v1",
        "contract_id": contract["contract_id"],
        "rights_basis": "PROJECT_AUTHORED_SCENARIOS",
        "source_sha256": sha256_file(SOURCE_PATH),
        "schema_sha256": sha256_file(SCHEMA_PATH),
        "train": {"path": train_path.name, "rows": len(train), "sha256": sha256_file(train_path)},
        "eval": {"path": eval_path.name, "rows": len(evaluation), "sha256": sha256_file(eval_path)},
        "excluded_from_gradients": contract["excluded_from_gradients"],
        "external_mutations": {"uploaded": False, "published": False, "deployed": False},
    }
    atomic_json(output / "curriculum-manifest.json", manifest)
    return manifest


def validate_curriculum() -> dict[str, Any]:
    if not MANIFEST_PATH.is_file() or not TRAIN_PATH.is_file() or not EVAL_PATH.is_file():
        raise GateRefused("generated curriculum is absent; run build")
    observed = load_object(MANIFEST_PATH)
    with tempfile.TemporaryDirectory(prefix="szl-nemo-curriculum-") as directory:
        expected = build_curriculum(Path(directory))
        if observed != expected or sha256_file(TRAIN_PATH) != expected["train"]["sha256"] or sha256_file(EVAL_PATH) != expected["eval"]["sha256"]:
            raise GateRefused("generated curriculum differs from its pinned source")
    train_prompts = {row["messages"][1]["content"].casefold() for row in iter_jsonl(TRAIN_PATH)}
    eval_prompts = {row["messages"][1]["content"].casefold() for row in iter_jsonl(EVAL_PATH)}
    if train_prompts & eval_prompts:
        raise GateRefused("train/eval prompt overlap detected")
    return observed


def curriculum_input_identity() -> dict[str, Any]:
    """Bind the exact admitted files used by one capacity/training process."""

    return {
        "manifest": {"bytes": MANIFEST_PATH.stat().st_size, "sha256": sha256_file(MANIFEST_PATH)},
        "train": {"bytes": TRAIN_PATH.stat().st_size, "sha256": sha256_file(TRAIN_PATH)},
        "eval": {"bytes": EVAL_PATH.stat().st_size, "sha256": sha256_file(EVAL_PATH)},
    }


def _safe_child(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise GateRefused("base file path escapes snapshot")
    path = root / candidate
    if not path.is_file():
        raise GateRefused(f"base file missing: {relative}")
    return path


def verify_base(snapshot: Path) -> list[dict[str, Any]]:
    contract = load_object(CONTRACT_PATH)
    if not snapshot.is_dir():
        raise GateRefused("operator-supplied NVIDIA base snapshot is absent")
    observed: list[dict[str, Any]] = []
    for expected in contract["base"]["required_files"]:
        path = _safe_child(snapshot, expected["path"])
        if path.stat().st_size != expected["bytes"]:
            raise GateRefused(f"base file size mismatch: {expected['path']}")
        if "sha256" in expected:
            digest = sha256_file(path)
            if digest != expected["sha256"]:
                raise GateRefused(f"base SHA-256 mismatch: {expected['path']}")
            observed.append({"path": expected["path"], "bytes": path.stat().st_size, "sha256": digest})
        else:
            digest = git_blob_sha1(path)
            if digest != expected["git_blob_sha1"]:
                raise GateRefused(f"base Git blob mismatch: {expected['path']}")
            observed.append({"path": expected["path"], "bytes": path.stat().st_size, "git_blob_sha1": digest})
    config = load_object(snapshot / "config.json")
    base = contract["base"]
    if config.get("model_type") != base["model_type"] or config.get("vocab_size") != base["vocab_size"] or base["architecture"] not in config.get("architectures", []):
        raise GateRefused("base architecture identity mismatch")
    if config.get("auto_map") != base["auto_map"]:
        raise GateRefused("pinned NVIDIA custom-code mapping mismatch")
    return observed


def verify_nemotron_execution_lane(snapshot: Path) -> dict[str, Any]:
    """Prove that the pinned NVIDIA custom class is importable on this host.

    Hashing the files is necessary but not sufficient.  NVIDIA's implementation
    is Linux-only and imports the Mamba/causal-convolution CUDA extensions.  A
    preflight cannot pass until those exact runtime dependencies and the pinned
    custom model class load locally without a network request.
    """

    contract = load_object(CONTRACT_PATH)
    runtime = contract["runtime"]
    observed_os = platform.system()
    if observed_os not in runtime["operating_system_allowlist"]:
        raise GateRefused(
            "SZL-Nemo training is unavailable on native Windows: the pinned "
            "NVIDIA implementation requires Linux Mamba and causal-convolution "
            "CUDA kernels; use the governed WSL2/Linux lane"
        )

    modules: dict[str, str] = {}
    for module_name in runtime["module_required"]:
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            raise GateRefused(
                f"required Linux runtime module is unavailable: {module_name} "
                f"({type(exc).__name__})"
            ) from exc
        modules[module_name] = str(getattr(module, "__version__", "UNKNOWN"))

    try:
        from transformers import AutoConfig, AutoTokenizer
        from transformers.dynamic_module_utils import get_class_from_dynamic_module

        config = AutoConfig.from_pretrained(
            str(snapshot), local_files_only=True, trust_remote_code=True
        )
        tokenizer = AutoTokenizer.from_pretrained(
            str(snapshot), local_files_only=True, trust_remote_code=True
        )
        model_class = get_class_from_dynamic_module(
            contract["base"]["auto_map"]["AutoModelForCausalLM"],
            str(snapshot),
            local_files_only=True,
        )
    except Exception as exc:
        raise GateRefused(
            "pinned NVIDIA custom config/model class failed local import: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    if config.model_type != contract["base"]["model_type"]:
        raise GateRefused("loaded custom config identity does not match contract")
    if model_class.__name__ != contract["base"]["architecture"]:
        raise GateRefused("loaded custom model class identity does not match contract")
    expected_code = {
        item["path"]: item["sha256"]
        for item in contract["base"]["required_files"]
        if item["path"] in {"configuration_nemotron_h.py", "modeling_nemotron_h.py"}
    }
    loaded_code = {
        "configuration_nemotron_h.py": Path(inspect.getfile(type(config))).resolve(),
        "modeling_nemotron_h.py": Path(inspect.getfile(model_class)).resolve(),
    }
    loaded_code_receipt: list[dict[str, Any]] = []
    for name, path in loaded_code.items():
        digest = sha256_file(path)
        if digest != expected_code.get(name):
            raise GateRefused(f"loaded pinned NVIDIA code hash mismatch: {name}")
        loaded_code_receipt.append({"path": str(path), "sha256": digest})
    return {
        "schema_version": "szl.nemo.execution-lane-receipt.v1",
        "state": "PASS",
        "operating_system": observed_os,
        "execution_lane": runtime["execution_lane"],
        "remote_code_policy": contract["base"]["remote_code_policy"],
        "qualification_scope": "CUSTOM_CLASS_IMPORT_BEFORE_MODEL_LOAD",
        "config_class": type(config).__name__,
        "model_class": model_class.__name__,
        "tokenizer_class": type(tokenizer).__name__,
        "modules": modules,
        "loaded_code": loaded_code_receipt,
    }


def query_gpu() -> dict[str, Any]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        raise GateRefused("nvidia-smi is unavailable")
    result = subprocess.run([executable, "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=15, check=True)
    values = [part.strip() for part in result.stdout.strip().splitlines()[0].split(",")]
    if len(values) != 6:
        raise GateRefused("unexpected nvidia-smi output")
    return {"measured_at_unix_ns": time.time_ns(), "gpu_name": values[0], "memory_total_mib": int(values[1]), "memory_used_mib": int(values[2]), "memory_free_mib": int(values[3]), "utilization_pct": int(values[4]), "temperature_c": int(values[5])}


def sample_gpu(policy: dict[str, Any], count: int, interval: int) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for index in range(count):
        sample = query_gpu()
        samples.append(sample)
        if (sample["gpu_name"] != load_object(CONTRACT_PATH)["runtime"]["required_device_name"] or sample["memory_free_mib"] < policy["minimum_free_memory_mib"] or sample["utilization_pct"] > policy["maximum_utilization_pct"] or sample["temperature_c"] > policy["maximum_temperature_c"]):
            raise GPUAdmissionRefused("fixed GPU admission thresholds were not maintained", samples)
        if index + 1 < count:
            time.sleep(interval)
    return samples


def verify_runtime(torch_module: Any) -> dict[str, Any]:
    contract = load_object(CONTRACT_PATH)
    runtime = contract["runtime"]
    if platform.system() not in runtime["operating_system_allowlist"]:
        raise GateRefused("operating system is outside the SZL-Nemo runtime allowlist")
    minor = f"{sys.version_info.major}.{sys.version_info.minor}"
    if minor not in runtime["python_minor_allowlist"] or str(torch_module.__version__) not in runtime["torch_exact_allowlist"]:
        raise GateRefused("Python or torch identity is outside the measured allowlist")
    cuda = tuple(int(part) for part in str(torch_module.version.cuda).split(".")[:2])
    capability = tuple(int(part) for part in torch_module.cuda.get_device_capability())
    if cuda < tuple(runtime["minimum_cuda_runtime"]) or capability < tuple(runtime["minimum_device_capability"]):
        raise GateRefused("CUDA runtime or device capability is below contract")
    if torch_module.cuda.get_device_name() != runtime["required_device_name"]:
        raise GateRefused("GPU identity does not match contract")
    packages: dict[str, str] = {}
    for package, expected in runtime["package_exact"].items():
        packages[package] = importlib.metadata.version(package)
        if packages[package] != expected:
            raise GateRefused(f"{package} runtime identity mismatch")
    for package in runtime["package_required_measured"]:
        packages[package] = importlib.metadata.version(package)
    return {"schema_version": "szl.nemo.runtime-identity.v1", "state": "PASS", "python": sys.version.split()[0], "torch": str(torch_module.__version__), "cuda_runtime": str(torch_module.version.cuda), "device_name": torch_module.cuda.get_device_name(), "device_capability": list(capability), "packages": packages}


def git_identity(contract: dict[str, Any]) -> dict[str, Any]:
    policy = contract.get("source_control")
    if not isinstance(policy, dict) or policy.get("require_clean_scope") is not True:
        raise GateRefused("training contract lacks a fail-closed source-control policy")
    configured = os.environ.get(str(policy.get("git_executable_env", "")), "").strip()
    executable = configured or shutil.which("git")
    if not executable or not Path(executable).is_file():
        raise GateRefused("Git is unavailable; set the contract-declared Git environment variable")
    paths = policy.get("paths")
    if not isinstance(paths, list) or not paths or not all(isinstance(path, str) and path for path in paths):
        raise GateRefused("source-control path scope is invalid")
    prefix = [str(Path(executable).resolve()), "-c", f"safe.directory={REPO.resolve()}"]
    commit = subprocess.run(prefix + ["rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True)
    if commit.returncode != 0 or len(commit.stdout.strip()) != 40:
        raise GateRefused("training source commit could not be measured")
    status = subprocess.run(prefix + ["status", "--porcelain=v1", "--untracked-files=all", "--", *paths], cwd=REPO, capture_output=True, text=True)
    if status.returncode != 0:
        raise GateRefused("training source cleanliness could not be measured")
    if status.stdout:
        raise GateRefused("training-critical source scope is dirty; commit reviewed changes first")
    return {"state": "CLEAN_REVIEWED_COMMIT", "commit": commit.stdout.strip(), "git_executable_sha256": sha256_file(Path(executable).resolve()), "scope": paths, "status_sha256": sha256_bytes(status.stdout.encode("utf-8"))}


@contextmanager
def deny_python_network() -> Iterable[dict[str, Any]]:
    original_socket, original_create, original_getaddrinfo = socket.socket, socket.create_connection, socket.getaddrinfo
    class DeniedSocket(original_socket):  # type: ignore[misc, valid-type]
        def connect(self, *_args: Any, **_kwargs: Any) -> Any:
            raise OSError("network denied by SZL-Nemo trainer")
        def connect_ex(self, *_args: Any, **_kwargs: Any) -> int:
            raise OSError("network denied by SZL-Nemo trainer")
    def denied(*_args: Any, **_kwargs: Any) -> Any:
        raise OSError("network denied by SZL-Nemo trainer")
    socket.socket, socket.create_connection, socket.getaddrinfo = DeniedSocket, denied, denied
    try:
        yield {"state": "PYTHON_SOCKET_DENIED", "framework_offline_flags": True, "os_network_namespace": "NOT_ESTABLISHED", "limitation": "Native extensions are not proven network-isolated."}
    finally:
        socket.socket, socket.create_connection, socket.getaddrinfo = original_socket, original_create, original_getaddrinfo


@contextmanager
def offline_framework_environment() -> Iterable[dict[str, str]]:
    required = {
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1",
        "WANDB_DISABLED": "true",
        "TOKENIZERS_PARALLELISM": "false",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "DO_NOT_TRACK": "1",
        "NO_PROXY": "*",
    }
    previous = {key: os.environ.get(key) for key in required}
    os.environ.update(required)
    try:
        yield dict(required)
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@contextmanager
def fresh_hf_modules_cache() -> Iterable[dict[str, Any]]:
    """Force pinned custom code through a new, empty cache for this process.

    The immutable snapshot is verified before Transformers is imported. A
    process-unique cache then prevents a stale or previously tampered dynamic
    module from winning lookup before its executed source can be checked.
    """

    previous = os.environ.get("HF_MODULES_CACHE")
    with tempfile.TemporaryDirectory(prefix="szl-nemo-hf-modules-") as directory:
        cache = Path(directory)
        if any(cache.iterdir()):
            raise GateRefused("fresh Transformers module cache is not empty")
        os.environ["HF_MODULES_CACHE"] = str(cache)
        receipt = {
            "state": "FRESH_PROCESS_UNIQUE_CACHE",
            "initial_entry_count": 0,
            "lifecycle": "DELETED_WHEN_COMMAND_EXITS",
            "source_policy": "IMMUTABLE_SNAPSHOT_HASH_VERIFIED_BEFORE_IMPORT",
        }
        try:
            yield receipt
        finally:
            if previous is None:
                os.environ.pop("HF_MODULES_CACHE", None)
            else:
                os.environ["HF_MODULES_CACHE"] = previous


def verify_loaded_model_source(model: Any, contract: dict[str, Any], phase: str) -> dict[str, Any]:
    """Bind an instantiated base class to the exact reviewed NVIDIA source."""

    source = Path(inspect.getfile(type(model))).resolve()
    digest = sha256_file(source)
    expected = next(
        item["sha256"]
        for item in contract["base"]["required_files"]
        if item["path"] == "modeling_nemotron_h.py"
    )
    if digest != expected:
        raise GateRefused(f"{phase} loaded NVIDIA model source hash mismatch")
    return {
        "phase": phase,
        "class": f"{type(model).__module__}.{type(model).__qualname__}",
        "source": str(source),
        "source_sha256": digest,
    }


def verify_linux_network_namespace() -> dict[str, Any]:
    """Require the WSL/Linux training process to have no non-loopback network."""

    if platform.system() != "Linux":
        raise GateRefused("Linux network namespace is required for SZL-Nemo training")
    interface_root = Path("/sys/class/net")
    if not interface_root.is_dir():
        raise GateRefused("network namespace interfaces cannot be measured")
    interfaces = sorted(path.name for path in interface_root.iterdir())
    non_loopback = [name for name in interfaces if name != "lo"]
    routes = Path("/proc/net/route").read_text(encoding="utf-8")
    default_routes = [
        line for line in routes.splitlines()[1:]
        if len(line.split()) > 1 and line.split()[1] == "00000000"
    ]
    if non_loopback or default_routes:
        raise GateRefused(
            "OS network namespace is not isolated; invoke training through "
            "unshare --user --map-root-user --net"
        )
    return {
        "state": "OS_NETWORK_NAMESPACE_DENIED",
        "interfaces": interfaces,
        "default_route_count": len(default_routes),
        "namespace_link": os.readlink("/proc/self/ns/net"),
    }


class RuntimeGuard:
    def __init__(self, contract: dict[str, Any]) -> None:
        self.maximum_seconds = contract["training"]["maximum_wall_clock_seconds"]
        self.maximum_temperature = contract["gpu_admission"]["maximum_training_temperature_c"]
        self.interval = contract["training"]["watchdog_interval_seconds"]
        self.started = time.monotonic()
        self.samples: list[dict[str, Any]] = []
        self.reason: str | None = None
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._watch, name="szl-nemo-runtime-guard", daemon=True)
    def _watch(self) -> None:
        while not self.stop.is_set():
            try:
                sample = query_gpu()
                self.samples.append(sample)
                if sample["temperature_c"] > self.maximum_temperature:
                    self.reason = "training thermal ceiling exceeded"
                    return
            except Exception as exc:
                self.reason = f"GPU watchdog failed: {type(exc).__name__}"
                return
            self.stop.wait(self.interval)
    def __enter__(self) -> "RuntimeGuard":
        self.thread.start(); return self
    def __exit__(self, *_args: Any) -> None:
        self.stop.set(); self.thread.join(timeout=self.interval + 2)
    def check(self, stage: str) -> None:
        if time.monotonic() - self.started > self.maximum_seconds:
            self.reason = f"wall-clock ceiling exceeded at {stage}"
        if self.reason:
            raise GateRefused(self.reason)
    def receipt(self) -> dict[str, Any]:
        return {"state": "TRIPPED" if self.reason else "PASS", "reason": self.reason, "samples": self.samples, "cooperative_interrupt_only": True}


def _atomic_lease_owner(path: Path, value: dict[str, Any]) -> None:
    token = str(value["owner_token"])
    temporary = path / f".{GPU_TRAINING_LEASE_OWNER}.{token}.tmp"
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path / GPU_TRAINING_LEASE_OWNER)
    finally:
        if temporary.exists():
            temporary.unlink()


def _lease_holder(path: Path) -> str:
    try:
        owner = load_object(path / GPU_TRAINING_LEASE_OWNER)
    except (OSError, ValueError, json.JSONDecodeError, GateRefused):
        return "owner metadata unavailable"
    return (
        f"pid={owner.get('pid', 'UNKNOWN')} host={owner.get('hostname', 'UNKNOWN')} "
        f"runtime={owner.get('runtime', 'UNKNOWN')}"
    )


def _remove_owned_lease(path: Path, owner_token: str) -> None:
    owner_path = path / GPU_TRAINING_LEASE_OWNER
    try:
        owner = load_object(owner_path)
    except (OSError, ValueError, json.JSONDecodeError, GateRefused):
        return
    if owner.get("owner_token") != owner_token:
        return
    owner_path.unlink()
    try:
        path.rmdir()
    except OSError:
        # Never recursively delete unexpected or stale lease evidence.
        pass


@contextmanager
def training_mutex(path: Path = SHARED_GPU_TRAINING_LEASE_DIR) -> Iterable[Path]:
    """Hold the same atomic repository lease from native Windows or WSL."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.mkdir()
    except FileExistsError as exc:
        raise GateRefused(
            "another governed SZL training process holds the shared GPU lease "
            f"({ _lease_holder(path) }); stale leases require operator review"
        ) from exc
    except OSError as exc:
        raise GateRefused("shared GPU lease directory could not be created") from exc

    owner_token = uuid.uuid4().hex
    owner = {
        "schema_version": "szl.gpu-training-lease-owner.v1",
        "owner_token": owner_token,
        "pid": os.getpid(),
        "hostname": socket.gethostname(),
        "runtime": f"{os.name}:{sys.platform}",
        "runner": str(Path(__file__).resolve()),
        "acquired_at_unix_ns": time.time_ns(),
        "arbitration": "ATOMIC_DIRECTORY_CREATION",
        "stale_policy": "OPERATOR_REVIEW_REQUIRED",
        "automatic_stale_deletion": False,
    }
    try:
        _atomic_lease_owner(path, owner)
    except Exception as exc:
        try:
            path.rmdir()
        except OSError:
            pass
        raise GateRefused("shared GPU lease owner metadata could not be published") from exc
    try:
        yield path
    finally:
        _remove_owned_lease(path, owner_token)


def _preflight_receipt(contract: dict[str, Any], state: str, checks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "szl.nemo.preflight-receipt.v1",
        "contract_id": contract.get("contract_id"),
        "state": state,
        "measured_at_unix_ns": time.time_ns(),
        "observed_operating_system": platform.system(),
        "contract_sha256": sha256_file(CONTRACT_PATH),
        "runner_sha256": sha256_file(Path(__file__)),
        "evidence_lineage": contract.get("evidence_lineage"),
        "checks": checks,
        "effects": {
            "training_started": False,
            "uploaded": False,
            "published": False,
            "deployed": False,
        },
    }


def preflight(snapshot: Path | None, check_gpu: bool = False, probe: bool = False) -> dict[str, Any]:
    contract = load_object(CONTRACT_PATH)
    checks: list[dict[str, Any]] = []
    try:
        _validate_contract_assets(contract); checks.append({"id": "PINNED_CONTRACT_ASSETS", "state": "PASS"})
        manifest = validate_curriculum(); checks.append({"id": "PROJECT_AUTHORED_CURRICULUM", "state": "PASS", "train_rows": manifest["train"]["rows"], "eval_rows": manifest["eval"]["rows"]})
        if snapshot is None:
            raise GateRefused("base snapshot was not supplied")
        files = verify_base(snapshot); checks.append({"id": "IMMUTABLE_NVIDIA_BASE", "state": "PASS", "revision": contract["base"]["revision"], "files": files})
        checks.append({"id": "LICENSE_LINEAGE", "state": "PASS", "license": contract["base"]["license"], "url": contract["base"]["license_url"], "operator_ack_required_for_training": True})
        try:
            with offline_framework_environment() as offline_flags, deny_python_network() as python_network:
                lane = verify_nemotron_execution_lane(snapshot)
            lane["python_network_guard"] = python_network
            lane["framework_offline_flags"] = offline_flags
            checks.append({"id": "LINUX_MAMBA_EXECUTION_LANE", "state": "PASS", **lane})
        except Exception as exc:
            checks.append({"id": "LINUX_MAMBA_EXECUTION_LANE", "state": "BLOCKED", "observed_operating_system": platform.system(), "required_operating_systems": contract["runtime"]["operating_system_allowlist"], "reason": str(exc)})
            return _preflight_receipt(contract, "BLOCKED", checks)
        if check_gpu:
            count = contract["gpu_admission"]["probe_samples"] if probe else contract["gpu_admission"]["training_soak_samples"]
            samples = sample_gpu(contract["gpu_admission"], count, contract["gpu_admission"]["sample_interval_seconds"])
            checks.append({"id": "GPU_ADMISSION", "state": "PASS", "samples": samples})
        return _preflight_receipt(contract, "PASS", checks)
    except GPUAdmissionRefused as exc:
        checks.append({"id": "GPU_ADMISSION", "state": "BLOCKED", "reason": str(exc), "samples": exc.samples})
    except Exception as exc:
        checks.append({"id": "REFUSAL", "state": "BLOCKED", "reason": str(exc)})
    return _preflight_receipt(contract, "BLOCKED", checks)


def fetch_base(destination: Path, confirmation: str) -> dict[str, Any]:
    if confirmation != FETCH_CONFIRMATION:
        raise GateRefused("exact base-fetch confirmation is required")
    if destination.exists() and any(destination.iterdir()):
        raise GateRefused("base destination must be absent or empty")
    contract = load_object(CONTRACT_PATH)
    from huggingface_hub import snapshot_download
    started = time.time_ns()
    path = Path(snapshot_download(repo_id=contract["base"]["repository"], revision=contract["base"]["revision"], local_dir=destination, allow_patterns=[item["path"] for item in contract["base"]["required_files"]], token=False))
    files = verify_base(path)
    receipt = {"schema_version": "szl.nemo.base-fetch-receipt.v1", "state": "PASS", "repository": contract["base"]["repository"], "revision": contract["base"]["revision"], "started_at_unix_ns": started, "completed_at_unix_ns": time.time_ns(), "files": files, "training_started": False, "uploaded": False, "published": False, "deployed": False}
    atomic_json(destination / "base-fetch-receipt.json", receipt)
    return receipt


def _inventory(root: Path) -> list[dict[str, Any]]:
    return [{"path": str(path.relative_to(root)).replace("\\", "/"), "bytes": path.stat().st_size, "sha256": sha256_file(path)} for path in sorted(root.rglob("*")) if path.is_file()]


def _evaluate_output(text: str, expected: dict[str, Any]) -> dict[str, Any]:
    folded = text.casefold()
    missing = [term for term in expected["required_terms"] if term.casefold() not in folded]
    forbidden = [term for term in expected["forbidden_terms"] if term.casefold() in folded]
    return {"state": "PASS" if not missing and not forbidden else "FAIL", "output_sha256": sha256_bytes(text.encode("utf-8")), "output_chars": len(text), "missing_required_terms": missing, "present_forbidden_terms": forbidden}


def _sign_summary(summary: dict[str, Any]) -> dict[str, Any]:
    sys.path.insert(0, str(REPO))
    import szl_dsse
    envelope = szl_dsse.sign_payload(summary, payload_type=PAYLOAD_TYPE)
    verdict = szl_dsse.verify_envelope(envelope)
    return {"envelope": envelope, "verification": verdict, "promotion_eligible_signature": bool(envelope.get("signed") and verdict.get("verified"))}


def capacity_probe(
    snapshot: Path,
    receipt_path: Path,
    confirmation: str,
    license_acknowledgement: str,
    module_cache_receipt: dict[str, Any] | None = None,
) -> int:
    """Prove this exact GPU can execute one bounded in-memory QLoRA step.

    This is deliberately stronger than importing the NVIDIA custom class and
    deliberately weaker than a training run.  It writes no adapter or model
    weights, makes no quality claim, and cannot promote a candidate.  It must
    run inside the same OS-level network namespace and fixed GPU admission gate
    used for training.
    """

    contract = load_object(CONTRACT_PATH)
    settings = contract["training"]
    if confirmation != settings["confirmation_phrase"]:
        raise GateRefused("exact capacity-probe confirmation is required")
    if license_acknowledgement != contract["base"]["license_acknowledgement"]:
        raise GateRefused("exact NVIDIA license acknowledgement is required")

    receipt: dict[str, Any] = {
        "schema_version": "szl.nemo.capacity-probe-receipt.v1",
        "contract_id": contract["contract_id"],
        "state": "RUNNING_NOT_TRAINED_NOT_PROMOTED",
        "started_at_unix_ns": time.time_ns(),
        "contract_sha256": sha256_file(CONTRACT_PATH),
        "runner_sha256": sha256_file(Path(__file__)),
        "base_revision": contract["base"]["revision"],
        "dynamic_module_cache": module_cache_receipt,
        "training_started": False,
        "effects": {
            "training_run_started": False,
            "capacity_optimization_step_started": False,
            "capacity_optimization_step_completed": False,
            "adapter_written": False,
            "uploaded": False,
            "published": False,
            "deployed": False,
            "promoted": False,
        },
    }
    atomic_json(receipt_path, receipt)

    try:
        source_control = git_identity(contract)
        admission = preflight(snapshot, check_gpu=True, probe=True)
        receipt["preflight"] = admission
        if admission["state"] != "PASS":
            receipt.update({"state": "BLOCKED_NOT_TRAINED_NOT_PROMOTED", "completed_at_unix_ns": time.time_ns()})
            atomic_json(receipt_path, receipt)
            return 3

        before = verify_base(snapshot)
        curriculum_before = curriculum_input_identity()
        capacity_row = next(iter(iter_jsonl(TRAIN_PATH)), None)
        if capacity_row is None:
            raise GateRefused("capacity probe has no admitted training row")
        if curriculum_input_identity() != curriculum_before:
            raise GateRefused("curriculum inputs changed while capacity row was admitted")
        namespace = verify_linux_network_namespace()
        receipt.update(
            {
                "source_control": source_control,
                "base_files_before": before,
                "curriculum_inputs_before": curriculum_before,
                "os_network_namespace": namespace,
            }
        )
        atomic_json(receipt_path, receipt)

        with offline_framework_environment() as offline_flags, deny_python_network() as network_control, RuntimeGuard(contract) as guard:
            import torch
            from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

            receipt["runtime_identity"] = verify_runtime(torch)
            receipt["framework_offline_flags"] = offline_flags
            receipt["python_network_control"] = network_control
            bf16 = bool(torch.cuda.is_bf16_supported())
            compute_dtype = torch.bfloat16 if bf16 else torch.float16
            quant = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=compute_dtype,
            )
            torch.cuda.reset_peak_memory_stats()
            guard.check("capacity-before-model-load")
            load_started = time.monotonic_ns()
            tokenizer = AutoTokenizer.from_pretrained(
                str(snapshot), local_files_only=True, trust_remote_code=True
            )
            model = AutoModelForCausalLM.from_pretrained(
                str(snapshot),
                local_files_only=True,
                quantization_config=quant,
                device_map={"": 0},
                trust_remote_code=True,
                use_safetensors=True,
                low_cpu_mem_usage=True,
            )
            receipt["model_load_duration_ms"] = (time.monotonic_ns() - load_started) // 1_000_000
            receipt["loaded_model_class"] = verify_loaded_model_source(
                model, contract, "capacity"
            )
            model.config.use_cache = False
            model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
            lora = LoraConfig(
                r=settings["lora_rank"],
                lora_alpha=settings["lora_alpha"],
                lora_dropout=settings["lora_dropout"],
                bias="none",
                task_type="CAUSAL_LM",
                target_modules=settings["target_modules"],
            )
            model = get_peft_model(model, lora)
            trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
            if not trainable:
                raise GateRefused("capacity probe produced no trainable adapter parameters")

            row = capacity_row
            text = tokenizer.apply_chat_template(
                row["messages"], tokenize=False, add_generation_prompt=False
            )
            sequence_length = int(settings["capacity_probe_sequence_length"])
            encoded = tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=sequence_length,
            )
            device = next(parameter.device for parameter in model.parameters() if parameter.device.type == "cuda")
            encoded = {key: value.to(device) for key, value in encoded.items()}
            model.train()
            optimizer = torch.optim.AdamW(trainable, lr=settings["learning_rate"])
            optimizer.zero_grad(set_to_none=True)
            guard.check("capacity-before-forward")
            receipt["effects"]["capacity_optimization_step_started"] = True
            atomic_json(receipt_path, receipt)
            step_started = time.monotonic_ns()
            output = model(**encoded, labels=encoded["input_ids"])
            loss = float(output.loss.detach().cpu())
            if not math.isfinite(loss):
                raise GateRefused("capacity probe loss is not finite")
            output.loss.backward()
            optimizer.step()
            torch.cuda.synchronize()
            guard.check("capacity-after-optimizer-step")
            receipt["effects"]["capacity_optimization_step_completed"] = True
            step_duration_ms = (time.monotonic_ns() - step_started) // 1_000_000

            receipt.update(
                {
                    "state": "PASS_CAPACITY_ONLY_NOT_TRAINED_NOT_PROMOTED",
                    "completed_at_unix_ns": time.time_ns(),
                    "probe": {
                        "record_id": row.get("record_id"),
                        "sequence_tokens": int(encoded["input_ids"].shape[-1]),
                        "sequence_limit": sequence_length,
                        "loss": loss,
                        "step_duration_ms": step_duration_ms,
                        "trainable_parameters": sum(parameter.numel() for parameter in trainable),
                        "peak_vram_allocated_bytes": int(torch.cuda.max_memory_allocated()),
                        "peak_vram_reserved_bytes": int(torch.cuda.max_memory_reserved()),
                        "compute_dtype": str(compute_dtype),
                    },
                    "runtime_guard": guard.receipt(),
                    "base_files_after": verify_base(snapshot),
                    "curriculum_inputs_after": curriculum_input_identity(),
                    "source_control_after": git_identity(contract),
                }
            )
            if receipt["base_files_before"] != receipt["base_files_after"]:
                raise GateRefused("base inputs changed during capacity probe")
            if receipt["curriculum_inputs_before"] != receipt["curriculum_inputs_after"]:
                raise GateRefused("curriculum inputs changed during capacity probe")
            if receipt["source_control"] != receipt["source_control_after"]:
                raise GateRefused("training source identity changed during capacity probe")
            atomic_json(receipt_path, receipt)
            del optimizer, output, encoded, model
            gc.collect()
            torch.cuda.empty_cache()
            return 0
    except Exception as exc:
        receipt.update(
            {
                "state": "FAILED_NOT_TRAINED_NOT_PROMOTED",
                "completed_at_unix_ns": time.time_ns(),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback_sha256": sha256_bytes(traceback.format_exc().encode("utf-8")),
            }
        )
        atomic_json(receipt_path, receipt)
        raise


def train(
    snapshot: Path,
    output: Path,
    confirmation: str,
    license_acknowledgement: str,
    module_cache_receipt: dict[str, Any] | None = None,
) -> int:
    contract = load_object(CONTRACT_PATH)
    if confirmation != contract["training"]["confirmation_phrase"]:
        raise GateRefused("exact training confirmation is required")
    if license_acknowledgement != contract["base"]["license_acknowledgement"]:
        raise GateRefused("exact NVIDIA license acknowledgement is required")
    if output.exists() and any(output.iterdir()):
        raise GateRefused("output directory must be absent or empty")
    if shutil.disk_usage(output.parent if output.parent.exists() else HERE).free < contract["training"]["minimum_output_free_bytes"]:
        raise GateRefused("output volume has insufficient free space")
    source_control_before = git_identity(contract)
    receipts = output / "receipts"; receipts.mkdir(parents=True, exist_ok=True)
    admission = preflight(snapshot, check_gpu=True)
    atomic_json(receipts / "preflight-receipt.json", admission)
    if admission["state"] != "PASS":
        return 3
    source_control = git_identity(contract)
    if source_control != source_control_before:
        raise GateRefused("training source identity changed during admission")
    before = verify_base(snapshot)
    validate_curriculum()
    curriculum_before = curriculum_input_identity()
    train_rows = list(iter_jsonl(TRAIN_PATH))
    eval_rows = list(iter_jsonl(EVAL_PATH))
    if curriculum_input_identity() != curriculum_before:
        raise GateRefused("curriculum inputs changed while rows were admitted")
    os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1", "WANDB_DISABLED": "true", "TOKENIZERS_PARALLELISM": "false", "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1", "NO_PROXY": "*"})
    network_namespace = verify_linux_network_namespace()
    receipt: dict[str, Any] = {"schema_version": "szl.nemo.training-receipt.v1", "contract_id": contract["contract_id"], "state": "RUNNING_NOT_PROMOTED", "started_at_unix_ns": time.time_ns(), "source_control": source_control, "contract_sha256": sha256_file(CONTRACT_PATH), "runner_sha256": sha256_file(Path(__file__)), "curriculum_manifest_sha256": sha256_file(MANIFEST_PATH), "curriculum_inputs_before": curriculum_before, "admitted_train_rows": len(train_rows), "admitted_eval_rows": len(eval_rows), "base_files_before": before, "dynamic_module_cache": module_cache_receipt, "license": contract["base"]["license"], "network_download_allowed": False, "os_network_namespace": network_namespace, "upload_allowed": False, "promotion": "NOT_PROMOTED"}
    atomic_json(receipts / "training-receipt.json", receipt)
    try:
        with deny_python_network() as network_control, RuntimeGuard(contract) as guard:
            receipt["network_control"] = network_control
            import torch
            from datasets import Dataset
            from peft import LoraConfig, PeftModel, prepare_model_for_kbit_training
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainerCallback
            from trl import SFTConfig, SFTTrainer
            if not torch.cuda.is_available():
                raise GateRefused("CUDA is unavailable after admission")
            receipt["runtime_identity"] = verify_runtime(torch)
            bf16 = bool(torch.cuda.is_bf16_supported())
            quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16 if bf16 else torch.float16)
            class ThermalGuard(TrainerCallback):
                def on_step_begin(self, args: Any, state: Any, control: Any, **kwargs: Any) -> Any:
                    guard.check(f"step-{state.global_step}-begin"); return control
                def on_step_end(self, args: Any, state: Any, control: Any, **kwargs: Any) -> Any:
                    guard.check(f"step-{state.global_step}-end"); return control
            guard.check("before-model-load")
            tokenizer = AutoTokenizer.from_pretrained(str(snapshot), local_files_only=True, trust_remote_code=True)
            model = AutoModelForCausalLM.from_pretrained(str(snapshot), local_files_only=True, quantization_config=quant, device_map="auto", trust_remote_code=True, use_safetensors=True, low_cpu_mem_usage=True)
            receipt["loaded_model_class"] = verify_loaded_model_source(model, contract, "training")
            model.config.use_cache = False
            model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
            texts = [tokenizer.apply_chat_template(row["messages"], tokenize=False, add_generation_prompt=False) for row in train_rows]
            dataset = Dataset.from_dict({"text": texts})
            settings = contract["training"]
            lora = LoraConfig(r=settings["lora_rank"], lora_alpha=settings["lora_alpha"], lora_dropout=settings["lora_dropout"], bias="none", task_type="CAUSAL_LM", target_modules=settings["target_modules"])
            arguments = SFTConfig(output_dir=str(output / "trainer"), max_steps=settings["max_steps"], per_device_train_batch_size=settings["per_device_batch_size"], gradient_accumulation_steps=settings["gradient_accumulation_steps"], learning_rate=settings["learning_rate"], warmup_ratio=settings["warmup_ratio"], optim=settings["optimizer"], seed=settings["seed"], bf16=bf16, fp16=not bf16, max_seq_length=settings["max_sequence_length"], dataset_text_field="text", logging_steps=1, save_strategy="no", report_to="none", gradient_checkpointing=True)
            trainer = SFTTrainer(model=model, processing_class=tokenizer, train_dataset=dataset, peft_config=lora, args=arguments, callbacks=[ThermalGuard()])
            receipt["state"] = "TRAINING_STARTED_NOT_PROMOTED"; receipt["training_started_at_unix_ns"] = time.time_ns(); atomic_json(receipts / "training-receipt.json", receipt)
            result = trainer.train(); guard.check("after-training")
            if int(result.global_step) != settings["max_steps"]:
                raise GateRefused("trainer did not complete the fixed step count")
            adapter = output / "adapter"; adapter.mkdir(parents=True, exist_ok=True)
            trainer.model.save_pretrained(adapter, safe_serialization=True); tokenizer.save_pretrained(adapter)
            inventory = _inventory(adapter)
            if "adapter_model.safetensors" not in {item["path"] for item in inventory} or any(item["path"].endswith(".bin") for item in inventory):
                raise GateRefused("adapter is not a safetensors-only package")
            atomic_json(receipts / "adapter-files.json", {"schema_version": "szl.nemo.adapter-files.v1", "files": inventory})
            receipt.update({"state": "TRAINING_COMPLETED_EVALUATION_REQUIRED", "training_completed_at_unix_ns": time.time_ns(), "global_steps": int(result.global_step), "training_loss": float(result.training_loss), "peak_vram_reserved_bytes": int(torch.cuda.max_memory_reserved()), "adapter_files_sha256": sha256_file(receipts / "adapter-files.json")})
            atomic_json(receipts / "training-receipt.json", receipt)
            del trainer, model; torch.cuda.empty_cache()
            reload_model = AutoModelForCausalLM.from_pretrained(str(snapshot), local_files_only=True, quantization_config=quant, device_map="auto", trust_remote_code=True, use_safetensors=True, low_cpu_mem_usage=True)
            receipt["reloaded_model_class"] = verify_loaded_model_source(reload_model, contract, "reload")
            reload_model = PeftModel.from_pretrained(reload_model, str(adapter), is_trainable=False, local_files_only=True); reload_model.eval()
            results: list[dict[str, Any]] = []
            for row in eval_rows:
                guard.check(row["record_id"])
                prompt = tokenizer.apply_chat_template(row["messages"], tokenize=False, add_generation_prompt=True, enable_thinking=False)
                inputs = tokenizer(prompt, return_tensors="pt").to(reload_model.device)
                with torch.inference_mode():
                    generated = reload_model.generate(**inputs, max_new_tokens=settings["maximum_eval_new_tokens"], do_sample=False, pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id)
                text = tokenizer.decode(generated[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()
                results.append({"record_id": row["record_id"], **_evaluate_output(text, row["expected"])})
            reload_state = "PASS" if results and all(item["state"] == "PASS" for item in results) else "FAIL"
            reload_receipt = {"schema_version": "szl.nemo.reload-evaluation-receipt.v1", "state": reload_state, "rows": len(results), "passes": sum(item["state"] == "PASS" for item in results), "adapter_files_sha256": sha256_file(receipts / "adapter-files.json"), "base_revision": contract["base"]["revision"], "eval_sha256": sha256_file(EVAL_PATH), "results": results, "promotion": "NONE_AUTOMATIC"}
            atomic_json(receipts / "reload-evaluation-receipt.json", reload_receipt)
            after = verify_base(snapshot)
            if before != after:
                raise GateRefused("base inputs changed during training")
            validate_curriculum()
            curriculum_after = curriculum_input_identity()
            if curriculum_before != curriculum_after:
                raise GateRefused("curriculum inputs changed during training")
            source_control_after = git_identity(contract)
            if source_control != source_control_after:
                raise GateRefused("training source identity changed during training")
            summary = {"schema_version": "szl.nemo.candidate-summary.v1", "contract_id": contract["contract_id"], "base_revision": contract["base"]["revision"], "adapter_files_receipt_sha256": sha256_file(receipts / "adapter-files.json"), "reload_evaluation_receipt_sha256": sha256_file(receipts / "reload-evaluation-receipt.json"), "evaluation_state": reload_state, "runtime_guard": guard.receipt(), "promotion": "NOT_PROMOTED"}
            signed = _sign_summary(summary); atomic_json(receipts / "candidate-summary.dsse.json", signed)
            receipt.update({"state": "CANDIDATE_GENERATED_NOT_PROMOTED" if reload_state == "PASS" else "EVALUATION_FAILED_NOT_PROMOTED", "completed_at_unix_ns": time.time_ns(), "base_files_after": after, "curriculum_inputs_after": curriculum_after, "source_control_after": source_control_after, "reload_evaluation_receipt_sha256": sha256_file(receipts / "reload-evaluation-receipt.json"), "candidate_summary_dsse_sha256": sha256_file(receipts / "candidate-summary.dsse.json"), "organization_signature_verified": signed["promotion_eligible_signature"], "runtime_guard": guard.receipt(), "promotion": "NOT_PROMOTED"})
            atomic_json(receipts / "training-receipt.json", receipt)
            return 0 if reload_state == "PASS" else 4
    except Exception as exc:
        receipt.update({"state": "FAILED_NOT_PROMOTED", "completed_at_unix_ns": time.time_ns(), "error_type": type(exc).__name__, "error": str(exc), "traceback_sha256": sha256_bytes(traceback.format_exc().encode("utf-8")), "promotion": "NOT_PROMOTED"})
        atomic_json(receipts / "training-receipt.json", receipt)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build")
    fetch = sub.add_parser("fetch-base"); fetch.add_argument("--destination", type=Path, required=True); fetch.add_argument("--confirmation", required=True)
    check = sub.add_parser("preflight"); check.add_argument("--base-snapshot", type=Path); check.add_argument("--check-gpu", action="store_true"); check.add_argument("--probe", action="store_true"); check.add_argument("--receipt", type=Path)
    capacity = sub.add_parser("capacity-probe"); capacity.add_argument("--base-snapshot", type=Path, required=True); capacity.add_argument("--receipt", type=Path, required=True); capacity.add_argument("--confirmation", required=True); capacity.add_argument("--license-acknowledgement", required=True)
    run = sub.add_parser("train"); run.add_argument("--base-snapshot", type=Path, required=True); run.add_argument("--output-dir", type=Path, required=True); run.add_argument("--confirmation", required=True); run.add_argument("--license-acknowledgement", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            with training_mutex(): result = build_curriculum()
            print(json.dumps(result, indent=2)); return 0
        if args.command == "fetch-base":
            print(json.dumps(fetch_base(args.destination, args.confirmation), indent=2)); return 0
        if args.command == "preflight":
            with fresh_hf_modules_cache() as module_cache:
                result = preflight(args.base_snapshot, args.check_gpu, args.probe)
                result["dynamic_module_cache"] = module_cache
            if args.receipt: atomic_json(args.receipt, result)
            print(json.dumps(result, indent=2)); return 0 if result["state"] == "PASS" else 3
        if args.command == "capacity-probe":
            with training_mutex(), fresh_hf_modules_cache() as module_cache:
                return capacity_probe(args.base_snapshot, args.receipt, args.confirmation, args.license_acknowledgement, module_cache)
        with training_mutex(), fresh_hf_modules_cache() as module_cache:
            return train(args.base_snapshot, args.output_dir, args.confirmation, args.license_acknowledgement, module_cache)
    except GateRefused as exc:
        print(json.dumps({"state": "BLOCKED", "reason": str(exc), "effects": {"training_started": False, "uploaded": False, "published": False, "deployed": False}}, indent=2), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
