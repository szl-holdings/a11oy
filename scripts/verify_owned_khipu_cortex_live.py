#!/usr/bin/env python3
"""Verify the deployed A11oy owned-Khipu cortex without retaining prompt/output text."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

HEALTH_SCHEMA = "szl.a11oy.owned-khipu-cortex-health/v1"
CONTRACT_SCHEMA = "szl.a11oy.owned-khipu-cortex-contract/v1"
RESPONSE_SCHEMA = "szl.a11oy.owned-khipu-cortex-response/v1"
RECEIPT_SCHEMA = "szl.a11oy.owned-khipu-cortex-receipt/v1"
MODEL_REPOSITORY = "SZLHOLDINGS/SZL-Khipu-1.5B-GGUF"
MODEL_REVISION = "67d60ec577730747055491640cfb91fc4a4b5d25"
MODEL_FILENAME = "SZL-Khipu-1.5B-Q4_K_M.gguf"
MODEL_SHA256 = "13c1a1993063e1dff92f7413ccf48eaca6d48efc8801ae9af35961ae3396623a"
NEMO_REVISION = "810231a531188bb569e3faa17396386eb0a5e260"
LOCKED_FORMULAS = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
PROMPT = (
    "According to the available evidence, what is Lambda's formal status and "
    "can it authorize an action? Cite at least one evidence node handle."
)
BANNED_RECEIPT_KEYS = {
    "prompt",
    "raw_prompt",
    "answer",
    "raw_answer",
    "content",
    "raw_content",
    "private_graph",
    "chain_of_thought",
    "hidden_reasoning",
}


class LiveProofError(RuntimeError):
    pass


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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise LiveProofError(message)


def walk_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            keys.add(str(key).lower())
            keys.update(walk_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(walk_keys(item))
    return keys


def request_json(
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout: float = 180.0,
) -> tuple[int, dict[str, Any], dict[str, str]]:
    data = canonical_bytes(payload) if payload is not None else None
    headers = {
        "Accept": "application/json",
        "Cache-Control": "no-cache, no-store, max-age=0",
        "Pragma": "no-cache",
        "User-Agent": "a11oy-owned-khipu-live-proof/1",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method="POST" if data is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
            if not isinstance(body, dict):
                raise LiveProofError(f"{url} did not return a JSON object")
            return (
                int(response.status),
                body,
                {key.lower(): value for key, value in response.headers.items()},
            )
    except urllib.error.HTTPError as exc:
        try:
            parsed = json.loads(exc.read().decode("utf-8"))
            body = parsed if isinstance(parsed, dict) else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            body = {}
        return (
            int(exc.code),
            body,
            {key.lower(): value for key, value in exc.headers.items()},
        )


def wait_for_health(
    base_url: str,
    expected_source: str,
    *,
    attempts: int = 40,
    delay_seconds: float = 15.0,
) -> tuple[dict[str, Any], dict[str, str], int]:
    last: dict[str, Any] = {}
    for attempt in range(1, attempts + 1):
        status, body, headers = request_json(
            f"{base_url}/api/v2/governed-health",
            timeout=240.0,
        )
        last = body
        if (
            status == 200
            and body.get("schema") == HEALTH_SCHEMA
            and body.get("status") == "READY"
            and body.get("source_revision") == expected_source
            and headers.get("x-szl-governed-inference") == "owned-khipu-v1"
        ):
            return body, headers, attempt
        if attempt != attempts:
            time.sleep(delay_seconds)
    raise LiveProofError(
        "owned cortex health did not converge: "
        + json.dumps(
            {
                "status": last.get("status"),
                "source_revision": last.get("source_revision"),
                "checks": last.get("checks"),
            },
            sort_keys=True,
        )[:2000]
    )


def verify_health(health: dict[str, Any], expected_source: str) -> None:
    require(health.get("schema") == HEALTH_SCHEMA, "health schema drift")
    require(health.get("status") == "READY", "health is not READY")
    require(health.get("source_revision") == expected_source, "health source drift")
    require(health.get("model_kind") == "OWNED_KHIPU_GGUF_LOCAL_CPU", "model kind drift")
    require(health.get("model_repository") == MODEL_REPOSITORY, "model repository drift")
    require(health.get("model_revision") == MODEL_REVISION, "model revision drift")
    require(health.get("tools") is False, "health enabled tools")
    require(health.get("executed") is False, "health reports execution")
    require(health.get("action_authority") == "NONE", "health gained action authority")
    checks = health.get("checks") or {}
    model = checks.get("owned_model") or {}
    require(model.get("state") == "READY", "owned model is not READY")
    require(model.get("revision") == MODEL_REVISION, "owned model check revision drift")
    require(model.get("filename") == MODEL_FILENAME, "owned model filename drift")
    require(model.get("sha256") == MODEL_SHA256, "owned model digest drift")
    require(model.get("runtime", {}).get("engine") == "llama-cpp-python", "runtime engine drift")
    brain = checks.get("second_brain") or {}
    require(brain.get("state") == "READY", "Second Brain is not READY")
    require((brain.get("probe_handle_count") or 0) >= 1, "Second Brain returned no handle")
    require(brain.get("private_graph_present") is False, "private graph exposed")
    formula = checks.get("formula_authority") or {}
    require(formula.get("state") == "READY", "formula authority unavailable")
    require(formula.get("locked_proven_ids") == LOCKED_FORMULAS, "locked formula drift")
    lambda_rule = formula.get("lambda") or {}
    require(lambda_rule.get("status") == "CONJECTURE_1_ADVISORY", "Lambda status drift")
    require(lambda_rule.get("can_authorize") is False, "Lambda gained authority")
    nemo = checks.get("nemo") or {}
    require(nemo.get("state") == "READY", "Nemo unavailable")
    require(nemo.get("version") == "0.4.0", "Nemo version drift")
    require(nemo.get("revision") == NEMO_REVISION, "Nemo revision drift")


def verify_contract(contract: dict[str, Any], expected_source: str) -> None:
    require(contract.get("schema") == CONTRACT_SCHEMA, "contract schema drift")
    require(contract.get("source_revision") == expected_source, "contract source drift")
    model = contract.get("model") or {}
    require(model.get("kind") == "OWNED_KHIPU_GGUF_LOCAL_CPU", "contract model kind drift")
    require(model.get("repository") == MODEL_REPOSITORY, "contract model repository drift")
    require(model.get("revision") == MODEL_REVISION, "contract model revision drift")
    require(model.get("sha256") == MODEL_SHA256, "contract model digest drift")
    authority = contract.get("authority") or {}
    require(authority.get("model_authority") == "PROPOSAL_ONLY", "model authority drift")
    require(authority.get("tool_execution") is False, "contract enabled tools")
    require(authority.get("autonomous_execution") is False, "autonomous execution enabled")
    require(authority.get("action_authority") == "NONE", "contract gained action authority")
    formulas = contract.get("formula_authority") or {}
    require(formulas.get("locked_proven_ids") == LOCKED_FORMULAS, "contract formula drift")
    require(formulas.get("f_id_to_callable_mapping") == "UNKNOWN_NOT_ASSERTED", "formula mapping fabricated")
    require((formulas.get("lambda") or {}).get("can_authorize") is False, "contract Lambda authority drift")
    nemo = contract.get("nemo") or {}
    require(nemo.get("revision") == NEMO_REVISION, "contract Nemo revision drift")
    require(nemo.get("envelope_rules") == "doctrine-v11/E1-E10", "Nemo envelope drift")
    require(nemo.get("text_rules") == "doctrine-v11/R1-R5", "Nemo text drift")
    require(nemo.get("generative") is False, "Nemo mislabeled generative")
    require(nemo.get("not_nemotron") is True, "Nemo identity drift")


def verify_inference(
    inference: dict[str, Any],
    headers: dict[str, str],
    expected_source: str,
) -> dict[str, Any]:
    require(inference.get("schema") == RESPONSE_SCHEMA, "inference schema drift")
    require(inference.get("source_revision") == expected_source, "inference source drift")
    require(inference.get("state") == "PROPOSAL", "inference is not a proposal")
    require(inference.get("decision") == "review", "inference review boundary drift")
    require(inference.get("executed") is False, "inference executed an action")
    require(inference.get("tool_execution") is False, "inference executed a tool")
    require(inference.get("authority_state") == "NO_ACTION_AUTHORITY", "inference gained authority")
    output = inference.get("output")
    require(isinstance(output, str) and bool(output.strip()), "inference returned no output")
    require(inference.get("output_sha256") == text_sha256(output), "output digest mismatch")
    model = inference.get("model") or {}
    require(model.get("repository") == MODEL_REPOSITORY, "result model repository drift")
    require(model.get("revision") == MODEL_REVISION, "result model revision drift")
    require(model.get("filename") == MODEL_FILENAME, "result model filename drift")
    require(model.get("sha256") == MODEL_SHA256, "result model digest drift")
    require(model.get("ownership") == "SZL_HOLDINGS_OWNED_ARTIFACT", "model ownership drift")
    runtime = inference.get("runtime") or {}
    require(runtime.get("engine") == "llama-cpp-python", "result runtime engine drift")
    evidence = inference.get("evidence_handles") or []
    require(isinstance(evidence, list) and len(evidence) >= 1, "no evidence handles returned")
    require(all(set(item) == {"node_id", "source", "sha256"} for item in evidence), "evidence handle shape drift")
    citations = inference.get("citations") or []
    require(isinstance(citations, list) and len(citations) >= 1, "model returned no evidence citation")
    allowed = {item["node_id"] for item in evidence}
    require(set(citations).issubset(allowed), "citation not bound to evidence")
    require(inference.get("evidence_set_sha256") == canonical_sha256(evidence), "evidence digest mismatch")
    require(inference.get("citations_sha256") == canonical_sha256(citations), "citation digest mismatch")
    claims = inference.get("claims") or []
    require(inference.get("claims_sha256") == canonical_sha256(claims), "claim digest mismatch")
    formulas = inference.get("formula_authority") or {}
    require(formulas.get("locked_proven_ids") == LOCKED_FORMULAS, "result formula drift")
    require(formulas.get("authorization_basis_ids") == [], "formula granted authorization")
    applications = formulas.get("applications") or []
    require(len(applications) == 1 and applications[0].get("formula_id") == "F1", "formula applicability drift")
    require(applications[0].get("scope") == "REPLAY_HASH_DETERMINISM_ONLY", "F1 scope drift")
    require(applications[0].get("can_authorize_action") is False, "F1 gained action authority")
    require((formulas.get("lambda") or {}).get("can_authorize") is False, "result Lambda authority drift")
    nemo = inference.get("nemo") or []
    require([row.get("stage") for row in nemo] == ["PRE_GENERATION", "TEXT_R1_R5", "POST_GENERATION"], "Nemo stage drift")
    require(all(row.get("decision") == "ALLOW" for row in nemo), "Nemo did not allow all stages")
    require(nemo[0].get("rule_version") == "doctrine-v11/E1-E10", "pre Nemo rule drift")
    require(nemo[1].get("rule_version") == "doctrine-v11/R1-R5", "text Nemo rule drift")
    require(nemo[2].get("rule_version") == "doctrine-v11/E1-E10", "post Nemo rule drift")
    receipt = inference.get("receipt") or {}
    require(receipt.get("schema") == RECEIPT_SCHEMA, "receipt schema drift")
    payload = receipt.get("payload") or {}
    require(receipt.get("receipt_sha256") == canonical_sha256(payload), "receipt digest mismatch")
    require(payload.get("source_revision") == expected_source, "receipt source drift")
    require(payload.get("output_sha256") == inference.get("output_sha256"), "receipt output binding drift")
    require(payload.get("executed") is False, "receipt claims execution")
    require(payload.get("tool_execution") is False, "receipt claims tool execution")
    require(payload.get("authority_state") == "NO_ACTION_AUTHORITY", "receipt authority drift")
    require(not (walk_keys(receipt) & BANNED_RECEIPT_KEYS), "receipt contains forbidden raw fields")
    require(PROMPT not in canonical_bytes(receipt).decode("utf-8"), "raw prompt persisted in receipt")
    signature = receipt.get("signature") or {}
    require(signature.get("status") == "UNSIGNED_RUNTIME", "receipt signature honesty drift")
    require(signature.get("durable") is False, "receipt mislabeled durable")
    require(signature.get("must_be_signed_before_consequential_action") is True, "signing boundary drift")
    anatomy = inference.get("anatomy_observation") or {}
    event = anatomy.get("event") or {}
    require(anatomy.get("delivery") == "DELIVERED", "Anatomy not delivered")
    require(anatomy.get("observer_authority") == "NONE", "Anatomy gained authority")
    require(anatomy.get("persistence") == "EPHEMERAL_PROCESS_MEMORY_ONLY", "Anatomy persistence drift")
    for key in ("raw_prompt_present", "raw_evidence_present", "raw_output_present", "private_reasoning_present", "private_graph_present"):
        require(event.get(key) is False, f"unsafe Anatomy flag: {key}")
    require(headers.get("x-szl-governed-inference") == "owned-khipu-v1", "inference header missing")
    require(headers.get("x-szl-source-revision") == expected_source, "source header drift")
    require(headers.get("x-szl-model-revision") == MODEL_REVISION, "model header drift")
    require(headers.get("x-szl-nemo-revision") == NEMO_REVISION, "Nemo header drift")
    return {
        "request_id": inference.get("request_id"),
        "output_sha256": inference.get("output_sha256"),
        "receipt_sha256": receipt.get("receipt_sha256"),
        "evidence_set_sha256": inference.get("evidence_set_sha256"),
        "citation_count": len(citations),
        "evidence_handle_count": len(evidence),
        "model_revision": model.get("revision"),
        "model_sha256": model.get("sha256"),
        "runtime_version": runtime.get("version"),
        "nemo_input_hashes": [row.get("input_hash") for row in nemo],
        "anatomy_observation_count": anatomy.get("observation_count"),
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="https://a-11-oy.com")
    parser.add_argument("--expected-source", required=True)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    expected = args.expected_source.strip().lower()
    base = args.base_url.rstrip("/")
    report: dict[str, Any] = {
        "schema": "szl.a11oy.owned-khipu-live-proof/v1",
        "state": "FAILED",
        "base_url_sha256": text_sha256(base),
        "expected_source": expected,
        "prompt_sha256": text_sha256(PROMPT),
        "prompt_or_output_text_persisted": False,
    }
    try:
        require(len(expected) == 40 and all(char in "0123456789abcdef" for char in expected), "expected source must be a full SHA")
        health, _, health_attempts = wait_for_health(base, expected)
        verify_health(health, expected)
        status, contract, _ = request_json(f"{base}/api/v2/governed-contract", timeout=60.0)
        require(status == 200, "contract endpoint failed")
        verify_contract(contract, expected)
        status, well_known, _ = request_json(
            f"{base}/.well-known/szl-governed-inference-contract.json",
            timeout=60.0,
        )
        require(status == 200, "well-known contract endpoint failed")
        require(well_known == contract, "well-known contract parity drift")

        last_status = 0
        inference: dict[str, Any] = {}
        inference_headers: dict[str, str] = {}
        for inference_attempt in range(1, 4):
            last_status, inference, inference_headers = request_json(
                f"{base}/api/v2/governed-infer",
                payload={"prompt": PROMPT, "max_new_tokens": 64, "k": 3},
                timeout=300.0,
            )
            if last_status == 200:
                break
            if inference_attempt != 3:
                time.sleep(20.0)
        require(last_status == 200, f"owned inference failed: HTTP {last_status} error={inference.get('error')}")
        evidence = verify_inference(inference, inference_headers, expected)

        status, anatomy, _ = request_json(f"{base}/api/v2/anatomy/last", timeout=60.0)
        require(status == 200, "Anatomy readback failed")
        require(anatomy.get("state") == "AVAILABLE", "Anatomy readback is empty")
        require(anatomy.get("observer_authority") == "NONE", "Anatomy readback gained authority")
        require(anatomy.get("persistence") == "EPHEMERAL_PROCESS_MEMORY_ONLY", "Anatomy readback persistence drift")
        require((anatomy.get("observation_count") or 0) >= 1, "Anatomy observed no inference")
        last = anatomy.get("last") or {}
        require(last.get("output_sha256") == evidence["output_sha256"], "Anatomy/output binding drift")
        require(last.get("receipt_sha256") == evidence["receipt_sha256"], "Anatomy/receipt binding drift")
        require(not (walk_keys(anatomy) & BANNED_RECEIPT_KEYS), "Anatomy exposes forbidden raw fields")

        report.update(
            {
                "state": "VERIFIED",
                "source_revision": expected,
                "health_attempts": health_attempts,
                "inference_attempts": inference_attempt,
                "model_repository": MODEL_REPOSITORY,
                "model_revision": MODEL_REVISION,
                "model_sha256": MODEL_SHA256,
                "nemo_revision": NEMO_REVISION,
                "locked_formula_ids": LOCKED_FORMULAS,
                "lambda_status": "CONJECTURE_1_ADVISORY",
                "tool_execution": False,
                "action_authority": False,
                "anatomy_observation_count": anatomy.get("observation_count"),
                "evidence": evidence,
            }
        )
        write_report(args.report, report)
        print(json.dumps(report, sort_keys=True))
        return 0
    except Exception as exc:
        report["error_type"] = type(exc).__name__
        report["error"] = str(exc)[:2000]
        write_report(args.report, report)
        print(json.dumps(report, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
