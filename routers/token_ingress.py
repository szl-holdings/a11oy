# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""Governed HTTP surface for state-native token ingress controls.

Only bounded computation is exposed.  Public callers cannot mark telemetry as
MEASURED, cannot read arbitrary repository files, cannot persist prefixes, and
cannot trigger provider/model/network effects.  Semantic qualification fails
closed unless explicit oracle/candidate token cases are supplied.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from routers.token_ingress_core import (
    IngressWorkload,
    PrefixFoundry,
    TokenizerNodeSignal,
    TokenizerParityCase,
    choose_ingress_node,
    qualify_tokenizer_candidate,
    verifier_reinvestment,
)

MAX_BODY = 64 * 1024
MAX_NODES = 64
MAX_CASES = 256
_FOUNDRY = PrefixFoundry()


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
        import json

        value = json.loads(raw)
    except Exception as exc:
        raise ValueError("request body must be valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("request body must be one JSON object")
    return value


def _bool(value: Any) -> bool:
    return value is True


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
                "tokenizer_promotion": "FAIL_CLOSED_ORACLE_REQUIRED",
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
            for item in raw_nodes:
                if not isinstance(item, dict):
                    raise ValueError("every node must be an object")
                nodes.append(
                    TokenizerNodeSignal(
                        node_id=str(item.get("node_id") or ""),
                        tokenizer_tokens_per_sec=float(item.get("tokenizer_tokens_per_sec", 0)),
                        tokenizer_cache_warmth=float(item.get("tokenizer_cache_warmth", 0)),
                        prefix_cache_hit_rate=float(item.get("prefix_cache_hit_rate", 0)),
                        kv_cache_hit_rate=float(item.get("kv_cache_hit_rate", 0)),
                        available=item.get("available", True) is not False,
                        measured=False,
                    )
                )
            raw_workload = payload.get("workload") or {}
            if not isinstance(raw_workload, dict):
                raise ValueError("workload must be an object")
            workload = IngressWorkload(
                prefix_heavy=_bool(raw_workload.get("prefix_heavy")),
                corpus_heavy=_bool(raw_workload.get("corpus_heavy")),
                prefill_heavy=_bool(raw_workload.get("prefill_heavy")),
            )
            result = choose_ingress_node(nodes, workload)
            result["evidence"] = "SAMPLE"
            result["telemetry_authority"] = "CALLER_SUPPLIED_NOT_MEASURED"
            return JSONResponse({"ready": True, "accepted": True, **result})
        except (TypeError, ValueError) as exc:
            return _error(422, "invalid_ingress_route", str(exc))

    @app.post(f"{prefix}/qualify", include_in_schema=False)
    async def qualify(request: Request) -> JSONResponse:
        try:
            payload = await _body(request)
            oracle = str(payload.get("oracle") or "")
            candidate = str(payload.get("candidate") or "")
            raw_cases = payload.get("cases")
            if not isinstance(raw_cases, list) or len(raw_cases) > MAX_CASES:
                raise ValueError(f"cases must be a list with at most {MAX_CASES} entries")
            cases: list[TokenizerParityCase] = []
            for item in raw_cases:
                if not isinstance(item, dict):
                    raise ValueError("every parity case must be an object")
                oracle_ids = item.get("oracle_ids")
                candidate_ids = item.get("candidate_ids")
                if not isinstance(oracle_ids, list) or not isinstance(candidate_ids, list):
                    raise ValueError("oracle_ids and candidate_ids must be arrays")
                cases.append(
                    TokenizerParityCase(
                        name=str(item.get("name") or f"case-{len(cases)+1}"),
                        oracle_ids=tuple(int(value) for value in oracle_ids),
                        candidate_ids=tuple(int(value) for value in candidate_ids),
                        oracle_special_tokens=tuple(str(v) for v in item.get("oracle_special_tokens", [])),
                        candidate_special_tokens=tuple(str(v) for v in item.get("candidate_special_tokens", [])),
                        oracle_normalized_text=item.get("oracle_normalized_text"),
                        candidate_normalized_text=item.get("candidate_normalized_text"),
                    )
                )
            result = qualify_tokenizer_candidate(oracle, candidate, cases)
            http_status = 200 if result["status"] == "PASS" else 409 if result["status"] == "FAIL" else 422
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
            saved = float(payload.get("saved_milliseconds", 0))
            result = verifier_reinvestment(saved, measured=False)
            result["evidence"] = "MODELED"
            result["measurement_authority"] = "NOT_ACCEPTED_FROM_PUBLIC_CALLER"
            return JSONResponse({"ready": True, "accepted": True, **result, "effectors": 0})
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
