#!/usr/bin/env python3
"""Governed, fail-closed SZL-Nemo QLoRA candidate pipeline.

``fetch-base`` is the only network-capable command and pins the public NVIDIA
snapshot to the exact revision in ``training-contract.json``.  ``build``,
``preflight``, ``train``, and ``evaluate-adapter`` are local-only.  Training and
evaluation never upload, publish, deploy, stop another process, weaken a GPU
threshold, or promote themselves.
"""

from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager, nullcontext
import gc
import hashlib
import importlib
import importlib.metadata
import importlib.util
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
import types
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
SHADOW_EVAL_PATH = GENERATED / "shadow-eval.jsonl"
DSSE_PATH = REPO / "szl_dsse.py"
CONTENT_ADDRESS_PATH = REPO / "szl_content_address.py"
SYSTEM_PROMPT = (
    "You are an SZL-Nemo governed-adapter candidate built on NVIDIA Nemotron 3 "
    "Nano 4B. Preserve upstream attribution and license lineage. Distinguish "
    "MEASURED, REPORTED, and UNKNOWN. Never invent evidence, execution, proof, "
    "signatures, receipts, or model quality. Brain retrieval and formulas remain "
    "external evidence planes unless separately admitted."
)
FETCH_CONFIRMATION = "FETCH_SZL_NEMO_BASE_dfaf35de3e30f1867dd8dbc38a7fc9fb52d3914f"
EVALUATION_CONFIRMATION = "EVALUATE_SZL_NEMO_GOVERNED_ADAPTER_V2"
PAYLOAD_TYPE = "application/vnd.szl.nemo-training+json"
SHARED_GPU_TRAINING_LEASE_DIR = REPO / "model_release" / "szl-forge" / "queue-state" / "gpu-training.lease"
GPU_TRAINING_LEASE_OWNER = "owner.json"
TRAINING_START_PROVEN_TRUE = "PROVEN_TRUE"
TRAINING_START_PROVEN_FALSE = "PROVEN_FALSE"
TRAINING_START_UNKNOWN = "UNKNOWN"


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


def host_memory_sample() -> dict[str, Any]:
    """Read Linux MemAvailable and process RSS/high-water marks.

    The governed execution lane is Linux/WSL2.  A missing procfs entry is
    reported as UNKNOWN rather than inferred or converted into a pass.
    """

    status_path = Path("/proc/self/status")
    meminfo_path = Path("/proc/meminfo")
    if not status_path.is_file() or not meminfo_path.is_file():
        return {"state": "UNKNOWN_PROCFS_UNAVAILABLE"}
    wanted = {"VmRSS": "rss_bytes", "VmHWM": "peak_rss_bytes"}
    observed: dict[str, Any] = {
        "state": "MEASURED_PROCFS",
        "measured_at_unix_ns": time.time_ns(),
    }
    try:
        for line in status_path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition(":")
            if separator and key in wanted:
                fields = value.strip().split()
                if len(fields) == 2 and fields[1] == "kB":
                    observed[wanted[key]] = int(fields[0]) * 1024
        for line in meminfo_path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition(":")
            if separator and key == "MemAvailable":
                fields = value.strip().split()
                if len(fields) == 2 and fields[1] == "kB":
                    observed["mem_available_bytes"] = int(fields[0]) * 1024
                break
    except (OSError, ValueError):
        return {"state": "UNKNOWN_PROCFS_READ_FAILED"}
    if any(
        field not in observed
        for field in ("rss_bytes", "peak_rss_bytes", "mem_available_bytes")
    ):
        return {"state": "UNKNOWN_PROCFS_FIELDS_MISSING"}
    return observed


def evaluate_host_ram_sample(
    sample: dict[str, Any], policy: dict[str, Any], baseline: dict[str, Any]
) -> dict[str, Any]:
    """Evaluate one procfs sample so bounds are enforced during execution."""

    if policy.get("unknown_measurement_action") != "REFUSE_CALIBRATION":
        raise GateRefused("activation-offload host-RAM UNKNOWN policy is not fail closed")
    if (
        sample.get("state") != "MEASURED_PROCFS"
        or baseline.get("state") != "MEASURED_PROCFS"
    ):
        raise GateRefused("activation-offload host-RAM evidence is UNKNOWN")
    bytes_per_mib = 1024 * 1024
    minimum_available = int(policy["minimum_mem_available_mib"]) * bytes_per_mib
    maximum_rss = int(policy["maximum_process_rss_mib"]) * bytes_per_mib
    maximum_delta = int(policy["maximum_process_rss_delta_mib"]) * bytes_per_mib
    if minimum_available <= 0 or maximum_rss <= 0 or maximum_delta <= 0:
        raise GateRefused("activation-offload host-RAM thresholds are invalid")
    baseline_rss = int(baseline["rss_bytes"])
    baseline_peak_rss = int(baseline["peak_rss_bytes"])
    rss = int(sample["rss_bytes"])
    peak_rss = int(sample["peak_rss_bytes"])
    mem_available = int(sample["mem_available_bytes"])
    rss_delta = max(0, rss - baseline_rss)
    peak_rss_delta = max(0, peak_rss - baseline_peak_rss)
    violations: list[str] = []
    if mem_available < minimum_available:
        violations.append("MEM_AVAILABLE_BELOW_FLOOR")
    if rss > maximum_rss or peak_rss > maximum_rss:
        violations.append("PROCESS_RSS_ABOVE_CEILING")
    if rss_delta > maximum_delta or peak_rss_delta > maximum_delta:
        violations.append("PROCESS_RSS_DELTA_ABOVE_CEILING")
    assessment = {
        "stage": sample.get("stage"),
        "mem_available_mib": mem_available // bytes_per_mib,
        "rss_mib": rss // bytes_per_mib,
        "peak_rss_mib": peak_rss // bytes_per_mib,
        "rss_delta_mib": rss_delta // bytes_per_mib,
        "peak_rss_delta_mib": peak_rss_delta // bytes_per_mib,
        "state": "PASS" if not violations else "FAIL",
        "violations": violations,
    }
    if violations:
        raise GateRefused(
            "activation-offload host-RAM threshold failed at "
            f"{sample.get('stage')}: " + ", ".join(violations)
        )
    return assessment


def append_governed_host_memory_sample(
    samples: list[dict[str, Any]], stage: str, policy: dict[str, Any]
) -> dict[str, Any]:
    """Append and immediately enforce a host-RAM sample."""

    sample = {"stage": stage, **host_memory_sample()}
    samples.append(sample)
    baseline = samples[0]
    evaluation = evaluate_host_ram_sample(sample, policy, baseline)
    sample["admission"] = evaluation
    return sample


def evaluate_host_ram_admission(
    samples: list[dict[str, Any]], policy: dict[str, Any]
) -> dict[str, Any]:
    """Require every declared host-RAM phase before calibration can pass."""

    required_stages = policy.get("required_sample_stages")
    if not isinstance(required_stages, list) or not all(
        isinstance(stage, str) and stage for stage in required_stages
    ):
        raise GateRefused("activation-offload host-RAM stages are malformed")
    observed_by_stage = {
        sample.get("stage"): sample
        for sample in samples
        if isinstance(sample, dict) and isinstance(sample.get("stage"), str)
    }
    if any(stage not in observed_by_stage for stage in required_stages):
        raise GateRefused("activation-offload host-RAM evidence is missing a required stage")
    baseline = observed_by_stage["before_model_load"]
    evaluations = [
        evaluate_host_ram_sample(observed_by_stage[stage], policy, baseline)
        for stage in required_stages
    ]
    return {
        "state": "PASS",
        "measurement_source": policy.get("measurement_source"),
        "policy": policy,
        "samples": evaluations,
        "violations": [],
        "training_authority": False,
    }


def _pinned_dsse_identity(contract: dict[str, Any]) -> dict[str, str]:
    policy = contract.get("dsse")
    if not isinstance(policy, dict) or policy.get("ambient_module_allowed") is not False:
        raise GateRefused("training contract lacks a fail-closed DSSE verifier policy")
    relative = policy.get("verifier_path")
    expected_sha = policy.get("verifier_sha256")
    content_address_relative = policy.get("content_address_path")
    content_address_expected_sha = policy.get("content_address_sha256")
    key_id = policy.get("key_id")
    fingerprint = policy.get("public_key_fingerprint_sha256")
    if (
        relative != "szl_dsse.py"
        or not isinstance(expected_sha, str)
        or len(expected_sha) != 64
        or content_address_relative != "szl_content_address.py"
        or not isinstance(content_address_expected_sha, str)
        or len(content_address_expected_sha) != 64
        or not isinstance(key_id, str)
        or not key_id
        or not isinstance(fingerprint, str)
        or len(fingerprint) != 64
    ):
        raise GateRefused("pinned DSSE verifier identity is malformed")
    candidate = REPO / relative
    if candidate.is_symlink() or not candidate.is_file():
        raise GateRefused("pinned DSSE verifier is absent or symlinked")
    if candidate.resolve() != DSSE_PATH.resolve() or sha256_file(candidate) != expected_sha:
        raise GateRefused("pinned DSSE verifier source mismatch")
    content_address_candidate = REPO / content_address_relative
    if content_address_candidate.is_symlink() or not content_address_candidate.is_file():
        raise GateRefused("pinned content-address dependency is absent or symlinked")
    if (
        content_address_candidate.resolve() != CONTENT_ADDRESS_PATH.resolve()
        or sha256_file(content_address_candidate) != content_address_expected_sha
    ):
        raise GateRefused("pinned content-address dependency source mismatch")
    return {
        "path": relative,
        "sha256": expected_sha,
        "content_address_path": content_address_relative,
        "content_address_sha256": content_address_expected_sha,
        "key_id": key_id,
        "public_key_fingerprint_sha256": fingerprint,
    }


def _load_pinned_dsse(contract: dict[str, Any]) -> tuple[Any, dict[str, str]]:
    identity = _pinned_dsse_identity(contract)
    dependency_spec = importlib.util.spec_from_file_location(
        "szl_content_address", CONTENT_ADDRESS_PATH
    )
    if dependency_spec is None or dependency_spec.loader is None:
        raise GateRefused("pinned content-address dependency could not be loaded")
    dependency = importlib.util.module_from_spec(dependency_spec)
    try:
        dependency_spec.loader.exec_module(dependency)
    except Exception as exc:
        raise GateRefused("pinned content-address dependency execution failed") from exc

    dsse_spec = importlib.util.spec_from_file_location(
        f"_szl_nemo_pinned_dsse_{uuid.uuid4().hex}", DSSE_PATH
    )
    if dsse_spec is None or dsse_spec.loader is None:
        raise GateRefused("pinned DSSE verifier could not be loaded")
    module = importlib.util.module_from_spec(dsse_spec)
    dependency_name = "szl_content_address"
    missing = object()
    prior_dependency = sys.modules.get(dependency_name, missing)
    try:
        # szl_dsse imports this dependency by its canonical name.  Supply only
        # the file whose path and digest were verified above, then restore any
        # ambient module so the pinned loader cannot mutate process-wide state.
        sys.modules[dependency_name] = dependency
        dsse_spec.loader.exec_module(module)
        observed_fingerprint = module.public_key_fingerprint()
    except Exception as exc:
        raise GateRefused("pinned DSSE verifier execution failed") from exc
    finally:
        if prior_dependency is missing:
            sys.modules.pop(dependency_name, None)
        else:
            sys.modules[dependency_name] = prior_dependency
    if (
        getattr(module, "KEYID", None) != identity["key_id"]
        or observed_fingerprint != identity["public_key_fingerprint_sha256"]
    ):
        raise GateRefused("pinned DSSE verifier key identity mismatch")
    return module, identity


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


def create_json_once(path: Path, value: dict[str, Any]) -> None:
    """Claim an append-only evidence path without a check-then-replace race."""

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise GateRefused(
            "capacity or calibration receipt path already exists; evidence is append-only"
        ) from exc


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
    _pinned_dsse_identity(contract)
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
    expected = {
        "schema_version", "owner", "license", "rights_basis", "profile_id",
        "notice", "train_scenarios", "contrastive_train_scenarios",
        "eval_scenarios", "shadow_eval_scenarios",
    }
    if set(source) != expected:
        raise GateRefused("curriculum source has unknown or missing fields")
    if source["schema_version"] != "szl.nemo.curriculum-source.v2":
        raise GateRefused("unsupported curriculum source schema")
    if (source["owner"], source["license"], source["rights_basis"], source["profile_id"]) != (
        "SZL Holdings", "Apache-2.0", "PROJECT_AUTHORED_SCENARIOS", "SZL-Nemo-Governed-v2"
    ):
        raise GateRefused("curriculum rights declaration is not admitted")
    if not isinstance(source["notice"], str) or not source["notice"].strip():
        raise GateRefused("curriculum notice is absent")
    train = source["train_scenarios"]
    contrastive = source["contrastive_train_scenarios"]
    evaluation = source["eval_scenarios"]
    shadow = source["shadow_eval_scenarios"]
    if (
        not isinstance(train, list)
        or not isinstance(contrastive, list)
        or (len(train) + len(contrastive)) * 3
        < contract["curriculum"]["minimum_train_rows"]
    ):
        raise GateRefused("training scenarios are below the contract minimum")
    if len(contrastive) < contract["curriculum"]["minimum_contrastive_scenarios"]:
        raise GateRefused("contrastive training scenarios are below the contract minimum")
    if not isinstance(evaluation, list) or len(evaluation) < contract["curriculum"]["minimum_eval_rows"]:
        raise GateRefused("evaluation scenarios are below the contract minimum")
    if not isinstance(shadow, list) or len(shadow) < contract["curriculum"]["minimum_shadow_eval_rows"]:
        raise GateRefused("shadow evaluation scenarios are below the contract minimum")
    ids: set[str] = set()
    prompts: set[str] = set()
    required_classes = set(contract["curriculum"]["required_contrastive_behavior_classes"])
    contrastive_counts = {name: 0 for name in required_classes}
    for split, scenarios in (
        ("train", train),
        ("contrastive", contrastive),
        ("eval", evaluation),
        ("shadow", shadow),
    ):
        for item in scenarios:
            if split == "train":
                keys = {"id", "prompt", "response"}
            elif split == "contrastive":
                keys = {"id", "behavior_class", "prompt", "response", "rights_admission"}
            elif split == "eval":
                keys = {"id", "prompt", "required_terms", "forbidden_terms"}
            else:
                keys = {"id", "behavior_class", "prompt", "required_terms", "forbidden_terms"}
            if not isinstance(item, dict) or set(item) != keys:
                raise GateRefused(f"{split} scenario has unknown or missing fields")
            if not all(isinstance(item[key], str) and item[key].strip() for key in ("id", "prompt")):
                raise GateRefused(f"{split} scenario identity or prompt is invalid")
            if item["id"] in ids or item["prompt"].casefold() in prompts:
                raise GateRefused("curriculum ids and prompts must be unique across splits")
            ids.add(item["id"])
            prompts.add(item["prompt"].casefold())
            if split in {"train", "contrastive"} and (not isinstance(item["response"], str) or not item["response"].strip()):
                raise GateRefused("training response is invalid")
            if split == "contrastive":
                behavior_class = item["behavior_class"]
                if behavior_class not in required_classes:
                    raise GateRefused("contrastive behavior class is not preregistered")
                admission = item["rights_admission"]
                expected_admission = {
                    "author": "SZL Holdings",
                    "license": "Apache-2.0",
                    "rights_basis": "PROJECT_AUTHORED_SCENARIOS",
                    "provenance": "INDEPENDENTLY_AUTHORED_FOR_NEMO_V2",
                    "held_out_contamination": "NO_ORIGINAL_OR_SHADOW_EVAL_TEXT_COPIED",
                }
                if admission != expected_admission:
                    raise GateRefused("contrastive training row lacks exact rights admission")
                contrastive_counts[behavior_class] += 1
            if split == "shadow" and item["behavior_class"] not in required_classes:
                raise GateRefused("shadow behavior class is not preregistered")
            if split in {"eval", "shadow"}:
                for key in ("required_terms", "forbidden_terms"):
                    terms = item[key]
                    if not isinstance(terms, list) or (key == "required_terms" and not terms) or any(not isinstance(term, str) or not term for term in terms):
                        raise GateRefused(f"evaluation {key} is invalid")
    minimum = contract["curriculum"]["minimum_contrastive_examples_per_class"]
    maximum = contract["curriculum"]["maximum_contrastive_examples_per_class"]
    if set(contrastive_counts) != required_classes or any(
        not minimum <= count <= maximum for count in contrastive_counts.values()
    ):
        raise GateRefused("contrastive behavior coverage is outside the preregistered bounds")


def _curriculum_rows(
    source: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
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
    for scenario in source["contrastive_train_scenarios"]:
        for index, prefix in enumerate(variants, 1):
            train.append({
                "schema_version": "szl.nemo.curriculum-record.v2",
                "record_id": f"train:contrastive:{scenario['id']}:{index}",
                "split": "TRAIN",
                "rights_basis": "PROJECT_AUTHORED_SCENARIOS",
                "behavior_class": scenario["behavior_class"],
                "rights_admission": scenario["rights_admission"],
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
    shadow = [{
        "schema_version": "szl.nemo.shadow-eval-record.v1",
        "record_id": f"shadow:{scenario['id']}",
        "split": "SHADOW_EVAL",
        "rights_basis": "PROJECT_AUTHORED_SCENARIOS",
        "behavior_class": scenario["behavior_class"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": scenario["prompt"]},
        ],
        "expected": {"required_terms": scenario["required_terms"], "forbidden_terms": scenario["forbidden_terms"]},
    } for scenario in source["shadow_eval_scenarios"]]
    return train, evaluation, shadow


def build_curriculum(output: Path = GENERATED) -> dict[str, Any]:
    contract = load_object(CONTRACT_PATH)
    _validate_contract_assets(contract)
    source = load_object(SOURCE_PATH)
    validate_source(source, contract)
    train, evaluation, shadow = _curriculum_rows(source)
    train_path = output / "train.jsonl"
    eval_path = output / "eval.jsonl"
    shadow_eval_path = output / "shadow-eval.jsonl"
    atomic_jsonl(train_path, train)
    atomic_jsonl(eval_path, evaluation)
    atomic_jsonl(shadow_eval_path, shadow)
    if sha256_file(eval_path) != contract["curriculum"]["frozen_original_eval_sha256"]:
        raise GateRefused("frozen original evaluation bytes changed")
    manifest = {
        "schema_version": "szl.nemo.curriculum-manifest.v2",
        "contract_id": contract["contract_id"],
        "rights_basis": "PROJECT_AUTHORED_SCENARIOS",
        "source_sha256": sha256_file(SOURCE_PATH),
        "schema_sha256": sha256_file(SCHEMA_PATH),
        "train": {"path": train_path.name, "rows": len(train), "sha256": sha256_file(train_path)},
        "eval": {"path": eval_path.name, "rows": len(evaluation), "sha256": sha256_file(eval_path)},
        "shadow_eval": {"path": shadow_eval_path.name, "rows": len(shadow), "sha256": sha256_file(shadow_eval_path)},
        "evaluation_gate": "ORIGINAL_AND_SHADOW_MUST_BOTH_PASS",
        "excluded_from_gradients": contract["excluded_from_gradients"],
        "external_mutations": {"uploaded": False, "published": False, "deployed": False},
    }
    atomic_json(output / "curriculum-manifest.json", manifest)
    return manifest


def validate_curriculum() -> dict[str, Any]:
    if not all(path.is_file() for path in (MANIFEST_PATH, TRAIN_PATH, EVAL_PATH, SHADOW_EVAL_PATH)):
        raise GateRefused("generated curriculum is absent; run build")
    observed = load_object(MANIFEST_PATH)
    with tempfile.TemporaryDirectory(prefix="szl-nemo-curriculum-") as directory:
        expected = build_curriculum(Path(directory))
        if (
            observed != expected
            or sha256_file(TRAIN_PATH) != expected["train"]["sha256"]
            or sha256_file(EVAL_PATH) != expected["eval"]["sha256"]
            or sha256_file(SHADOW_EVAL_PATH) != expected["shadow_eval"]["sha256"]
        ):
            raise GateRefused("generated curriculum differs from its pinned source")
    train_prompts = {row["messages"][1]["content"].casefold() for row in iter_jsonl(TRAIN_PATH)}
    eval_prompts = {row["messages"][1]["content"].casefold() for row in iter_jsonl(EVAL_PATH)}
    shadow_prompts = {row["messages"][1]["content"].casefold() for row in iter_jsonl(SHADOW_EVAL_PATH)}
    if train_prompts & (eval_prompts | shadow_prompts) or eval_prompts & shadow_prompts:
        raise GateRefused("training, original evaluation, and shadow evaluation prompts must be disjoint")
    contract = load_object(CONTRACT_PATH)
    if sha256_file(EVAL_PATH) != contract["curriculum"]["frozen_original_eval_sha256"]:
        raise GateRefused("frozen original evaluation identity changed")
    return observed


def curriculum_input_identity() -> dict[str, Any]:
    """Bind the exact admitted files used by one capacity/training process."""

    return {
        "manifest": {"bytes": MANIFEST_PATH.stat().st_size, "sha256": sha256_file(MANIFEST_PATH)},
        "train": {"bytes": TRAIN_PATH.stat().st_size, "sha256": sha256_file(TRAIN_PATH)},
        "eval": {"bytes": EVAL_PATH.stat().st_size, "sha256": sha256_file(EVAL_PATH)},
        "shadow_eval": {"bytes": SHADOW_EVAL_PATH.stat().st_size, "sha256": sha256_file(SHADOW_EVAL_PATH)},
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
        from transformers import AutoConfig, AutoTokenizer, GenerationConfig
        from transformers.dynamic_module_utils import get_class_from_dynamic_module

        config = AutoConfig.from_pretrained(
            str(snapshot), local_files_only=True, trust_remote_code=True
        )
        tokenizer = AutoTokenizer.from_pretrained(
            str(snapshot), local_files_only=True, trust_remote_code=True
        )
        generation_config = GenerationConfig.from_pretrained(
            str(snapshot), local_files_only=True
        )
        padding = admit_padding_token(tokenizer, contract, "execution-lane")
        padding_config = verify_model_padding_binding(
            types.SimpleNamespace(config=config, generation_config=generation_config),
            padding,
            "execution-lane",
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
        "padding_token_admission": padding,
        "padding_config_binding": padding_config,
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


def physical_gpu_phase_sample(stage: str) -> dict[str, Any]:
    """Sample physical free VRAM without turning UNKNOWN into a failure claim."""

    try:
        return {
            "stage": stage,
            "state": "MEASURED_NVIDIA_SMI",
            **query_gpu(),
        }
    except Exception as exc:
        return {
            "stage": stage,
            "state": "UNKNOWN_GPU_QUERY_FAILED",
            "error_type": type(exc).__name__,
        }


def evaluate_activation_offload_adoption(
    samples: list[dict[str, Any]],
    requirements: dict[str, Any],
    sequence_tokens: int,
    loss_is_finite: bool,
    adapter_gradients_are_finite: bool,
) -> dict[str, Any]:
    """Assess empirical adoption evidence without granting training authority.

    A failed empirical predicate does not erase a valid calibration result.  A
    passing predicate remains NOT_EVALUATED for profile adoption while the
    contract's independent review is outstanding.
    """

    required_phases = requirements.get("required_vram_headroom_phases")
    if not isinstance(required_phases, list) or not all(
        isinstance(stage, str) and stage for stage in required_phases
    ):
        raise GateRefused("activation-offload VRAM adoption phases are malformed")
    observed_by_stage = {
        sample.get("stage"): sample
        for sample in samples
        if isinstance(sample, dict) and isinstance(sample.get("stage"), str)
    }
    missing = [stage for stage in required_phases if stage not in observed_by_stage]
    unknown = [
        stage
        for stage in required_phases
        if stage in observed_by_stage
        and observed_by_stage[stage].get("state") != "MEASURED_NVIDIA_SMI"
    ]
    minimum_required = int(requirements["minimum_measured_vram_headroom_mib"])
    if minimum_required <= 0:
        raise GateRefused("activation-offload VRAM adoption threshold is invalid")

    predicate: dict[str, Any] = {
        "state": "NOT_EVALUATED",
        "measurement_source": requirements.get("vram_measurement_source"),
        "minimum_required_free_memory_mib": minimum_required,
        "required_phases": required_phases,
        "missing_phases": missing,
        "unknown_phases": unknown,
        "minimum_observed_free_memory_mib": None,
        "sequence_tokens": sequence_tokens,
        "loss_is_finite": loss_is_finite,
        "adapter_gradients_are_finite": adapter_gradients_are_finite,
    }
    if not missing and not unknown:
        phase_samples = [observed_by_stage[stage] for stage in required_phases]
        required_gpu = load_object(CONTRACT_PATH)["runtime"]["required_device_name"]
        identity_matches = all(
            sample.get("gpu_name") == required_gpu for sample in phase_samples
        )
        minimum_observed = min(
            int(sample["memory_free_mib"]) for sample in phase_samples
        )
        predicate.update(
            {
                "minimum_observed_free_memory_mib": minimum_observed,
                "gpu_identity_matches": identity_matches,
            }
        )
        predicate["state"] = (
            "PASS"
            if identity_matches
            and minimum_observed >= minimum_required
            and sequence_tokens == 768
            and loss_is_finite
            and adapter_gradients_are_finite
            else "FAIL"
        )

    independent_review_required = requirements.get("independent_review_required") is True
    if predicate["state"] == "FAIL":
        adoption_state = "FAIL"
        reason = "EMPIRICAL_ADOPTION_PREDICATE_FAILED"
    elif predicate["state"] == "NOT_EVALUATED":
        adoption_state = "NOT_EVALUATED"
        reason = "PHYSICAL_VRAM_EVIDENCE_INCOMPLETE_OR_UNKNOWN"
    elif independent_review_required:
        adoption_state = "NOT_EVALUATED"
        reason = "EMPIRICAL_PREDICATE_PASSED_INDEPENDENT_REVIEW_REQUIRED"
    else:
        adoption_state = "PASS"
        reason = "ALL_DECLARED_ADOPTION_REQUIREMENTS_SATISFIED"
    return {
        "state": adoption_state,
        "reason": reason,
        "empirical_predicate": predicate,
        "independent_review": {
            "required": independent_review_required,
            "state": "NOT_EVALUATED" if independent_review_required else "NOT_REQUIRED",
        },
        "training_authority": False,
        "queue_progression_allowed": False,
        "canonical_gpu_threshold_changed": False,
    }


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


def admit_padding_token(
    tokenizer: Any, contract: dict[str, Any], phase: str
) -> dict[str, Any]:
    """Bind padding to an already-pinned special token without changing vocab."""

    policy = contract.get("training", {}).get("padding_policy")
    expected_keys = {
        "source",
        "token",
        "token_id",
        "special_token_attribute",
        "vocabulary_mutation_allowed",
    }
    if not isinstance(policy, dict) or set(policy) != expected_keys:
        raise GateRefused(f"{phase} padding policy is absent or malformed")
    if policy["source"] != "PINNED_MODEL_AND_GENERATION_CONFIG":
        raise GateRefused(f"{phase} padding token source is not admitted")
    if policy["vocabulary_mutation_allowed"] is not False:
        raise GateRefused(f"{phase} padding policy permits vocabulary mutation")
    expected_token = policy["token"]
    expected_id = policy["token_id"]
    attribute = policy["special_token_attribute"]
    if not isinstance(expected_token, str) or not expected_token:
        raise GateRefused(f"{phase} padding token is invalid")
    if not isinstance(expected_id, int) or isinstance(expected_id, bool) or expected_id < 0:
        raise GateRefused(f"{phase} padding token id is invalid")
    if not isinstance(attribute, str) or not attribute.endswith("_token"):
        raise GateRefused(f"{phase} padding special-token attribute is invalid")

    try:
        length_before = len(tokenizer)
        added_before = dict(tokenizer.get_added_vocab())
        source_token = getattr(tokenizer, attribute)
        source_id = getattr(tokenizer, f"{attribute}_id")
        id_token = tokenizer.convert_ids_to_tokens(expected_id)
        token_id = tokenizer.convert_tokens_to_ids(expected_token)
    except Exception as exc:
        raise GateRefused(f"{phase} tokenizer cannot prove padding identity") from exc
    if (source_token, source_id, id_token, token_id) != (
        expected_token,
        expected_id,
        expected_token,
        expected_id,
    ):
        raise GateRefused(f"{phase} pinned padding token identity is inconsistent")

    pad_before = {
        "token": getattr(tokenizer, "pad_token", None),
        "token_id": getattr(tokenizer, "pad_token_id", None),
    }
    if pad_before["token"] not in {None, expected_token} or pad_before[
        "token_id"
    ] not in {None, expected_id}:
        raise GateRefused(f"{phase} tokenizer has conflicting padding identity")
    tokenizer.pad_token = expected_token
    try:
        length_after = len(tokenizer)
        added_after = dict(tokenizer.get_added_vocab())
    except Exception as exc:
        raise GateRefused(f"{phase} tokenizer padding mutation cannot be measured") from exc
    if (
        tokenizer.pad_token != expected_token
        or tokenizer.pad_token_id != expected_id
        or length_after != length_before
        or added_after != added_before
    ):
        raise GateRefused(f"{phase} padding bind changed vocabulary or token identity")
    return {
        "state": "BOUND_PINNED_SPECIAL_TOKEN_NO_VOCAB_MUTATION",
        "phase": phase,
        "source": policy["source"],
        "special_token_attribute": attribute,
        "token": expected_token,
        "token_id": expected_id,
        "pad_before": pad_before,
        "pad_after": {"token": tokenizer.pad_token, "token_id": tokenizer.pad_token_id},
        "vocabulary_size_before": length_before,
        "vocabulary_size_after": length_after,
        "added_vocabulary_unchanged": True,
    }


def verify_model_padding_binding(
    model: Any, padding: dict[str, Any], phase: str
) -> dict[str, Any]:
    """Require model and generation configs to match admitted tokenizer padding."""

    expected_id = padding.get("token_id")
    model_config = getattr(model, "config", None)
    generation_config = getattr(model, "generation_config", None)
    model_id = getattr(model_config, "pad_token_id", None)
    generation_id = getattr(generation_config, "pad_token_id", None)
    if model_id != expected_id or generation_id != expected_id:
        raise GateRefused(f"{phase} model/generation padding identity is inconsistent")
    return {
        "state": "CONSISTENT_PINNED_PADDING_IDS",
        "phase": phase,
        "token": padding["token"],
        "token_id": expected_id,
        "model_config_pad_token_id": model_id,
        "generation_config_pad_token_id": generation_id,
    }


def _decomposed_mamba_cuda_forward(
    mixer: Any,
    hidden_states: Any,
    cache_params: Any = None,
    cache_position: Any = None,
    attention_mask: Any = None,
) -> Any:
    """Use NVIDIA's decomposed CUDA scan while preserving LoRA module calls.

    In the pinned NVIDIA implementation, ``cuda_kernels_forward`` selects its
    combined training kernel solely from the mixer's own ``training`` flag.
    The alternate branch still uses the official CUDA convolution and Mamba
    scan kernels, but finishes with ``self.out_proj(scan_output)``.  Temporarily
    changing only the mixer's flag selects that branch without recursively
    changing the PEFT projection's training state or its LoRA dropout.
    """

    mixer_training = getattr(mixer, "training", None)
    projection = getattr(mixer, "out_proj", None)
    projection_training = getattr(projection, "training", None)
    if mixer_training is not True or projection_training is not True:
        raise GateRefused("decomposed Mamba CUDA training dispatch requires active module training")
    mixer.training = False
    try:
        if getattr(projection, "training", None) is not True:
            raise GateRefused("Mamba LoRA projection training state changed during dispatch")
        return mixer.cuda_kernels_forward(
            hidden_states, cache_params, cache_position, attention_mask
        )
    finally:
        mixer.training = mixer_training


def mamba_naive_pairwise_memory_model(
    config: Any, batch_size: int, sequence_length: int
) -> dict[str, Any]:
    """Model the explicit float32 pairwise tensor in NVIDIA ``torch_forward``."""

    fields = {
        "batch_size": batch_size,
        "sequence_length": sequence_length,
        "chunk_size": getattr(config, "chunk_size", None),
        "mamba_num_heads": getattr(config, "mamba_num_heads", None),
        "ssm_state_size": getattr(config, "ssm_state_size", None),
    }
    if not all(isinstance(value, int) and value > 0 for value in fields.values()):
        raise GateRefused("Mamba pairwise memory dimensions are invalid")
    chunk_size = fields["chunk_size"]
    chunks = math.ceil(sequence_length / chunk_size)
    shape = [
        batch_size,
        chunks,
        chunk_size,
        chunk_size,
        fields["mamba_num_heads"],
        fields["ssm_state_size"],
    ]
    elements = math.prod(shape)
    byte_count = elements * 4
    return {
        "state": "MODELED_FROM_HASH_VERIFIED_NVIDIA_TORCH_FORWARD",
        "operation": "G_INTERMEDIATE_EQUALS_C_PAIRWISE_TIMES_B",
        "dtype": "float32",
        "shape": shape,
        "elements": elements,
        "bytes": byte_count,
        "gib": byte_count / (1024**3),
        "padded_sequence_length": chunks * chunk_size,
        "receipt_comparison": "COMPARE_TO_CUDA_OOM_REQUEST_NOT_PHYSICAL_ALLOCATION",
    }


def optimizer_state_inventory(optimizer: Any) -> dict[str, Any]:
    state = getattr(optimizer, "state", None)
    if state is None or not hasattr(state, "values"):
        raise GateRefused("optimizer state cannot be measured")
    tensor_count = 0
    tensor_bytes = 0
    for entry in state.values():
        values = entry.values() if hasattr(entry, "values") else ()
        for value in values:
            numel = getattr(value, "numel", None)
            element_size = getattr(value, "element_size", None)
            if callable(numel) and callable(element_size):
                tensor_count += 1
                tensor_bytes += int(numel()) * int(element_size())
    return {
        "state": "MEASURED_FROM_OPTIMIZER_STATE",
        "entry_count": len(state),
        "tensor_count": tensor_count,
        "tensor_bytes": tensor_bytes,
    }


def gradient_checkpointing_evidence(model: Any, phase: str) -> dict[str, Any]:
    active = getattr(model, "is_gradient_checkpointing", None)
    if active is not True:
        raise GateRefused(f"{phase} gradient checkpointing is not active")
    return {
        "state": "ACTIVE_MEASURED_FROM_MODEL_FLAG",
        "phase": phase,
        "requested": True,
        "active": True,
        "use_reentrant": False,
        "early_stop": True,
        "policy_source": "PYTORCH_NON_REENTRANT_RECOMMENDATION",
    }


def bind_quantized_mamba_lora_forward(
    model: Any, contract: dict[str, Any], phase: str
) -> dict[str, Any]:
    """Bind Mamba mixers to NVIDIA's module-aware decomposed CUDA branch.

    The combined training kernel reads ``out_proj.weight`` directly, which is
    incompatible with compressed ``Linear4bit`` storage and bypasses PEFT LoRA.
    NVIDIA's decomposed CUDA branch calls ``self.out_proj(...)`` and avoids the
    explicit 9 GiB pairwise tensor in the pure-PyTorch fallback at seq-768.
    """

    config = getattr(model, "config", None)
    pattern = getattr(config, "hybrid_override_pattern", None)
    if not isinstance(pattern, str) or not pattern:
        raise GateRefused(f"{phase} model has no hybrid override pattern")
    if any(symbol not in {"M", "-", "*"} for symbol in pattern):
        raise GateRefused(f"{phase} hybrid override pattern is invalid")
    expected_mixers = pattern.count("M")
    if expected_mixers <= 0:
        raise GateRefused(f"{phase} hybrid override pattern has no Mamba mixers")

    required_files = contract.get("base", {}).get("required_files", [])
    expected_source_sha256 = next(
        (
            item.get("sha256")
            for item in required_files
            if item.get("path") == "modeling_nemotron_h.py"
        ),
        None,
    )
    if not isinstance(expected_source_sha256, str) or len(expected_source_sha256) != 64:
        raise GateRefused("reviewed Nemotron model source hash is absent from contract")

    named_modules = getattr(model, "named_modules", None)
    if not callable(named_modules):
        raise GateRefused(f"{phase} model cannot enumerate modules")
    mixers = [
        (name, module)
        for name, module in named_modules()
        if type(module).__name__ == "NemotronHMamba2Mixer"
    ]
    if len(mixers) != expected_mixers:
        raise GateRefused(
            f"{phase} Mamba mixer count mismatch: expected {expected_mixers}, "
            f"observed {len(mixers)}"
        )

    config_flag_before = getattr(config, "use_mamba_kernels", "UNDECLARED")
    module_receipts: list[dict[str, Any]] = []
    for name, mixer in mixers:
        source = Path(inspect.getfile(type(mixer))).resolve()
        source_sha256 = sha256_file(source)
        if source_sha256 != expected_source_sha256:
            raise GateRefused(f"{phase} Mamba mixer source hash mismatch")

        reviewed_forward = getattr(mixer, "cuda_kernels_forward", None)
        if not callable(reviewed_forward):
            raise GateRefused(f"{phase} Mamba mixer lacks reviewed cuda_kernels_forward")
        forward_function = getattr(reviewed_forward, "__func__", reviewed_forward)
        module_globals = getattr(forward_function, "__globals__", {})
        fast_path_before = module_globals.get("is_fast_path_available", "UNDECLARED")
        if fast_path_before is not True:
            raise GateRefused(f"{phase} reviewed Mamba CUDA kernels are unavailable")

        out_proj = getattr(mixer, "out_proj", None)
        base_layer = getattr(out_proj, "base_layer", None)
        lora_a = getattr(out_proj, "lora_A", None)
        lora_b = getattr(out_proj, "lora_B", None)
        if base_layer is None or lora_a is None or lora_b is None:
            raise GateRefused(f"{phase} Mamba out_proj is not a PEFT LoRA wrapper")
        try:
            lora_a_names = sorted(str(key) for key in lora_a.keys())
            lora_b_names = sorted(str(key) for key in lora_b.keys())
        except (AttributeError, TypeError) as exc:
            raise GateRefused(f"{phase} Mamba out_proj LoRA adapters cannot be measured") from exc
        if not lora_a_names or lora_a_names != lora_b_names:
            raise GateRefused(f"{phase} Mamba out_proj LoRA adapter sets are incomplete")

        base_class = f"{type(base_layer).__module__}.{type(base_layer).__qualname__}"
        if type(base_layer).__name__ != "Linear4bit" or not type(base_layer).__module__.startswith(
            "bitsandbytes"
        ):
            raise GateRefused(f"{phase} Mamba out_proj base is not bitsandbytes Linear4bit")

        in_proj = getattr(mixer, "in_proj", None)
        in_proj_weight = getattr(in_proj, "weight", None)
        execution_device = getattr(getattr(in_proj_weight, "device", None), "type", None)
        if execution_device != "cuda":
            raise GateRefused(f"{phase} Mamba mixer is not resident on CUDA")

        mixer.forward = types.MethodType(_decomposed_mamba_cuda_forward, mixer)
        rebound = getattr(mixer, "forward", None)
        if getattr(rebound, "__func__", rebound) is not _decomposed_mamba_cuda_forward:
            raise GateRefused(f"{phase} Mamba decomposed CUDA binding did not hold")
        fast_path_after = module_globals.get("is_fast_path_available", "UNDECLARED")
        if fast_path_after != fast_path_before:
            raise GateRefused(f"{phase} Mamba global fast-path state changed")

        module_receipts.append(
            {
                "name": name,
                "class": f"{type(mixer).__module__}.{type(mixer).__qualname__}",
                "source": str(source),
                "source_sha256": source_sha256,
                "projection_wrapper_class": (
                    f"{type(out_proj).__module__}.{type(out_proj).__qualname__}"
                ),
                "projection_base_class": base_class,
                "lora_adapter_names": lora_a_names,
                "execution_device": execution_device,
                "dispatch_target": "HASH_VERIFIED_NVIDIA_CUDA_KERNELS_FORWARD",
                "combined_training_kernel_selected": False,
                "projection_module_forward_preserved": True,
                "module_global_fast_path_before": fast_path_before,
                "module_global_fast_path_after": fast_path_after,
            }
        )

    config.use_mamba_kernels = True
    if getattr(config, "use_mamba_kernels", None) is not True:
        raise GateRefused(f"{phase} Mamba kernel declaration could not be retained")
    return {
        "state": "BOUND_REVIEWED_DECOMPOSED_CUDA_FORWARD",
        "phase": phase,
        "reason": (
            "COMBINED_PATH_BYPASSES_LORA_AND_TORCH_PATH_MODELS_A_9_GIB_PAIRWISE_TENSOR"
        ),
        "scope": "PER_MIXER_INSTANCE_NO_PINNED_SOURCE_OR_MODULE_GLOBAL_MUTATION",
        "expected_mixer_count": expected_mixers,
        "bound_mixer_count": len(module_receipts),
        "config_use_mamba_kernels_before": config_flag_before,
        "config_use_mamba_kernels_after": True,
        "modules": module_receipts,
    }


def verify_linux_network_namespace() -> dict[str, Any]:
    """Require the WSL/Linux training process to have no non-loopback network."""

    if platform.system() != "Linux":
        raise GateRefused("Linux network namespace is required for SZL-Nemo training")
    try:
        interface_rows = socket.if_nameindex()
    except OSError as exc:
        raise GateRefused("network namespace interfaces cannot be measured") from exc
    if not interface_rows or not all(
        isinstance(index, int) and index > 0 and isinstance(name, str) and name
        for index, name in interface_rows
    ):
        raise GateRefused("network namespace interface evidence is invalid")
    interfaces = sorted({name for _index, name in interface_rows})
    non_loopback = [name for name in interfaces if name != "lo"]
    route_path = Path("/proc/net/route")
    try:
        routes = route_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GateRefused("network namespace routes cannot be measured") from exc
    route_lines = routes.splitlines()
    if route_lines:
        if "Iface" not in route_lines[0] or "Destination" not in route_lines[0]:
            raise GateRefused("network namespace route evidence is invalid")
        route_rows = [line.split() for line in route_lines[1:] if line.strip()]
    else:
        route_rows = []
    if any(len(row) < 2 for row in route_rows):
        raise GateRefused("network namespace route evidence is invalid")
    default_routes = [
        row for row in route_rows if row[1] == "00000000"
    ]
    if non_loopback or default_routes:
        raise GateRefused(
            "OS network namespace is not isolated; invoke training through "
            "unshare --user --map-root-user --net"
        )
    try:
        namespace_link = os.readlink("/proc/self/ns/net")
    except OSError as exc:
        raise GateRefused("network namespace identity cannot be measured") from exc
    return {
        "state": "OS_NETWORK_NAMESPACE_DENIED",
        "interfaces": interfaces,
        "default_route_count": len(default_routes),
        "interface_measurement_source": "socket.if_nameindex",
        "route_measurement_source": str(route_path),
        "namespace_link": namespace_link,
    }


class RuntimeGuard:
    def __init__(
        self,
        contract: dict[str, Any],
        maximum_temperature: int | None = None,
        maximum_seconds: int | None = None,
        thermal_scope: str = "training",
    ) -> None:
        self.maximum_seconds = (
            int(maximum_seconds)
            if maximum_seconds is not None
            else contract["training"]["maximum_wall_clock_seconds"]
        )
        self.maximum_temperature = (
            int(maximum_temperature)
            if maximum_temperature is not None
            else contract["gpu_admission"]["maximum_training_temperature_c"]
        )
        self.interval = contract["training"]["watchdog_interval_seconds"]
        if thermal_scope not in {"training", "evaluation"}:
            raise GateRefused("runtime guard thermal scope is invalid")
        self.thermal_scope = thermal_scope
        self.started_at_unix_ns = time.time_ns()
        self.started_monotonic_ns = time.monotonic_ns()
        self.finalized_at_unix_ns: int | None = None
        self.elapsed_monotonic_ms: int | None = None
        self.samples: list[dict[str, Any]] = []
        self.reason: str | None = None
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.thread_started = False
        self.thread = threading.Thread(target=self._watch, name="szl-nemo-runtime-guard", daemon=True)

    def _record(self, stage: str) -> None:
        sample = {**query_gpu(), "stage": stage}
        with self.lock:
            self.samples.append(sample)
            if sample["temperature_c"] > self.maximum_temperature:
                self.reason = f"{self.thermal_scope} thermal ceiling exceeded"

    def _watch(self) -> None:
        while not self.stop.wait(self.interval):
            try:
                self._record("watchdog")
                if self.reason:
                    return
            except Exception as exc:
                with self.lock:
                    self.reason = f"GPU watchdog failed: {type(exc).__name__}"
                return

    def __enter__(self) -> "RuntimeGuard":
        try:
            self._record("initial")
        except Exception as exc:
            self.reason = f"GPU watchdog failed: {type(exc).__name__}"
        self.check("initial")
        self.thread.start()
        self.thread_started = True
        return self

    def __exit__(self, exc_type: Any, *_args: Any) -> None:
        if exc_type is None:
            if self.finalized_at_unix_ns is None:
                self.finalize()
        else:
            self.finalize_failure()
        self.stop.set()
        if self.thread_started:
            self.thread.join(timeout=self.interval + 2)

    def finalize_failure(self) -> None:
        """Capture terminal guard evidence without masking the primary error."""

        self.stop.set()
        if self.thread_started:
            self.thread.join(timeout=self.interval + 2)
        if self.finalized_at_unix_ns is not None:
            return
        try:
            self._record("failure")
        except Exception as exc:
            if self.reason is None:
                self.reason = f"GPU watchdog failed: {type(exc).__name__}"
        self.finalized_at_unix_ns = time.time_ns()
        self.elapsed_monotonic_ms = (
            time.monotonic_ns() - self.started_monotonic_ns
        ) // 1_000_000

    def check(self, stage: str) -> None:
        if (time.monotonic_ns() - self.started_monotonic_ns) / 1_000_000_000 > self.maximum_seconds:
            self.reason = f"wall-clock ceiling exceeded at {stage}"
        if self.reason:
            raise GateRefused(self.reason)

    def finalize(self) -> None:
        if self.finalized_at_unix_ns is not None:
            self.check("finalized")
            return
        self.stop.set()
        if self.thread_started:
            self.thread.join(timeout=self.interval + 2)
        try:
            self._record("final")
        except Exception as exc:
            self.reason = f"GPU watchdog failed: {type(exc).__name__}"
        self.finalized_at_unix_ns = time.time_ns()
        self.elapsed_monotonic_ms = (
            time.monotonic_ns() - self.started_monotonic_ns
        ) // 1_000_000
        self.check("final")

    def receipt(self) -> dict[str, Any]:
        with self.lock:
            samples = [dict(sample) for sample in self.samples]
        state = "TRIPPED" if self.reason else (
            "PASS" if self.finalized_at_unix_ns is not None else "INCOMPLETE"
        )
        return {
            "schema_version": "szl.nemo.runtime-guard.v1",
            "state": state,
            "reason": self.reason,
            "thresholds": {
                "maximum_training_temperature_c": self.maximum_temperature,
                "maximum_wall_clock_seconds": self.maximum_seconds,
                "watchdog_interval_seconds": self.interval,
            },
            "thermal_scope": self.thermal_scope,
            "timing": {
                "started_at_unix_ns": self.started_at_unix_ns,
                "finalized_at_unix_ns": self.finalized_at_unix_ns,
                "elapsed_monotonic_ms": self.elapsed_monotonic_ms,
            },
            "samples": samples,
            "cooperative_interrupt_only": True,
        }


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


def preflight(
    snapshot: Path | None,
    check_gpu: bool = False,
    probe: bool = False,
    gpu_profile_key: str = "canonical_capacity",
    gpu_policy: dict[str, Any] | None = None,
    gpu_check_id: str | None = None,
) -> dict[str, Any]:
    contract = load_object(CONTRACT_PATH)
    declared_gpu_profiles = {
        "canonical_capacity": (contract["gpu_admission"], "GPU_ADMISSION"),
        "low_vram_calibration": (
            contract["low_vram_calibration"]["gpu_admission"],
            "GPU_LOW_VRAM_CALIBRATION_ATTEMPT_FLOOR",
        ),
        "activation_offload_calibration": (
            contract["activation_offload_calibration"]["gpu_admission"],
            "GPU_ACTIVATION_OFFLOAD_CALIBRATION_ATTEMPT_FLOOR",
        ),
    }
    selected = declared_gpu_profiles.get(gpu_profile_key)
    if selected is None:
        return _preflight_receipt(
            contract,
            "BLOCKED",
            [{"id": "REFUSAL", "state": "BLOCKED", "reason": "unknown GPU profile key"}],
        )
    declared_gpu_policy, declared_gpu_check_id = selected
    effective_gpu_policy = declared_gpu_policy if gpu_policy is None else gpu_policy
    effective_gpu_check_id = declared_gpu_check_id if gpu_check_id is None else gpu_check_id
    checks: list[dict[str, Any]] = []
    try:
        if effective_gpu_policy != declared_gpu_policy:
            raise GateRefused("GPU policy override is not the selected contract-declared profile")
        if effective_gpu_check_id != declared_gpu_check_id:
            raise GateRefused("GPU policy must retain its selected profile check identity")
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
            policy = effective_gpu_policy
            count = policy["probe_samples"] if probe else policy["training_soak_samples"]
            samples = sample_gpu(policy, count, policy["sample_interval_seconds"])
            checks.append({"id": effective_gpu_check_id, "state": "PASS", "policy": policy, "samples": samples})
        return _preflight_receipt(contract, "PASS", checks)
    except GPUAdmissionRefused as exc:
        checks.append({"id": effective_gpu_check_id, "state": "BLOCKED", "reason": str(exc), "policy": effective_gpu_policy, "samples": exc.samples})
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


def evaluate_mandatory_sets(
    tokenizer: Any,
    model: Any,
    original_rows: list[dict[str, Any]],
    shadow_rows: list[dict[str, Any]],
    contract: dict[str, Any],
    guard: "RuntimeGuard",
    adapter_files_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Run both preregistered sets and return one fail-closed gate receipt."""

    import torch

    settings = contract["training"]

    def evaluate_set(
        set_id: str,
        rows: list[dict[str, Any]],
        source_path: Path,
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for row in rows:
            guard.check(row["record_id"])
            prompt = tokenizer.apply_chat_template(
                row["messages"],
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
            inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
            with torch.inference_mode():
                generated = model.generate(
                    **inputs,
                    max_new_tokens=settings["maximum_eval_new_tokens"],
                    do_sample=False,
                    pad_token_id=tokenizer.pad_token_id,
                )
            text = tokenizer.decode(
                generated[0][inputs["input_ids"].shape[1]:],
                skip_special_tokens=True,
            ).strip()
            results.append(
                {"record_id": row["record_id"], **_evaluate_output(text, row["expected"])}
            )
        state = "PASS" if results and all(item["state"] == "PASS" for item in results) else "FAIL"
        return {
            "set_id": set_id,
            "state": state,
            "rows": len(results),
            "passes": sum(item["state"] == "PASS" for item in results),
            "source_sha256": sha256_file(source_path),
            "results": results,
        }

    original = evaluate_set("ORIGINAL_FROZEN", original_rows, EVAL_PATH)
    shadow = evaluate_set("SHADOW_PREREGISTERED", shadow_rows, SHADOW_EVAL_PATH)
    required_set_ids = contract["evaluation"]["mandatory_sets"]
    observed_sets = {original["set_id"]: original, shadow["set_id"]: shadow}
    state = "PASS" if (
        contract["evaluation"]["requires_both_sets_pass"]
        and set(required_set_ids) == set(observed_sets)
        and all(observed_sets[set_id]["state"] == "PASS" for set_id in required_set_ids)
    ) else "FAIL"
    receipt = {
        "schema_version": "szl.nemo.reload-evaluation-receipt.v2",
        "state": state,
        "gate": "ORIGINAL_AND_SHADOW_MUST_BOTH_PASS",
        "mandatory_sets": required_set_ids,
        "rows": original["rows"] + shadow["rows"],
        "passes": original["passes"] + shadow["passes"],
        "adapter_files_sha256": adapter_files_sha256,
        "base_revision": contract["base"]["revision"],
        "original": original,
        "shadow": shadow,
        "promotion": "NONE_AUTOMATIC",
    }
    return original, shadow, receipt


def _subsequence_offsets(sequence: list[int], subsequence: list[int]) -> list[int]:
    if not subsequence:
        return []
    width = len(subsequence)
    return [
        index
        for index in range(len(sequence) - width + 1)
        if sequence[index:index + width] == subsequence
    ]


def completion_only_training_setup(
    tokenizer: Any,
    texts: list[str],
    settings: dict[str, Any],
    collator_type: Any,
) -> tuple[Any, dict[str, Any]]:
    """Bind loss to the assistant completion and prove no completion truncation."""

    if settings.get("loss_scope") != "ASSISTANT_COMPLETION_ONLY":
        raise GateRefused("training loss scope is not assistant-completion-only")
    marker = settings.get("assistant_response_template")
    if not isinstance(marker, str) or not marker:
        raise GateRefused("assistant response template is absent")
    marker_tokens = tokenizer.encode(marker, add_special_tokens=False)
    if not marker_tokens:
        raise GateRefused("assistant response template tokenization is empty")
    max_length = int(settings["max_sequence_length"])
    full_counts: list[int] = []
    supervised_counts: list[int] = []
    masked_counts: list[int] = []
    features: list[dict[str, Any]] = []
    for text in texts:
        feature = tokenizer(text, add_special_tokens=False, truncation=False)
        token_ids = list(feature["input_ids"])
        if len(token_ids) > max_length:
            raise GateRefused("assistant completion would be truncated at the contract sequence length")
        offsets = _subsequence_offsets(token_ids, marker_tokens)
        if len(offsets) != 1:
            raise GateRefused("rendered training row does not contain exactly one assistant response marker")
        completion_start = offsets[0] + len(marker_tokens)
        supervised = len(token_ids) - completion_start
        if supervised <= 0:
            raise GateRefused("rendered training row has no assistant completion tokens")
        full_counts.append(len(token_ids))
        supervised_counts.append(supervised)
        masked_counts.append(completion_start)
        features.append(feature)
    collator = collator_type(
        response_template=marker_tokens,
        tokenizer=tokenizer,
        mlm=False,
    )
    probe = collator(features)
    observed_supervised = []
    for labels in probe["labels"]:
        values = labels.tolist() if hasattr(labels, "tolist") else list(labels)
        observed_supervised.append(sum(value != -100 for value in values))
    if observed_supervised != supervised_counts:
        raise GateRefused("completion-only collator supervision does not match the preregistered boundary")
    evidence = {
        "schema_version": "szl.nemo.training-format.v1",
        "state": "PASS_ASSISTANT_COMPLETION_ONLY",
        "loss_scope": settings["loss_scope"],
        "assistant_response_template_sha256": sha256_bytes(marker.encode("utf-8")),
        "assistant_response_template_token_ids": marker_tokens,
        "rows": len(texts),
        "full_tokens": {"minimum": min(full_counts), "maximum": max(full_counts)},
        "masked_prompt_tokens": {"minimum": min(masked_counts), "maximum": max(masked_counts)},
        "supervised_completion_tokens": {"minimum": min(supervised_counts), "maximum": max(supervised_counts)},
        "truncated_rows": 0,
        "collator_probe_rows": len(observed_supervised),
    }
    return collator, evidence


def _sign_summary(
    summary: dict[str, Any],
    contract: dict[str, Any],
    expected_identity: dict[str, str],
) -> dict[str, Any]:
    szl_dsse, observed_identity = _load_pinned_dsse(contract)
    if observed_identity != expected_identity:
        raise GateRefused("DSSE verifier identity changed before candidate signing")
    envelope = szl_dsse.sign_payload(summary, payload_type=PAYLOAD_TYPE)
    verdict = szl_dsse.verify_envelope(envelope)
    if (
        verdict.get("keyid_expected") != expected_identity["key_id"]
        or verdict.get("pub_fingerprint_sha256")
        != expected_identity["public_key_fingerprint_sha256"]
    ):
        raise GateRefused("candidate DSSE verification used an unexpected key")
    return {"envelope": envelope, "verification": verdict, "promotion_eligible_signature": bool(envelope.get("signed") and verdict.get("verified"))}


def capacity_probe(
    snapshot: Path,
    receipt_path: Path,
    confirmation: str,
    license_acknowledgement: str,
    module_cache_receipt: dict[str, Any] | None = None,
    probe_kind: str = "canonical_capacity",
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
    if probe_kind not in {
        "canonical_capacity",
        "low_vram_calibration",
        "activation_offload_calibration",
    }:
        raise GateRefused("unknown capacity probe kind")
    calibration = probe_kind != "canonical_capacity"
    activation_offload = probe_kind == "activation_offload_calibration"
    calibration_profile = contract.get(probe_kind) if calibration else None
    host_ram_policy = (
        calibration_profile.get("host_ram_admission")
        if activation_offload and calibration_profile is not None
        else None
    )
    if activation_offload and not isinstance(host_ram_policy, dict):
        raise GateRefused("activation-offload host-RAM policy is absent")
    expected_confirmation = (
        calibration_profile["confirmation_phrase"]
        if calibration_profile is not None
        else settings["confirmation_phrase"]
    )
    if confirmation != expected_confirmation:
        qualifier = (
            "activation-offload calibration"
            if activation_offload
            else "low-VRAM calibration"
            if calibration
            else "capacity-probe"
        )
        raise GateRefused(f"exact {qualifier} confirmation is required")
    if license_acknowledgement != contract["base"]["license_acknowledgement"]:
        raise GateRefused("exact NVIDIA license acknowledgement is required")
    schema_version = (
        calibration_profile["receipt_schema_version"]
        if calibration_profile is not None
        else settings["capacity_probe_receipt_schema_version"]
    )
    state_prefix = "ACTIVATION_OFFLOAD_" if activation_offload else ""
    running_state = (
        f"RUNNING_{state_prefix}CALIBRATION_NOT_TRAINED_NOT_QUALIFIED_NOT_PROMOTED"
        if calibration
        else "RUNNING_NOT_TRAINED_NOT_PROMOTED"
    )
    blocked_state = (
        f"BLOCKED_{state_prefix}CALIBRATION_NOT_TRAINED_NOT_QUALIFIED_NOT_PROMOTED"
        if calibration
        else "BLOCKED_NOT_TRAINED_NOT_PROMOTED"
    )
    pass_state = (
        f"PASS_{state_prefix}CALIBRATION_ONLY_NOT_TRAINED_NOT_QUALIFIED_NOT_PROMOTED"
        if calibration
        else "PASS_CAPACITY_ONLY_NOT_TRAINED_NOT_PROMOTED"
    )
    failed_state = (
        f"FAILED_{state_prefix}CALIBRATION_NOT_TRAINED_NOT_QUALIFIED_NOT_PROMOTED"
        if calibration
        else "FAILED_NOT_TRAINED_NOT_PROMOTED"
    )
    profile_id = (
        calibration_profile["profile_id"]
        if calibration_profile is not None
        else settings["capacity_profile_id"]
    )
    optimizer_name = (
        calibration_profile["optimizer"]
        if calibration_profile is not None
        else settings["optimizer"]
    )
    if optimizer_name != "paged_adamw_8bit" or optimizer_name != settings["optimizer"]:
        raise GateRefused("capacity optimizer profile does not match the training contract")

    receipt: dict[str, Any] = {
        "schema_version": schema_version,
        "contract_id": contract["contract_id"],
        "profile_id": profile_id,
        "state": running_state,
        "started_at_unix_ns": time.time_ns(),
        "contract_sha256": sha256_file(CONTRACT_PATH),
        "runner_sha256": sha256_file(Path(__file__)),
        "base_revision": contract["base"]["revision"],
        "dynamic_module_cache": module_cache_receipt,
        "training_started": False,
        "activation_offload": {
            "enabled": activation_offload,
            "mechanism": (
                calibration_profile.get("mechanism")
                if activation_offload and calibration_profile is not None
                else None
            ),
            "pin_memory": (
                calibration_profile.get("pin_memory")
                if activation_offload and calibration_profile is not None
                else None
            ),
            "saved_tensor_transfer_bytes": {
                "state": "UNKNOWN_NO_STABLE_PUBLIC_COUNTER"
            },
            "claim_scope": (
                "API_ACTIVE_PLUS_EMPIRICAL_PEAK_ONLY" if activation_offload else None
            ),
            "parameter_offload": False,
            "optimizer_offload": False,
            "training_admission_effect": "NONE" if activation_offload else None,
        },
        "adoption_assessment": {
            "state": "NOT_EVALUATED",
            "reason": "CALIBRATION_NOT_COMPLETED",
            "training_authority": False,
            "queue_progression_allowed": False,
            "canonical_gpu_threshold_changed": False,
        },
        "effects": {
            "training_run_started": False,
            "capacity_optimization_step_started": False,
            "capacity_optimization_step_completed": False,
            "adapter_written": False,
            "uploaded": False,
            "published": False,
            "deployed": False,
            "promoted": False,
            "training_authorized": False,
            "queue_progression_allowed": not calibration,
            "canonical_capacity_satisfied": False,
            "canonical_threshold_changed": False,
        },
    }
    create_json_once(receipt_path, receipt)

    guard: RuntimeGuard | None = None
    torch_module: Any = None
    optimizer: Any = None
    model: Any = None
    tokenizer: Any = None
    encoded: dict[str, Any] | None = None
    output: Any = None
    trainable: list[Any] | None = None
    micro_step_memory: list[dict[str, Any]] = []
    host_memory_samples: list[dict[str, Any]] = []
    physical_gpu_phase_samples: list[dict[str, Any]] = []

    try:
        source_control = git_identity(contract)
        admission = preflight(
            snapshot,
            check_gpu=True,
            probe=True,
            gpu_profile_key=probe_kind,
        )
        receipt["preflight"] = admission
        if admission["state"] != "PASS":
            receipt.update({"state": blocked_state, "completed_at_unix_ns": time.time_ns()})
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

        guard = RuntimeGuard(
            contract,
            maximum_temperature=(
                calibration_profile["gpu_admission"]["maximum_temperature_c"]
                if calibration_profile is not None
                else None
            ),
            maximum_seconds=(
                calibration_profile["maximum_wall_clock_seconds"]
                if calibration_profile is not None
                else None
            ),
        )
        with offline_framework_environment() as offline_flags, deny_python_network() as network_control, guard:
            import torch
            from bitsandbytes.optim import PagedAdamW8bit
            from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

            torch_module = torch
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
            if activation_offload:
                append_governed_host_memory_sample(
                    host_memory_samples, "before_model_load", host_ram_policy
                )
                physical_gpu_phase_samples.append(
                    physical_gpu_phase_sample("before_model_load")
                )
            guard.check("capacity-before-model-load")
            load_started = time.monotonic_ns()
            tokenizer = AutoTokenizer.from_pretrained(
                str(snapshot), local_files_only=True, trust_remote_code=True
            )
            receipt["padding_token_admission"] = admit_padding_token(
                tokenizer, contract, "capacity"
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
            receipt["model_padding_binding"] = verify_model_padding_binding(
                model, receipt["padding_token_admission"], "capacity"
            )
            if activation_offload:
                torch.cuda.synchronize()
                append_governed_host_memory_sample(
                    host_memory_samples, "after_model_load", host_ram_policy
                )
                physical_gpu_phase_samples.append(
                    physical_gpu_phase_sample("after_model_load")
                )
            model.config.use_cache = False
            model = prepare_model_for_kbit_training(
                model,
                use_gradient_checkpointing=True,
                gradient_checkpointing_kwargs={"use_reentrant": False},
            )
            receipt["gradient_checkpointing"] = gradient_checkpointing_evidence(
                model, "capacity"
            )
            lora = LoraConfig(
                r=settings["lora_rank"],
                lora_alpha=settings["lora_alpha"],
                lora_dropout=settings["lora_dropout"],
                bias="none",
                task_type="CAUSAL_LM",
                target_modules=settings["target_modules"],
            )
            model = get_peft_model(model, lora)
            receipt["mamba_forward_compatibility"] = bind_quantized_mamba_lora_forward(
                model, contract, "capacity"
            )
            trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
            if not trainable:
                raise GateRefused("capacity probe produced no trainable adapter parameters")

            row = capacity_row
            text = tokenizer.apply_chat_template(
                row["messages"], tokenize=False, add_generation_prompt=False
            )
            sequence_length = int(
                calibration_profile["sequence_length"]
                if calibration_profile is not None
                else settings["capacity_probe_sequence_length"]
            )
            encoded = tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=sequence_length,
                padding="max_length",
            )
            input_shape = [int(value) for value in encoded["input_ids"].shape]
            if input_shape != [1, sequence_length]:
                raise GateRefused("capacity probe did not produce the exact single-row shape")
            receipt["execution_shape"] = {
                "state": "MEASURED_FROM_TOKENIZER_OUTPUT",
                "input_ids_shape": input_shape,
                "batch_size": input_shape[0],
                "sequence_length": input_shape[1],
                "packing": False,
                "packing_policy": "SINGLE_PADDED_ROW_NO_PACKING",
                "gradient_accumulation_changes_per_micro_step_shape": False,
            }
            receipt["memory_model"] = {
                "naive_torch_forward_pairwise_intermediate": (
                    mamba_naive_pairwise_memory_model(
                        model.config, input_shape[0], input_shape[1]
                    )
                ),
                "selected_path": "NVIDIA_DECOMPOSED_CUDA_SCAN_WITH_MODULE_PROJECTION",
                "selected_path_materializes_naive_pairwise_intermediate": False,
            }
            device = next(parameter.device for parameter in model.parameters() if parameter.device.type == "cuda")
            encoded = {key: value.to(device) for key, value in encoded.items()}
            labels = encoded["input_ids"].clone()
            if "attention_mask" in encoded:
                labels = labels.masked_fill(encoded["attention_mask"] == 0, -100)
            model.train()
            optimizer = PagedAdamW8bit(trainable, lr=float(settings["learning_rate"]))
            receipt["optimizer_state_before_forward"] = optimizer_state_inventory(optimizer)
            if receipt["optimizer_state_before_forward"]["tensor_bytes"] != 0:
                raise GateRefused("optimizer allocated tensor state before the first backward")
            optimizer.zero_grad(set_to_none=True)
            if activation_offload:
                append_governed_host_memory_sample(
                    host_memory_samples, "before_forward", host_ram_policy
                )
                physical_gpu_phase_samples.append(
                    physical_gpu_phase_sample("before_forward")
                )
            guard.check("capacity-before-forward")
            receipt["effects"]["capacity_optimization_step_started"] = True
            receipt["activation_offload"]["context_entered"] = False
            receipt["activation_offload"]["context_exited"] = False
            receipt["activation_offload"]["backward_completed_inside_context"] = False
            atomic_json(receipt_path, receipt)
            step_started = time.monotonic_ns()
            accumulation = int(
                calibration_profile["gradient_accumulation_micro_steps"]
                if calibration_profile is not None
                else settings["gradient_accumulation_steps"]
            )
            losses: list[float] = []
            micro_step_memory = []
            for micro_step in range(accumulation):
                guard.check(f"capacity-micro-step-{micro_step}")
                if activation_offload:
                    graph = getattr(torch.autograd, "graph", None)
                    save_on_cpu = getattr(graph, "save_on_cpu", None)
                    if not callable(save_on_cpu):
                        raise GateRefused("pinned torch runtime lacks save_on_cpu")
                    if calibration_profile.get("pin_memory") is not False:
                        raise GateRefused("activation-offload profile must keep pin_memory false")
                    offload_context = save_on_cpu(pin_memory=False, device_type="cuda")
                else:
                    offload_context = nullcontext()
                with offload_context:
                    if activation_offload:
                        receipt["activation_offload"]["context_entered"] = True
                    output = model(**encoded, labels=labels)
                    loss = float(output.loss.detach().cpu())
                    if not math.isfinite(loss):
                        raise GateRefused("capacity probe loss is not finite")
                    losses.append(loss)
                    torch.cuda.synchronize()
                    receipt["forward_evidence"] = {
                        "state": "PASS",
                        "completed": True,
                        "loss_is_finite": True,
                        "cuda_allocated_bytes": int(torch.cuda.memory_allocated()),
                        "cuda_reserved_bytes": int(torch.cuda.memory_reserved()),
                        "optimizer_state_before_backward": optimizer_state_inventory(
                            optimizer
                        ),
                    }
                    if receipt["forward_evidence"]["optimizer_state_before_backward"][
                        "tensor_bytes"
                    ] != 0:
                        raise GateRefused("optimizer allocated tensor state before backward")
                    atomic_json(receipt_path, receipt)
                    backward_hook = None
                    if activation_offload:
                        def sample_during_backward(gradient: Any) -> Any:
                            append_governed_host_memory_sample(
                                host_memory_samples,
                                f"during_backward_{micro_step + 1}",
                                host_ram_policy,
                            )
                            return gradient

                        backward_hook = output.loss.register_hook(sample_during_backward)
                    try:
                        (output.loss / accumulation).backward()
                    finally:
                        if backward_hook is not None:
                            backward_hook.remove()
                    if activation_offload:
                        receipt["activation_offload"][
                            "backward_completed_inside_context"
                        ] = True
                if activation_offload:
                    receipt["activation_offload"]["context_exited"] = True
                    torch.cuda.synchronize()
                    append_governed_host_memory_sample(
                        host_memory_samples,
                        f"after_backward_{micro_step + 1}",
                        host_ram_policy,
                    )
                    physical_gpu_phase_samples.append(
                        physical_gpu_phase_sample(f"after_backward_{micro_step + 1}")
                    )
                micro_step_memory.append(
                    {
                        "micro_step": micro_step + 1,
                        "allocated_bytes": int(torch.cuda.memory_allocated()),
                        "reserved_bytes": int(torch.cuda.memory_reserved()),
                    }
                )
                del output
            trainable_gradient_tensors = 0
            finite_gradient_tensors = 0
            frozen_parameters_with_gradients = 0
            gradient_l2_squared = 0.0
            for parameter in model.parameters():
                if parameter.requires_grad:
                    if parameter.grad is None:
                        continue
                    trainable_gradient_tensors += 1
                    if bool(torch.isfinite(parameter.grad).all().item()):
                        finite_gradient_tensors += 1
                    gradient_l2_squared += float(
                        parameter.grad.detach().float().pow(2).sum().cpu()
                    )
                elif parameter.grad is not None:
                    frozen_parameters_with_gradients += 1
            gradient_receipt = {
                "trainable_gradient_tensors": trainable_gradient_tensors,
                "finite_gradient_tensors": finite_gradient_tensors,
                "all_trainable_gradients_finite": (
                    trainable_gradient_tensors > 0
                    and finite_gradient_tensors == trainable_gradient_tensors
                ),
                "frozen_parameters_with_gradients": frozen_parameters_with_gradients,
                "l2_norm": math.sqrt(gradient_l2_squared),
            }
            if not gradient_receipt["all_trainable_gradients_finite"]:
                raise GateRefused("capacity probe adapter gradients are absent or non-finite")
            if frozen_parameters_with_gradients:
                raise GateRefused("capacity probe produced gradients on frozen parameters")
            optimizer.step()
            torch.cuda.synchronize()
            if activation_offload:
                append_governed_host_memory_sample(
                    host_memory_samples, "after_optimizer", host_ram_policy
                )
                physical_gpu_phase_samples.append(
                    physical_gpu_phase_sample("after_optimizer")
                )
                receipt["activation_offload"]["host_ram_admission"] = (
                    evaluate_host_ram_admission(host_memory_samples, host_ram_policy)
                )
            if activation_offload and not all(
                receipt["activation_offload"].get(field) is True
                for field in (
                    "context_entered",
                    "context_exited",
                    "backward_completed_inside_context",
                )
            ):
                raise GateRefused("activation-offload context evidence is incomplete")
            guard.check("capacity-after-optimizer-step")
            receipt["effects"]["capacity_optimization_step_completed"] = True
            receipt["effects"]["canonical_capacity_satisfied"] = not calibration
            if activation_offload:
                receipt["adoption_assessment"] = evaluate_activation_offload_adoption(
                    physical_gpu_phase_samples,
                    calibration_profile["adoption_requirements"],
                    int(encoded["input_ids"].shape[-1]),
                    all(math.isfinite(loss) for loss in losses),
                    bool(gradient_receipt["all_trainable_gradients_finite"]),
                )
            step_duration_ms = (time.monotonic_ns() - step_started) // 1_000_000
            guard.finalize()
            runtime_guard = guard.receipt()

            receipt.update(
                {
                    "state": pass_state,
                    "completed_at_unix_ns": time.time_ns(),
                    "probe": {
                        "record_id": row.get("record_id"),
                        "sequence_tokens": int(encoded["input_ids"].shape[-1]),
                        "sequence_limit": sequence_length,
                        "loss": sum(losses) / len(losses),
                        "step_duration_ms": step_duration_ms,
                        "trainable_parameters": sum(parameter.numel() for parameter in trainable),
                        "peak_vram_allocated_bytes": int(torch.cuda.max_memory_allocated()),
                        "peak_vram_reserved_bytes": int(torch.cuda.max_memory_reserved()),
                        "compute_dtype": str(compute_dtype),
                        "profile_id": profile_id,
                        "optimizer": optimizer_name,
                        "optimizer_class": type(optimizer).__name__,
                        "gradient_accumulation_micro_steps": accumulation,
                        "micro_step_memory": micro_step_memory,
                        "device_map": {"": 0},
                        "activation_offload": {"enabled": activation_offload},
                        "host_memory_samples": host_memory_samples,
                        "physical_gpu_phase_samples": physical_gpu_phase_samples,
                        "gradient_receipt": gradient_receipt,
                    },
                    "runtime_guard": runtime_guard,
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
            return 0
    except Exception as exc:
        failure_evidence: dict[str, Any] = {
            "completed_micro_steps": len(micro_step_memory),
            "micro_step_memory": micro_step_memory,
            "host_memory_samples": host_memory_samples,
            "physical_gpu_phase_samples": physical_gpu_phase_samples,
            "activation_offload": receipt.get("activation_offload"),
            "adoption_assessment": receipt.get("adoption_assessment"),
        }
        if guard is not None:
            try:
                guard.finalize_failure()
            except Exception as evidence_exc:
                failure_evidence["runtime_guard_finalize_error"] = type(evidence_exc).__name__
            runtime_guard_receipt = guard.receipt()
            failure_evidence["runtime_guard"] = runtime_guard_receipt
            receipt["runtime_guard"] = runtime_guard_receipt
        if torch_module is not None:
            try:
                failure_evidence.update(
                    {
                        "cuda_allocated_bytes": int(torch_module.cuda.memory_allocated()),
                        "cuda_reserved_bytes": int(torch_module.cuda.memory_reserved()),
                        "peak_vram_allocated_bytes": int(torch_module.cuda.max_memory_allocated()),
                        "peak_vram_reserved_bytes": int(torch_module.cuda.max_memory_reserved()),
                    }
                )
            except Exception as evidence_exc:
                failure_evidence["cuda_evidence_error"] = type(evidence_exc).__name__
        try:
            failure_evidence["terminal_gpu_sample"] = query_gpu()
        except Exception as evidence_exc:
            failure_evidence["terminal_gpu_sample_error"] = type(evidence_exc).__name__
        receipt.update(
            {
                "state": failed_state,
                "completed_at_unix_ns": time.time_ns(),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback_sha256": sha256_bytes(traceback.format_exc().encode("utf-8")),
                "failure_evidence": failure_evidence,
            }
        )
        atomic_json(receipt_path, receipt)
        raise
    finally:
        output = None
        optimizer = None
        encoded = None
        trainable = None
        model = None
        tokenizer = None
        gc.collect()
        if torch_module is not None:
            try:
                torch_module.cuda.empty_cache()
            except Exception:
                pass


def low_vram_calibration(
    snapshot: Path,
    receipt_path: Path,
    confirmation: str,
    license_acknowledgement: str,
    module_cache_receipt: dict[str, Any] | None = None,
) -> int:
    """Measure a bounded non-qualifying QLoRA step below the training gate.

    A pass is evidence for operator review only.  It cannot satisfy the queue's
    canonical capacity schema, authorize training, write an adapter, or mutate
    the fixed production admission thresholds.
    """

    return capacity_probe(
        snapshot,
        receipt_path,
        confirmation,
        license_acknowledgement,
        module_cache_receipt,
        probe_kind="low_vram_calibration",
    )


def activation_offload_calibration(
    snapshot: Path,
    receipt_path: Path,
    confirmation: str,
    license_acknowledgement: str,
    module_cache_receipt: dict[str, Any] | None = None,
) -> int:
    """Measure exact-shape saved-tensor CPU offload without training authority.

    This profile keeps the canonical 768-token shape and paged optimizer but
    is intentionally excluded from the queue.  A pass is evidence for a later
    profile-adoption review; it does not lower the canonical admission floor.
    """

    return capacity_probe(
        snapshot,
        receipt_path,
        confirmation,
        license_acknowledgement,
        module_cache_receipt,
        probe_kind="activation_offload_calibration",
    )


def admit_evaluation_resume(
    snapshot: Path,
    training_output: Path,
    contract: dict[str, Any],
) -> dict[str, Any]:
    """Bind a saved adapter to its completed thermal-failed training attempt."""

    receipts = training_output / "receipts"
    training_receipt_path = receipts / "training-receipt.json"
    adapter_receipt_path = receipts / "adapter-files.json"
    adapter = training_output / "adapter"
    if not training_receipt_path.is_file() or not adapter_receipt_path.is_file():
        raise GateRefused("evaluation resume requires training and adapter receipts")
    if not adapter.is_dir():
        raise GateRefused("evaluation resume requires the saved adapter directory")

    training_receipt = load_object(training_receipt_path)
    adapter_receipt = load_object(adapter_receipt_path)
    if training_receipt.get("schema_version") != "szl.nemo.training-receipt.v2":
        raise GateRefused("evaluation resume requires a v2 training receipt")
    if training_receipt.get("contract_id") != contract["contract_id"]:
        raise GateRefused("training receipt contract identity mismatch")
    if training_receipt.get("state") != "FAILED_NOT_PROMOTED":
        raise GateRefused("evaluation resume is limited to a failed unpromoted attempt")
    if (
        training_receipt.get("error_type") != "GateRefused"
        or training_receipt.get("error") != "training thermal ceiling exceeded"
    ):
        raise GateRefused("evaluation resume requires the post-training thermal refusal")
    if training_receipt.get("global_steps") != contract["training"]["max_steps"]:
        raise GateRefused("evaluation resume requires every preregistered training step")
    if not isinstance(training_receipt.get("training_completed_at_unix_ns"), int):
        raise GateRefused("evaluation resume lacks completed-training evidence")
    if training_receipt.get("contract_sha256") != sha256_file(CONTRACT_PATH):
        raise GateRefused("training receipt contract hash mismatch")
    if training_receipt.get("curriculum_manifest_sha256") != sha256_file(MANIFEST_PATH):
        raise GateRefused("training receipt curriculum manifest hash mismatch")
    origin_source = training_receipt.get("source_control")
    if not isinstance(origin_source, dict) or origin_source.get("state") != "CLEAN_REVIEWED_COMMIT":
        raise GateRefused("training receipt lacks clean source-control evidence")
    origin_commit = origin_source.get("commit")
    origin_runner_sha256 = training_receipt.get("runner_sha256")
    if (
        not isinstance(origin_commit, str)
        or len(origin_commit) != 40
        or any(character not in "0123456789abcdef" for character in origin_commit)
        or not isinstance(origin_runner_sha256, str)
        or len(origin_runner_sha256) != 64
        or any(character not in "0123456789abcdef" for character in origin_runner_sha256)
    ):
        raise GateRefused("training receipt origin identity is malformed")

    if adapter_receipt.get("schema_version") != "szl.nemo.adapter-files.v1":
        raise GateRefused("adapter inventory receipt schema mismatch")
    adapter_receipt_sha256 = sha256_file(adapter_receipt_path)
    if training_receipt.get("adapter_files_sha256") != adapter_receipt_sha256:
        raise GateRefused("training receipt does not bind the adapter inventory")
    expected_inventory = adapter_receipt.get("files")
    observed_inventory = _inventory(adapter)
    if not isinstance(expected_inventory, list) or expected_inventory != observed_inventory:
        raise GateRefused("saved adapter inventory changed after training")
    paths = {item.get("path") for item in observed_inventory if isinstance(item, dict)}
    if "adapter_model.safetensors" not in paths or any(
        isinstance(path, str) and path.endswith(".bin") for path in paths
    ):
        raise GateRefused("saved adapter is not a safetensors-only package")

    base_files = verify_base(snapshot)
    if training_receipt.get("base_files_before") != base_files:
        raise GateRefused("base snapshot differs from the completed training attempt")
    validate_curriculum()
    curriculum_inputs = curriculum_input_identity()
    if training_receipt.get("curriculum_inputs_before") != curriculum_inputs:
        raise GateRefused("holdout or curriculum inputs differ from the training attempt")
    if sha256_file(EVAL_PATH) != contract["curriculum"]["frozen_original_eval_sha256"]:
        raise GateRefused("frozen original evaluation hash mismatch")
    manifest = load_object(MANIFEST_PATH)
    if manifest.get("shadow_eval", {}).get("sha256") != sha256_file(SHADOW_EVAL_PATH):
        raise GateRefused("preregistered shadow evaluation hash mismatch")

    return {
        "training_receipt": training_receipt,
        "training_receipt_path": training_receipt_path,
        "training_receipt_sha256": sha256_file(training_receipt_path),
        "adapter_receipt_path": adapter_receipt_path,
        "adapter_receipt_sha256": adapter_receipt_sha256,
        "adapter": adapter,
        "adapter_inventory": observed_inventory,
        "base_files": base_files,
        "curriculum_inputs": curriculum_inputs,
        "origin_commit": origin_commit,
        "origin_runner_sha256": origin_runner_sha256,
    }


def evaluate_saved_adapter(
    snapshot: Path,
    training_output: Path,
    receipt_path: Path,
    confirmation: str,
    license_acknowledgement: str,
    module_cache_receipt: dict[str, Any] | None = None,
) -> int:
    """Evaluate one immutable saved adapter without reopening training."""

    contract = load_object(CONTRACT_PATH)
    if confirmation != EVALUATION_CONFIRMATION:
        raise GateRefused("exact evaluation-only confirmation is required")
    if license_acknowledgement != contract["base"]["license_acknowledgement"]:
        raise GateRefused("exact NVIDIA license acknowledgement is required")
    if receipt_path.exists():
        raise GateRefused("evaluation receipt path already exists; evidence is append-only")

    origin = admit_evaluation_resume(snapshot, training_output, contract)
    source_control = git_identity(contract)
    eval_rows = list(iter_jsonl(EVAL_PATH))
    shadow_rows = list(iter_jsonl(SHADOW_EVAL_PATH))
    initial = {
        "schema_version": "szl.nemo.evaluation-resume-receipt.v1",
        "contract_id": contract["contract_id"],
        "state": "RUNNING_EVALUATION_ONLY_NOT_PROMOTED_NOT_SIGNED",
        "started_at_unix_ns": time.time_ns(),
        "contract_sha256": sha256_file(CONTRACT_PATH),
        "evaluator_runner_sha256": sha256_file(Path(__file__)),
        "source_control": source_control,
        "originating_training": {
            "receipt_sha256": origin["training_receipt_sha256"],
            "state": origin["training_receipt"]["state"],
            "commit": origin["origin_commit"],
            "runner_sha256": origin["origin_runner_sha256"],
            "global_steps": origin["training_receipt"]["global_steps"],
            "training_loss": origin["training_receipt"]["training_loss"],
            "training_completed_at_unix_ns": origin["training_receipt"]["training_completed_at_unix_ns"],
        },
        "adapter_files_receipt_sha256": origin["adapter_receipt_sha256"],
        "base_revision": contract["base"]["revision"],
        "base_files": origin["base_files"],
        "frozen_original_eval_sha256": sha256_file(EVAL_PATH),
        "preregistered_shadow_eval_sha256": sha256_file(SHADOW_EVAL_PATH),
        "mandatory_sets": contract["evaluation"]["mandatory_sets"],
        "dynamic_module_cache": module_cache_receipt,
        "training_started": False,
        "adapter_written": False,
        "uploaded": False,
        "published": False,
        "deployed": False,
        "signed": False,
        "promotion": "NOT_PROMOTED",
    }
    create_json_once(receipt_path, initial)
    receipt = dict(initial)
    guard: RuntimeGuard | None = None
    try:
        admission = preflight(snapshot, check_gpu=True)
        receipt["gpu_admission"] = admission
        atomic_json(receipt_path, receipt)
        if admission["state"] != "PASS":
            receipt.update({"state": "GPU_ADMISSION_REFUSED_NOT_EVALUATED_NOT_PROMOTED", "completed_at_unix_ns": time.time_ns()})
            atomic_json(receipt_path, receipt)
            return 3
        os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1", "WANDB_DISABLED": "true", "TOKENIZERS_PARALLELISM": "false", "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1", "NO_PROXY": "*"})
        receipt["os_network_namespace"] = verify_linux_network_namespace()
        with deny_python_network() as network_control, RuntimeGuard(
            contract, thermal_scope="evaluation"
        ) as guard:
            receipt["network_control"] = network_control
            import torch
            from peft import PeftModel
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

            if not torch.cuda.is_available():
                raise GateRefused("CUDA is unavailable after evaluation admission")
            receipt["runtime_identity"] = verify_runtime(torch)
            bf16 = bool(torch.cuda.is_bf16_supported())
            quant = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.bfloat16 if bf16 else torch.float16,
            )
            guard.check("before-evaluation-model-load")
            tokenizer = AutoTokenizer.from_pretrained(
                str(snapshot), local_files_only=True, trust_remote_code=True
            )
            receipt["padding_token_admission"] = admit_padding_token(
                tokenizer, contract, "evaluation-resume"
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
            receipt["reloaded_model_class"] = verify_loaded_model_source(
                model, contract, "evaluation-resume"
            )
            receipt["reload_padding_binding"] = verify_model_padding_binding(
                model, receipt["padding_token_admission"], "evaluation-resume"
            )
            model = PeftModel.from_pretrained(
                model,
                str(origin["adapter"]),
                is_trainable=False,
                local_files_only=True,
            )
            model.eval()
            original, shadow, evaluation = evaluate_mandatory_sets(
                tokenizer,
                model,
                eval_rows,
                shadow_rows,
                contract,
                guard,
                origin["adapter_receipt_sha256"],
            )
            guard.finalize()
            runtime_guard = guard.receipt()

        if verify_base(snapshot) != origin["base_files"]:
            raise GateRefused("base snapshot changed during evaluation")
        validate_curriculum()
        if curriculum_input_identity() != origin["curriculum_inputs"]:
            raise GateRefused("holdout or curriculum inputs changed during evaluation")
        if sha256_file(origin["training_receipt_path"]) != origin["training_receipt_sha256"]:
            raise GateRefused("originating training receipt changed during evaluation")
        if sha256_file(origin["adapter_receipt_path"]) != origin["adapter_receipt_sha256"]:
            raise GateRefused("adapter inventory receipt changed during evaluation")
        if _inventory(origin["adapter"]) != origin["adapter_inventory"]:
            raise GateRefused("saved adapter changed during evaluation")
        source_control_after = git_identity(contract)
        if source_control_after != source_control:
            raise GateRefused("evaluation source identity changed during evaluation")

        receipt.update(
            {
                "state": "QUALIFICATION_PASS_NOT_PROMOTED_NOT_SIGNED" if evaluation["state"] == "PASS" else "EVALUATION_FAILED_NOT_PROMOTED_NOT_SIGNED",
                "completed_at_unix_ns": time.time_ns(),
                "evaluation": evaluation,
                "original": original,
                "shadow": shadow,
                "runtime_guard": runtime_guard,
                "source_control_after": source_control_after,
                "training_started": False,
                "adapter_written": False,
                "uploaded": False,
                "published": False,
                "deployed": False,
                "signed": False,
                "promotion": "NOT_PROMOTED",
            }
        )
        atomic_json(receipt_path, receipt)
        return 0 if evaluation["state"] == "PASS" else 4
    except Exception as exc:
        if guard is not None:
            guard.finalize_failure()
            receipt["runtime_guard"] = guard.receipt()
        receipt.update(
            {
                "state": "FAILED_EVALUATION_ONLY_NOT_PROMOTED_NOT_SIGNED",
                "completed_at_unix_ns": time.time_ns(),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback_sha256": sha256_bytes(traceback.format_exc().encode("utf-8")),
                "training_started": False,
                "adapter_written": False,
                "uploaded": False,
                "published": False,
                "deployed": False,
                "signed": False,
                "promotion": "NOT_PROMOTED",
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
    _, dsse_verifier = _load_pinned_dsse(contract)
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
    shadow_eval_rows = list(iter_jsonl(SHADOW_EVAL_PATH))
    if curriculum_input_identity() != curriculum_before:
        raise GateRefused("curriculum inputs changed while rows were admitted")
    os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1", "WANDB_DISABLED": "true", "TOKENIZERS_PARALLELISM": "false", "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1", "NO_PROXY": "*"})
    network_namespace = verify_linux_network_namespace()
    receipt: dict[str, Any] = {"schema_version": "szl.nemo.training-receipt.v2", "contract_id": contract["contract_id"], "state": "RUNNING_NOT_PROMOTED", "started_at_unix_ns": time.time_ns(), "source_control": source_control, "contract_sha256": sha256_file(CONTRACT_PATH), "runner_sha256": sha256_file(Path(__file__)), "curriculum_manifest_sha256": sha256_file(MANIFEST_PATH), "curriculum_inputs_before": curriculum_before, "admitted_train_rows": len(train_rows), "admitted_eval_rows": len(eval_rows), "admitted_shadow_eval_rows": len(shadow_eval_rows), "base_files_before": before, "dynamic_module_cache": module_cache_receipt, "license": contract["base"]["license"], "network_download_allowed": False, "os_network_namespace": network_namespace, "upload_allowed": False, "promotion": "NOT_PROMOTED"}
    atomic_json(receipts / "training-receipt.json", receipt)
    try:
        with deny_python_network() as network_control, RuntimeGuard(contract) as guard:
            receipt["network_control"] = network_control
            import torch
            from datasets import Dataset
            from peft import LoraConfig, PeftModel, prepare_model_for_kbit_training
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainerCallback
            from trl import DataCollatorForCompletionOnlyLM, SFTConfig, SFTTrainer
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
            receipt["padding_token_admission"] = admit_padding_token(
                tokenizer, contract, "training"
            )
            model = AutoModelForCausalLM.from_pretrained(str(snapshot), local_files_only=True, quantization_config=quant, device_map={"": 0}, trust_remote_code=True, use_safetensors=True, low_cpu_mem_usage=True)
            receipt["loaded_model_class"] = verify_loaded_model_source(model, contract, "training")
            receipt["model_padding_binding"] = verify_model_padding_binding(
                model, receipt["padding_token_admission"], "training"
            )
            model.config.use_cache = False
            model = prepare_model_for_kbit_training(
                model,
                use_gradient_checkpointing=True,
                gradient_checkpointing_kwargs={"use_reentrant": False},
            )
            texts = [tokenizer.apply_chat_template(row["messages"], tokenize=False, add_generation_prompt=False) for row in train_rows]
            dataset = Dataset.from_dict({"text": texts})
            settings = contract["training"]
            completion_collator, formatting_evidence = completion_only_training_setup(
                tokenizer, texts, settings, DataCollatorForCompletionOnlyLM
            )
            receipt["training_format"] = formatting_evidence
            lora = LoraConfig(r=settings["lora_rank"], lora_alpha=settings["lora_alpha"], lora_dropout=settings["lora_dropout"], bias="none", task_type="CAUSAL_LM", target_modules=settings["target_modules"])
            arguments = SFTConfig(output_dir=str(output / "trainer"), max_steps=settings["max_steps"], per_device_train_batch_size=settings["per_device_batch_size"], gradient_accumulation_steps=settings["gradient_accumulation_steps"], learning_rate=settings["learning_rate"], warmup_ratio=settings["warmup_ratio"], optim=settings["optimizer"], seed=settings["seed"], bf16=bf16, fp16=not bf16, max_seq_length=settings["max_sequence_length"], dataset_text_field="text", logging_steps=1, save_strategy="no", report_to="none", gradient_checkpointing=True, gradient_checkpointing_kwargs={"use_reentrant": False})
            trainer = SFTTrainer(model=model, processing_class=tokenizer, train_dataset=dataset, data_collator=completion_collator, peft_config=lora, args=arguments, callbacks=[ThermalGuard()])
            receipt["gradient_checkpointing"] = gradient_checkpointing_evidence(
                trainer.model, "training"
            )
            receipt["mamba_forward_compatibility"] = bind_quantized_mamba_lora_forward(
                trainer.model, contract, "training"
            )
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
            reload_model = AutoModelForCausalLM.from_pretrained(str(snapshot), local_files_only=True, quantization_config=quant, device_map={"": 0}, trust_remote_code=True, use_safetensors=True, low_cpu_mem_usage=True)
            receipt["reloaded_model_class"] = verify_loaded_model_source(reload_model, contract, "reload")
            receipt["reload_padding_binding"] = verify_model_padding_binding(
                reload_model, receipt["padding_token_admission"], "reload"
            )
            reload_model = PeftModel.from_pretrained(reload_model, str(adapter), is_trainable=False, local_files_only=True); reload_model.eval()
            original_evaluation, shadow_evaluation, reload_receipt = evaluate_mandatory_sets(
                tokenizer,
                reload_model,
                eval_rows,
                shadow_eval_rows,
                contract,
                guard,
                sha256_file(receipts / "adapter-files.json"),
            )
            reload_state = reload_receipt["state"]
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
            guard.finalize()
            runtime_guard = guard.receipt()
            training_evidence = {
                "schema_version": "szl.nemo.training-evidence.v2",
                "contract_id": contract["contract_id"],
                "candidate_id": contract["candidate_id"],
                "base_revision": contract["base"]["revision"],
                "contract_sha256": receipt["contract_sha256"],
                "runner_sha256": receipt["runner_sha256"],
                "curriculum_manifest_sha256": receipt["curriculum_manifest_sha256"],
                "dsse_verifier": dsse_verifier,
                "runtime_identity": receipt["runtime_identity"],
                "model_code": {
                    "loaded_model_class": receipt["loaded_model_class"],
                    "reloaded_model_class": receipt["reloaded_model_class"],
                },
                "runtime_guard": runtime_guard,
                "source_control": {"before": source_control, "after": source_control_after},
                "base_files": {"before": before, "after": after},
                "curriculum_inputs": {
                    "before": curriculum_before,
                    "after": curriculum_after,
                },
                "step_evidence": {
                    "training_started_at_unix_ns": receipt["training_started_at_unix_ns"],
                    "training_completed_at_unix_ns": receipt["training_completed_at_unix_ns"],
                    "expected_global_steps": settings["max_steps"],
                    "observed_global_steps": receipt["global_steps"],
                    "training_loss": receipt["training_loss"],
                    "peak_vram_reserved_bytes": receipt["peak_vram_reserved_bytes"],
                    "training_format": receipt["training_format"],
                },
                "artifact_evidence": {
                    "adapter_files_receipt_sha256": sha256_file(receipts / "adapter-files.json"),
                    "reload_evaluation_receipt_sha256": sha256_file(receipts / "reload-evaluation-receipt.json"),
                    "frozen_original_eval_sha256": sha256_file(EVAL_PATH),
                    "preregistered_shadow_eval_sha256": sha256_file(SHADOW_EVAL_PATH),
                    "mandatory_evaluation_sets": contract["evaluation"]["mandatory_sets"],
                },
                "promotion": "NOT_PROMOTED",
            }
            atomic_json(receipts / "training-evidence.json", training_evidence)
            training_evidence_sha256 = sha256_file(receipts / "training-evidence.json")
            summary = {
                "schema_version": "szl.nemo.candidate-summary.v2",
                "contract_id": contract["contract_id"],
                "base_revision": contract["base"]["revision"],
                "adapter_files_receipt_sha256": sha256_file(receipts / "adapter-files.json"),
                "reload_evaluation_receipt_sha256": sha256_file(receipts / "reload-evaluation-receipt.json"),
                "training_evidence_sha256": training_evidence_sha256,
                "dsse_verifier": dsse_verifier,
                "evaluation_state": reload_state,
                "evaluation_sets": {
                    "original": original_evaluation["state"],
                    "shadow": shadow_evaluation["state"],
                },
                "runtime_guard": runtime_guard,
                "promotion": "NOT_PROMOTED",
            }
            signed = _sign_summary(summary, contract, dsse_verifier); atomic_json(receipts / "candidate-summary.dsse.json", signed)
            receipt.update({"state": "CANDIDATE_GENERATED_NOT_PROMOTED" if reload_state == "PASS" else "EVALUATION_FAILED_NOT_PROMOTED", "completed_at_unix_ns": time.time_ns(), "base_files_after": after, "curriculum_inputs_after": curriculum_after, "source_control_after": source_control_after, "reload_evaluation_receipt_sha256": sha256_file(receipts / "reload-evaluation-receipt.json"), "training_evidence_sha256": training_evidence_sha256, "candidate_summary_dsse_sha256": sha256_file(receipts / "candidate-summary.dsse.json"), "organization_signature_verified": signed["promotion_eligible_signature"], "dsse_verifier": dsse_verifier, "runtime_guard": runtime_guard, "promotion": "NOT_PROMOTED"})
            atomic_json(receipts / "training-receipt.json", receipt)
            return 0 if reload_state == "PASS" else 4
    except Exception as exc:
        receipt.update({"state": "FAILED_NOT_PROMOTED", "completed_at_unix_ns": time.time_ns(), "error_type": type(exc).__name__, "error": str(exc), "traceback_sha256": sha256_bytes(traceback.format_exc().encode("utf-8")), "promotion": "NOT_PROMOTED"})
        atomic_json(receipts / "training-receipt.json", receipt)
        raise


def observed_training_started(output: Path) -> str:
    """Report what the durable receipt proves after a caught training refusal."""

    path = output / "receipts" / "training-receipt.json"
    if not path.is_file():
        return TRAINING_START_UNKNOWN
    try:
        receipt = load_object(path)
    except (OSError, ValueError, json.JSONDecodeError, GateRefused):
        return TRAINING_START_UNKNOWN
    if receipt.get("schema_version") not in {
        "szl.nemo.training-receipt.v1",
        "szl.nemo.training-receipt.v2",
    }:
        return TRAINING_START_UNKNOWN
    marker = receipt.get("training_started_at_unix_ns")
    if "training_started_at_unix_ns" not in receipt:
        return (
            TRAINING_START_PROVEN_FALSE
            if receipt.get("state") == "RUNNING_NOT_PROMOTED"
            else TRAINING_START_UNKNOWN
        )
    if type(marker) is int and marker > 0:
        return TRAINING_START_PROVEN_TRUE
    return TRAINING_START_UNKNOWN


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build")
    fetch = sub.add_parser("fetch-base"); fetch.add_argument("--destination", type=Path, required=True); fetch.add_argument("--confirmation", required=True)
    check = sub.add_parser("preflight"); check.add_argument("--base-snapshot", type=Path); check.add_argument("--check-gpu", action="store_true"); check.add_argument("--probe", action="store_true"); check.add_argument("--receipt", type=Path)
    capacity = sub.add_parser("capacity-probe"); capacity.add_argument("--base-snapshot", type=Path, required=True); capacity.add_argument("--receipt", type=Path, required=True); capacity.add_argument("--confirmation", required=True); capacity.add_argument("--license-acknowledgement", required=True)
    calibrate = sub.add_parser("calibrate-vram"); calibrate.add_argument("--base-snapshot", type=Path, required=True); calibrate.add_argument("--receipt", type=Path, required=True); calibrate.add_argument("--confirmation", required=True); calibrate.add_argument("--license-acknowledgement", required=True)
    offload = sub.add_parser("calibrate-activation-offload"); offload.add_argument("--base-snapshot", type=Path, required=True); offload.add_argument("--receipt", type=Path, required=True); offload.add_argument("--confirmation", required=True); offload.add_argument("--license-acknowledgement", required=True)
    evaluate = sub.add_parser("evaluate-adapter"); evaluate.add_argument("--base-snapshot", type=Path, required=True); evaluate.add_argument("--training-output", type=Path, required=True); evaluate.add_argument("--receipt", type=Path, required=True); evaluate.add_argument("--confirmation", required=True); evaluate.add_argument("--license-acknowledgement", required=True)
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
        if args.command == "calibrate-vram":
            with training_mutex(), fresh_hf_modules_cache() as module_cache:
                return low_vram_calibration(args.base_snapshot, args.receipt, args.confirmation, args.license_acknowledgement, module_cache)
        if args.command == "calibrate-activation-offload":
            with training_mutex(), fresh_hf_modules_cache() as module_cache:
                return activation_offload_calibration(args.base_snapshot, args.receipt, args.confirmation, args.license_acknowledgement, module_cache)
        if args.command == "evaluate-adapter":
            with training_mutex(), fresh_hf_modules_cache() as module_cache:
                return evaluate_saved_adapter(args.base_snapshot, args.training_output, args.receipt, args.confirmation, args.license_acknowledgement, module_cache)
        with training_mutex(), fresh_hf_modules_cache() as module_cache:
            return train(args.base_snapshot, args.output_dir, args.confirmation, args.license_acknowledgement, module_cache)
    except GateRefused as exc:
        training_started = TRAINING_START_PROVEN_FALSE
        if args.command == "train":
            training_started = observed_training_started(args.output_dir)
        print(json.dumps({"state": "BLOCKED", "reason": str(exc), "effects": {"training_started": training_started, "uploaded": False, "published": False, "deployed": False}}, indent=2), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
