#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""MODELED synthetic fixtures for the pinned public CPU contract.

These fixtures never establish live readiness, generated quality, or a signature.
Preflight shapes follow Space source 675d3fb83f0e1b765eeed5374e17faee656ecc6a.
"""

import copy
import hashlib
import json

import a11oy_cpu_lab_contract as contract

_PREFLIGHT = {'identity': {'schema': 'szl.hf-free-inference-identity/v1',
              'status': 'READY',
              'space': {'id': 'SZLHOLDINGS/szl-model-inference-lab',
                        'release_id': 'brain13-1d3960c-controller-9f227f6-atlas-d7b08cde',
                        'release_manifest_sha256': '557e4c1463e46d02ef15fd92366b3106e274a7dc5edd3785288ef416f82e25ac',
                        'source_integrity': True,
                        'source_integrity_meaning': 'internal release-file checksum consistency; '
                                                    'not external authorship evidence',
                        'license': 'Apache-2.0'},
              'hardware': {'required': 'cpu-basic',
                           'accelerator_observed': 'cpu',
                           'cpu_cores_observed': '2',
                           'memory_observed': '16.0G'},
              'model': {'repo': 'SZLHOLDINGS/SZL-Khipu-1.5B-GGUF',
                        'revision': '67d60ec577730747055491640cfb91fc4a4b5d25',
                        'file': 'SZL-Khipu-1.5B-Q4_K_M.gguf',
                        'size': 986047904,
                        'sha256_expected': '13c1a1993063e1dff92f7413ccf48eaca6d48efc8801ae9af35961ae3396623a',
                        'sha256_loaded': '13c1a1993063e1dff92f7413ccf48eaca6d48efc8801ae9af35961ae3396623a',
                        'base_model': 'Qwen/Qwen2.5-1.5B-Instruct',
                        'license': 'Apache-2.0'},
              'runtime': {'python': '3.11.15',
                          'llama_cpp_python': '0.3.21',
                          'prompt_cache': {'status': 'DISABLED',
                                           'advisory': 'CVE-2025-69872',
                                           'boundary': 'llama-cpp-python requires DiskCache, but '
                                                       'this runtime never attaches a prompt cache '
                                                       'and fails startup if one is present'},
                          'concurrency': 1,
                          'max_input_chars': 1200,
                          'max_chat_messages': 12,
                          'max_formatted_prompt_tokens': 800,
                          'max_new_tokens': 32,
                          'inference_budget_seconds': 45.0,
                          'inference_budget_semantics': 'best-effort cutoff checked between '
                                                        'streamed token chunks; not a hard '
                                                        'wall-clock deadline',
                          'dependency_boundary': 'Python package versions are pinned; llama CPU '
                                                 'wheel is hash-pinned; a full system-package/SBOM '
                                                 'attestation is not claimed',
                          'max_request_body_bytes': 8192,
                          'body_read_timeout_seconds': 10.0,
                          'openai_compatible_subset': {'models': 'GET /v1/models',
                                                       'chat_completions': {'method': 'POST',
                                                                            'path': '/v1/chat/completions',
                                                                            'status_code': 410,
                                                                            'state': 'RETIRED',
                                                                            'reason_code': 'LEGACY_COMPATIBILITY_ROUTE_RETIRED',
                                                                            'successor': '/api/v3/governed-infer'},
                                                       'model_id': 'SZLHOLDINGS/SZL-Khipu-1.5B-GGUF@67d60ec577730747055491640cfb91fc4a4b5d25'}},
              'receipt_boundary': {'status': 'DECLARED_KEY_SIGNATURES_VALID',
                                   'evidence': {'status': 'DECLARED_KEY_SIGNATURES_VALID',
                                                'key_id': '89540347a69b789e',
                                                'training_canonical_sha256': '242b52435df315aecefb42f0ae1f87bf10acc83f9af42976986b4f0f34efc081',
                                                'eval_canonical_sha256': '9a88c74863099c752bfcd20e7d602ca14c161cc8d68eb78d052af686aebb600e'},
                                   'covers': 'training/eval signatures verify against the '
                                             'repository-declared key, including their '
                                             'canonical-payload hash chain',
                                   'does_not_cover': ['independent identity or key-ownership '
                                                      'binding',
                                                      'Space source authorship',
                                                      'GGUF quantization quality',
                                                      "this runtime's outputs",
                                                      'independent benchmarking',
                                                      'safety certification']},
              'failure_code': None},
 'contract': {'schema': 'szl.model-inference-lab.governed-contract/v3',
              'status': 'OPERATIONAL_WHEN_GOVERNED_HEALTH_IS_READY',
              'endpoint': {'method': 'POST',
                           'path': '/api/v3/governed-infer',
                           'response_schema': 'szl.forge.public-governed-inference/v3',
                           'authentication': 'PUBLIC_PROJECTION_FIXED_SCOPE',
                           'tools': False,
                           'max_input_chars': 1200,
                           'max_completion_tokens': 32,
                           'max_retrieval_handles': 4},
              'retired_public_post': {'path': '/api/v2/governed-infer',
                                      'status_code': 410,
                                      'continuation_available': False},
              'public_read_only_endpoints': {'formula_atlas': '/api/v2/formula-atlas',
                                             'source': '/api/source',
                                             'well_known_source': '/.well-known/szl-source.json'},
              'controller': {'repository': 'szl-holdings/szl-forge',
                             'revision': '9f227f6a10dac178b29130c742c98451b6ed8391',
                             'version': '0.2.0'},
              'second_brain': {'revision': '1d3960c69235f117b7ec2b5ea97472f81fb588f5',
                               'version': '1.3.0',
                               'content_access': 'HANDLES_ONLY_PUBLIC',
                               'authorized_hydration': 'IN_PROCESS_CONTROLLER_ONLY',
                               'private_graph_present': False},
              'nemo': {'revision': '810231a531188bb569e3faa17396386eb0a5e260',
                       'version': '0.4.0',
                       'structured_witness': 'doctrine-v11/E1-E10',
                       'text_witness': 'doctrine-v11/R1-R5'},
              'formula_authority': {'locked_proven_count': 8,
                                    'locked_proven_ids': ['F1',
                                                          'F4',
                                                          'F7',
                                                          'F11',
                                                          'F12',
                                                          'F18',
                                                          'F19',
                                                          'F22'],
                                    'f_id_to_callable_mapping': 'UNKNOWN_NOT_ASSERTED',
                                    'lambda': {'formula_id': 'F23',
                                               'status': 'CONJECTURE_1_ADVISORY',
                                               'can_authorize': False,
                                               'can_be_sole_allow_basis': False}},
              'model': {'id': 'SZLHOLDINGS/SZL-Khipu-1.5B-GGUF@67d60ec577730747055491640cfb91fc4a4b5d25',
                        'revision': '67d60ec577730747055491640cfb91fc4a4b5d25',
                        'gguf_sha256': '13c1a1993063e1dff92f7413ccf48eaca6d48efc8801ae9af35961ae3396623a'},
              'authority': {'model': 'PROPOSAL_ONLY',
                            'public_endpoint_tool_execution': 'DISABLED',
                            'a11oy': 'NOT_INVOKED_BY_PUBLIC_ENDPOINT',
                            'anatomy': 'LOCAL_SANITIZED_OBSERVER_ONLY'},
              'runtime_selection': {'winner': 'UNSELECTED',
                                    'policy': 'MEASURED_WORKLOAD_BAKEOFF_REQUIRED',
                                    'qualified_lanes': ['local-cpu-gguf',
                                                        'single-node-gpu',
                                                        'distributed-gpu']},
              'privacy': {'raw_prompt_persisted': False,
                          'hydrated_content_persisted': False,
                          'private_reasoning_persisted': False,
                          'platform_logging_outside_source': 'NOT_ASSERTED'}},
 'health': {'schema': 'szl.model-inference-lab.governed-health/v2',
            'status': 'READY',
            'legacy_model_runtime': 'READY',
            'source_revision': 'c94e9218093e0815745cbd5dccaddea1797379a3',
            'controller_revision': '9f227f6a10dac178b29130c742c98451b6ed8391',
            'dependency_status': {'ready': True,
                                  'packages': {'szl-forge-inference': {'expected': '0.2.0',
                                                                       'observed': '0.2.0',
                                                                       'match': True,
                                                                       'direct_url': {'archive_info': {'hash': 'sha256=e1e5d3fdd0de04be06344246c57f79b1a67130c4afe4fd0c278b4c62d0e89daf',
                                                                                                       'hashes': {'sha256': 'e1e5d3fdd0de04be06344246c57f79b1a67130c4afe4fd0c278b4c62d0e89daf'}},
                                                                                      'url': 'https://github.com/szl-holdings/szl-forge/archive/9f227f6a10dac178b29130c742c98451b6ed8391.tar.gz'}},
                                               'szl-second-brain': {'expected': '1.3.0',
                                                                    'observed': '1.3.0',
                                                                    'match': True,
                                                                    'direct_url': {'archive_info': {'hash': 'sha256=23260a61b905818302429d5881a7ad0e6127f32b0a2ff4e8d2482bbc3a16b44b',
                                                                                                    'hashes': {'sha256': '23260a61b905818302429d5881a7ad0e6127f32b0a2ff4e8d2482bbc3a16b44b'}},
                                                                                   'url': 'https://github.com/szl-holdings/szl-second-brain/archive/1d3960c69235f117b7ec2b5ea97472f81fb588f5.tar.gz'}},
                                               'szl-nemo': {'expected': '0.4.0',
                                                            'observed': '0.4.0',
                                                            'match': True,
                                                            'direct_url': {'archive_info': {'hash': 'sha256=600c992d4b34a9c2e4fbee68d2766717a0d719aa7e0ecab1ae19ad423c40f452',
                                                                                            'hashes': {'sha256': '600c992d4b34a9c2e4fbee68d2766717a0d719aa7e0ecab1ae19ad423c40f452'}},
                                                                           'url': 'https://github.com/szl-holdings/szl-nemo/archive/810231a531188bb569e3faa17396386eb0a5e260.tar.gz'}}},
                                  'contract_ready': True,
                                  'contract_error': None,
                                  'formula_atlas_ready': True,
                                  'formula_atlas_error': None,
                                  'formula_atlas_counts': {'attributed_formula_count': 30,
                                                           'executable_formula_count': 21,
                                                           'quant_domain_count': 9,
                                                           'locked_proven_count': 8}},
            'formula_atlas': {'ready': True,
                              'attributed_formula_count': 30,
                              'executable_formula_count': 21,
                              'quant_domain_count': 9,
                              'locked_proven_count': 8,
                              'formula_may_authorize': False},
            'second_brain': {'ready': True,
                             'public_chunk_count': 575,
                             'content_access': 'HANDLES_ONLY',
                             'private_graph_present': False,
                             'frontier': {'ready': True,
                                          'state': 'REVIEW_REQUIRED',
                                          'candidate_count': 129,
                                          'source_count': 7,
                                          'candidate_set_sha256': 'fb15e2d2822a9afb445c3eae7e077a7c250a59565fdd395a9e11f2247b12a884',
                                          'training_authority': 'NONE',
                                          'execution_authority': 'NONE'}},
            'nemo': {'version': '0.4.0',
                     'envelope_rules': 'doctrine-v11/E1-E10',
                     'text_rules': 'doctrine-v11/R1-R5'},
            'component_error': None}}


def canonical_sha256(value):
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def text_sha256(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def identity_document(**changes):
    doc = copy.deepcopy(_PREFLIGHT["identity"])
    doc.update(changes)
    return doc


def contract_document(**changes):
    doc = copy.deepcopy(_PREFLIGHT["contract"])
    doc.update(changes)
    return doc


def health_document(**changes):
    doc = copy.deepcopy(_PREFLIGHT["health"])
    doc.update(changes)
    return doc


RECEIPT_PAYLOAD_FIELDS = (
    "schema request_id state authority_state prompt_sha256 principal_id_sha256 "
    "tenant_id_sha256 policy_revision retrieval_query_sha256 ranking_receipt_sha256 "
    "evidence_set_sha256 formula_binding model runtime output_sha256 claims_sha256 "
    "citations_sha256 nemo tool_intent_sha256 action_admission_sha256 "
    "action_receipt_sha256 executed"
).split()


def rehash_response(doc, *, prompt=None):
    """Recompute unsigned fixture digests; this does not create a signature.

    Existing semantic changes remain changes. Supplying prompt also binds the
    text witness to the modified output, allowing adversarial tests past hashes.
    """
    doc["output_sha256"] = text_sha256(doc["output"]) if doc["output"] is not None else None
    doc["claims_sha256"] = canonical_sha256(doc["claims"])
    doc["citations_sha256"] = canonical_sha256(doc["citations"])
    if prompt is not None and doc["state"] == "PROPOSAL":
        doc["metrics"]["nemo_text_witness"]["input_hash"] = "sha256:" + canonical_sha256({
            "prompt": prompt.strip(), "answer": doc["output"],
        })
    event = doc["anatomy_observation"]["event"]
    for key in (
        "request_id", "state", "authority_state", "prompt_sha256",
        "principal_id_sha256", "tenant_id_sha256", "policy_revision",
        "evidence_set_sha256", "output_sha256", "claims_sha256", "tool_intent_sha256",
    ):
        event[key] = copy.deepcopy(doc[key])
    event.update({
        "formula_ids": copy.deepcopy(doc["formula_binding"]["requested_ids"]),
        "model_revision": (doc["model"] or {}).get("revision"),
        "runtime_engine": (doc["runtime"] or {}).get("engine"),
        "nemo_decisions": [{"stage": w["stage"], "decision": w["decision"]}
                           for w in doc["nemo"]],
    })
    payload = {key: copy.deepcopy(doc[key]) for key in RECEIPT_PAYLOAD_FIELDS}
    payload["schema"] = "szl.forge.production-governed-inference/v2"
    doc["receipt"]["payload"] = payload
    doc["receipt"]["receipt_sha256"] = canonical_sha256(payload)
    doc["public_export_receipt"]["public_sha256"] = canonical_sha256({
        key: value for key, value in doc.items() if key != "public_export_receipt"
    })
    return doc


def response_document(request_body, state="PROPOSAL", answer="A small blue ceramic cup."):
    prompt = request_body["prompt"].strip()
    policy = "sha256:" + canonical_sha256({
        "schema": "szl.public-memory-policy/v1", "principal": "public-anonymous",
        "tenant": "public", "second_brain_revision": contract.SECOND_BRAIN_REVISION,
        "access": "PUBLIC_PROJECTION_ONLY", "tool_authority": "NONE",
    })
    proposal = state == "PROPOSAL"

    def witness(stage, decision="ALLOW"):
        return {
            "stage": stage, "decision": decision,
            "rule_version": "doctrine-v11/E1-E10",
            "input_hash": "sha256:" + text_sha256("MODELED envelope " + stage),
            "violated_rules": [], "reasons": [],
        }

    nemo = [witness("PRE_GENERATION"), witness("POST_GENERATION")] if proposal else []
    reasons = []
    if state == "ABSTAIN":
        reasons = ["NO_GROUNDED_EVIDENCE"]
    elif state == "REVIEW":
        nemo = [witness("PRE_GENERATION", "REVIEW")]
        reasons = ["NEMO_PRE_GENERATION_REVIEW"]
    elif state == "BLOCKED":
        reasons = ["SECOND_BRAIN_RETRIEVAL_INVALID", "ModeledFixtureError"]
    doc = {
        "schema": "szl.forge.public-governed-inference/v3",
        "request_id": text_sha256("public\x00public-anonymous\x00" + policy + "\x00" + prompt)[:24],
        "prompt_sha256": text_sha256(prompt),
        "principal_id_sha256": text_sha256("public-anonymous"),
        "tenant_id_sha256": text_sha256("public"),
        "policy_revision": policy,
        "retrieval_query_sha256": text_sha256(prompt),
        "ranking_receipt_sha256": canonical_sha256({"modeled_fixture": True}),
        "evidence_set_sha256": canonical_sha256(["MODELED public node"]),
        "formula_binding": {
            "requested_ids": [], "authorization_basis_ids": [],
            "applications_sha256": canonical_sha256([]),
            "locked_proven_ids": ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
            "formal_source_commit": "c497b4ed402249f23da7f290426f0e21c70ab926",
            "kernel_source_commit": "46cfa948367e8133eaa8dd6bcfb781b19165b9bb",
            "lambda_status": "CONJECTURE_1_ADVISORY",
        },
        "executed": False, "state": state,
        "authority_state": "NO_ACTION_AUTHORITY" if proposal else "NONE",
        "reason_codes": reasons, "nemo": nemo,
        "output": answer if proposal else None, "output_sha256": None,
        "claims": [{
            "label": "MODELED", "statement_sha256": text_sha256(answer),
            "supporting_node_ids": ["modeled-public-node-1"],
        }] if proposal else [],
        "claims_sha256": None, "citations": [], "citations_sha256": None,
        "model": {
            "id": contract.MODEL_ID, "revision": contract.MODEL_REVISION,
            "adapter_revision": "none", "tokenizer_revision": contract.MODEL_REVISION,
            "template_revision": contract.SOURCE_REVISION,
            "quantization_revision": "sha256:" + contract.MODEL_SHA256,
        } if proposal else None,
        "runtime": {
            "engine": "llama-cpp-python", "version": "0.3.21",
            "hardware_fingerprint": "sha256:" + text_sha256("MODELED fixture hardware"),
        } if proposal else None,
        "metrics": {
            "elapsed_ms": 125.0, "prompt_tokens": 18,
            "completion_tokens": min(7, request_body.get("max_new_tokens", 24)),
            "finish_reason": "stop",
            "nemo_text_witness": {
                "decision": "ALLOW", "rule_version": "doctrine-v11/R1-R5",
                "input_hash": "", "violated_rules": [], "reasons": [],
            },
        } if proposal else {},
        "tool_intent_sha256": None, "action_admission_sha256": None,
        "action_receipt_sha256": None,
        "anatomy_observation": {
            "delivery": "DELIVERED",
            "event": {
                "schema": "szl.anatomy.production-inference-observation/v2",
                "raw_prompt_present": False, "hydrated_content_present": False,
                "private_reasoning_present": False, "observer_authority": "NONE",
            },
        },
        "receipt": {
            "schema": "szl.forge.production-inference-receipt/v2",
            "canonicalization": "utf8-json-sort-keys-compact", "algorithm": "sha256",
            "payload": {}, "receipt_sha256": "",
            "signature": {"status": "UNSIGNED_LOCAL",
                          "must_be_signed_before_consequential_action": True},
        },
        "public_export_receipt": {
            "schema": "szl.forge.public-transcript-export-receipt/v1",
            "state": "EXPORTED", "policy": "strict-v1-private-continuation-omitted",
            "source_schema": "szl.forge.production-governed-inference/v2",
            "public_sha256": "", "signature_status": "UNSIGNED_LOCAL",
        },
    }
    if proposal:
        doc["output_schema"] = "szl.answer-with-node-citations/v2"
        doc["evidence_handles"] = [{
            "nodeId": "modeled-public-node-1", "nodeKind": "formula",
            "label": "MODELED fixture node", "note": "Synthetic test evidence only.",
        }]
    return rehash_response(doc, prompt=prompt)
