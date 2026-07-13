#!/usr/bin/env python3
"""Fail-closed SZL-Forge-1.5B training path.

The dependency-light ``build`` and ``preflight`` commands run without a GPU
stack.  Heavy ML imports occur only after the curriculum, immutable base, GPU
soak, and explicit confirmation gates pass.  The script never uploads,
publishes, deploys, stops another process, or weakens the fixed GPU policy.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
from typing import Any, Callable, Iterable


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CONTRACT_PATH = HERE / "training-contract.json"
SOURCE_PATH = HERE / "curriculum-source.json"
GENERATED = HERE / "generated"
TRAIN_PATH = GENERATED / "train.jsonl"
EVAL_PATH = GENERATED / "eval.jsonl"
MANIFEST_PATH = GENERATED / "curriculum-manifest.json"

ROW_SCHEMA = "szl.forge-curriculum-record.v1"
DRAFT_SCHEMA = "szl.forge-receipt-draft.v1"
RIGHTS_BASIS = "PROJECT_AUTHORED_SCHEMA_GENERATED"


class GateRefused(RuntimeError):
    """Raised when a fixed admission gate refuses work."""


class GPUAdmissionRefused(GateRefused):
    def __init__(self, reason: str, samples: list[dict[str, Any]]) -> None:
        super().__init__(reason)
        self.samples = samples


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise GateRefused(f"{path} is not a JSON object")
    return value


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise GateRefused(f"{path}:{line_number} is not an object")
            yield value


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _draft_for(scenario: dict[str, Any]) -> dict[str, Any]:
    kind = scenario["kind"]
    if kind in {"ANSWER", "TOOL"}:
        draft = {
            "schema_version": DRAFT_SCHEMA,
            "status": "ANSWER_PROPOSED",
            "answer": scenario["answer"],
            "evidence_ids": scenario["evidence"],
            "formula_refs": [],
            "uncertainty": {
                "band": scenario.get("uncertainty", "MEDIUM"),
                "basis": "Bounded project-authored fixture evidence only; runtime validation is still required.",
            },
            "abstention": {"required": False, "code": "NONE", "detail": "No model-side abstention requested."},
            "tool_proposal": {"state": "NONE", "tool_id": None, "arguments": None},
        }
        if kind == "TOOL":
            draft["tool_proposal"] = {
                "state": "PROPOSED",
                "tool_id": scenario["tool_id"],
                "arguments": {"fixture_key": "alpha", "read_only": True},
            }
        return draft

    code = scenario["code"]
    return {
        "schema_version": DRAFT_SCHEMA,
        "status": "UNAVAILABLE" if kind == "UNAVAILABLE" else "ABSTAINED",
        "answer": None,
        "evidence_ids": [],
        "formula_refs": [],
        "uncertainty": {
            "band": "NOT_EVALUATED" if kind == "UNAVAILABLE" else "HIGH",
            "basis": "The requested operation lacks an admitted, policy-valid basis.",
        },
        "abstention": {"required": True, "code": code, "detail": f"Fail closed: {code}."},
        "tool_proposal": {"state": "NONE", "tool_id": None, "arguments": None},
    }


def validate_draft(value: Any) -> list[str]:
    """Small dependency-free conformance check used by reload evaluation.

    Full JSON Schema validation remains a release gate.  This check deliberately
    covers the security-relevant invariants needed by the offline runner.
    """
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["draft is not an object"]
    required = {
        "schema_version", "status", "answer", "evidence_ids", "formula_refs",
        "uncertainty", "abstention", "tool_proposal",
    }
    unknown = set(value) - required
    missing = required - set(value)
    if missing:
        errors.append("missing fields: " + ",".join(sorted(missing)))
    if unknown:
        errors.append("unknown fields: " + ",".join(sorted(unknown)))
    if value.get("schema_version") != DRAFT_SCHEMA:
        errors.append("wrong schema_version")
    status = value.get("status")
    if status not in {"ANSWER_PROPOSED", "ABSTAINED", "UNAVAILABLE"}:
        errors.append("invalid status")
    evidence = value.get("evidence_ids")
    if not isinstance(evidence, list) or any(not isinstance(item, str) for item in evidence):
        errors.append("evidence_ids must be strings")
    abstention = value.get("abstention")
    if not isinstance(abstention, dict):
        errors.append("abstention must be an object")
    elif status in {"ABSTAINED", "UNAVAILABLE"}:
        if value.get("answer") is not None or abstention.get("required") is not True:
            errors.append("fail-closed status must have null answer and required abstention")
    elif status == "ANSWER_PROPOSED":
        if not isinstance(value.get("answer"), str) or not value.get("answer"):
            errors.append("answer proposal requires text")
        if not evidence:
            errors.append("answer proposal requires evidence identifiers")
        if isinstance(abstention, dict) and abstention.get("required") is not False:
            errors.append("answer proposal cannot require abstention")
    tool = value.get("tool_proposal")
    if not isinstance(tool, dict) or tool.get("state") not in {"NONE", "PROPOSED"}:
        errors.append("invalid tool_proposal")
    return errors


def _row(scenario: dict[str, Any], split: str, variant: int) -> dict[str, Any]:
    scenario_id = scenario["id"]
    prompt = f"{scenario['prompt']} Fixture variant {variant + 1}."
    assistant = canonical_json(_draft_for(scenario))
    messages = [
        {
            "role": "system",
            "content": (
                "You are the ReceiptAgent profile of SZL-Forge-1.5B. Return only one "
                "szl.forge-receipt-draft.v1 JSON object. Never claim to sign a receipt, "
                "execute a tool, admit evidence, or transfer proof status. The governed "
                "A11oy runtime performs those deterministic operations."
            ),
        },
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": assistant},
    ]
    return {
        "schema_version": ROW_SCHEMA,
        "record_id": f"receipt-agent:{split.lower()}:{scenario_id}:v{variant + 1}",
        "profile_id": "ReceiptAgent-v1",
        "split": split,
        "training_eligible": split == "TRAIN",
        "rights_basis": RIGHTS_BASIS,
        "source_classes": ["PROJECT_AUTHORED_POLICY", "PROJECT_AUTHORED_SCHEMA"],
        "source_refs": [
            "model_release/szl-forge/curriculum-source.json",
            "model_release/szl-forge/schemas/receipt-agent-draft.schema.json",
        ],
        "forbidden_source_refs": [],
        "prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
        "target_sha256": sha256_bytes(assistant.encode("utf-8")),
        "messages": messages,
    }


def build_curriculum(output_dir: Path = GENERATED) -> dict[str, Any]:
    source = load_json(SOURCE_PATH)
    if source.get("rights_basis") != RIGHTS_BASIS or source.get("owner") != "SZL Holdings":
        raise GateRefused("curriculum source lacks the project-authored rights declaration")

    train_rows = [
        _row(scenario, "TRAIN", variant)
        for scenario in source["train_scenarios"]
        for variant in range(3)
    ]
    eval_rows = [_row(scenario, "EVAL", 0) for scenario in source["eval_scenarios"]]
    output_dir.mkdir(parents=True, exist_ok=True)
    train_path = output_dir / "train.jsonl"
    eval_path = output_dir / "eval.jsonl"
    train_path.write_text("".join(canonical_json(row) + "\n" for row in train_rows), encoding="utf-8")
    eval_path.write_text("".join(canonical_json(row) + "\n" for row in eval_rows), encoding="utf-8")
    def manifest_path(path: Path) -> str:
        try:
            return str(path.resolve().relative_to(REPO)).replace("\\", "/")
        except ValueError:
            return str(path.resolve())

    manifest = {
        "schema_version": "szl.forge-curriculum-manifest.v1",
        "contract_id": "szl-forge-1.5b.receipt-agent-v1",
        "profile_id": "ReceiptAgent-v1",
        "state": "ADMITTED_PROJECT_AUTHORED_ONLY",
        "rights_basis": RIGHTS_BASIS,
        "source": {"path": str(SOURCE_PATH.relative_to(REPO)).replace("\\", "/"), "sha256": sha256_file(SOURCE_PATH)},
        "draft_schema": {
            "path": "model_release/szl-forge/schemas/receipt-agent-draft.schema.json",
            "sha256": sha256_file(HERE / "schemas" / "receipt-agent-draft.schema.json"),
        },
        "train": {"path": manifest_path(train_path), "rows": len(train_rows), "sha256": sha256_file(train_path)},
        "eval": {"path": manifest_path(eval_path), "rows": len(eval_rows), "sha256": sha256_file(eval_path)},
        "excluded_training_classes": ["BRAIN_RAW_NODE", "FORMULA_HOLDOUT", "HISTORICAL_UNREVIEWED_SEED", "ORPO_QUARANTINE", "THIRD_PARTY_TRACE"],
        "external_mutations": {"trained": False, "uploaded": False, "published": False, "deployed": False},
    }
    atomic_json(output_dir / "curriculum-manifest.json", manifest)
    validate_curriculum(manifest_path=output_dir / "curriculum-manifest.json", repo=REPO)
    return manifest


def _resolve_repo(path: str, repo: Path = REPO) -> Path:
    return (repo / Path(path)).resolve()


def validate_curriculum(manifest_path: Path = MANIFEST_PATH, repo: Path = REPO) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    contract = load_json(CONTRACT_PATH if repo == REPO else repo / "model_release/szl-forge/training-contract.json")
    if manifest.get("state") != "ADMITTED_PROJECT_AUTHORED_ONLY" or manifest.get("rights_basis") != RIGHTS_BASIS:
        raise GateRefused("curriculum manifest is not project-authored and admitted")

    prompt_hashes: dict[str, set[str]] = {"TRAIN": set(), "EVAL": set()}
    for split, key in (("TRAIN", "train"), ("EVAL", "eval")):
        entry = manifest[key]
        path = _resolve_repo(entry["path"], repo)
        if not path.is_file() or sha256_file(path) != entry["sha256"]:
            raise GateRefused(f"{split} curriculum hash mismatch")
        rows = list(iter_jsonl(path))
        minimum = contract["curriculum"]["minimum_train_rows" if split == "TRAIN" else "minimum_eval_rows"]
        if len(rows) != entry["rows"] or len(rows) < minimum:
            raise GateRefused(f"{split} curriculum row count is below contract")
        ids: set[str] = set()
        for row in rows:
            if row.get("schema_version") != ROW_SCHEMA or row.get("split") != split:
                raise GateRefused(f"{split} row schema or split mismatch")
            expected_eligible = split == "TRAIN"
            if row.get("training_eligible") is not expected_eligible:
                raise GateRefused(f"{split} training_eligible mismatch")
            if row.get("rights_basis") != RIGHTS_BASIS:
                raise GateRefused(f"{split} row lacks project-authored rights basis")
            if set(row.get("source_classes", [])) - set(contract["curriculum"]["allowed_source_classes"]):
                raise GateRefused(f"{split} row contains an unapproved source class")
            if row.get("forbidden_source_refs") != []:
                raise GateRefused(f"{split} row references forbidden material")
            if row["record_id"] in ids:
                raise GateRefused(f"duplicate {split} record id")
            ids.add(row["record_id"])
            prompt_hashes[split].add(row["prompt_sha256"])
            messages = row.get("messages")
            if not isinstance(messages, list) or len(messages) != 3:
                raise GateRefused(f"{split} row has invalid messages")
            target = json.loads(messages[-1]["content"])
            errors = validate_draft(target)
            if errors:
                raise GateRefused(f"{split} row has invalid target: {'; '.join(errors)}")

    if prompt_hashes["TRAIN"] & prompt_hashes["EVAL"]:
        raise GateRefused("train/eval prompt overlap detected")
    raw = (_resolve_repo(manifest["train"]["path"], repo).read_text(encoding="utf-8") +
           _resolve_repo(manifest["eval"]["path"], repo).read_text(encoding="utf-8"))
    for excluded in contract["excluded_from_training"]:
        if excluded["path"] in raw:
            raise GateRefused(f"excluded corpus leaked into curriculum: {excluded['path']}")
    return manifest


def query_gpu() -> dict[str, Any]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        raise GateRefused("nvidia-smi is unavailable")
    result = subprocess.run(
        [executable, "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"],
        check=True, capture_output=True, text=True, timeout=15,
    )
    line = result.stdout.strip().splitlines()[0]
    values = [part.strip() for part in line.split(",")]
    if len(values) != 6:
        raise GateRefused("unexpected nvidia-smi output")
    return {
        "measured_at_unix_ns": time.time_ns(),
        "gpu_name": values[0],
        "memory_total_mib": int(values[1]),
        "memory_used_mib": int(values[2]),
        "memory_free_mib": int(values[3]),
        "utilization_pct": int(values[4]),
        "temperature_c": int(values[5]),
    }


def sample_gpu(policy: dict[str, Any], count: int, interval: int, query: Callable[[], dict[str, Any]] = query_gpu, sleeper: Callable[[float], None] = time.sleep) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for index in range(count):
        sample = query()
        samples.append(sample)
        if (sample["memory_free_mib"] < policy["minimum_free_memory_mib"] or
                sample["utilization_pct"] > policy["maximum_utilization_pct"] or
                sample["temperature_c"] > policy["maximum_temperature_c"]):
            raise GPUAdmissionRefused("GPU admission thresholds were not maintained", samples)
        if index + 1 < count:
            sleeper(interval)
    return samples


def _verify_base(base_snapshot: Path, contract: dict[str, Any]) -> list[dict[str, Any]]:
    if not base_snapshot.is_dir():
        raise GateRefused("operator-supplied immutable base snapshot is absent")
    identity_path = _resolve_repo(contract["base"]["identity_manifest"])
    identity = load_json(identity_path)
    observed: list[dict[str, Any]] = []
    for item in identity["base"]["files"]:
        path = base_snapshot / item["path"]
        if not path.is_file():
            raise GateRefused(f"base file missing: {item['path']}")
        digest = sha256_file(path)
        if digest != item["sha256"] or path.stat().st_size != item["bytes"]:
            raise GateRefused(f"base file identity mismatch: {item['path']}")
        observed.append({"path": item["path"], "bytes": path.stat().st_size, "sha256": digest})
    return observed


def preflight(base_snapshot: Path | None, check_gpu: bool, gpu_samples: int | None = None,
              query: Callable[[], dict[str, Any]] = query_gpu,
              sleeper: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    contract = load_json(CONTRACT_PATH)
    checks: list[dict[str, Any]] = []
    try:
        manifest = validate_curriculum()
        checks.append({"id": "CURRICULUM_ADMISSION", "state": "PASS", "sha256": sha256_file(MANIFEST_PATH), "train_rows": manifest["train"]["rows"], "eval_rows": manifest["eval"]["rows"]})
        if base_snapshot is None:
            raise GateRefused("base snapshot must be supplied explicitly")
        base_files = _verify_base(base_snapshot.resolve(), contract)
        checks.append({"id": "IMMUTABLE_BASE", "state": "PASS", "files": base_files})
        gpu: list[dict[str, Any]] = []
        if check_gpu:
            count = gpu_samples or contract["gpu_admission"]["training_soak_samples"]
            allowed = {contract["gpu_admission"]["queue_probe_samples"], contract["gpu_admission"]["training_soak_samples"]}
            if count not in allowed:
                raise GateRefused("GPU sample count cannot weaken the fixed probe/soak policy")
            gpu = sample_gpu(contract["gpu_admission"], count, contract["gpu_admission"]["sample_interval_seconds"], query, sleeper)
            checks.append({"id": "GPU_ADMISSION", "state": "PASS", "samples": gpu})
        else:
            checks.append({"id": "GPU_ADMISSION", "state": "NOT_EVALUATED"})
        state = "PASS" if check_gpu else "READY_FOR_GPU_ADMISSION"
        return {"schema_version": "szl.forge-preflight-receipt.v1", "contract_id": contract["contract_id"], "state": state, "gpu_policy": contract["gpu_admission"], "checks": checks, "external_mutations": {"training_started": False, "uploaded": False, "published": False, "deployed": False}}
    except GPUAdmissionRefused as exc:
        checks.append({"id": "GPU_ADMISSION", "state": "BLOCKED", "reason": str(exc), "samples": exc.samples})
        return {"schema_version": "szl.forge-preflight-receipt.v1", "contract_id": contract.get("contract_id"), "state": "BLOCKED", "gpu_policy": contract["gpu_admission"], "checks": checks, "external_mutations": {"training_started": False, "uploaded": False, "published": False, "deployed": False}}
    except Exception as exc:
        checks.append({"id": "REFUSAL", "state": "BLOCKED", "reason": str(exc)})
        return {"schema_version": "szl.forge-preflight-receipt.v1", "contract_id": contract.get("contract_id"), "state": "BLOCKED", "gpu_policy": contract["gpu_admission"], "checks": checks, "external_mutations": {"training_started": False, "uploaded": False, "published": False, "deployed": False}}


def _file_inventory(root: Path) -> list[dict[str, Any]]:
    return [
        {"path": str(path.relative_to(root)).replace("\\", "/"), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in sorted(root.rglob("*")) if path.is_file()
    ]


def _git_commit() -> str | None:
    git = shutil.which("git")
    if not git:
        return None
    result = subprocess.run([git, "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def _run_reload_evaluation(base_snapshot: Path, adapter_dir: Path, output_dir: Path,
                           max_length: int) -> dict[str, Any]:
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    bf16 = bool(torch.cuda.is_bf16_supported())
    quant = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16 if bf16 else torch.float16,
    )
    tokenizer = AutoTokenizer.from_pretrained(str(base_snapshot), local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        str(base_snapshot), local_files_only=True, quantization_config=quant, device_map="auto"
    )
    model = PeftModel.from_pretrained(model, str(adapter_dir), is_trainable=False, local_files_only=True)
    model.eval()
    results: list[dict[str, Any]] = []
    for row in iter_jsonl(EVAL_PATH):
        prompt_messages = row["messages"][:-1]
        text = tokenizer.apply_chat_template(prompt_messages, tokenize=False, add_generation_prompt=True)
        encoded = tokenizer(text, return_tensors="pt", truncation=True, max_length=max_length)
        encoded = {key: value.to(model.device) for key, value in encoded.items()}
        with torch.no_grad():
            generated = model.generate(**encoded, max_new_tokens=384, do_sample=False)
        completion = tokenizer.decode(generated[0][encoded["input_ids"].shape[1]:], skip_special_tokens=True).strip()
        try:
            value = json.loads(completion)
            errors = validate_draft(value)
        except Exception as exc:
            errors = [f"JSON_PARSE:{type(exc).__name__}"]
        results.append({"record_id": row["record_id"], "output_sha256": sha256_bytes(completion.encode("utf-8")), "schema_conformant": not errors, "errors": errors})
    passed = sum(1 for result in results if result["schema_conformant"])
    receipt = {
        "schema_version": "szl.forge-reload-evaluation-receipt.v1",
        "state": "PASS" if passed == len(results) else "FAIL",
        "adapter_sha256_set": _file_inventory(adapter_dir),
        "eval_manifest_sha256": sha256_file(EVAL_PATH),
        "rows": len(results),
        "schema_conformant_rows": passed,
        "strict_schema_valid_rate": passed / len(results) if results else 0.0,
        "promotion_effect": "NONE_AUTOMATIC",
        "results": results,
    }
    atomic_json(output_dir / "reload-evaluation-receipt.json", receipt)
    return receipt


def run_training(base_snapshot: Path, output_dir: Path, confirmation: str) -> int:
    contract = load_json(CONTRACT_PATH)
    if confirmation != contract["training"]["confirmation_phrase"]:
        raise GateRefused("exact training confirmation phrase is required")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise GateRefused("output directory must be absent or empty; prior receipts are immutable")
    receipt_dir = output_dir / "receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    preflight_receipt = preflight(base_snapshot, check_gpu=True)
    atomic_json(receipt_dir / "preflight-receipt.json", preflight_receipt)
    if preflight_receipt["state"] != "PASS":
        return 3

    os.environ.update({
        "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1", "WANDB_DISABLED": "true",
        "TOKENIZERS_PARALLELISM": "false",
    })
    started_ns = time.time_ns()
    training_receipt: dict[str, Any] = {
        "schema_version": "szl.forge-training-receipt.v1",
        "contract_id": contract["contract_id"],
        "state": "RUNNING",
        "started_at_unix_ns": started_ns,
        "git_commit": _git_commit(),
        "contract_sha256": sha256_file(CONTRACT_PATH),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "curriculum_manifest_sha256": sha256_file(MANIFEST_PATH),
        "draft_schema_sha256": sha256_file(HERE / "schemas" / "receipt-agent-draft.schema.json"),
        "network_download_allowed": False,
        "upload_allowed": False,
    }
    atomic_json(receipt_dir / "training-receipt.json", training_receipt)
    try:
        import torch
        from datasets import Dataset
        from peft import LoraConfig
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainerCallback
        from trl import SFTConfig, SFTTrainer

        policy = contract["gpu_admission"]
        if not torch.cuda.is_available():
            raise GateRefused("CUDA disappeared after GPU admission")

        class ThermalGuard(TrainerCallback):
            def on_step_end(self, args: Any, state: Any, control: Any, **kwargs: Any) -> Any:
                sample = query_gpu()
                if sample["temperature_c"] > policy["maximum_training_temperature_c"]:
                    raise RuntimeError("training thermal ceiling exceeded; trainer stopped fail-closed")
                return control

        bf16 = bool(torch.cuda.is_bf16_supported())
        quant = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16 if bf16 else torch.float16,
        )
        tokenizer = AutoTokenizer.from_pretrained(str(base_snapshot), local_files_only=True)
        model = AutoModelForCausalLM.from_pretrained(
            str(base_snapshot), local_files_only=True, quantization_config=quant, device_map="auto"
        )
        rows = list(iter_jsonl(TRAIN_PATH))
        texts = [tokenizer.apply_chat_template(row["messages"], tokenize=False, add_generation_prompt=False) for row in rows]
        dataset = Dataset.from_dict({"text": texts})
        train = contract["training"]
        lora = LoraConfig(
            r=train["lora_rank"], lora_alpha=train["lora_alpha"], lora_dropout=train["lora_dropout"],
            bias="none", task_type="CAUSAL_LM", target_modules=train["target_modules"],
        )
        args = SFTConfig(
            output_dir=str(output_dir / "trainer"), max_steps=train["max_steps"],
            per_device_train_batch_size=train["per_device_batch_size"],
            gradient_accumulation_steps=train["gradient_accumulation_steps"],
            learning_rate=train["learning_rate"], warmup_ratio=train["warmup_ratio"],
            optim=train["optimizer"], seed=train["seed"], bf16=bf16, fp16=not bf16,
            max_length=train["max_sequence_length"], dataset_text_field="text",
            logging_steps=1, save_strategy="no", report_to="none", gradient_checkpointing=True,
        )
        trainer = SFTTrainer(model=model, processing_class=tokenizer, train_dataset=dataset, peft_config=lora, args=args, callbacks=[ThermalGuard()])
        result = trainer.train()
        adapter_dir = output_dir / "adapter"
        adapter_dir.mkdir(parents=True, exist_ok=True)
        trainer.model.save_pretrained(adapter_dir)
        tokenizer.save_pretrained(adapter_dir)
        inventory = _file_inventory(adapter_dir)
        atomic_json(receipt_dir / "adapter-files.json", {"schema_version": "szl.forge-adapter-files.v1", "files": inventory})
        training_receipt.update({
            "state": "TRAINING_COMPLETED_EVALUATION_REQUIRED",
            "completed_at_unix_ns": time.time_ns(),
            "global_steps": int(result.global_step),
            "training_loss": float(result.training_loss),
            "peak_vram_reserved_bytes": int(torch.cuda.max_memory_reserved()),
            "curriculum_manifest_sha256": sha256_file(MANIFEST_PATH),
            "adapter_files_receipt_sha256": sha256_file(receipt_dir / "adapter-files.json"),
            "package_versions": {
                "torch": torch.__version__,
                **{
                    package: importlib.metadata.version(package)
                    for package in ("transformers", "trl", "peft", "bitsandbytes", "accelerate", "datasets")
                },
            },
        })
        atomic_json(receipt_dir / "training-receipt.json", training_receipt)
        del trainer, model
        torch.cuda.empty_cache()
        reload_receipt = _run_reload_evaluation(base_snapshot, adapter_dir, receipt_dir, train["max_sequence_length"])
        training_receipt["state"] = "CANDIDATE_GENERATED_NOT_PROMOTED" if reload_receipt["state"] == "PASS" else "EVALUATION_FAILED_NOT_PROMOTED"
        training_receipt["reload_evaluation_receipt_sha256"] = sha256_file(receipt_dir / "reload-evaluation-receipt.json")
        training_receipt["promotion"] = "NOT_PROMOTED"
        atomic_json(receipt_dir / "training-receipt.json", training_receipt)
        return 0 if reload_receipt["state"] == "PASS" else 4
    except Exception as exc:
        training_receipt.update({
            "state": "FAILED_NOT_PROMOTED", "completed_at_unix_ns": time.time_ns(),
            "error_type": type(exc).__name__, "error": str(exc),
            "traceback_sha256": sha256_bytes(traceback.format_exc().encode("utf-8")),
            "promotion": "NOT_PROMOTED",
        })
        atomic_json(receipt_dir / "training-receipt.json", training_receipt)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build", help="build the deterministic project-authored curriculum")
    status = sub.add_parser("preflight", help="validate data/base and optionally the fixed GPU admission gate")
    status.add_argument("--base-snapshot", type=Path)
    status.add_argument("--check-gpu", action="store_true")
    status.add_argument("--probe", action="store_true", help="use the fixed three-sample queue probe; train always uses the eleven-sample soak")
    status.add_argument("--receipt", type=Path)
    train = sub.add_parser("train", help="run the governed offline QLoRA path")
    train.add_argument("--base-snapshot", type=Path, required=True)
    train.add_argument("--output-dir", type=Path, required=True)
    train.add_argument("--confirmation", required=True)
    args = parser.parse_args(argv)

    try:
        if args.command == "build":
            print(json.dumps(build_curriculum(), indent=2))
            return 0
        if args.command == "preflight":
            contract = load_json(CONTRACT_PATH)
            samples = contract["gpu_admission"]["queue_probe_samples"] if args.probe else None
            result = preflight(args.base_snapshot, args.check_gpu, samples)
            if args.receipt:
                atomic_json(args.receipt, result)
            print(json.dumps(result, indent=2))
            return 0 if result["state"] in {"PASS", "READY_FOR_GPU_ADMISSION"} else 3
        return run_training(args.base_snapshot, args.output_dir, args.confirmation)
    except GateRefused as exc:
        print(f"SZL-Forge gate refused: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
