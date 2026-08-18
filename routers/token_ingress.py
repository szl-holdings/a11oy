# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""Governed HTTP surface for state-native token ingress controls.

Only bounded computation is exposed. Public callers cannot mark telemetry as
MEASURED, read arbitrary repository files, persist tokenized prefixes, invoke a
provider, mutate a model, or trigger a network effector. Tokenizer qualification
fails closed unless complete semantic contracts and representative token cases are
supplied.
"""

import json
import math
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from routers.token_ingress_core import (
    IngressWorkload,
    PrefixFoundry,
    SemanticTokenContract,
    TokenizerNodeSignal,
    TokenizerParityCase,
    choose_ingress_node,
    qualify_tokenizer_candidate,
    verifier_reinvestment,
)

MAX_BODY = 64 * 1024
MAX_NODES = 64
MAX_CASES = 256
MAX_TOKEN_IDS_PER_CASE = 8192
MAX_TEXT_CHARS_PER_CASE = 256 * 1024
_FOUNDRY = PrefixFoundry()

_CONTRACT_DIGEST_FIELDS = (
    "vocabulary_sha256",
    "normalization_sha256",
    "special_tokens_sha256",
    "added_tokens_sha256",
    "chat_template_sha256",
    "document_separator_sha256",
)


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        {
            "ready": status < 500,
            "accepted": False,
            "status": "BLOCKED" if status < 500 else "UNAVAILABLE",
            "error": {"code": code, "message": message[:240]},
            "effectors": 0,
        },
        status_code=status,
    )


def _closed_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is forbidden: {value}")


async def _body(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise ValueError("content-type must be application/json")

    declared = request.headers.get("content-length")
    if declared:
        try:
            size = int(declared)
        except ValueError as exc:
            raise ValueError("content-length must be an integer") from exc
        if size < 0 or size > MAX_BODY:
            raise ValueError("request body exceeds 64 KiB")

    raw = await request.body()
    if len(raw) > MAX_BODY:
        raise ValueError("request body exceeds 64 KiB")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_closed_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("request body must be strict JSON with unique fields") from exc
    if not isinstance(value, dict):
        raise ValueError("request body must be one JSON object")
    return value


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


def _strict_bool(value: Any, field: str, *, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a boolean")
    return value


def _token_ids(value: Any, field: str) -> tuple[int, ...]:
    if not isinstance(value, list) or len(value) > MAX_TOKEN_IDS_PER_CASE:
        raise ValueError(f"{field} must be an array with at most {MAX_TOKEN_IDS_PER_CASE} entries")
    if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in value):
        raise ValueError(f"{field} must contain non-negative integer token IDs")
    return tuple(value)


def _bounded_text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    if len(value) > MAX_TEXT_CHARS_PER_CASE:
        raise ValueError(f"{field} exceeds the text boundary")
    return value


def _semantic_contract(value: Any, field: str) -> SemanticTokenContract:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    allowed = {"source", "tokenizer_family", *_CONTRACT_DIGEST_FIELDS}
    extras = sorted(set(value) - allowed)
    if extras:
        raise ValueError(f"{field} contains unsupported fields: {','.join(extras)}")
    source = value.get("source")
    family = value.get("tokenizer_family")
    if not isinstance(source, str) or not isinstance(family, str):
        raise ValueError(f"{field}.source and {field}.tokenizer_family must be strings")
    digests: dict[str, str] = {}
    for digest_field in _CONTRACT_DIGEST_FIELDS:
        digest = value.get(digest_field)
        if not isinstance(digest, str):
            raise ValueError(f"{field}.{digest_field} must be a string")
        digests[digest_field] = digest
    contract = SemanticTokenContract(
        source=source,
        tokenizer_family=family,
        **digests,
    )
    contract.validate()
    return contract


def register(app, ns: str = "a11oy") -> dict[str, Any]:
    prefix = f"/api/{ns}/v1/token-ingress"
    if any(getattr(route, "path", None) == f"{prefix}/status" for route in app.router.routes):
        return {"ok": True, "state": "ALREADY_REGISTERED", "routes": []}

    @app.get(f"{prefix}/status", include_in_schema=False)
    async def status() -> JSONResponse:
        return JSONResponse(
            {
                "ready": True,
                "implementation": "REAL",
                "execution": "BOUNDED_COMPUTATION_ONLY",
                "telemetry": "CALLER_SAMPLE_ONLY",
                "tokenizer_promotion": "FAIL_CLOSED_SEMANTIC_CONTRACT_REQUIRED",
                "semantic_contract_fields": [
                    "tokenizer_family",
                    *_CONTRACT_DIGEST_FIELDS,
                ],
                "prefix_foundry": _FOUNDRY.snapshot(),
                "repository_ingestion": "INTERNAL_LIBRARY_ONLY",
                "effectors": 0,
                "provider_calls": 0,
                "network_calls": 0,
            }
        )

    @app.post(f"{prefix}/route", include_in_schema=False)
    async def route(request: Request) -> JSONResponse:
        try:
            payload = await _body(request)
            raw_nodes = payload.get("nodes")
            if not isinstance(raw_nodes, list) or not 1 <= len(raw_nodes) <= MAX_NODES:
                raise ValueError(f"nodes must contain 1..{MAX_NODES} entries")

            nodes: list[TokenizerNodeSignal] = []
            for index, item in enumerate(raw_nodes):
                if not isinstance(item, dict):
                    raise ValueError("every node must be an object")
                allowed = {
                    "node_id",
                    "tokenizer_tokens_per_sec",
                    "tokenizer_cache_warmth",
                    "prefix_cache_hit_rate",
                    "kv_cache_hit_rate",
                    "available",
                    "measured",
                }
                extras = sorted(set(item) - allowed)
                if extras:
                    raise ValueError(f"node {index} contains unsupported fields: {','.join(extras)}")
                node_id = item.get("node_id")
                if not isinstance(node_id, str):
                    raise ValueError("node_id must be a string")
                nodes.append(
                    TokenizerNodeSignal(
                        node_id=node_id,
                        tokenizer_tokens_per_sec=_number(
                            item.get("tokenizer_tokens_per_sec", 0),
                            "tokenizer_tokens_per_sec",
                        ),
                        tokenizer_cache_warmth=_number(
                            item.get("tokenizer_cache_warmth", 0),
                            "tokenizer_cache_warmth",
                        ),
                        prefix_cache_hit_rate=_number(
                            item.get("prefix_cache_hit_rate", 0),
                            "prefix_cache_hit_rate",
                        ),
                        kv_cache_hit_rate=_number(
                            item.get("kv_cache_hit_rate", 0),
                            "kv_cache_hit_rate",
                        ),
                        available=_strict_bool(
                            item.get("available"), "available", default=True
                        ),
                        measured=False,
                    )
                )

            raw_workload = payload.get("workload") or {}
            if not isinstance(raw_workload, dict):
                raise ValueError("workload must be an object")
            workload_allowed = {"prefix_heavy", "corpus_heavy", "prefill_heavy"}
            workload_extras = sorted(set(raw_workload) - workload_allowed)
            if workload_extras:
                raise ValueError(
                    "workload contains unsupported fields: " + ",".join(workload_extras)
                )
            workload = IngressWorkload(
                prefix_heavy=_strict_bool(
                    raw_workload.get("prefix_heavy"), "prefix_heavy", default=False
                ),
                corpus_heavy=_strict_bool(
                    raw_workload.get("corpus_heavy"), "corpus_heavy", default=False
                ),
                prefill_heavy=_strict_bool(
                    raw_workload.get("prefill_heavy"), "prefill_heavy", default=False
                ),
            )

            result = choose_ingress_node(nodes, workload)
            result["evidence"] = "SAMPLE"
            result["telemetry_authority"] = "CALLER_SUPPLIED_NOT_MEASURED"
            accepted = result["status"] == "PASS"
            return JSONResponse(
                {"ready": True, "accepted": accepted, **result},
                status_code=200 if accepted else 409,
            )
        except (TypeError, ValueError) as exc:
            return _error(422, "invalid_ingress_route", str(exc))

    @app.post(f"{prefix}/qualify", include_in_schema=False)
    async def qualify(request: Request) -> JSONResponse:
        try:
            payload = await _body(request)
            oracle = _semantic_contract(payload.get("oracle_contract"), "oracle_contract")
            candidate = _semantic_contract(
                payload.get("candidate_contract"), "candidate_contract"
            )
            raw_cases = payload.get("cases")
            if not isinstance(raw_cases, list) or len(raw_cases) > MAX_CASES:
                raise ValueError(f"cases must be a list with at most {MAX_CASES} entries")

            cases: list[TokenizerParityCase] = []
            for item in raw_cases:
                if not isinstance(item, dict):
                    raise ValueError("every parity case must be an object")
                allowed = {
                    "name",
                    "oracle_ids",
                    "candidate_ids",
                    "oracle_decoded_text",
                    "candidate_decoded_text",
                }
                extras = sorted(set(item) - allowed)
                if extras:
                    raise ValueError("parity case contains unsupported fields: " + ",".join(extras))
                name = item.get("name")
                if not isinstance(name, str) or not name:
                    raise ValueError("case name must be a non-empty string")
                cases.append(
                    TokenizerParityCase(
                        name=name,
                        oracle_ids=_token_ids(item.get("oracle_ids"), "oracle_ids"),
                        candidate_ids=_token_ids(item.get("candidate_ids"), "candidate_ids"),
                        oracle_decoded_text=_bounded_text(
                            item.get("oracle_decoded_text"), "oracle_decoded_text"
                        ),
                        candidate_decoded_text=_bounded_text(
                            item.get("candidate_decoded_text"), "candidate_decoded_text"
                        ),
                    )
                )

            result = qualify_tokenizer_candidate(oracle, candidate, cases)
            http_status = (
                200
                if result["status"] == "PASS"
                else 409
                if result["status"] == "FAIL"
                else 422
            )
            return JSONResponse(
                {
                    "ready": True,
                    "accepted": result["status"] == "PASS",
                    **result,
                    "effectors": 0,
                },
                status_code=http_status,
            )
        except (TypeError, ValueError) as exc:
            return _error(422, "invalid_tokenizer_qualification", str(exc))

    @app.post(f"{prefix}/verification-budget", include_in_schema=False)
    async def verification_budget(request: Request) -> JSONResponse:
        try:
            payload = await _body(request)
            saved = _number(payload.get("saved_milliseconds", 0), "saved_milliseconds")
            result = verifier_reinvestment(saved, measured=False)
            result["evidence"] = "MODELED"
            result["measurement_authority"] = "NOT_ACCEPTED_FROM_PUBLIC_CALLER"
            return JSONResponse(
                {"ready": True, "accepted": True, **result, "effectors": 0}
            )
        except (TypeError, ValueError) as exc:
            return _error(422, "invalid_verification_budget", str(exc))

    return {
        "ok": True,
        "state": "REGISTERED",
        "routes": [
            f"{prefix}/status",
            f"{prefix}/route",
            f"{prefix}/qualify",
            f"{prefix}/verification-budget",
        ],
        "effectors": 0,
    }
