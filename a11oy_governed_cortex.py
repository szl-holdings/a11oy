# SPDX-License-Identifier: Apache-2.0
"""A11oy local owned-model governed inference cortex.

This module wires the existing A11oy public Second Brain, the canonical formal
formula authority, the exact szl-nemo E1-E10/R1-R5 witness, and the owned Khipu
GGUF into one proposal-only CPU inference path. It never grants tool or action
authority and never persists prompt, evidence text, model output, or private
reasoning.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import re
import threading
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = "szl.a11oy.owned-khipu-cortex/v1"
HEALTH_SCHEMA = "szl.a11oy.owned-khipu-cortex-health/v1"
CONTRACT_SCHEMA = "szl.a11oy.owned-khipu-cortex-contract/v1"
RESPONSE_SCHEMA = "szl.a11oy.owned-khipu-cortex-response/v1"
RECEIPT_SCHEMA = "szl.a11oy.owned-khipu-cortex-receipt/v1"
ANATOMY_SCHEMA = "szl.anatomy.ephemeral-owned-inference/v1"
MODEL_REPOSITORY = "SZLHOLDINGS/SZL-Khipu-1.5B-GGUF"
MODEL_REVISION = "67d60ec577730747055491640cfb91fc4a4b5d25"
MODEL_FILENAME = "SZL-Khipu-1.5B-Q4_K_M.gguf"
MODEL_SHA256 = "13c1a1993063e1dff92f7413ccf48eaca6d48efc8801ae9af35961ae3396623a"
MODEL_SIZE = 986_047_904
NEMO_REVISION = "810231a531188bb569e3faa17396386eb0a5e260"
NEMO_VERSION = "0.4.0"
LOCKED_FORMULAS = ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")
MAX_PROMPT_CHARS = 4_000
MAX_NEW_TOKENS = 128
MAX_EVIDENCE = 4
GENERATION_QUEUE_SECONDS = 2.0
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
RESERVED_TOKENS = ("<|im_start|>", "<|im_end|>", "<s>", "</s>")

_MODEL_LOCK = threading.Lock()
_GENERATION_LOCK = threading.Lock()
_ANATOMY_LOCK = threading.Lock()
_MODEL: Any | None = None
_MODEL_IDENTITY: dict[str, Any] | None = None
_MODEL_ERROR: str | None = None
_ANATOMY = {"observation_count": 0, "last": None}


class CortexBoundaryError(RuntimeError):
    def __init__(self, code: str, status: int = 503):
        super().__init__(code)
        self.code = code
        self.status = status


class GovernedInferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=MAX_PROMPT_CHARS)
    max_new_tokens: int = Field(default=64, ge=16, le=MAX_NEW_TOKENS)
    k: int = Field(default=3, ge=1, le=MAX_EVIDENCE)

    @field_validator("prompt")
    @classmethod
    def normalize_prompt(cls, value: str) -> str:
        clean = value.strip()
        if not clean or "\x00" in clean:
            raise ValueError("prompt must contain visible text and no NUL bytes")
        if any(token in clean for token in RESERVED_TOKENS):
            raise ValueError("prompt contains a reserved chat control token")
        return clean


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def source_revision() -> str | None:
    for key in ("SZL_GIT_SHA", "A11OY_GIT_SHA", "GITHUB_SHA"):
        value = (os.environ.get(key) or "").strip().lower()
        if FULL_SHA_RE.fullmatch(value):
            return value
    return None


def model_path() -> Path:
    configured = (os.environ.get("A11OY_KHIPU_GGUF") or "").strip()
    if configured:
        return Path(configured)
    legacy = (os.environ.get("A11OY_ALLOY_GGUF") or "").strip()
    if legacy and Path(legacy).name == MODEL_FILENAME:
        return Path(legacy)
    return Path("/app/models") / MODEL_FILENAME


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_model_artifact(path: Path | None = None) -> dict[str, Any]:
    selected = path or model_path()
    if not selected.is_file() or selected.is_symlink():
        raise CortexBoundaryError("owned_model_artifact_missing")
    size = selected.stat().st_size
    if size != MODEL_SIZE:
        raise CortexBoundaryError("owned_model_size_mismatch")
    digest = _hash_file(selected)
    if digest != MODEL_SHA256:
        raise CortexBoundaryError("owned_model_sha256_mismatch")
    return {
        "repository": MODEL_REPOSITORY,
        "revision": MODEL_REVISION,
        "filename": MODEL_FILENAME,
        "sha256": digest,
        "size": size,
        "path": str(selected),
        "state": "VERIFIED",
    }


def _load_formula_authority() -> dict[str, Any]:
    try:
        import szl_formula_registry as registry

        document = registry.load_registry(verify=True)
        payload = document["payload"]
    except Exception as exc:
        raise CortexBoundaryError(
            f"formula_authority_unavailable:{type(exc).__name__}"
        ) from exc
    if tuple(payload.get("locked_proven_ids") or ()) != LOCKED_FORMULAS:
        raise CortexBoundaryError("formula_locked_set_drift")
    if payload.get("locked_proven_count") != len(LOCKED_FORMULAS):
        raise CortexBoundaryError("formula_locked_count_drift")
    lambda_rule = payload.get("lambda") or {}
    if (
        lambda_rule.get("formula_id") != "F23"
        or lambda_rule.get("status") != "CONJECTURE_1_ADVISORY"
        or lambda_rule.get("can_authorize") is not False
        or lambda_rule.get("can_be_sole_allow_basis") is not False
    ):
        raise CortexBoundaryError("lambda_authority_drift")
    return {
        "registry_digest": document["registry_digest"]["value"],
        "formal_source_repository": payload["formal_source"]["repository"],
        "formal_source_commit": payload["formal_source"]["commit"],
        "kernel_source_repository": payload["kernel_source"]["repository"],
        "kernel_source_commit": payload["kernel_source"]["commit"],
        "f_id_to_callable_mapping": payload["kernel_source"][
            "f_id_to_callable_mapping"
        ],
        "locked_proven_count": payload["locked_proven_count"],
        "locked_proven_ids": list(payload["locked_proven_ids"]),
        "lambda": deepcopy(lambda_rule),
        "policy": deepcopy(payload["policy"]),
    }


def _load_nemo() -> Any:
    try:
        import szl_nemo
    except Exception as exc:
        raise CortexBoundaryError(f"nemo_unavailable:{type(exc).__name__}") from exc
    if getattr(szl_nemo, "__version__", None) != NEMO_VERSION:
        raise CortexBoundaryError("nemo_version_drift")
    if tuple(szl_nemo.LOCKED_PROVEN_FORMULA_IDS) != LOCKED_FORMULAS:
        raise CortexBoundaryError("nemo_locked_set_drift")
    return szl_nemo


def _hardware_fingerprint(artifact: Mapping[str, Any]) -> str:
    return "sha256:" + canonical_sha256(
        {
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "model_sha256": artifact["sha256"],
            "model_size": artifact["size"],
            "threads": max(1, min(int(os.environ.get("A11OY_KHIPU_THREADS", "2")), 4)),
        }
    )


def _load_model() -> tuple[Any, dict[str, Any]]:
    global _MODEL, _MODEL_IDENTITY, _MODEL_ERROR
    if _MODEL is not None and _MODEL_IDENTITY is not None:
        return _MODEL, deepcopy(_MODEL_IDENTITY)
    with _MODEL_LOCK:
        if _MODEL is not None and _MODEL_IDENTITY is not None:
            return _MODEL, deepcopy(_MODEL_IDENTITY)
        try:
            artifact = verify_model_artifact()
            import llama_cpp

            version = importlib.metadata.version("llama-cpp-python")
            threads = max(
                1,
                min(int(os.environ.get("A11OY_KHIPU_THREADS", "2")), 4),
            )
            model = llama_cpp.Llama(
                model_path=artifact["path"],
                n_ctx=2048,
                n_batch=128,
                n_threads=threads,
                n_threads_batch=threads,
                seed=17,
                use_mmap=True,
                use_mlock=False,
                logits_all=False,
                embedding=False,
                verbose=False,
            )
            revision = source_revision()
            if revision is None:
                raise CortexBoundaryError("source_revision_unavailable")
            identity = {
                "model": {
                    "id": f"{MODEL_REPOSITORY}/{MODEL_FILENAME}",
                    "repository": MODEL_REPOSITORY,
                    "revision": MODEL_REVISION,
                    "filename": MODEL_FILENAME,
                    "sha256": MODEL_SHA256,
                    "size": MODEL_SIZE,
                    "adapter_revision": "none",
                    "tokenizer_revision": MODEL_REVISION,
                    "template_revision": revision,
                    "ownership": "SZL_HOLDINGS_OWNED_ARTIFACT",
                },
                "runtime": {
                    "engine": "llama-cpp-python",
                    "version": version,
                    "library_version": getattr(llama_cpp, "__version__", version),
                    "hardware_fingerprint": _hardware_fingerprint(artifact),
                    "device": "CPU",
                    "threads": threads,
                },
                "artifact": artifact,
            }
            _MODEL = model
            _MODEL_IDENTITY = identity
            _MODEL_ERROR = None
            return _MODEL, deepcopy(_MODEL_IDENTITY)
        except CortexBoundaryError as exc:
            _MODEL_ERROR = exc.code
            raise
        except Exception as exc:
            _MODEL_ERROR = f"{type(exc).__name__}"
            raise CortexBoundaryError(
                f"owned_model_runtime_unavailable:{type(exc).__name__}"
            ) from exc


def _safe_fragment(value: Any, limit: int = 400) -> str:
    text = " ".join(str(value or "").replace("\x00", " ").split())
    for token in RESERVED_TOKENS:
        text = text.replace(token, "[reserved-token]")
    return text[:limit]


def _brain_evidence(prompt: str, k: int) -> dict[str, Any]:
    try:
        import szl_brain_api

        index = szl_brain_api.get_index("a11oy")
        result = index.ask(prompt, k=k)
        stats = index.stats()
    except Exception as exc:
        raise CortexBoundaryError(
            f"second_brain_unavailable:{type(exc).__name__}"
        ) from exc
    grounding = result.get("grounding_subgraph") or {}
    raw_nodes = grounding.get("nodes") or []
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise CortexBoundaryError("second_brain_returned_no_grounding")
    projections: list[dict[str, Any]] = []
    for raw in raw_nodes[:MAX_EVIDENCE]:
        if not isinstance(raw, Mapping):
            continue
        node_id = _safe_fragment(raw.get("id"), 160)
        if not node_id:
            continue
        source = _safe_fragment(
            raw.get("url") or raw.get("source") or raw.get("kind") or "a11oy-brain",
            500,
        )
        public_projection = {
            "node_id": node_id,
            "title": _safe_fragment(raw.get("title") or node_id, 500),
            "kind": _safe_fragment(raw.get("kind"), 100) or None,
            "source": source,
            "url": _safe_fragment(raw.get("url"), 500) or None,
            "formula_id": _safe_fragment(raw.get("formula_id"), 32) or None,
            "proof_status": _safe_fragment(raw.get("proof_status"), 100) or None,
            "node_label": _safe_fragment(raw.get("node_label"), 100) or None,
            "ppr": raw.get("ppr") if isinstance(raw.get("ppr"), (int, float)) else None,
        }
        projection_text = canonical_bytes(public_projection).decode("utf-8")
        projections.append(
            {
                **public_projection,
                "projection_text": projection_text,
                "sha256": text_sha256(projection_text),
            }
        )
    if not projections:
        raise CortexBoundaryError("second_brain_returned_no_usable_handles")
    return {
        "state": "READY",
        "retrieval": result.get("retrieval"),
        "content_access": "PUBLIC_PROJECTION_HANDLES_ONLY",
        "private_graph_present": False,
        "node_count": stats.get("node_count"),
        "content_hash": getattr(index, "content_hash", None),
        "query_latency": result.get("query_latency"),
        "items": projections,
    }


def _formula_binding(
    authority: Mapping[str, Any],
    *,
    prompt_sha256: str,
    evidence_set_sha256: str,
) -> dict[str, Any]:
    basis = {
        "formula_id": "F1",
        "purpose": "canonical request/evidence/receipt replay identity",
        "prompt_sha256": prompt_sha256,
        "evidence_set_sha256": evidence_set_sha256,
        "registry_digest": authority["registry_digest"],
    }
    return {
        "locked_proven_ids": list(authority["locked_proven_ids"]),
        "locked_proven_count": authority["locked_proven_count"],
        "formal_source_repository": authority["formal_source_repository"],
        "formal_source_commit": authority["formal_source_commit"],
        "kernel_source_repository": authority["kernel_source_repository"],
        "kernel_source_commit": authority["kernel_source_commit"],
        "f_id_to_callable_mapping": authority["f_id_to_callable_mapping"],
        "requested_formula_ids": ["F1"],
        "authorization_basis_ids": [],
        "applications": [
            {
                "formula_id": "F1",
                "applicability": "APPLIES",
                "basis_sha256": canonical_sha256(basis),
                "scope": "REPLAY_HASH_DETERMINISM_ONLY",
                "can_authorize_action": False,
            }
        ],
        "lambda": deepcopy(authority["lambda"]),
    }


def _scope() -> dict[str, Any]:
    policy = {
        "principal": "public-anonymous",
        "tenant": "public",
        "access": "PUBLIC_A11OY_BRAIN_PROJECTION_ONLY",
        "model_authority": "PROPOSAL_ONLY",
        "tools": False,
    }
    return {
        "principal_id_sha256": text_sha256("public-anonymous"),
        "tenant_id_sha256": text_sha256("public"),
        "access_decision": "ALLOW",
        "policy_revision": "sha256:" + canonical_sha256(policy),
    }


def _nemo_envelope(
    *,
    stage: str,
    identity: Mapping[str, Any],
    evidence: Mapping[str, Any],
    formulas: Mapping[str, Any],
    claims: list[dict[str, Any]],
) -> dict[str, Any]:
    items = [
        {
            "node_id": item["node_id"],
            "source": item["source"],
            "sha256": item["sha256"],
        }
        for item in evidence["items"]
    ]
    return {
        "schema": "szl.nemo.inference-envelope.v1",
        "stage": stage,
        "witness_identity": {
            "artifact_kind": "SOFTWARE_KERNEL",
            "generative": False,
            "not_nemotron": True,
        },
        "model": {
            "id": identity["model"]["id"],
            "revision": identity["model"]["revision"],
            "adapter_revision": identity["model"]["adapter_revision"],
            "tokenizer_revision": identity["model"]["tokenizer_revision"],
            "template_revision": identity["model"]["template_revision"],
        },
        "runtime": {
            "engine": identity["runtime"]["engine"],
            "version": identity["runtime"]["version"],
            "hardware_fingerprint": identity["runtime"]["hardware_fingerprint"],
        },
        "scope": _scope(),
        "evidence": {
            "content_access": "HANDLES_ONLY",
            "grounding_required": True,
            "handles": [{"nodeId": item["node_id"]} for item in items],
            "items": items,
            "evidence_set_sha256": canonical_sha256(items),
        },
        "formulas": {
            "locked_proven_ids": formulas["locked_proven_ids"],
            "locked_proven_count": formulas["locked_proven_count"],
            "formal_source_repository": formulas["formal_source_repository"],
            "formal_source_commit": formulas["formal_source_commit"],
            "kernel_source_repository": formulas["kernel_source_repository"],
            "kernel_source_commit": formulas["kernel_source_commit"],
            "f_id_to_callable_mapping": formulas["f_id_to_callable_mapping"],
            "requested_formula_ids": formulas["requested_formula_ids"],
            "authorization_basis_ids": formulas["authorization_basis_ids"],
            "applications": [
                {
                    "formula_id": item["formula_id"],
                    "applicability": item["applicability"],
                    "basis_sha256": item["basis_sha256"],
                }
                for item in formulas["applications"]
            ],
            "lambda": formulas["lambda"],
        },
        "authority": {
            "model_authority": "PROPOSAL_ONLY",
            "executed": False,
            "execution_authority": "NONE",
        },
        "witness_history": [] if stage == "PRE_GENERATION" else ["PRE_GENERATION"],
        "claims": claims,
    }


def _decision_dict(decision: Any) -> dict[str, Any]:
    if hasattr(decision, "to_dict"):
        value = decision.to_dict()
    else:
        value = {
            "decision": getattr(decision, "decision", None),
            "violated_rules": list(getattr(decision, "violated_rules", ())),
            "rule_version": getattr(decision, "rule_version", None),
            "input_hash": getattr(decision, "input_hash", None),
            "reasons": list(getattr(decision, "reasons", ())),
        }
    return {
        "decision": str(value.get("decision") or ""),
        "violated_rules": [str(item) for item in value.get("violated_rules") or ()],
        "rule_version": str(value.get("rule_version") or ""),
        "input_hash": str(value.get("input_hash") or ""),
        "reasons": [str(item) for item in value.get("reasons") or ()],
    }


def _compose_messages(
    prompt: str,
    evidence: Mapping[str, Any],
    formulas: Mapping[str, Any],
) -> list[dict[str, str]]:
    rows = []
    for item in evidence["items"]:
        rows.append(
            f"[{item['node_id']}] title={item['title']}; kind={item['kind']}; "
            f"source={item['source']}; proof_status={item['proof_status']}; "
            f"label={item['node_label']}"
        )
    system = (
        "You are the local SZL Khipu proposal cortex inside A11oy. Answer only "
        "from the supplied public evidence projections and cite supporting node "
        "IDs in square brackets. If evidence is insufficient, state that plainly. "
        "Do not expose hidden reasoning. Do not issue tool calls or claim that an "
        "action was executed. Lambda is Conjecture 1, advisory, and cannot "
        "authorize action. Never call Lambda a theorem, proven, certified, or "
        "guaranteed. Never claim perfect or 100% trust. If asked about model "
        "training, disclose that SZL fine-tuned Khipu from Qwen2.5-1.5B-Instruct "
        "and did not train a foundation model from scratch. Label benchmark or "
        "numeric performance claims MEASURED, REPORTED, MODELED, HEURISTIC, "
        "UNKNOWN, or UNAVAILABLE. Return only the final proposal."
    )
    user = (
        f"Operator request:\n{prompt}\n\n"
        "Authorized evidence projections:\n"
        + "\n".join(rows)
        + "\n\nFormula applicability: F1 applies only to deterministic replay "
        "hashing for this request. The other locked formulas are authority "
        "metadata and are not asserted applicable. No formula independently "
        "authorizes action.\n\nReturn a concise evidence-cited proposal."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _sanitize_output(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.I)
    text = re.sub(r"<analysis>[\s\S]*?</analysis>", "", text, flags=re.I)
    text = re.sub(r"```analysis[\s\S]*?```", "", text, flags=re.I)
    text = text.replace("\x00", " ").strip()
    if not text:
        raise CortexBoundaryError("owned_model_returned_empty_output", 502)
    return text[:24_000]


def _extract_output(result: Any) -> str:
    if not isinstance(result, Mapping):
        raise CortexBoundaryError("owned_model_response_invalid", 502)
    choices = result.get("choices")
    if not isinstance(choices, list) or not choices:
        raise CortexBoundaryError("owned_model_response_invalid", 502)
    message = choices[0].get("message") if isinstance(choices[0], Mapping) else None
    if not isinstance(message, Mapping):
        raise CortexBoundaryError("owned_model_response_invalid", 502)
    tool_calls = message.get("tool_calls")
    if isinstance(tool_calls, list) and tool_calls:
        raise CortexBoundaryError("owned_model_attempted_tool_call", 502)
    return _sanitize_output(message.get("content"))


def _generate(
    prompt: str,
    evidence: Mapping[str, Any],
    formulas: Mapping[str, Any],
    max_new_tokens: int,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    model, identity = _load_model()
    acquired = _GENERATION_LOCK.acquire(timeout=GENERATION_QUEUE_SECONDS)
    if not acquired:
        raise CortexBoundaryError("owned_model_busy", 429)
    started = time.perf_counter_ns()
    try:
        result = model.create_chat_completion(
            messages=_compose_messages(prompt, evidence, formulas),
            max_tokens=max_new_tokens,
            temperature=0.15,
            top_p=0.9,
            repeat_penalty=1.05,
            stream=False,
        )
    except Exception as exc:
        raise CortexBoundaryError(
            f"owned_model_generation_failed:{type(exc).__name__}", 502
        ) from exc
    finally:
        _GENERATION_LOCK.release()
    elapsed_ms = round((time.perf_counter_ns() - started) / 1_000_000, 3)
    output = _extract_output(result)
    usage = result.get("usage") if isinstance(result, Mapping) else None
    metrics = {
        "generation_latency": {
            "label": "MEASURED",
            "value_ms": elapsed_ms,
            "scope": "in-process llama.cpp create_chat_completion call",
        },
        "prompt_tokens": usage.get("prompt_tokens") if isinstance(usage, Mapping) else None,
        "completion_tokens": usage.get("completion_tokens") if isinstance(usage, Mapping) else None,
        "token_counts_label": "MEASURED" if isinstance(usage, Mapping) else "UNAVAILABLE",
    }
    return output, identity, metrics


def _extract_citations(output: str, evidence: Mapping[str, Any]) -> list[str]:
    allowed = {item["node_id"] for item in evidence["items"]}
    found: list[str] = []
    for candidate in re.findall(r"\[([^\[\]]{1,160})\]", output):
        if candidate in allowed and candidate not in found:
            found.append(candidate)
    return found


def _observe_anatomy(event: Mapping[str, Any]) -> dict[str, Any]:
    forbidden = {"prompt", "answer", "content", "raw_prompt", "raw_answer", "private_graph"}
    serialized = canonical_bytes(dict(event)).decode("utf-8")
    if any(f'"{key}"' in serialized for key in forbidden):
        raise CortexBoundaryError("unsafe_anatomy_observation", 500)
    with _ANATOMY_LOCK:
        _ANATOMY["observation_count"] += 1
        _ANATOMY["last"] = deepcopy(dict(event))
        return {
            "observation_count": _ANATOMY["observation_count"],
            "last": deepcopy(_ANATOMY["last"]),
        }


def _headers() -> dict[str, str]:
    revision = source_revision()
    return {
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "X-SZL-Governed-Inference": "owned-khipu-v1",
        "X-SZL-Source-Revision": revision or "unavailable",
        "X-SZL-Model-Revision": MODEL_REVISION,
        "X-SZL-Nemo-Revision": NEMO_REVISION,
    }


def _error(code: str, status: int) -> JSONResponse:
    return JSONResponse(
        {
            "schema": "szl.a11oy.owned-khipu-cortex-error/v1",
            "error": code,
            "state": "UNAVAILABLE",
            "executed": False,
            "tool_execution": False,
            "authority_state": "NO_ACTION_AUTHORITY",
        },
        status_code=status,
        headers=_headers(),
    )


def health_payload(*, load_model: bool = True) -> tuple[dict[str, Any], int]:
    revision = source_revision()
    checks: dict[str, Any] = {
        "source_revision": {
            "state": "READY" if revision else "UNAVAILABLE",
            "revision": revision,
        }
    }
    ready = revision is not None
    try:
        formula = _load_formula_authority()
        checks["formula_authority"] = {
            "state": "READY",
            "registry_digest": formula["registry_digest"],
            "locked_proven_count": formula["locked_proven_count"],
            "locked_proven_ids": formula["locked_proven_ids"],
            "lambda": formula["lambda"],
        }
    except CortexBoundaryError as exc:
        ready = False
        checks["formula_authority"] = {"state": "UNAVAILABLE", "error": exc.code}
    try:
        nemo = _load_nemo()
        checks["nemo"] = {
            "state": "READY",
            "version": nemo.__version__,
            "revision": NEMO_REVISION,
            "envelope_rules": nemo.ENVELOPE_RULE_VERSION,
            "text_rules": "doctrine-v11/R1-R5",
        }
    except CortexBoundaryError as exc:
        ready = False
        checks["nemo"] = {"state": "UNAVAILABLE", "error": exc.code}
    try:
        probe = _brain_evidence("Lambda proof status", 1)
        checks["second_brain"] = {
            "state": "READY",
            "node_count": probe["node_count"],
            "content_hash": probe["content_hash"],
            "content_access": probe["content_access"],
            "private_graph_present": False,
            "probe_handle_count": len(probe["items"]),
        }
    except CortexBoundaryError as exc:
        ready = False
        checks["second_brain"] = {"state": "UNAVAILABLE", "error": exc.code}
    try:
        if load_model:
            _, identity = _load_model()
        else:
            artifact = verify_model_artifact()
            identity = {"artifact": artifact, "runtime": {"state": "NOT_LOADED"}}
        checks["owned_model"] = {
            "state": "READY" if load_model else "ARTIFACT_VERIFIED",
            "repository": MODEL_REPOSITORY,
            "revision": MODEL_REVISION,
            "filename": MODEL_FILENAME,
            "sha256": MODEL_SHA256,
            "size": MODEL_SIZE,
            "runtime": identity.get("runtime"),
        }
    except CortexBoundaryError as exc:
        ready = False
        checks["owned_model"] = {
            "state": "UNAVAILABLE",
            "error": exc.code,
            "last_error": _MODEL_ERROR,
        }
    payload = {
        "schema": HEALTH_SCHEMA,
        "status": "READY" if ready else "UNAVAILABLE",
        "source_revision": revision,
        "checks": checks,
        "model_kind": "OWNED_KHIPU_GGUF_LOCAL_CPU",
        "model_repository": MODEL_REPOSITORY,
        "model_revision": MODEL_REVISION,
        "tools": False,
        "executed": False,
        "action_authority": "NONE",
        "receipt_persistence": "EPHEMERAL_PROCESS_MEMORY_ONLY",
    }
    return payload, 200 if ready else 503


def contract_payload() -> dict[str, Any]:
    revision = source_revision()
    return {
        "schema": CONTRACT_SCHEMA,
        "version": "1.0.0",
        "source_repository": "szl-holdings/a11oy",
        "source_revision": revision,
        "endpoints": {
            "health": "/api/v2/governed-health",
            "contract": "/api/v2/governed-contract",
            "infer": "/api/v2/governed-infer",
            "anatomy_last": "/api/v2/anatomy/last",
        },
        "model": {
            "kind": "OWNED_KHIPU_GGUF_LOCAL_CPU",
            "repository": MODEL_REPOSITORY,
            "revision": MODEL_REVISION,
            "filename": MODEL_FILENAME,
            "sha256": MODEL_SHA256,
            "size": MODEL_SIZE,
            "lineage": "SZL fine-tune of Qwen/Qwen2.5-1.5B-Instruct; not a foundation model trained from scratch",
        },
        "second_brain": {
            "implementation": "szl_brain_api.BrainIndex.ask",
            "retrieval": "HippoRAG-style PPR plus GraphRAG community context",
            "content_access": "PUBLIC_PROJECTION_HANDLES_ONLY",
            "private_graph_allowed": False,
        },
        "formula_authority": {
            "implementation": "szl_formula_registry",
            "locked_proven_count": len(LOCKED_FORMULAS),
            "locked_proven_ids": list(LOCKED_FORMULAS),
            "applicability": "EVIDENCE_BOUND_PER_REQUEST",
            "f_id_to_callable_mapping": "UNKNOWN_NOT_ASSERTED",
            "lambda": {
                "formula_id": "F23",
                "status": "CONJECTURE_1_ADVISORY",
                "can_authorize": False,
                "can_be_sole_allow_basis": False,
            },
        },
        "nemo": {
            "package": "szl-nemo",
            "version": NEMO_VERSION,
            "revision": NEMO_REVISION,
            "envelope_rules": "doctrine-v11/E1-E10",
            "text_rules": "doctrine-v11/R1-R5",
            "generative": False,
            "not_nemotron": True,
        },
        "authority": {
            "model_authority": "PROPOSAL_ONLY",
            "tool_execution": False,
            "autonomous_execution": False,
            "action_authority": "NONE",
        },
        "receipts": {
            "schema": RECEIPT_SCHEMA,
            "signature_status": "UNSIGNED_RUNTIME",
            "persistence": "EPHEMERAL_PROCESS_MEMORY_ONLY",
            "raw_prompt_persisted": False,
            "raw_evidence_persisted": False,
            "private_reasoning_persisted": False,
            "must_be_signed_before_consequential_action": True,
        },
    }


def infer_payload(request: GovernedInferenceRequest) -> dict[str, Any]:
    revision = source_revision()
    if revision is None:
        raise CortexBoundaryError("source_revision_unavailable")
    prompt_digest = text_sha256(request.prompt)
    authority = _load_formula_authority()
    nemo = _load_nemo()
    evidence = _brain_evidence(request.prompt, request.k)
    envelope_items = [
        {
            "node_id": item["node_id"],
            "source": item["source"],
            "sha256": item["sha256"],
        }
        for item in evidence["items"]
    ]
    evidence_set_sha256 = canonical_sha256(envelope_items)
    formulas = _formula_binding(
        authority,
        prompt_sha256=prompt_digest,
        evidence_set_sha256=evidence_set_sha256,
    )
    _, identity = _load_model()
    pre_envelope = _nemo_envelope(
        stage="PRE_GENERATION",
        identity=identity,
        evidence=evidence,
        formulas=formulas,
        claims=[],
    )
    pre = _decision_dict(nemo.evaluate_envelope(pre_envelope))
    if pre["decision"] != "ALLOW":
        raise CortexBoundaryError("nemo_pre_generation_blocked", 422)
    output, identity, metrics = _generate(
        request.prompt,
        evidence,
        formulas,
        request.max_new_tokens,
    )
    text_witness = _decision_dict(nemo.evaluate(request.prompt, output))
    if text_witness["decision"] != "ALLOW":
        raise CortexBoundaryError("nemo_text_witness_blocked", 422)
    output_digest = text_sha256(output)
    claims = [{"label": "MODELED", "statement_sha256": output_digest}]
    post_envelope = _nemo_envelope(
        stage="POST_GENERATION",
        identity=identity,
        evidence=evidence,
        formulas=formulas,
        claims=claims,
    )
    post = _decision_dict(nemo.evaluate_envelope(post_envelope))
    if post["decision"] != "ALLOW":
        raise CortexBoundaryError("nemo_post_generation_blocked", 422)
    citations = _extract_citations(output, evidence)
    request_id = canonical_sha256(
        {
            "source_revision": revision,
            "prompt_sha256": prompt_digest,
            "evidence_set_sha256": evidence_set_sha256,
            "model_revision": MODEL_REVISION,
            "max_new_tokens": request.max_new_tokens,
            "k": request.k,
        }
    )[:32]
    receipt_payload = {
        "schema": RECEIPT_SCHEMA,
        "request_id": request_id,
        "source_repository": "szl-holdings/a11oy",
        "source_revision": revision,
        "prompt_sha256": prompt_digest,
        "evidence_set_sha256": evidence_set_sha256,
        "output_sha256": output_digest,
        "model": {
            "repository": MODEL_REPOSITORY,
            "revision": MODEL_REVISION,
            "filename": MODEL_FILENAME,
            "sha256": MODEL_SHA256,
            "kind": "OWNED_KHIPU_GGUF_LOCAL_CPU",
        },
        "formula_applications": formulas["applications"],
        "nemo": {
            "revision": NEMO_REVISION,
            "pre_input_hash": pre["input_hash"],
            "text_input_hash": text_witness["input_hash"],
            "post_input_hash": post["input_hash"],
        },
        "decision": "REVIEW_PROPOSAL_ONLY",
        "authority_state": "NO_ACTION_AUTHORITY",
        "executed": False,
        "tool_execution": False,
    }
    receipt_digest = canonical_sha256(receipt_payload)
    anatomy_event = {
        "schema": ANATOMY_SCHEMA,
        "request_id": request_id,
        "source_revision": revision,
        "prompt_sha256": prompt_digest,
        "evidence_set_sha256": evidence_set_sha256,
        "output_sha256": output_digest,
        "receipt_sha256": receipt_digest,
        "model_revision": MODEL_REVISION,
        "raw_prompt_present": False,
        "raw_evidence_present": False,
        "raw_output_present": False,
        "private_reasoning_present": False,
        "private_graph_present": False,
        "observer_authority": "NONE",
    }
    observed = _observe_anatomy(anatomy_event)
    return {
        "schema": RESPONSE_SCHEMA,
        "request_id": request_id,
        "state": "PROPOSAL",
        "decision": "review",
        "output": output,
        "output_sha256": output_digest,
        "source_revision": revision,
        "executed": False,
        "tool_execution": False,
        "authority_state": "NO_ACTION_AUTHORITY",
        "model": identity["model"],
        "runtime": identity["runtime"],
        "second_brain": {
            "state": evidence["state"],
            "retrieval": evidence["retrieval"],
            "node_count": evidence["node_count"],
            "content_hash": evidence["content_hash"],
            "content_access": evidence["content_access"],
            "private_graph_present": False,
            "query_latency": evidence["query_latency"],
        },
        "evidence_handles": envelope_items,
        "evidence_set_sha256": evidence_set_sha256,
        "citations": citations,
        "citations_sha256": canonical_sha256(citations),
        "claims": claims,
        "claims_sha256": canonical_sha256(claims),
        "formula_authority": {
            "locked_proven_count": formulas["locked_proven_count"],
            "locked_proven_ids": formulas["locked_proven_ids"],
            "applications": formulas["applications"],
            "authorization_basis_ids": [],
            "lambda": formulas["lambda"],
        },
        "nemo": [
            {"stage": "PRE_GENERATION", **pre},
            {"stage": "TEXT_R1_R5", **text_witness},
            {"stage": "POST_GENERATION", **post},
        ],
        "metrics": metrics,
        "receipt": {
            "schema": RECEIPT_SCHEMA,
            "payload": receipt_payload,
            "receipt_sha256": receipt_digest,
            "signature": {
                "status": "UNSIGNED_RUNTIME",
                "durable": False,
                "must_be_signed_before_consequential_action": True,
            },
            "persistence": "EPHEMERAL_PROCESS_MEMORY_ONLY",
            "prompt_or_evidence_text_persisted": False,
        },
        "anatomy_observation": {
            "delivery": "DELIVERED",
            "persistence": "EPHEMERAL_PROCESS_MEMORY_ONLY",
            "observer_authority": "NONE",
            "observation_count": observed["observation_count"],
            "event": anatomy_event,
        },
        "honesty": {
            "output_is_owned_khipu_inference": True,
            "output_is_model_proposal": True,
            "output_is_signed": False,
            "action_authority": False,
            "lambda_is_theorem": False,
            "private_chain_of_thought_exposed": False,
        },
    }


def register(app: FastAPI, ns: str = "a11oy") -> str:
    del ns
    existing = {getattr(route, "path", None) for route in app.routes}
    if "/api/v2/governed-health" in existing:
        return "owned-khipu-cortex-already-registered"

    @app.get("/api/v2/governed-health")
    def governed_health() -> JSONResponse:
        payload, status = health_payload(load_model=True)
        return JSONResponse(payload, status_code=status, headers=_headers())

    @app.get("/api/v2/governed-contract")
    @app.get("/.well-known/szl-governed-inference-contract.json")
    def governed_contract() -> JSONResponse:
        return JSONResponse(contract_payload(), headers=_headers())

    @app.post("/api/v2/governed-infer")
    def governed_infer(request: GovernedInferenceRequest) -> JSONResponse:
        try:
            payload = infer_payload(request)
            return JSONResponse(payload, headers=_headers())
        except CortexBoundaryError as exc:
            return _error(exc.code, exc.status)

    @app.get("/api/v2/anatomy/last")
    def anatomy_last() -> JSONResponse:
        with _ANATOMY_LOCK:
            payload = {
                "schema": "szl.anatomy.last-owned-inference/v1",
                "state": "AVAILABLE" if _ANATOMY["last"] else "EMPTY",
                "persistence": "EPHEMERAL_PROCESS_MEMORY_ONLY",
                "observer_authority": "NONE",
                "observation_count": _ANATOMY["observation_count"],
                "last": deepcopy(_ANATOMY["last"]),
            }
        return JSONResponse(payload, headers=_headers())

    return "owned-khipu-cortex-registered"


__all__ = [
    "ANATOMY_SCHEMA",
    "CONTRACT_SCHEMA",
    "CortexBoundaryError",
    "GovernedInferenceRequest",
    "HEALTH_SCHEMA",
    "LOCKED_FORMULAS",
    "MODEL_FILENAME",
    "MODEL_REPOSITORY",
    "MODEL_REVISION",
    "MODEL_SHA256",
    "MODEL_SIZE",
    "NEMO_REVISION",
    "NEMO_VERSION",
    "RECEIPT_SCHEMA",
    "RESPONSE_SCHEMA",
    "canonical_bytes",
    "canonical_sha256",
    "contract_payload",
    "health_payload",
    "infer_payload",
    "model_path",
    "register",
    "source_revision",
    "text_sha256",
    "verify_model_artifact",
]
