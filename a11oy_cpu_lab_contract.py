#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Pure provenance boundary for the pinned public CPU lab (services/provenance).

This validates unsigned self-consistency, not authorship, accuracy, or action
authority. No network, runtime imports, credential access, signing, or execution.

Pinned upstream projection and controller:
https://huggingface.co/spaces/SZLHOLDINGS/szl-model-inference-lab/tree/675d3fb83f0e1b765eeed5374e17faee656ecc6a
(public_transcript_export.py, app_governed.py, inference/production.py).
Text witness canonicalization:
https://github.com/szl-holdings/szl-nemo/blob/810231a531188bb569e3faa17396386eb0a5e260/szl_nemo/engine.py
"""

import hashlib
import json
import math
import re

ORIGIN = "https://szlholdings-szl-model-inference-lab.hf.space"
MODEL_REPO = "SZLHOLDINGS/SZL-Khipu-1.5B-GGUF"
MODEL_REVISION = "67d60ec577730747055491640cfb91fc4a4b5d25"
MODEL_ID = MODEL_REPO + "@" + MODEL_REVISION
MODEL_FILE = "SZL-Khipu-1.5B-Q4_K_M.gguf"
MODEL_SHA256 = "13c1a1993063e1dff92f7413ccf48eaca6d48efc8801ae9af35961ae3396623a"
MODEL_SIZE = 986047904
SOURCE_REVISION = "c94e9218093e0815745cbd5dccaddea1797379a3"
RELEASE_ID = "brain13-1d3960c-controller-9f227f6-atlas-d7b08cde"
RELEASE_MANIFEST_SHA256 = "557e4c1463e46d02ef15fd92366b3106e274a7dc5edd3785288ef416f82e25ac"
CONTROLLER_REVISION = "9f227f6a10dac178b29130c742c98451b6ed8391"
SECOND_BRAIN_REVISION = "1d3960c69235f117b7ec2b5ea97472f81fb588f5"
NEMO_REVISION = "810231a531188bb569e3faa17396386eb0a5e260"
FORMAL_REVISION = "c497b4ed402249f23da7f290426f0e21c70ab926"
KERNEL_REVISION = "46cfa948367e8133eaa8dd6bcfb781b19165b9bb"
LOCKED_EIGHT = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
PUBLIC_SCHEMA = "szl.forge.public-governed-inference/v3"
SOURCE_SCHEMA = "szl.forge.production-governed-inference/v2"
ENDPOINT = "/api/v3/governed-infer"


class ContractError(ValueError):
    """A bounded local reason code, without upstream text or values."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(condition, code):
    if not condition:
        raise ContractError(code)


def _json_bytes(value):
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, UnicodeError, RecursionError):
        raise ContractError("JSON_INVALID") from None


def _sha(value):
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _text_sha(value):
    try:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
    except (AttributeError, UnicodeError):
        raise ContractError("TEXT_INVALID") from None


PUBLIC_POLICY_REVISION = "sha256:" + _sha({
    "schema": "szl.public-memory-policy/v1",
    "principal": "public-anonymous", "tenant": "public",
    "second_brain_revision": SECOND_BRAIN_REVISION,
    "access": "PUBLIC_PROJECTION_ONLY", "tool_authority": "NONE",
})
_FORMULA = {
    "requested_ids": [], "authorization_basis_ids": [],
    "applications_sha256": _sha([]), "locked_proven_ids": LOCKED_EIGHT,
    "formal_source_commit": FORMAL_REVISION,
    "kernel_source_commit": KERNEL_REVISION,
    "lambda_status": "CONJECTURE_1_ADVISORY",
}
_MODEL = {
    # The controller's _validate_identity normalizes the generator's NONE.
    "id": MODEL_ID, "revision": MODEL_REVISION, "adapter_revision": "none",
    "tokenizer_revision": MODEL_REVISION, "template_revision": SOURCE_REVISION,
    "quantization_revision": "sha256:" + MODEL_SHA256,
}
_MODEL_IDENTITY = {
    "repo": MODEL_REPO, "revision": MODEL_REVISION, "file": MODEL_FILE,
    "size": MODEL_SIZE, "sha256_expected": MODEL_SHA256,
    "sha256_loaded": MODEL_SHA256, "base_model": "Qwen/Qwen2.5-1.5B-Instruct",
    "license": "Apache-2.0",
}
_FORMULA_AUTHORITY = {
    "locked_proven_count": 8, "locked_proven_ids": LOCKED_EIGHT,
    "f_id_to_callable_mapping": "UNKNOWN_NOT_ASSERTED",
    "lambda": {"formula_id": "F23", "status": "CONJECTURE_1_ADVISORY",
               "can_authorize": False, "can_be_sole_allow_basis": False},
}
_CONTRACT = {
    "schema": "szl.model-inference-lab.governed-contract/v3",
    "status": "OPERATIONAL_WHEN_GOVERNED_HEALTH_IS_READY",
    "endpoint": {
        "method": "POST", "path": ENDPOINT, "response_schema": PUBLIC_SCHEMA,
        "authentication": "PUBLIC_PROJECTION_FIXED_SCOPE", "tools": False,
        "max_input_chars": 1200, "max_completion_tokens": 32,
        "max_retrieval_handles": 4,
    },
    "retired_public_post": {
        "path": "/api/v2/governed-infer", "status_code": 410,
        "continuation_available": False,
    },
    "public_read_only_endpoints": {
        "formula_atlas": "/api/v2/formula-atlas", "source": "/api/source",
        "well_known_source": "/.well-known/szl-source.json",
    },
    "controller": {"repository": "szl-holdings/szl-forge",
                   "revision": CONTROLLER_REVISION, "version": "0.2.0"},
    "second_brain": {
        "revision": SECOND_BRAIN_REVISION, "version": "1.3.0",
        "content_access": "HANDLES_ONLY_PUBLIC",
        "authorized_hydration": "IN_PROCESS_CONTROLLER_ONLY",
        "private_graph_present": False,
    },
    "nemo": {"revision": NEMO_REVISION, "version": "0.4.0",
             "structured_witness": "doctrine-v11/E1-E10",
             "text_witness": "doctrine-v11/R1-R5"},
    "formula_authority": _FORMULA_AUTHORITY,
    "model": {"id": MODEL_ID, "revision": MODEL_REVISION,
              "gguf_sha256": MODEL_SHA256},
    "authority": {
        "model": "PROPOSAL_ONLY", "public_endpoint_tool_execution": "DISABLED",
        "a11oy": "NOT_INVOKED_BY_PUBLIC_ENDPOINT",
        "anatomy": "LOCAL_SANITIZED_OBSERVER_ONLY",
    },
    "runtime_selection": {
        "winner": "UNSELECTED", "policy": "MEASURED_WORKLOAD_BAKEOFF_REQUIRED",
        "qualified_lanes": ["local-cpu-gguf", "single-node-gpu", "distributed-gpu"],
    },
    "privacy": {
        "raw_prompt_persisted": False, "hydrated_content_persisted": False,
        "private_reasoning_persisted": False,
        "platform_logging_outside_source": "NOT_ASSERTED",
    },
}
_PACKAGE_PINS = {
    "szl-forge-inference": ("0.2.0", "szl-forge", CONTROLLER_REVISION,
        "e1e5d3fdd0de04be06344246c57f79b1a67130c4afe4fd0c278b4c62d0e89daf"),
    "szl-second-brain": ("1.3.0", "szl-second-brain", SECOND_BRAIN_REVISION,
        "23260a61b905818302429d5881a7ad0e6127f32b0a2ff4e8d2482bbc3a16b44b"),
    "szl-nemo": ("0.4.0", "szl-nemo", NEMO_REVISION,
        "600c992d4b34a9c2e4fbee68d2766717a0d719aa7e0ecab1ae19ad423c40f452"),
}
_FORMULA_COUNTS = {
    "attributed_formula_count": 30, "executable_formula_count": 21,
    "quant_domain_count": 9, "locked_proven_count": 8,
}
_RETIREMENT = {
    "method": "POST", "path": "/v1/chat/completions", "status_code": 410,
    "state": "RETIRED", "reason_code": "LEGACY_COMPATIBILITY_ROUTE_RETIRED",
    "successor": ENDPOINT,
}


def _document(doc):
    """Bound JSON shape before hashing; reject non-JSON and pathological objects."""
    budget = [8192]

    def visit(value, depth=0):
        budget[0] -= 1
        _require(depth <= 20 and budget[0] >= 0, "JSON_INVALID")
        kind = type(value)
        if kind is dict:
            _require(len(value) <= 128, "JSON_INVALID")
            for key, item in value.items():
                _require(type(key) is str and len(key) <= 128, "JSON_INVALID")
                visit(item, depth + 1)
        elif kind is list:
            _require(len(value) <= 256, "JSON_INVALID")
            for item in value:
                visit(item, depth + 1)
        elif kind is str:
            _require(len(value) <= 16384, "JSON_INVALID")
        elif kind is float:
            _require(math.isfinite(value), "JSON_INVALID")
        elif kind is int:
            _require(value.bit_length() <= 128, "JSON_INVALID")
        else:
            _require(value is None or kind is bool, "JSON_INVALID")

    _require(type(doc) is dict, "DOCUMENT_INVALID")
    visit(doc)
    _json_bytes(doc)


def _keys(value, fields, code="RESPONSE_SCHEMA"):
    _require(type(value) is dict and set(value) == set(fields), code)


def _same(actual, expected, code):
    _require(_json_bytes(actual) == _json_bytes(expected), code)


def _at(doc, path):
    value = doc
    for key in path:
        _require(type(value) is dict and key in value, "PREFLIGHT_SCHEMA")
        value = value[key]
    return value


def _expect_paths(doc, pairs, code):
    for path, expected in pairs:
        _same(_at(doc, path), expected, code)


def _hash(value, code="DIGEST_INVALID", prefixed=False):
    pattern = r"sha256:[0-9a-f]{64}" if prefixed else r"[0-9a-f]{64}"
    _require(type(value) is str and re.fullmatch(pattern, value) is not None, code)


def _strings(value, limit=32, code="RESPONSE_SCHEMA"):
    _require(type(value) is list and len(value) <= limit, code)
    _require(all(type(item) is str and 0 < len(item) <= 2048 for item in value), code)


def validate_identity(doc):
    """Check the pinned artifact/release and declared unsigned-output boundary."""
    _document(doc)
    _keys(doc, ("schema", "status", "space", "hardware", "model", "runtime",
                "receipt_boundary", "failure_code"), "IDENTITY_SCHEMA")
    _expect_paths(doc, [
        (("schema",), "szl.hf-free-inference-identity/v1"),
        (("status",), "READY"), (("failure_code",), None),
        (("space", "id"), "SZLHOLDINGS/szl-model-inference-lab"),
        (("space", "release_id"), RELEASE_ID),
        (("space", "release_manifest_sha256"), RELEASE_MANIFEST_SHA256),
        (("space", "source_integrity"), True),
        (("hardware", "required"), "cpu-basic"),
        (("hardware", "accelerator_observed"), "cpu"),
        (("runtime", "llama_cpp_python"), "0.3.21"),
        (("runtime", "prompt_cache", "status"), "DISABLED"),
        (("runtime", "concurrency"), 1),
        (("runtime", "max_input_chars"), 1200),
        (("runtime", "max_formatted_prompt_tokens"), 800),
        (("runtime", "max_new_tokens"), 32),
        (("runtime", "inference_budget_seconds"), 45.0),
        (("runtime", "max_request_body_bytes"), 8192),
        (("runtime", "body_read_timeout_seconds"), 10.0),
        (("runtime", "openai_compatible_subset", "model_id"), MODEL_ID),
        (("runtime", "openai_compatible_subset", "chat_completions"), _RETIREMENT),
        (("receipt_boundary", "status"), "DECLARED_KEY_SIGNATURES_VALID"),
        (("receipt_boundary", "evidence", "status"), "DECLARED_KEY_SIGNATURES_VALID"),
    ], "IDENTITY_PIN_MISMATCH")
    _same(doc["model"], _MODEL_IDENTITY, "MODEL_PIN_MISMATCH")
    _same(_at(doc, ("receipt_boundary", "does_not_cover")), [
        "independent identity or key-ownership binding", "Space source authorship",
        "GGUF quantization quality", "this runtime's outputs",
        "independent benchmarking", "safety certification",
    ], "IDENTITY_TRUST_BOUNDARY")
    return {"status": "READY", "model_id": MODEL_ID, "model_revision": MODEL_REVISION,
            "model_sha256": MODEL_SHA256, "release_id": RELEASE_ID,
            "release_manifest_sha256": RELEASE_MANIFEST_SHA256}


def validate_contract(doc):
    """No schema negotiation or endpoint discovery may widen this public lane."""
    _document(doc)
    _same(doc, _CONTRACT, "CONTRACT_DRIFT")
    return {"schema": _CONTRACT["schema"], "endpoint": ENDPOINT,
            "response_schema": PUBLIC_SCHEMA, "tool_execution": "DISABLED"}


def validate_health(doc):
    """Observe readiness without interpreting it as a completed inference."""
    _document(doc)
    _expect_paths(doc, [
        (("schema",), "szl.model-inference-lab.governed-health/v2"),
        (("status",), "READY"), (("legacy_model_runtime",), "READY"),
        (("source_revision",), SOURCE_REVISION),
        (("controller_revision",), CONTROLLER_REVISION),
        (("component_error",), None),
        (("dependency_status", "ready"), True),
        (("dependency_status", "contract_ready"), True),
        (("dependency_status", "contract_error"), None),
        (("dependency_status", "formula_atlas_ready"), True),
        (("dependency_status", "formula_atlas_error"), None),
        (("dependency_status", "formula_atlas_counts"), _FORMULA_COUNTS),
        (("formula_atlas",), {"ready": True, **_FORMULA_COUNTS,
                              "formula_may_authorize": False}),
        (("second_brain", "ready"), True),
        (("second_brain", "content_access"), "HANDLES_ONLY"),
        (("second_brain", "private_graph_present"), False),
        (("second_brain", "frontier", "ready"), True),
        (("second_brain", "frontier", "state"), "REVIEW_REQUIRED"),
        (("second_brain", "frontier", "source_count"), 7),
        (("second_brain", "frontier", "training_authority"), "NONE"),
        (("second_brain", "frontier", "execution_authority"), "NONE"),
        (("nemo",), {"version": "0.4.0", "envelope_rules": "doctrine-v11/E1-E10",
                     "text_rules": "doctrine-v11/R1-R5"}),
    ], "HEALTH_NOT_READY")
    packages = _at(doc, ("dependency_status", "packages"))
    _keys(packages, _PACKAGE_PINS, "DEPENDENCY_DRIFT")
    for name, (version, repository, revision, digest) in _PACKAGE_PINS.items():
        _same(packages[name], {
            "expected": version, "observed": version, "match": True,
            "direct_url": {
                "archive_info": {"hash": "sha256=" + digest,
                                 "hashes": {"sha256": digest}},
                "url": "https://github.com/szl-holdings/" + repository +
                       "/archive/" + revision + ".tar.gz",
            },
        }, "DEPENDENCY_DRIFT")
    for path in (("second_brain", "public_chunk_count"),
                 ("second_brain", "frontier", "candidate_count")):
        count = _at(doc, path)
        _require(type(count) is int and 0 < count <= 1000000, "HEALTH_NOT_READY")
    _hash(_at(doc, ("second_brain", "frontier", "candidate_set_sha256")))
    return {"status": "READY", "source_revision": SOURCE_REVISION,
            "controller_revision": CONTROLLER_REVISION,
            "second_brain_revision": SECOND_BRAIN_REVISION,
            "nemo_revision": NEMO_REVISION}


_RECEIPT_FIELDS = (
    "schema request_id state authority_state prompt_sha256 principal_id_sha256 "
    "tenant_id_sha256 policy_revision retrieval_query_sha256 ranking_receipt_sha256 "
    "evidence_set_sha256 formula_binding model runtime output_sha256 claims_sha256 "
    "citations_sha256 nemo tool_intent_sha256 action_admission_sha256 "
    "action_receipt_sha256 executed"
).split()
_PUBLIC_FIELDS = set(_RECEIPT_FIELDS) | {
    "reason_codes", "output", "output_schema", "claims", "citations", "metrics",
    "evidence_handles", "anatomy_observation", "receipt", "public_export_receipt",
}
_NEMO_FIELDS = (
    "stage decision rule_version input_hash violated_rules reasons"
).split()
_ANATOMY_FIELDS = (
    "schema request_id state authority_state prompt_sha256 principal_id_sha256 "
    "tenant_id_sha256 policy_revision evidence_set_sha256 formula_ids model_revision "
    "runtime_engine output_sha256 claims_sha256 nemo_decisions tool_intent_sha256 "
    "raw_prompt_present hydrated_content_present private_reasoning_present observer_authority"
).split()


def _witness(item, *, text=False):
    fields = set(_NEMO_FIELDS) - ({"stage"} if text else set())
    _keys(item, fields, "WITNESS_SCHEMA")
    _require(item["decision"] in ("ALLOW", "REVIEW", "BLOCK"), "WITNESS_DECISION")
    _same(item["rule_version"],
          "doctrine-v11/R1-R5" if text else "doctrine-v11/E1-E10", "WITNESS_VERSION")
    _hash(item["input_hash"], prefixed=True)
    _strings(item["violated_rules"], 16, "WITNESS_SCHEMA")
    _strings(item["reasons"], 16, "WITNESS_SCHEMA")
    if item["decision"] == "ALLOW":
        _same(item["violated_rules"], [], "WITNESS_DECISION")
    if not text:
        _require(item["stage"] in ("PRE_GENERATION", "POST_GENERATION"), "WITNESS_STAGE")


def _count(value, minimum, maximum):
    _require(type(value) in (int, float) and math.isfinite(value)
             and value == int(value) and minimum <= value <= maximum, "TOKEN_BOUNDARY")
    return int(value)


def _receipt(doc):
    receipt = doc["receipt"]
    _keys(receipt, ("schema", "canonicalization", "algorithm", "payload",
                    "receipt_sha256", "signature"), "RECEIPT_SCHEMA")
    _same(receipt["schema"], "szl.forge.production-inference-receipt/v2", "RECEIPT_SCHEMA")
    _same(receipt["canonicalization"], "utf8-json-sort-keys-compact", "RECEIPT_SCHEMA")
    _same(receipt["algorithm"], "sha256", "RECEIPT_SCHEMA")
    _same(receipt["signature"], {
        "status": "UNSIGNED_LOCAL", "must_be_signed_before_consequential_action": True,
    }, "UNSIGNED_BOUNDARY")
    payload = receipt["payload"]
    _keys(payload, _RECEIPT_FIELDS, "RECEIPT_SCHEMA")
    _same(payload["schema"], SOURCE_SCHEMA, "RECEIPT_SCHEMA")
    for key in _RECEIPT_FIELDS:
        if key != "schema":
            _same(payload[key], doc[key], "RECEIPT_BINDING")
    _same(receipt["receipt_sha256"], _sha(payload), "RECEIPT_DIGEST")
    export = doc["public_export_receipt"]
    _keys(export, ("schema", "state", "policy", "source_schema", "public_sha256",
                   "signature_status"), "EXPORT_SCHEMA")
    _same({k: v for k, v in export.items() if k != "public_sha256"}, {
        "schema": "szl.forge.public-transcript-export-receipt/v1", "state": "EXPORTED",
        "policy": "strict-v1-private-continuation-omitted",
        "source_schema": SOURCE_SCHEMA, "signature_status": "UNSIGNED_LOCAL",
    }, "EXPORT_SCHEMA")
    body = {key: value for key, value in doc.items() if key != "public_export_receipt"}
    _same(export["public_sha256"], _sha(body), "EXPORT_DIGEST")


def _anatomy(doc):
    observation = doc["anatomy_observation"]
    _keys(observation, ("delivery", "event"), "OBSERVER_SCHEMA")
    _same(observation["delivery"], "DELIVERED", "OBSERVER_UNAVAILABLE")
    event = observation["event"]
    _keys(event, _ANATOMY_FIELDS, "OBSERVER_SCHEMA")
    expected = {
        key: doc[key] for key in (
            "request_id", "state", "authority_state", "prompt_sha256",
            "principal_id_sha256", "tenant_id_sha256", "policy_revision",
            "evidence_set_sha256", "output_sha256", "claims_sha256", "tool_intent_sha256",
        )
    }
    expected.update({
        "schema": "szl.anatomy.production-inference-observation/v2",
        "formula_ids": doc["formula_binding"]["requested_ids"],
        "model_revision": (doc["model"] or {}).get("revision"),
        "runtime_engine": (doc["runtime"] or {}).get("engine"),
        "nemo_decisions": [{"stage": w["stage"], "decision": w["decision"]}
                           for w in doc["nemo"]],
        "raw_prompt_present": False, "hydrated_content_present": False,
        "private_reasoning_present": False, "observer_authority": "NONE",
    })
    _same(event, expected, "OBSERVER_BINDING")


def validate_response(doc, *, prompt, max_new_tokens, http_status):
    """Return bounded answer metadata only after exact unsigned v3 validation."""
    _document(doc)
    _require(type(prompt) is str and 0 < len(prompt) <= 1200 and prompt.strip()
             and "\x00" not in prompt
             and not any(t in prompt for t in ("<|im_start|>", "<|im_end|>", "<|endoftext|>")),
             "REQUEST_INVALID")
    prompt = prompt.strip()
    _require(type(max_new_tokens) is int and 1 <= max_new_tokens <= 32, "REQUEST_INVALID")
    state = doc.get("state")
    status_by_state = {"PROPOSAL": 200, "ABSTAIN": 422, "REVIEW": 409, "BLOCKED": 503}
    _require(type(state) is str and state in status_by_state, "RESPONSE_STATE")
    _require(type(http_status) is int and http_status == status_by_state[state], "HTTP_STATE_MISMATCH")
    fields = _PUBLIC_FIELDS if state == "PROPOSAL" else _PUBLIC_FIELDS - {"output_schema", "evidence_handles"}
    _keys(doc, fields)
    _same(doc["schema"], PUBLIC_SCHEMA, "RESPONSE_SCHEMA")
    _same(doc["executed"], False, "ACTION_AUTHORITY")
    _same(doc["authority_state"], "NO_ACTION_AUTHORITY" if state == "PROPOSAL" else "NONE",
          "ACTION_AUTHORITY")
    for key in ("tool_intent_sha256", "action_admission_sha256", "action_receipt_sha256"):
        _same(doc[key], None, "ACTION_AUTHORITY")
    expected_request = {
        "prompt_sha256": _text_sha(prompt),
        "retrieval_query_sha256": _text_sha(prompt),
        "principal_id_sha256": _text_sha("public-anonymous"),
        "tenant_id_sha256": _text_sha("public"),
        "policy_revision": PUBLIC_POLICY_REVISION,
        "request_id": _text_sha(
            "public\x00public-anonymous\x00" + PUBLIC_POLICY_REVISION + "\x00" + prompt
        )[:24],
    }
    for key, value in expected_request.items():
        _same(doc[key], value, "REQUEST_BINDING")
    for key in ("ranking_receipt_sha256", "evidence_set_sha256"):
        _hash(doc[key])
    _same(doc["formula_binding"], _FORMULA, "FORMULA_AUTHORITY")
    _strings(doc["reason_codes"], 32)
    _require(type(doc["nemo"]) is list and len(doc["nemo"]) <= 2, "WITNESS_SCHEMA")
    for witness in doc["nemo"]:
        _witness(witness)
    stages = [w["stage"] for w in doc["nemo"]]
    _require(stages in ([], ["PRE_GENERATION"], ["PRE_GENERATION", "POST_GENERATION"]),
             "WITNESS_SEQUENCE")
    if len(doc["nemo"]) == 2:
        _same(doc["nemo"][0]["decision"], "ALLOW", "WITNESS_SEQUENCE")
    _same(doc["claims_sha256"], _sha(doc["claims"]), "CLAIMS_DIGEST")
    _same(doc["citations_sha256"], _sha(doc["citations"]), "CITATIONS_DIGEST")
    usage = {}
    if state == "PROPOSAL":
        _same(doc["reason_codes"], [], "PROPOSAL_REASONS")
        _same([(w["stage"], w["decision"]) for w in doc["nemo"]],
              [("PRE_GENERATION", "ALLOW"), ("POST_GENERATION", "ALLOW")],
              "WITNESS_SEQUENCE")
        _require(type(doc["output"]) is str and 0 < len(doc["output"]) <= 16384
                 and bool(doc["output"].strip()), "OUTPUT_INVALID")
        _same(doc["output_sha256"], _text_sha(doc["output"]), "OUTPUT_DIGEST")
        _same(doc["output_schema"], "szl.answer-with-node-citations/v2", "OUTPUT_SCHEMA")
        _same(doc["model"], _MODEL, "MODEL_PIN_MISMATCH")
        _keys(doc["runtime"], ("engine", "version", "hardware_fingerprint"), "RUNTIME_SCHEMA")
        _same(doc["runtime"]["engine"], "llama-cpp-python", "RUNTIME_PIN_MISMATCH")
        _same(doc["runtime"]["version"], "0.3.21", "RUNTIME_PIN_MISMATCH")
        _hash(doc["runtime"]["hardware_fingerprint"], prefixed=True)
        metrics = doc["metrics"]
        _keys(metrics, ("elapsed_ms", "prompt_tokens", "completion_tokens",
                        "finish_reason", "nemo_text_witness"), "METRICS_SCHEMA")
        _same(metrics["finish_reason"], "stop", "INCOMPLETE_OUTPUT")
        _require(type(metrics["elapsed_ms"]) in (int, float)
                 and math.isfinite(metrics["elapsed_ms"]) and metrics["elapsed_ms"] >= 0,
                 "METRICS_INVALID")
        count_in = _count(metrics["prompt_tokens"], 1, 800)
        count_out = _count(metrics["completion_tokens"], 1, max_new_tokens)
        usage = {"prompt_tokens": count_in, "completion_tokens": count_out,
                 "total_tokens": count_in + count_out}
        _witness(metrics["nemo_text_witness"], text=True)
        _same(metrics["nemo_text_witness"]["decision"], "ALLOW", "TEXT_WITNESS_BLOCKED")
        _same(metrics["nemo_text_witness"]["input_hash"],
              "sha256:" + _sha({"prompt": prompt, "answer": doc["output"]}),
              "TEXT_WITNESS_BINDING")
        handles = doc["evidence_handles"]
        _require(type(handles) is list and 1 <= len(handles) <= 3, "EVIDENCE_BOUNDARY")
        for handle in handles:
            _keys(handle, ("nodeId", "nodeKind", "label", "note"), "EVIDENCE_SCHEMA")
            _require(all(type(v) is str for v in handle.values())
                     and 0 < len(handle["nodeId"]) <= 256, "EVIDENCE_SCHEMA")
        ids = [h["nodeId"] for h in handles]
        _require(len(ids) == len(set(ids)), "EVIDENCE_BOUNDARY")
        _strings(doc["citations"], 3)
        _require(len(doc["citations"]) == len(set(doc["citations"]))
                 and set(doc["citations"]).issubset(ids), "CITATION_BINDING")
        _require(type(doc["claims"]) is list and len(doc["claims"]) == 1, "CLAIM_SCHEMA")
        claim = doc["claims"][0]
        _keys(claim, ("label", "statement_sha256", "supporting_node_ids"), "CLAIM_SCHEMA")
        _same(claim["label"], "MODELED", "CLAIM_LABEL")
        _same(claim["statement_sha256"], doc["output_sha256"], "CLAIM_BINDING")
        _strings(claim["supporting_node_ids"], 3)
        support = claim["supporting_node_ids"]
        _require(support and len(support) == len(set(support))
                 and set(support).issubset(ids), "CLAIM_BINDING")
    else:
        _require(bool(doc["reason_codes"]), "TERMINAL_REASON")
        for key in ("output", "output_sha256", "model", "runtime"):
            _same(doc[key], None, "TERMINAL_OUTPUT")
        for key, empty in (("metrics", {}), ("claims", []), ("citations", [])):
            _same(doc[key], empty, "TERMINAL_OUTPUT")
        if state == "ABSTAIN":
            _same(doc["nemo"], [], "WITNESS_SEQUENCE")
            _same(doc["reason_codes"], ["NO_GROUNDED_EVIDENCE"], "TERMINAL_REASON")
        if state == "REVIEW":
            _require(doc["nemo"] and doc["nemo"][-1]["decision"] == "REVIEW",
                     "WITNESS_SEQUENCE")
        if state == "BLOCKED" and doc["nemo"]:
            _require(doc["nemo"][-1]["decision"] in ("ALLOW", "BLOCK"),
                     "WITNESS_SEQUENCE")
    _anatomy(doc)
    _receipt(doc)
    return {
        "state": state, "answer": doc["output"] if state == "PROPOSAL" else None,
        "usage": usage, "provider_response_id": doc["request_id"],
        "inference_receipt_sha256": doc["receipt"]["receipt_sha256"],
        "public_export_sha256": doc["public_export_receipt"]["public_sha256"],
        "evidence_handles": [
            {key: handle[key] for key in ("nodeId", "nodeKind", "label", "note")}
            for handle in doc.get("evidence_handles", [])
        ],
        "citations": list(doc["citations"]),
    }
