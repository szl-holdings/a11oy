#!/usr/bin/env python3
"""Fail-closed SZL-Forge-1.5B training path.

The dependency-light ``build`` and ``preflight`` commands run without a GPU
stack.  Heavy ML imports occur only after the curriculum, immutable base, GPU
soak, and explicit confirmation gates pass.  The script never uploads,
publishes, deploys, stops another process, or weakens the fixed GPU policy.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import socket
import stat
import subprocess
import sys
import threading
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
SYSTEM_PROMPT = (
    "You are the ReceiptAgent profile of SZL-Forge-1.5B. Return only one "
    "szl.forge-receipt-draft.v1 JSON object. Never claim to sign a receipt, "
    "execute a tool, admit evidence, or transfer proof status. The governed "
    "A11oy runtime performs those deterministic operations."
)
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9._:/-]+$")
EVIDENCE_PATTERN = re.compile(r"^(fixture|brain|artifact|source|receipt):[A-Za-z0-9._:/-]+$")
FORMULA_STATUSES = {"KERNEL_ACCEPTED", "CONDITIONAL", "OPEN", "REFUTED", "NOT_EVALUATED"}
ABSTENTION_CODES = {
    "NONE", "MODEL_UNAVAILABLE", "EVIDENCE_NOT_ADMITTED", "EVIDENCE_INSUFFICIENT",
    "FORMULA_NAMESPACE_CONFLICT", "RECEIPT_INVALID", "POLICY_DENIED", "UNCERTAINTY_TOO_HIGH",
}
ANSWER_ABSTENTION_CODES = ABSTENTION_CODES - {"NONE", "MODEL_UNAVAILABLE"}
MAX_RETAINED_COMPLETION_CHARS = 8192


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


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def _resolve_beneath(root: Path, relative_path: Any, label: str) -> Path:
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise GateRefused(f"{label} path must be a non-empty relative path")
    path = Path(relative_path)
    if path.is_absolute():
        raise GateRefused(f"{label} path must not be absolute")
    resolved_root = root.resolve()
    resolved = (resolved_root / path).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise GateRefused(f"{label} path escapes its allowed root") from exc
    return resolved


def _resolve_repo(path: Any, repo: Path = REPO) -> Path:
    return _resolve_beneath(repo, path, "repository artifact")


def _verify_contract_assets(contract: dict[str, Any], repo: Path = REPO) -> tuple[Path, Path]:
    curriculum = contract.get("curriculum")
    if not isinstance(curriculum, dict):
        raise GateRefused("training contract lacks curriculum controls")
    source_path = _resolve_repo(curriculum.get("source"), repo)
    schema_path = _resolve_repo(curriculum.get("draft_schema"), repo)
    for label, path, expected in (
        ("curriculum source", source_path, curriculum.get("source_sha256")),
        ("draft schema", schema_path, curriculum.get("draft_schema_sha256")),
    ):
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise GateRefused(f"training contract lacks a pinned {label} digest")
        if not path.is_file() or sha256_file(path) != expected:
            raise GateRefused(f"pinned {label} digest mismatch")
    return source_path, schema_path


def validate_curriculum_source(source: dict[str, Any], contract: dict[str, Any]) -> None:
    expected_keys = {
        "schema_version", "owner", "license", "rights_basis", "profile_id", "notice",
        "train_scenarios", "eval_scenarios",
    }
    if set(source) != expected_keys:
        raise GateRefused("curriculum source has unknown or missing fields")
    if source.get("schema_version") != "szl.forge-curriculum-source.v1":
        raise GateRefused("curriculum source schema is unsupported")
    if (source.get("owner") != "SZL Holdings" or source.get("license") != "Apache-2.0" or
            source.get("rights_basis") != RIGHTS_BASIS or source.get("profile_id") != "ReceiptAgent-v1"):
        raise GateRefused("curriculum source lacks the pinned project-authored rights declaration")
    if not isinstance(source.get("notice"), str) or not source["notice"]:
        raise GateRefused("curriculum source requires a non-empty notice")

    seen_ids: set[str] = set()
    minimums = {
        "train_scenarios": contract["curriculum"]["minimum_train_rows"] // 3,
        "eval_scenarios": contract["curriculum"]["minimum_eval_rows"],
    }
    for section in ("train_scenarios", "eval_scenarios"):
        scenarios = source.get(section)
        if not isinstance(scenarios, list) or len(scenarios) < minimums[section]:
            raise GateRefused(f"{section} is below the contract minimum")
        for index, scenario in enumerate(scenarios):
            if not isinstance(scenario, dict):
                raise GateRefused(f"{section}[{index}] is not an object")
            kind = scenario.get("kind")
            expected = {"id", "kind", "prompt"}
            if kind in {"ANSWER", "TOOL"}:
                expected |= {"answer", "evidence", "uncertainty"}
                if kind == "TOOL":
                    expected.add("tool_id")
            elif kind in {"ABSTAIN", "UNAVAILABLE"}:
                expected.add("code")
            else:
                raise GateRefused(f"{section}[{index}] has unsupported kind")
            if set(scenario) != expected:
                raise GateRefused(f"{section}[{index}] has unknown or missing fields")
            scenario_id = scenario.get("id")
            if not isinstance(scenario_id, str) or IDENTIFIER_PATTERN.fullmatch(scenario_id) is None:
                raise GateRefused(f"{section}[{index}] has invalid id")
            if scenario_id in seen_ids:
                raise GateRefused("curriculum scenario ids must be unique across splits")
            seen_ids.add(scenario_id)
            prompt = scenario.get("prompt")
            if not isinstance(prompt, str) or not prompt or len(prompt) > 4096:
                raise GateRefused(f"{section}[{index}] has invalid prompt")
            if kind in {"ANSWER", "TOOL"}:
                answer = scenario.get("answer")
                evidence = scenario.get("evidence")
                if not isinstance(answer, str) or not answer or len(answer) > 4096:
                    raise GateRefused(f"{section}[{index}] has invalid answer")
                if (not isinstance(evidence, list) or not evidence or
                        any(not isinstance(item, str) or EVIDENCE_PATTERN.fullmatch(item) is None for item in evidence) or
                        len(evidence) != len(set(evidence))):
                    raise GateRefused(f"{section}[{index}] has invalid evidence identifiers")
                if scenario.get("uncertainty") not in {"LOW", "MEDIUM"}:
                    raise GateRefused(f"{section}[{index}] has invalid uncertainty")
                if kind == "TOOL":
                    tool_id = scenario.get("tool_id")
                    if not isinstance(tool_id, str) or IDENTIFIER_PATTERN.fullmatch(tool_id) is None:
                        raise GateRefused(f"{section}[{index}] has invalid tool id")
            elif kind == "UNAVAILABLE":
                if scenario.get("code") != "MODEL_UNAVAILABLE":
                    raise GateRefused(f"{section}[{index}] has invalid unavailable code")
            elif scenario.get("code") not in ANSWER_ABSTENTION_CODES:
                raise GateRefused(f"{section}[{index}] has invalid abstention code")


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
    """Dependency-light validation equivalent to the checked-in draft schema."""
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
    answer = value.get("answer")
    if answer is not None and not isinstance(answer, str):
        errors.append("answer must be text or null")
    evidence = value.get("evidence_ids")
    if not isinstance(evidence, list):
        errors.append("evidence_ids must be an array")
        evidence = []
    else:
        if any(not isinstance(item, str) or EVIDENCE_PATTERN.fullmatch(item) is None for item in evidence):
            errors.append("evidence_ids contain an invalid identifier")
        if len(evidence) != len(set(item for item in evidence if isinstance(item, str))):
            errors.append("evidence_ids must be unique")

    formula_refs = value.get("formula_refs")
    if not isinstance(formula_refs, list):
        errors.append("formula_refs must be an array")
        formula_refs = []
    else:
        seen_formula_refs: set[str] = set()
        for index, item in enumerate(formula_refs):
            if not isinstance(item, dict):
                errors.append(f"formula_refs[{index}] must be an object")
                continue
            expected_formula_keys = {"namespace", "formula_id", "claimed_status"}
            if set(item) != expected_formula_keys:
                errors.append(f"formula_refs[{index}] has invalid fields")
            namespace = item.get("namespace")
            formula_id = item.get("formula_id")
            if not isinstance(namespace, str) or IDENTIFIER_PATTERN.fullmatch(namespace) is None:
                errors.append(f"formula_refs[{index}] has invalid namespace")
            if not isinstance(formula_id, str) or IDENTIFIER_PATTERN.fullmatch(formula_id) is None:
                errors.append(f"formula_refs[{index}] has invalid formula_id")
            if item.get("claimed_status") not in FORMULA_STATUSES:
                errors.append(f"formula_refs[{index}] has invalid claimed_status")
            fingerprint = canonical_json(item)
            if fingerprint in seen_formula_refs:
                errors.append("formula_refs must be unique")
            seen_formula_refs.add(fingerprint)

    uncertainty = value.get("uncertainty")
    if not isinstance(uncertainty, dict):
        errors.append("uncertainty must be an object")
        uncertainty = {}
    else:
        if set(uncertainty) != {"band", "basis"}:
            errors.append("uncertainty has invalid fields")
        if uncertainty.get("band") not in {"LOW", "MEDIUM", "HIGH", "NOT_EVALUATED"}:
            errors.append("uncertainty has invalid band")
        if not isinstance(uncertainty.get("basis"), str) or not uncertainty.get("basis"):
            errors.append("uncertainty requires a non-empty basis")

    abstention = value.get("abstention")
    if not isinstance(abstention, dict):
        errors.append("abstention must be an object")
        abstention = {}
    else:
        if set(abstention) != {"required", "code", "detail"}:
            errors.append("abstention has invalid fields")
        if type(abstention.get("required")) is not bool:
            errors.append("abstention.required must be boolean")
        if abstention.get("code") not in ABSTENTION_CODES:
            errors.append("abstention has invalid code")
        if not isinstance(abstention.get("detail"), str) or not abstention.get("detail"):
            errors.append("abstention requires non-empty detail")

    tool = value.get("tool_proposal")
    if not isinstance(tool, dict):
        errors.append("tool_proposal must be an object")
        tool = {}
    else:
        if set(tool) != {"state", "tool_id", "arguments"}:
            errors.append("tool_proposal has invalid fields")
        state = tool.get("state")
        if state == "NONE":
            if tool.get("tool_id") is not None or tool.get("arguments") is not None:
                errors.append("NONE tool proposal must have null tool_id and arguments")
        elif state == "PROPOSED":
            tool_id = tool.get("tool_id")
            if not isinstance(tool_id, str) or IDENTIFIER_PATTERN.fullmatch(tool_id) is None:
                errors.append("PROPOSED tool requires a valid tool_id")
            if not isinstance(tool.get("arguments"), dict) or not tool.get("arguments"):
                errors.append("PROPOSED tool requires non-empty object arguments")
        else:
            errors.append("invalid tool_proposal state")

    if status == "ANSWER_PROPOSED":
        if not isinstance(answer, str) or not answer:
            errors.append("answer proposal requires text")
        if not evidence:
            errors.append("answer proposal requires evidence identifiers")
        if uncertainty.get("band") not in {"LOW", "MEDIUM"}:
            errors.append("answer proposal requires LOW or MEDIUM uncertainty")
        if abstention.get("required") is not False or abstention.get("code") != "NONE":
            errors.append("answer proposal cannot require abstention")
    elif status == "ABSTAINED":
        if answer is not None or evidence or formula_refs or abstention.get("required") is not True:
            errors.append("fail-closed status must have null answer, no references, and required abstention")
        if abstention.get("code") not in ANSWER_ABSTENTION_CODES:
            errors.append("abstention requires a fail-closed code")
        if uncertainty.get("band") != "HIGH":
            errors.append("abstention requires HIGH uncertainty")
        if tool.get("state") != "NONE":
            errors.append("abstention cannot propose a tool")
    elif status == "UNAVAILABLE":
        if answer is not None or evidence or formula_refs or abstention.get("required") is not True:
            errors.append("fail-closed status must have null answer, no references, and required abstention")
        if abstention.get("code") != "MODEL_UNAVAILABLE":
            errors.append("unavailable status requires MODEL_UNAVAILABLE")
        if uncertainty.get("band") != "NOT_EVALUATED":
            errors.append("unavailable status requires NOT_EVALUATED uncertainty")
        if tool.get("state") != "NONE":
            errors.append("unavailable status cannot propose a tool")

    if tool.get("state") == "PROPOSED" and status != "ANSWER_PROPOSED":
        errors.append("only an answer proposal can propose a tool")
    return errors


def _row(scenario: dict[str, Any], split: str, variant: int) -> dict[str, Any]:
    scenario_id = scenario["id"]
    prompt = f"{scenario['prompt']} Fixture variant {variant + 1}."
    assistant = canonical_json(_draft_for(scenario))
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
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
        "messages_sha256": sha256_bytes(canonical_json(messages).encode("utf-8")),
        "messages": messages,
    }


def build_curriculum(output_dir: Path = GENERATED) -> dict[str, Any]:
    contract = load_json(CONTRACT_PATH)
    source_path, schema_path = _verify_contract_assets(contract)
    source = load_json(source_path)
    validate_curriculum_source(source, contract)

    train_rows = [
        _row(scenario, "TRAIN", variant)
        for scenario in source["train_scenarios"]
        for variant in range(3)
    ]
    eval_rows = [_row(scenario, "EVAL", 0) for scenario in source["eval_scenarios"]]
    output_dir.mkdir(parents=True, exist_ok=True)
    train_path = output_dir / "train.jsonl"
    eval_path = output_dir / "eval.jsonl"
    atomic_text(train_path, "".join(canonical_json(row) + "\n" for row in train_rows))
    atomic_text(eval_path, "".join(canonical_json(row) + "\n" for row in eval_rows))
    manifest = {
        "schema_version": "szl.forge-curriculum-manifest.v1",
        "contract_id": "szl-forge-1.5b.receipt-agent-v1",
        "profile_id": "ReceiptAgent-v1",
        "state": "ADMITTED_PROJECT_AUTHORED_ONLY",
        "rights_basis": RIGHTS_BASIS,
        "source": {"path": contract["curriculum"]["source"], "sha256": sha256_file(source_path)},
        "draft_schema": {
            "path": contract["curriculum"]["draft_schema"],
            "sha256": sha256_file(schema_path),
        },
        "train": {"path": train_path.name, "rows": len(train_rows), "sha256": sha256_file(train_path)},
        "eval": {"path": eval_path.name, "rows": len(eval_rows), "sha256": sha256_file(eval_path)},
        "excluded_training_classes": ["BRAIN_RAW_NODE", "FORMULA_HOLDOUT", "HISTORICAL_UNREVIEWED_SEED", "ORPO_QUARANTINE", "THIRD_PARTY_TRACE"],
        "external_mutations": {"trained": False, "uploaded": False, "published": False, "deployed": False},
    }
    atomic_json(output_dir / "curriculum-manifest.json", manifest)
    validate_curriculum(manifest_path=output_dir / "curriculum-manifest.json", repo=REPO)
    return manifest


def validate_curriculum(manifest_path: Path = MANIFEST_PATH, repo: Path = REPO) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    contract = load_json(CONTRACT_PATH if repo == REPO else repo / "model_release/szl-forge/training-contract.json")
    source_path, schema_path = _verify_contract_assets(contract, repo)
    source = load_json(source_path)
    validate_curriculum_source(source, contract)
    expected_manifest_keys = {
        "schema_version", "contract_id", "profile_id", "state", "rights_basis", "source",
        "draft_schema", "train", "eval", "excluded_training_classes", "external_mutations",
    }
    if set(manifest) != expected_manifest_keys:
        raise GateRefused("curriculum manifest has unknown or missing fields")
    if (manifest.get("schema_version") != "szl.forge-curriculum-manifest.v1" or
            manifest.get("contract_id") != contract.get("contract_id") or
            manifest.get("profile_id") != contract.get("profile_id")):
        raise GateRefused("curriculum manifest identity mismatch")
    if manifest.get("state") != "ADMITTED_PROJECT_AUTHORED_ONLY" or manifest.get("rights_basis") != RIGHTS_BASIS:
        raise GateRefused("curriculum manifest is not project-authored and admitted")
    for key, expected_path, actual_path, expected_hash in (
        ("source", contract["curriculum"]["source"], source_path, contract["curriculum"]["source_sha256"]),
        ("draft_schema", contract["curriculum"]["draft_schema"], schema_path, contract["curriculum"]["draft_schema_sha256"]),
    ):
        entry = manifest.get(key)
        if (not isinstance(entry, dict) or set(entry) != {"path", "sha256"} or
                entry.get("path") != expected_path or entry.get("sha256") != expected_hash or
                sha256_file(actual_path) != expected_hash):
            raise GateRefused(f"curriculum manifest {key} binding mismatch")

    expected_rows = {
        "TRAIN": [_row(scenario, "TRAIN", variant) for scenario in source["train_scenarios"] for variant in range(3)],
        "EVAL": [_row(scenario, "EVAL", 0) for scenario in source["eval_scenarios"]],
    }

    prompt_hashes: dict[str, set[str]] = {"TRAIN": set(), "EVAL": set()}
    for split, key in (("TRAIN", "train"), ("EVAL", "eval")):
        entry = manifest.get(key)
        expected_filename = Path(contract["curriculum"][key.lower()]).name
        if not isinstance(entry, dict) or set(entry) != {"path", "rows", "sha256"}:
            raise GateRefused(f"{split} curriculum manifest entry is invalid")
        path = _resolve_beneath(manifest_path.parent, entry["path"], f"{split} curriculum")
        if entry.get("path") != expected_filename:
            raise GateRefused(f"{split} curriculum manifest entry is invalid")
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
            expected_roles = ("system", "user", "assistant")
            for message, role in zip(messages, expected_roles):
                if (not isinstance(message, dict) or set(message) != {"role", "content"} or
                        message.get("role") != role or not isinstance(message.get("content"), str)):
                    raise GateRefused(f"{split} row has invalid message structure")
            if messages[0]["content"] != SYSTEM_PROMPT:
                raise GateRefused(f"{split} row system policy mismatch")
            if row.get("prompt_sha256") != sha256_bytes(messages[1]["content"].encode("utf-8")):
                raise GateRefused(f"{split} row prompt hash mismatch")
            if row.get("target_sha256") != sha256_bytes(messages[2]["content"].encode("utf-8")):
                raise GateRefused(f"{split} row target hash mismatch")
            if row.get("messages_sha256") != sha256_bytes(canonical_json(messages).encode("utf-8")):
                raise GateRefused(f"{split} row messages hash mismatch")
            target = json.loads(messages[-1]["content"])
            errors = validate_draft(target)
            if errors:
                raise GateRefused(f"{split} row has invalid target: {'; '.join(errors)}")
        if [canonical_json(row) for row in rows] != [canonical_json(row) for row in expected_rows[split]]:
            raise GateRefused(f"{split} curriculum differs from the pinned project-authored source")

    if prompt_hashes["TRAIN"] & prompt_hashes["EVAL"]:
        raise GateRefused("train/eval prompt overlap detected")
    raw = (_resolve_beneath(manifest_path.parent, manifest["train"]["path"], "TRAIN curriculum").read_text(encoding="utf-8") +
           _resolve_beneath(manifest_path.parent, manifest["eval"]["path"], "EVAL curriculum").read_text(encoding="utf-8"))
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


@contextmanager
def training_mutex(path: Path = HERE / "queue-state" / "training.lock") -> Iterable[Path]:
    """Hold one process-wide training lease across admission, training, and reload."""
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a+b")
    stream.seek(0, os.SEEK_END)
    if stream.tell() == 0:
        stream.write(b"0")
        stream.flush()
    stream.seek(0)
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        stream.close()
        raise GateRefused("another SZL-Forge training process holds the exclusive lease") from exc
    try:
        yield path
    finally:
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()


class PythonNetworkDenied(OSError):
    """Raised when Python code attempts a network operation during training."""


@contextmanager
def deny_python_network() -> Iterable[dict[str, Any]]:
    """Deny Python socket connections in addition to framework offline flags.

    This is deliberately labeled as a Python-process control rather than an OS
    network namespace. Native extensions are outside this control and remain an
    explicit limitation in the receipt.
    """
    original_socket = socket.socket
    original_create_connection = socket.create_connection
    original_getaddrinfo = socket.getaddrinfo

    class DeniedSocket(original_socket):  # type: ignore[misc, valid-type]
        def connect(self, *args: Any, **kwargs: Any) -> Any:
            raise PythonNetworkDenied("network access is denied by the SZL-Forge runner")

        def connect_ex(self, *args: Any, **kwargs: Any) -> int:
            raise PythonNetworkDenied("network access is denied by the SZL-Forge runner")

    def denied(*args: Any, **kwargs: Any) -> Any:
        raise PythonNetworkDenied("network access is denied by the SZL-Forge runner")

    socket.socket = DeniedSocket
    socket.create_connection = denied
    socket.getaddrinfo = denied
    control = {
        "state": "PYTHON_SOCKET_DENIED",
        "framework_offline_flags": True,
        "os_network_namespace": "NOT_ESTABLISHED",
        "limitation": "Native extensions are not proven network-isolated by this Python-process control.",
    }
    try:
        yield control
    finally:
        socket.socket = original_socket
        socket.create_connection = original_create_connection
        socket.getaddrinfo = original_getaddrinfo


class RuntimeGuard:
    """Cooperative thermal and wall-clock watchdog for bounded local training."""

    def __init__(self, contract: dict[str, Any], query: Callable[[], dict[str, Any]] = query_gpu) -> None:
        training = contract["training"]
        self.maximum_seconds = int(training["maximum_wall_clock_seconds"])
        self.interval_seconds = int(training["watchdog_interval_seconds"])
        self.maximum_temperature_c = int(contract["gpu_admission"]["maximum_training_temperature_c"])
        self.query = query
        self.started_ns = time.time_ns()
        self.samples: list[dict[str, Any]] = []
        self.reason: str | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._watch, name="szl-forge-runtime-guard", daemon=True)

    def _watch(self) -> None:
        while not self._stop.is_set():
            try:
                sample = self.query()
                self.samples.append(sample)
                self.samples = self.samples[-256:]
                if sample["temperature_c"] > self.maximum_temperature_c:
                    self.reason = "training thermal ceiling exceeded"
                    return
            except Exception as exc:
                self.reason = f"runtime guard could not sample GPU: {type(exc).__name__}"
                return
            if self._stop.wait(self.interval_seconds):
                return

    def __enter__(self) -> "RuntimeGuard":
        self._thread.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self._stop.set()
        self._thread.join(timeout=max(1, self.interval_seconds + 1))

    def check(self, stage: str) -> None:
        elapsed = (time.time_ns() - self.started_ns) / 1_000_000_000
        if elapsed > self.maximum_seconds:
            self.reason = f"training wall-clock ceiling exceeded at {stage}"
        if self.reason:
            raise GateRefused(self.reason)

    def receipt(self) -> dict[str, Any]:
        return {
            "state": "TRIPPED" if self.reason else "PASS",
            "reason": self.reason,
            "maximum_wall_clock_seconds": self.maximum_seconds,
            "watchdog_interval_seconds": self.interval_seconds,
            "maximum_temperature_c": self.maximum_temperature_c,
            "cooperative_interrupt_only": True,
            "samples": self.samples,
        }


def _verify_base(base_snapshot: Path, contract: dict[str, Any]) -> list[dict[str, Any]]:
    if not base_snapshot.is_dir():
        raise GateRefused("operator-supplied immutable base snapshot is absent")
    identity_path = _resolve_repo(contract["base"]["identity_manifest"])
    identity = load_json(identity_path)
    identity_base = identity.get("base")
    if not isinstance(identity_base, dict):
        raise GateRefused("base identity manifest lacks a base object")
    for key in ("repository", "revision", "architecture", "license"):
        if identity_base.get(key) != contract["base"].get(key):
            raise GateRefused(f"base identity {key} does not match the training contract")
    files = identity_base.get("files")
    if not isinstance(files, list) or not files:
        raise GateRefused("base identity manifest has no file inventory")
    observed: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for item in files:
        if not isinstance(item, dict) or set(item) != {"path", "bytes", "sha256"}:
            raise GateRefused("base identity file entry is invalid")
        if item["path"] in seen_paths:
            raise GateRefused("base identity file paths must be unique")
        seen_paths.add(item["path"])
        path = _resolve_beneath(base_snapshot, item["path"], "base file")
        if not path.is_file():
            raise GateRefused(f"base file missing: {item['path']}")
        digest = sha256_file(path)
        if digest != item["sha256"] or path.stat().st_size != item["bytes"]:
            raise GateRefused(f"base file identity mismatch: {item['path']}")
        observed.append({"path": item["path"], "bytes": path.stat().st_size, "sha256": digest})
    return observed


def _collect_input_identity(base_snapshot: Path) -> dict[str, Any]:
    contract = load_json(CONTRACT_PATH)
    manifest = validate_curriculum()
    base_files = _verify_base(base_snapshot.resolve(), contract)
    identity_manifest = _resolve_repo(contract["base"]["identity_manifest"])
    train_path = _resolve_beneath(MANIFEST_PATH.parent, manifest["train"]["path"], "TRAIN curriculum")
    eval_path = _resolve_beneath(MANIFEST_PATH.parent, manifest["eval"]["path"], "EVAL curriculum")
    identity: dict[str, Any] = {
        "schema_version": "szl.forge-input-identity.v1",
        "contract_sha256": sha256_file(CONTRACT_PATH),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "curriculum_manifest_sha256": sha256_file(MANIFEST_PATH),
        "source_sha256": manifest["source"]["sha256"],
        "draft_schema_sha256": manifest["draft_schema"]["sha256"],
        "train": {"path": manifest["train"]["path"], "sha256": sha256_file(train_path), "rows": manifest["train"]["rows"]},
        "eval": {"path": manifest["eval"]["path"], "sha256": sha256_file(eval_path), "rows": manifest["eval"]["rows"]},
        "base_identity_manifest_sha256": sha256_file(identity_manifest),
        "base_files": base_files,
    }
    identity["identity_sha256"] = sha256_bytes(canonical_json(identity).encode("utf-8"))
    return identity


def _stage_inputs(base_snapshot: Path, output_dir: Path, receipt_dir: Path,
                  identity: dict[str, Any], contract: dict[str, Any]) -> tuple[Path, Path, Path]:
    inputs_dir = output_dir / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=False)
    required_free = int(contract["training"]["minimum_output_free_bytes"])
    if shutil.disk_usage(inputs_dir).free < required_free:
        raise GateRefused("output volume lacks the fixed free-space reserve for a private input snapshot")
    staged: dict[str, dict[str, Any]] = {}
    paths: dict[str, Path] = {}
    for key in ("train", "eval"):
        source = _resolve_beneath(MANIFEST_PATH.parent, identity[key]["path"], f"{key.upper()} curriculum")
        destination = inputs_dir / f"{key}.jsonl"
        shutil.copyfile(source, destination)
        digest = sha256_file(destination)
        if digest != identity[key]["sha256"]:
            raise GateRefused(f"staged {key} curriculum digest mismatch")
        destination.chmod(stat.S_IREAD)
        staged[key] = {"path": str(destination.relative_to(output_dir)).replace("\\", "/"), "sha256": digest, "rows": identity[key]["rows"]}
        paths[key] = destination
    staged_base = inputs_dir / "base"
    staged_base.mkdir(parents=True, exist_ok=False)
    staged_base_files: list[dict[str, Any]] = []
    for item in identity["base_files"]:
        source = _resolve_beneath(base_snapshot, item["path"], "base file")
        destination = _resolve_beneath(staged_base, item["path"], "staged base file")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        digest = sha256_file(destination)
        if digest != item["sha256"] or destination.stat().st_size != item["bytes"]:
            raise GateRefused(f"staged base file identity mismatch: {item['path']}")
        destination.chmod(stat.S_IREAD)
        staged_base_files.append({"path": item["path"], "bytes": destination.stat().st_size, "sha256": digest})
    receipt = {
        "schema_version": "szl.forge-input-snapshot-receipt.v1",
        "state": "PASS",
        "input_identity": identity,
        "staged_curriculum": staged,
        "staged_base_files": staged_base_files,
        "base_snapshot_strategy": "PRIVATE_HASH_VERIFIED_COPY",
        "base_snapshot_path_scope": "RUN_OUTPUT_RELATIVE:inputs/base",
    }
    atomic_json(receipt_dir / "input-snapshot-receipt.json", receipt)
    return staged_base, paths["train"], paths["eval"]


def _finalize_input_integrity(base_snapshot: Path, initial: dict[str, Any], receipt_dir: Path) -> dict[str, Any]:
    try:
        final = _collect_input_identity(base_snapshot)
    except Exception as exc:
        receipt = {
            "schema_version": "szl.forge-final-input-integrity-receipt.v1",
            "state": "FAIL",
            "initial_identity_sha256": initial["identity_sha256"],
            "final_identity_sha256": None,
            "reason": f"{type(exc).__name__}: {exc}",
        }
        atomic_json(receipt_dir / "final-input-integrity-receipt.json", receipt)
        raise GateRefused("training inputs could not be reverified; candidate is not promotable") from exc
    matched = final["identity_sha256"] == initial["identity_sha256"]
    receipt = {
        "schema_version": "szl.forge-final-input-integrity-receipt.v1",
        "state": "PASS" if matched else "FAIL",
        "initial_identity_sha256": initial["identity_sha256"],
        "final_identity_sha256": final["identity_sha256"],
        "final_identity": final,
    }
    atomic_json(receipt_dir / "final-input-integrity-receipt.json", receipt)
    if not matched:
        raise GateRefused("training inputs changed after admission; candidate is not promotable")
    return receipt


def preflight(base_snapshot: Path | None, check_gpu: bool, gpu_samples: int | None = None,
              query: Callable[[], dict[str, Any]] = query_gpu,
              sleeper: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    contract = load_json(CONTRACT_PATH)
    checks: list[dict[str, Any]] = []
    try:
        manifest = validate_curriculum()
        checks.append({
            "id": "CURRICULUM_ADMISSION", "state": "PASS",
            "manifest_sha256": sha256_file(MANIFEST_PATH),
            "contract_sha256": sha256_file(CONTRACT_PATH),
            "source_sha256": manifest["source"]["sha256"],
            "draft_schema_sha256": manifest["draft_schema"]["sha256"],
            "train_rows": manifest["train"]["rows"], "eval_rows": manifest["eval"]["rows"],
        })
        if base_snapshot is None:
            raise GateRefused("base snapshot must be supplied explicitly")
        base_files = _verify_base(base_snapshot.resolve(), contract)
        checks.append({
            "id": "IMMUTABLE_BASE", "state": "PASS",
            "identity_manifest_sha256": sha256_file(_resolve_repo(contract["base"]["identity_manifest"])),
            "files": base_files,
        })
        try:
            source_control = _git_identity(contract)
            checks.append({"id": "SOURCE_CONTROL", "state": "PASS", **source_control})
        except GateRefused as exc:
            checks.append({"id": "SOURCE_CONTROL", "state": "BLOCKED", "reason": str(exc)})
            raise
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


def _git_identity(contract: dict[str, Any]) -> dict[str, Any]:
    policy = contract.get("source_control")
    if not isinstance(policy, dict):
        raise GateRefused("training contract lacks source-control policy")
    explicit_git = os.environ.get(str(policy.get("git_executable_env", "")), "").strip()
    git = explicit_git or shutil.which("git")
    if not git:
        raise GateRefused("git is required on PATH or through the contract-declared environment variable")
    git_path = Path(git).expanduser().resolve()
    if not git_path.is_file():
        raise GateRefused("configured git executable is not a file")
    prefix = [str(git_path), "-c", f"safe.directory={REPO.resolve()}"]
    commit = subprocess.run(prefix + ["rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True)
    if commit.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", commit.stdout.strip()):
        raise GateRefused("training source commit could not be measured")
    if policy.get("require_clean_scope") is not True:
        raise GateRefused("training contract does not require a clean source scope")
    paths = policy.get("paths")
    if not isinstance(paths, list) or not paths or not all(isinstance(path, str) and path for path in paths):
        raise GateRefused("training contract lacks a source-control path scope")
    status = subprocess.run(
        prefix + ["status", "--porcelain=v1", "--untracked-files=all", "--", *paths],
        cwd=REPO, capture_output=True, text=True,
    )
    if status.returncode != 0:
        raise GateRefused("training source cleanliness could not be measured")
    if status.stdout:
        raise GateRefused("training-critical source scope is dirty; commit reviewed changes first")
    return {
        "state": "CLEAN_REVIEWED_COMMIT",
        "commit": commit.stdout.strip(),
        "git_executable_sha256": sha256_file(git_path),
        "required_clean_scope": paths,
        "status_sha256": sha256_bytes(status.stdout.encode("utf-8")),
    }


def verify_runtime_identity(
    torch_module: Any,
    contract: dict[str, Any],
    version_lookup: Callable[[str], str] = importlib.metadata.version,
    python_version: tuple[int, int, int] | None = None,
) -> dict[str, Any]:
    """Measure and enforce the runtime identity before any model load."""
    runtime = contract["runtime"]
    observed_python = python_version or (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)
    python_minor = f"{observed_python[0]}.{observed_python[1]}"
    if python_minor not in runtime["python_minor_allowlist"]:
        raise GateRefused(f"Python {python_minor} is outside the runtime allowlist")

    torch_version = str(torch_module.__version__)
    if torch_version not in runtime["torch_exact_allowlist"]:
        raise GateRefused(f"torch {torch_version} is outside the measured runtime allowlist")
    cuda_text = str(getattr(torch_module.version, "cuda", "") or "")
    match = re.match(r"^(\d+)\.(\d+)", cuda_text)
    if not match:
        raise GateRefused("torch does not report a CUDA runtime")
    cuda_tuple = (int(match.group(1)), int(match.group(2)))
    if cuda_tuple < tuple(runtime["minimum_cuda_runtime"]):
        raise GateRefused("CUDA runtime is below the Blackwell minimum")
    capability = tuple(int(value) for value in torch_module.cuda.get_device_capability())
    if capability < tuple(runtime["minimum_device_capability"]):
        raise GateRefused("GPU compute capability is below the training contract")
    device_name = str(torch_module.cuda.get_device_name())
    if device_name != runtime["required_device_name"]:
        raise GateRefused("GPU identity does not match the training contract")

    packages: dict[str, str] = {}
    for package, expected in runtime["package_exact"].items():
        observed = version_lookup(package)
        packages[package] = observed
        if observed != expected:
            raise GateRefused(f"{package} {observed} does not match pinned runtime {expected}")
    for package in runtime["package_required_measured"]:
        packages[package] = version_lookup(package)

    return {
        "schema_version": "szl.forge-runtime-identity.v1",
        "state": "PASS",
        "python": ".".join(str(value) for value in observed_python),
        "torch": torch_version,
        "cuda_runtime": cuda_text,
        "device_name": device_name,
        "device_capability": list(capability),
        "packages": packages,
        "policy": "MEASURED_AT_RUN_FAIL_CLOSED",
    }


def evaluate_draft_completion(completion: str, expected: dict[str, Any]) -> dict[str, Any]:
    value: Any = None
    try:
        value = json.loads(completion)
        errors = validate_draft(value)
    except Exception as exc:
        errors = [f"JSON_PARSE:{type(exc).__name__}"]
    retained = completion[:MAX_RETAINED_COMPLETION_CHARS]
    return {
        "output_sha256": sha256_bytes(completion.encode("utf-8")),
        "output_chars": len(completion),
        "retained_output": retained,
        "retained_output_truncated": len(retained) != len(completion),
        "draft_schema_valid": not errors,
        "exact_expected_match": not errors and canonical_json(value) == canonical_json(expected),
        "errors": errors,
    }


def _run_reload_evaluation(base_snapshot: Path, adapter_dir: Path, output_dir: Path,
                           eval_path: Path, max_length: int,
                           guard: RuntimeGuard | None = None) -> dict[str, Any]:
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
    tokenizer = AutoTokenizer.from_pretrained(str(base_snapshot), local_files_only=True, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(
        str(base_snapshot), local_files_only=True, quantization_config=quant, device_map="auto",
        trust_remote_code=False, use_safetensors=True,
    )
    model = PeftModel.from_pretrained(model, str(adapter_dir), is_trainable=False, local_files_only=True)
    model.eval()
    results: list[dict[str, Any]] = []
    for row in iter_jsonl(eval_path):
        if guard:
            guard.check(f"reload-evaluation:{row['record_id']}")
        prompt_messages = row["messages"][:-1]
        expected = json.loads(row["messages"][-1]["content"])
        text = tokenizer.apply_chat_template(prompt_messages, tokenize=False, add_generation_prompt=True)
        encoded = tokenizer(text, return_tensors="pt", truncation=True, max_length=max_length)
        encoded = {key: value.to(model.device) for key, value in encoded.items()}
        with torch.no_grad():
            generated = model.generate(**encoded, max_new_tokens=384, do_sample=False)
        completion = tokenizer.decode(generated[0][encoded["input_ids"].shape[1]:], skip_special_tokens=True).strip()
        result = evaluate_draft_completion(completion, expected)
        results.append({
            "record_id": row["record_id"],
            "expected_target_sha256": row["target_sha256"],
            **result,
        })
    schema_passed = sum(1 for result in results if result["draft_schema_valid"])
    semantic_passed = sum(1 for result in results if result["exact_expected_match"])
    receipt = {
        "schema_version": "szl.forge-reload-evaluation-receipt.v1",
        "state": "PASS" if semantic_passed == len(results) and bool(results) else "FAIL",
        "adapter_sha256_set": _file_inventory(adapter_dir),
        "eval_manifest_sha256": sha256_file(eval_path),
        "rows": len(results),
        "draft_schema_valid_rows": schema_passed,
        "draft_schema_valid_rate": schema_passed / len(results) if results else 0.0,
        "exact_expected_match_rows": semantic_passed,
        "exact_expected_match_rate": semantic_passed / len(results) if results else 0.0,
        "retained_output_policy": f"LOCAL_RECEIPT_ONLY_FIRST_{MAX_RETAINED_COMPLETION_CHARS}_CHARS_WITH_FULL_SHA256",
        "promotion_effect": "NONE_AUTOMATIC",
        "results": results,
    }
    atomic_json(output_dir / "reload-evaluation-receipt.json", receipt)
    return receipt


def _run_training_locked(base_snapshot: Path, output_dir: Path, confirmation: str) -> int:
    contract = load_json(CONTRACT_PATH)
    if confirmation != contract["training"]["confirmation_phrase"]:
        raise GateRefused("exact training confirmation phrase is required")
    source_control_before_admission = _git_identity(contract)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise GateRefused("output directory must be absent or empty; prior receipts are immutable")
    receipt_dir = output_dir / "receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    preflight_receipt = preflight(base_snapshot, check_gpu=True)
    atomic_json(receipt_dir / "preflight-receipt.json", preflight_receipt)
    if preflight_receipt["state"] != "PASS":
        return 3

    source_control = _git_identity(contract)
    if source_control != source_control_before_admission:
        raise GateRefused("training source identity changed during GPU admission")
    initial_identity = _collect_input_identity(base_snapshot)
    staged_base, staged_train, staged_eval = _stage_inputs(
        base_snapshot, output_dir, receipt_dir, initial_identity, contract,
    )

    try:
        post_stage_gpu = sample_gpu(contract["gpu_admission"], 1, 0)[0]
        atomic_json(receipt_dir / "gpu-load-admission-receipt.json", {
            "schema_version": "szl.forge-gpu-load-admission-receipt.v1",
            "state": "PASS",
            "stage": "AFTER_PRIVATE_INPUT_STAGING",
            "sample": post_stage_gpu,
        })
    except GPUAdmissionRefused as exc:
        atomic_json(receipt_dir / "gpu-load-admission-receipt.json", {
            "schema_version": "szl.forge-gpu-load-admission-receipt.v1",
            "state": "BLOCKED_BEFORE_MODEL_LOAD",
            "stage": "AFTER_PRIVATE_INPUT_STAGING",
            "reason": str(exc),
            "samples": exc.samples,
        })
        return 3

    os.environ.update({
        "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1", "WANDB_DISABLED": "true",
        "TOKENIZERS_PARALLELISM": "false", "HF_HUB_DISABLE_TELEMETRY": "1",
        "DO_NOT_TRACK": "1", "NO_PROXY": "*",
    })
    started_ns = time.time_ns()
    training_receipt: dict[str, Any] = {
        "schema_version": "szl.forge-training-receipt.v1",
        "contract_id": contract["contract_id"],
        "state": "RUNNING",
        "started_at_unix_ns": started_ns,
        "source_control": source_control,
        "contract_sha256": sha256_file(CONTRACT_PATH),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "curriculum_manifest_sha256": sha256_file(MANIFEST_PATH),
        "draft_schema_sha256": sha256_file(HERE / "schemas" / "receipt-agent-draft.schema.json"),
        "preflight_receipt_sha256": sha256_file(receipt_dir / "preflight-receipt.json"),
        "input_snapshot_receipt_sha256": sha256_file(receipt_dir / "input-snapshot-receipt.json"),
        "gpu_load_admission_receipt_sha256": sha256_file(receipt_dir / "gpu-load-admission-receipt.json"),
        "input_identity_sha256": initial_identity["identity_sha256"],
        "network_download_allowed": False,
        "upload_allowed": False,
    }
    atomic_json(receipt_dir / "training-receipt.json", training_receipt)
    with deny_python_network() as network_control, RuntimeGuard(contract) as guard:
        training_receipt["network_control"] = network_control
        atomic_json(receipt_dir / "training-receipt.json", training_receipt)
        try:
            import torch
            from datasets import Dataset
            from peft import LoraConfig
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainerCallback
            from trl import SFTConfig, SFTTrainer

            if not torch.cuda.is_available():
                raise GateRefused("CUDA disappeared after GPU admission")
            runtime_identity = verify_runtime_identity(torch, contract)
            training_receipt["runtime_identity"] = runtime_identity
            guard.check("runtime-identity")

            class ThermalGuard(TrainerCallback):
                def on_train_begin(self, args: Any, state: Any, control: Any, **kwargs: Any) -> Any:
                    guard.check("train-begin")
                    return control

                def on_step_begin(self, args: Any, state: Any, control: Any, **kwargs: Any) -> Any:
                    guard.check(f"step-{state.global_step}-begin")
                    return control

                def on_step_end(self, args: Any, state: Any, control: Any, **kwargs: Any) -> Any:
                    guard.check(f"step-{state.global_step}-end")
                    return control

            bf16 = bool(torch.cuda.is_bf16_supported())
            quant = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.bfloat16 if bf16 else torch.float16,
            )
            guard.check("before-model-load")
            preload_gpu = sample_gpu(contract["gpu_admission"], 1, 0)[0]
            training_receipt["immediate_preload_gpu_sample"] = preload_gpu
            atomic_json(receipt_dir / "training-receipt.json", training_receipt)
            tokenizer = AutoTokenizer.from_pretrained(
                str(staged_base), local_files_only=True, trust_remote_code=False,
            )
            model = AutoModelForCausalLM.from_pretrained(
                str(staged_base), local_files_only=True, quantization_config=quant, device_map="auto",
                trust_remote_code=False, use_safetensors=True,
            )
            guard.check("after-model-load")
            rows = list(iter_jsonl(staged_train))
            if len(rows) != initial_identity["train"]["rows"] or sha256_file(staged_train) != initial_identity["train"]["sha256"]:
                raise GateRefused("staged training curriculum changed after snapshot")
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
            trainer = SFTTrainer(
                model=model, processing_class=tokenizer, train_dataset=dataset,
                peft_config=lora, args=args, callbacks=[ThermalGuard()],
            )
            training_receipt.update({
                "state": "TRAINING_STARTED_NOT_PROMOTED",
                "training_started_at_unix_ns": time.time_ns(),
            })
            atomic_json(receipt_dir / "training-receipt.json", training_receipt)
            result = trainer.train()
            guard.check("after-training")
            if int(result.global_step) != int(train["max_steps"]):
                raise GateRefused("trainer did not complete the fixed step contract")
            adapter_dir = output_dir / "adapter"
            adapter_dir.mkdir(parents=True, exist_ok=True)
            trainer.model.save_pretrained(adapter_dir, safe_serialization=True)
            tokenizer.save_pretrained(adapter_dir)
            inventory = _file_inventory(adapter_dir)
            inventory_paths = {item["path"] for item in inventory}
            if "adapter_model.safetensors" not in inventory_paths or any(path.endswith(".bin") for path in inventory_paths):
                raise GateRefused("adapter artifact is not a safetensors-only package")
            atomic_json(receipt_dir / "adapter-files.json", {"schema_version": "szl.forge-adapter-files.v1", "files": inventory})
            training_receipt.update({
                "state": "TRAINING_COMPLETED_EVALUATION_REQUIRED",
                "training_completed_at_unix_ns": time.time_ns(),
                "global_steps": int(result.global_step),
                "training_loss": float(result.training_loss),
                "peak_vram_reserved_bytes": int(torch.cuda.max_memory_reserved()),
                "adapter_files_receipt_sha256": sha256_file(receipt_dir / "adapter-files.json"),
                "runtime_guard": guard.receipt(),
            })
            atomic_json(receipt_dir / "training-receipt.json", training_receipt)
            del trainer, model
            torch.cuda.empty_cache()
            reload_receipt = _run_reload_evaluation(
                staged_base, adapter_dir, receipt_dir, staged_eval,
                train["max_sequence_length"], guard,
            )
            final_integrity = _finalize_input_integrity(base_snapshot, initial_identity, receipt_dir)
            training_receipt["state"] = "CANDIDATE_GENERATED_NOT_PROMOTED" if reload_receipt["state"] == "PASS" else "EVALUATION_FAILED_NOT_PROMOTED"
            training_receipt["completed_at_unix_ns"] = time.time_ns()
            training_receipt["reload_evaluation_receipt_sha256"] = sha256_file(receipt_dir / "reload-evaluation-receipt.json")
            training_receipt["final_input_integrity_receipt_sha256"] = sha256_file(receipt_dir / "final-input-integrity-receipt.json")
            training_receipt["final_input_integrity_state"] = final_integrity["state"]
            training_receipt["runtime_guard"] = guard.receipt()
            training_receipt["promotion"] = "NOT_PROMOTED"
            atomic_json(receipt_dir / "training-receipt.json", training_receipt)
            return 0 if reload_receipt["state"] == "PASS" else 4
        except GPUAdmissionRefused as exc:
            if not (receipt_dir / "final-input-integrity-receipt.json").exists():
                try:
                    _finalize_input_integrity(base_snapshot, initial_identity, receipt_dir)
                except Exception:
                    pass
            training_receipt.update({
                "state": "GPU_RECHECK_BLOCKED_BEFORE_TRAINING",
                "completed_at_unix_ns": time.time_ns(),
                "error_type": type(exc).__name__, "error": str(exc),
                "gpu_recheck_samples": exc.samples,
                "runtime_guard": guard.receipt(),
                "promotion": "NOT_PROMOTED",
            })
            atomic_json(receipt_dir / "training-receipt.json", training_receipt)
            return 3
        except Exception as exc:
            if not (receipt_dir / "final-input-integrity-receipt.json").exists():
                try:
                    _finalize_input_integrity(base_snapshot, initial_identity, receipt_dir)
                except Exception:
                    pass
            training_receipt.update({
                "state": "FAILED_NOT_PROMOTED", "completed_at_unix_ns": time.time_ns(),
                "error_type": type(exc).__name__, "error": str(exc),
                "traceback_sha256": sha256_bytes(traceback.format_exc().encode("utf-8")),
                "runtime_guard": guard.receipt(),
                "promotion": "NOT_PROMOTED",
            })
            if (receipt_dir / "final-input-integrity-receipt.json").exists():
                training_receipt["final_input_integrity_receipt_sha256"] = sha256_file(receipt_dir / "final-input-integrity-receipt.json")
            atomic_json(receipt_dir / "training-receipt.json", training_receipt)
            raise


def run_training(base_snapshot: Path, output_dir: Path, confirmation: str) -> int:
    contract = load_json(CONTRACT_PATH)
    if confirmation != contract["training"]["confirmation_phrase"]:
        raise GateRefused("exact training confirmation phrase is required")
    with training_mutex():
        return _run_training_locked(base_snapshot, output_dir, confirmation)


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
            with training_mutex():
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
        return 5 if args.command == "train" else 3


if __name__ == "__main__":
    raise SystemExit(main())
