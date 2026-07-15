#!/usr/bin/env python3
"""Fail-closed live verifier for the A11oy Khipu Second Brain.

The verifier deliberately runs outside the serving process.  It obtains the
boot-scoped public key over HTTP, exercises Maskaq and Yupaq with bounded
prompts, verifies each DSSE ECDSA-P256 signature, and independently rebuilds
the hashes that bind prompts, answers, model identity, grounding, evidence,
handles, augmented prompts, and citations.

No response text, prompt text, private key, credential, or environment value is
written to the output.  A content-addressed summary is created only after every
required check passes.  A failure creates no output directory or artifact.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Callable, Mapping
import urllib.error
import urllib.parse
import urllib.request

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec


SCHEMA = "szl.khipu.second-brain-live-verification.v1"
SECOND_BRAIN_SCHEMA = "szl.khipu.compound-second-brain.v1"
RECEIPT_PAYLOAD_TYPE = "application/vnd.szl.receipt+json"
VERIFY_KEY_PATH = "/api/a11oy/cosign.pub"
EXPECTED_BRAIN_HANDLE_COUNT = 9464
MAX_HTTP_BODY_BYTES = 8 * 1024 * 1024
HEX64 = re.compile(r"^[0-9a-f]{64}$")

MASKAQ_PROMPT = (
    "Return only JSON with decision and citedNodeIds. Propose a retrieval plan "
    "for the A11oy Brain provenance boundary using only offered handles."
)
YUPAQ_PROMPT = (
    "Return a bounded proposal that names the receipt checks required before a "
    "Brain training row may enter gradients. Do not claim execution."
)


class VerificationError(RuntimeError):
    """A fail-closed verification failure safe to display to an operator."""


def _require(condition: Any, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256(_canonical_json(value))


def _strict_json_bytes(body: bytes, *, label: str) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in pairs:
            if key in out:
                raise VerificationError(f"{label}: duplicate JSON key {key!r}")
            out[key] = value
        return out

    try:
        return json.loads(body.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except VerificationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"{label}: malformed UTF-8 JSON ({type(exc).__name__})") from exc


def _pae(payload_type: str, body: bytes) -> bytes:
    type_bytes = payload_type.encode("utf-8")
    return (
        b"DSSEv1 "
        + str(len(type_bytes)).encode("ascii")
        + b" "
        + type_bytes
        + b" "
        + str(len(body)).encode("ascii")
        + b" "
        + body
    )


def verify_dsse_receipt(envelope: Mapping[str, Any], public_pem: bytes) -> dict[str, Any]:
    """Verify one receipt and return its decoded signed payload.

    Mutable envelope metadata is never trusted.  It is accepted only when it is
    byte-for-byte consistent with the signer identity inside the signed payload.
    """
    _require(isinstance(envelope, Mapping), "receipt is not a JSON object")
    _require(envelope.get("signed") is True, "receipt is not marked signed")
    payload_type = envelope.get("payloadType")
    _require(payload_type == RECEIPT_PAYLOAD_TYPE, "unexpected DSSE payloadType")
    encoded = envelope.get("payload")
    _require(isinstance(encoded, str) and encoded, "receipt payload is missing")
    try:
        body = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise VerificationError("receipt payload is not canonical base64") from exc
    payload = _strict_json_bytes(body, label="receipt payload")
    _require(isinstance(payload, dict), "receipt payload is not a JSON object")
    _require(body == _canonical_json(payload), "receipt payload is not canonical JSON")

    signatures = envelope.get("signatures")
    _require(isinstance(signatures, list) and len(signatures) == 1,
             "receipt must carry exactly one signature")
    signature_entry = signatures[0]
    _require(isinstance(signature_entry, dict), "signature entry is malformed")
    keyid = signature_entry.get("keyid")
    _require(isinstance(keyid, str) and keyid, "signature keyid is missing")
    encoded_signature = signature_entry.get("sig")
    _require(isinstance(encoded_signature, str) and encoded_signature,
             "signature bytes are missing")
    try:
        signature = base64.b64decode(encoded_signature, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise VerificationError("signature is not canonical base64") from exc

    identity = payload.get("_signing_identity")
    _require(isinstance(identity, dict), "signed key identity is missing")
    fingerprint = _sha256(public_pem.strip())
    expected_identity = {
        "keyid": keyid,
        "verify_key_url": VERIFY_KEY_PATH,
        "key_scope": "PROCESS_BOOT_EPHEMERAL",
        "key_lifetime": "UNTIL_PROCESS_RESTART",
        "key_fingerprint_sha256": fingerprint,
    }
    for field, expected in expected_identity.items():
        _require(identity.get(field) == expected,
                 f"signed key identity mismatch for {field}")
    # The current wire contract duplicates discovery/lifetime fields for
    # operator ergonomics, but the keyid remains in the DSSE signature entry.
    # The signed identity above is authoritative for all five fields.
    for field, expected in expected_identity.items():
        if field == "keyid":
            continue
        _require(envelope.get(field) == expected,
                 f"envelope metadata mismatch for {field}")

    try:
        public_key = serialization.load_pem_public_key(public_pem)
    except (TypeError, ValueError) as exc:
        raise VerificationError("verify key is not a valid PEM public key") from exc
    _require(isinstance(public_key, ec.EllipticCurvePublicKey),
             "verify key is not an EC public key")
    _require(isinstance(public_key.curve, ec.SECP256R1),
             "verify key is not P-256")
    pae = _pae(payload_type, body)
    if "_pae_sha256" in envelope:
        _require(envelope.get("_pae_sha256") == _sha256(pae),
                 "DSSE PAE digest mismatch")
    try:
        public_key.verify(signature, pae, ec.ECDSA(hashes.SHA256()))
    except InvalidSignature as exc:
        raise VerificationError("DSSE ECDSA signature verification failed") from exc
    return payload


def _parse_citation_answer(answer: str) -> list[str]:
    candidate = answer.strip()
    if candidate.startswith("```") and candidate.endswith("```"):
        candidate = candidate[3:-3].strip()
        if candidate.lower().startswith("json"):
            candidate = candidate[4:].lstrip()
    parsed = _strict_json_bytes(candidate.encode("utf-8"), label="Maskaq answer")
    _require(isinstance(parsed, dict), "Maskaq answer is not a JSON object")
    if "citedNodeIds" in parsed:
        cited = parsed["citedNodeIds"]
    else:
        cited = parsed.get("cited_node_ids")
    _require(isinstance(cited, list), "Maskaq answer has no citation list")
    _require(all(isinstance(item, str) and item for item in cited),
             "Maskaq answer has a malformed citation")
    _require(len(cited) == len(set(cited)), "Maskaq answer repeats a citation")
    return cited


def _validate_grounding(prompt: str, turn: Mapping[str, Any], receipt: Mapping[str, Any]) -> dict[str, Any]:
    grounding = turn.get("grounding")
    _require(isinstance(grounding, dict), "Maskaq grounding is missing")
    _require(grounding.get("schema") == "szl.brain.navigator-context/v1",
             "Maskaq grounding schema mismatch")
    _require(grounding.get("ready") is True, "Maskaq grounding did not pass")
    _require(grounding.get("state") == "GROUNDED_HANDLES_READY",
             "Maskaq grounding state is not ready")
    _require(grounding.get("content_access") == "HANDLES_ONLY",
             "Maskaq received content rather than handles")
    _require(grounding.get("query_sha256") == _sha256(prompt.encode("utf-8")),
             "grounding query digest mismatch")

    handles = grounding.get("handles")
    evidence = grounding.get("evidence")
    _require(isinstance(handles, list) and handles, "Maskaq has no offered handles")
    _require(isinstance(evidence, list) and evidence, "Maskaq has no evidence set")
    handle_rows: list[tuple[str, str, str]] = []
    for row in handles:
        _require(isinstance(row, dict), "malformed grounding handle")
        values = (row.get("nodeId"), row.get("chunkId"), row.get("sha256"))
        _require(all(isinstance(value, str) and value for value in values),
                 "grounding handle lacks node/chunk/digest identity")
        _require(bool(HEX64.fullmatch(values[2])), "grounding handle has invalid digest")
        handle_rows.append(values)  # type: ignore[arg-type]
    evidence_rows: list[tuple[str, str, str]] = []
    for row in evidence:
        _require(isinstance(row, dict), "malformed grounding evidence")
        values = (row.get("node_id"), row.get("chunk_id"), row.get("sha256"))
        _require(all(isinstance(value, str) and value for value in values),
                 "grounding evidence lacks node/chunk/digest identity")
        _require(bool(HEX64.fullmatch(values[2])), "grounding evidence has invalid digest")
        evidence_rows.append(values)  # type: ignore[arg-type]
    _require(len(handle_rows) == len(set(handle_rows)), "duplicate grounding handle")
    _require(len(evidence_rows) == len(set(evidence_rows)), "duplicate grounding evidence")
    _require(set(handle_rows) == set(evidence_rows),
             "handle and evidence memberships are not equivalent")
    _require(grounding.get("handle_evidence_set_equivalent") is True,
             "controller did not attest handle/evidence equivalence")

    handles_sha = _sha256_json(handles)
    evidence_sha = _sha256_json(evidence)
    _require(grounding.get("handles_sha256") == handles_sha,
             "grounding handle digest mismatch")
    _require(grounding.get("evidence_set_sha256") == evidence_sha,
             "grounding evidence-set digest mismatch")
    _require(receipt.get("handles_sha256") == handles_sha,
             "receipt handle digest mismatch")
    _require(receipt.get("evidence_set_sha256") == evidence_sha,
             "receipt evidence-set digest mismatch")

    augmented = (
        prompt
        + "\n\nCANDIDATE_HANDLES_JSON (controller-provided; no node content):\n"
        + json.dumps(handles, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\nReturn a retrieval plan using only offered nodeId values. "
          "If none supports the query, return ABSTAIN with zero citations."
    )
    augmented_sha = _sha256(augmented.encode("utf-8"))
    _require(grounding.get("augmented_prompt_sha256") == augmented_sha,
             "augmented prompt digest mismatch")
    _require(receipt.get("augmented_prompt_sha256") == augmented_sha,
             "receipt augmented prompt digest mismatch")

    answer = turn.get("answer")
    _require(isinstance(answer, str) and answer, "Maskaq returned no grounded answer")
    cited = _parse_citation_answer(answer)
    offered = {row[0] for row in handle_rows}
    _require(set(cited) <= offered, "Maskaq cited an unoffered node")
    validation = grounding.get("citation_validation")
    _require(isinstance(validation, dict), "citation validation is missing")
    _require(validation.get("state") == "CITATIONS_WITHIN_OFFERED_HANDLES",
             "citation validation did not pass")
    _require(validation.get("cited_node_ids") == cited,
             "citation validation does not bind the answer citations")
    _require(validation.get("cited_node_ids_sha256") == _sha256_json(cited),
             "cited-node digest mismatch")
    _require(receipt.get("citation_validation_sha256") == _sha256_json(validation),
             "receipt citation-validation digest mismatch")
    return {
        "grounded_count": len(handles),
        "evidence_set_sha256": evidence_sha,
        "handles_sha256": handles_sha,
        "augmented_prompt_sha256": augmented_sha,
        "citation_count": len(cited),
        "cited_node_ids_sha256": _sha256_json(cited),
    }


def _profile_runtime(binding_contract: Mapping[str, Any], profile: str) -> Mapping[str, Any]:
    runtime = binding_contract.get("runtime_backend")
    _require(isinstance(runtime, dict), "model-binding runtime status is missing")
    forge = runtime.get("forge_profiles")
    _require(isinstance(forge, dict), "Forge profile status is missing")
    profiles = forge.get("profiles")
    _require(isinstance(profiles, dict), "Forge profile map is missing")
    status = profiles.get(profile)
    _require(isinstance(status, dict), f"runtime status missing for profile {profile}")
    return status


def verify_turn(
    *,
    persona: str,
    prompt: str,
    response: Mapping[str, Any],
    public_pem: bytes,
    binding_contract: Mapping[str, Any],
) -> dict[str, Any]:
    _require(isinstance(response, Mapping), f"{persona} response is not an object")
    ask_id = response.get("ask_id")
    _require(isinstance(ask_id, str) and ask_id, f"{persona} ask_id is missing")
    turn = response.get("turn")
    _require(isinstance(turn, dict), f"{persona} turn is missing")
    _require(turn.get("persona") == persona, f"{persona} identity mismatch")
    _require(turn.get("stub") is False, f"{persona} used a stub or refusal")
    _require(turn.get("timeout") is False, f"{persona} turn timed out")
    answer = turn.get("answer")
    _require(isinstance(answer, str) and answer, f"{persona} returned no answer")

    receipt = verify_dsse_receipt(response.get("receipt"), public_pem)
    _require(receipt.get("ask_id") == ask_id, f"{persona} receipt ask_id mismatch")
    _require(receipt.get("persona") == persona, f"{persona} receipt identity mismatch")
    _require(receipt.get("prompt_sha256") == _sha256(prompt.encode("utf-8")),
             f"{persona} prompt digest mismatch")
    answer_sha = _sha256(answer.encode("utf-8"))
    _require(receipt.get("answer_present") is True, f"{persona} answer presence mismatch")
    _require(receipt.get("answer_sha256") == answer_sha, f"{persona} answer digest mismatch")
    _require(receipt.get("output_sha256") == answer_sha, f"{persona} output digest mismatch")
    honesty = turn.get("honesty")
    _require(receipt.get("honesty_sha256") == _sha256(str(honesty).encode("utf-8")),
             f"{persona} honesty digest mismatch")
    turn_output = {
        "answer": answer,
        "honesty": honesty,
        "stub": False,
        "timeout": False,
        "model": turn.get("model"),
    }
    _require(receipt.get("turn_output_sha256") == _sha256_json(turn_output),
             f"{persona} turn-output digest mismatch")

    binding = turn.get("model_binding")
    attestation = turn.get("model_attestation")
    _require(isinstance(binding, dict), f"{persona} model binding is missing")
    _require(isinstance(attestation, dict), f"{persona} model attestation is missing")
    _require(binding.get("model_attestation") == attestation,
             f"{persona} binding carries a different attestation")
    binding_sha = _sha256_json(binding)
    attestation_sha = _sha256_json(attestation)
    _require(receipt.get("model_binding_sha256") == binding_sha,
             f"{persona} model-binding digest mismatch")
    _require(binding.get("model_attestation_sha256") == attestation_sha,
             f"{persona} binding attestation digest mismatch")
    _require(receipt.get("model_attestation_sha256") == attestation_sha,
             f"{persona} receipt attestation digest mismatch")

    profile = binding.get("primary_profile")
    _require(isinstance(profile, str) and profile, f"{persona} profile intent is missing")
    runtime = _profile_runtime(binding_contract, profile)
    expected_tag = runtime.get("expected_model")
    served_tag = runtime.get("served_model")
    actual_tag = turn.get("model")
    _require(runtime.get("available") is True, f"{persona} profile is not available")
    _require(isinstance(expected_tag, str) and expected_tag,
             f"{persona} expected tag is missing")
    _require(served_tag == expected_tag, f"{persona} runtime served/expected tag mismatch")
    _require(actual_tag == expected_tag, f"{persona} response did not use exact expected tag")
    _require(binding.get("actual_model") == actual_tag,
             f"{persona} binding actual-model mismatch")
    _require(binding.get("attested_served_model") == actual_tag,
             f"{persona} binding served-model mismatch")
    _require(binding.get("model_identity_reconciled") is True,
             f"{persona} model identity is not reconciled")
    _require(attestation.get("expected_model") == expected_tag,
             f"{persona} attestation expected-model mismatch")
    _require(attestation.get("served_model") == expected_tag,
             f"{persona} attestation served-model mismatch")
    _require(attestation.get("available") is True,
             f"{persona} attestation is not available")
    _require(receipt.get("model") == actual_tag, f"{persona} receipt model mismatch")
    _require(receipt.get("profile_intent") == profile,
             f"{persona} receipt profile mismatch")

    grounding_summary = None
    if persona == "Maskaq":
        grounding_summary = _validate_grounding(prompt, turn, receipt)
        binding_grounding = binding.get("grounding")
        _require(isinstance(binding_grounding, dict), "Maskaq binding grounding is missing")
        grounding_sha = _sha256_json(binding_grounding)
        _require(binding.get("grounding_sha256") == grounding_sha,
                 "Maskaq binding grounding digest mismatch")
        _require(receipt.get("grounding_sha256") == grounding_sha,
                 "Maskaq receipt grounding digest mismatch")

    signature = response["receipt"]["signatures"][0]
    return {
        "persona": persona,
        "ask_id_sha256": _sha256(ask_id.encode("utf-8")),
        "prompt_sha256": _sha256(prompt.encode("utf-8")),
        "answer_sha256": answer_sha,
        "profile": profile,
        "exact_served_model": actual_tag,
        "model_binding_sha256": binding_sha,
        "model_attestation_sha256": attestation_sha,
        "receipt_payload_sha256": _sha256(base64.b64decode(response["receipt"]["payload"])),
        "receipt_signature_sha256": _sha256(base64.b64decode(signature["sig"])),
        "grounding": grounding_summary,
    }


def _dig_path(value: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = value
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


HANDLE_COUNT_PATHS = (
    ("brain_handle_count",),
    ("brain_handle_node_count",),
    ("canonical_brain_handle_count",),
    ("brain_handle_plane", "count"),
    ("brain_handle_plane", "node_count"),
    ("brain_handles", "count"),
    ("brain_handles", "node_count"),
    ("memory", "brain_handle_count"),
    ("memory", "brain_handle_node_count"),
    ("memory", "brain_handle_plane", "count"),
    ("memory", "brain_handle_plane", "node_count"),
)


def _handle_plane_observation(*documents: Mapping[str, Any]) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    for document_index, document in enumerate(documents):
        for path in HANDLE_COUNT_PATHS:
            value = _dig_path(document, path)
            if value is not None:
                _require(isinstance(value, int) and not isinstance(value, bool),
                         f"handle-plane count at {'.'.join(path)} is not an integer")
                _require(value == EXPECTED_BRAIN_HANDLE_COUNT,
                         f"handle-plane count is {value}, expected {EXPECTED_BRAIN_HANDLE_COUNT}")
                observations.append({
                    "document": document_index,
                    "path": ".".join(path),
                    "count": value,
                })
    return {
        "state": "VERIFIED" if observations else "NOT_EXPOSED",
        "expected_count": EXPECTED_BRAIN_HANDLE_COUNT,
        "observations": observations,
    }


class HTTPClient:
    def __init__(self, base_url: str, timeout_s: float) -> None:
        parsed = urllib.parse.urlsplit(base_url)
        _require(parsed.scheme in {"http", "https"}, "base URL must use HTTP(S)")
        _require(parsed.hostname in {"127.0.0.1", "localhost", "::1"},
                 "live verifier only accepts a loopback A11oy URL")
        _require(not parsed.username and not parsed.password,
                 "credentials in the base URL are forbidden")
        _require(parsed.path in {"", "/"} and not parsed.query and not parsed.fragment,
                 "base URL must be an origin without path, query, or fragment")
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        class _NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
                return None
        self._opener = urllib.request.build_opener(_NoRedirect)

    def _request(self, method: str, path: str, payload: Any = None) -> tuple[bytes, str]:
        _require(path.startswith("/") and not path.startswith("//"), "invalid request path")
        body = _canonical_json(payload) if payload is not None else None
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            self.base_url + path, data=body, headers=headers, method=method)
        try:
            with self._opener.open(request, timeout=self.timeout_s) as response:
                raw = response.read(MAX_HTTP_BODY_BYTES + 1)
                content_type = response.headers.get("Content-Type", "")
                status = response.status
        except urllib.error.HTTPError as exc:
            raise VerificationError(f"{method} {path} returned HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise VerificationError(f"{method} {path} failed ({type(exc).__name__})") from exc
        _require(status == 200, f"{method} {path} returned HTTP {status}")
        _require(len(raw) <= MAX_HTTP_BODY_BYTES, f"{method} {path} response is oversized")
        return raw, content_type

    def json(self, method: str, path: str, payload: Any = None) -> Mapping[str, Any]:
        body, content_type = self._request(method, path, payload)
        _require("json" in content_type.lower(), f"{path} did not return JSON")
        parsed = _strict_json_bytes(body, label=path)
        _require(isinstance(parsed, dict), f"{path} did not return an object")
        return parsed

    def bytes(self, method: str, path: str) -> bytes:
        body, _content_type = self._request(method, path)
        return body


def verify_live(
    base_url: str,
    *,
    timeout_s: float = 75.0,
    client: Any = None,
    now: Callable[[], dt.datetime] | None = None,
) -> dict[str, Any]:
    """Exercise and independently verify the live Second Brain contract."""
    http = client or HTTPClient(base_url, timeout_s)
    public_pem = http.bytes("GET", VERIFY_KEY_PATH)
    try:
        public_key = serialization.load_pem_public_key(public_pem)
    except (TypeError, ValueError) as exc:
        raise VerificationError("published key is not valid PEM") from exc
    _require(isinstance(public_key, ec.EllipticCurvePublicKey),
             "published key is not an EC public key")
    _require(isinstance(public_key.curve, ec.SECP256R1),
             "published key is not P-256")
    public_fingerprint = _sha256(public_pem.strip())

    second_brain = http.json("GET", "/api/a11oy/v1/ayllu/second-brain")
    _require(second_brain.get("schema") == SECOND_BRAIN_SCHEMA,
             "Second Brain schema mismatch")
    _require(second_brain.get("ready_for_grounded_navigation") is True,
             "Second Brain is not ready for grounded navigation")
    _require(second_brain.get("signer_ready_this_request") is True,
             "Second Brain signer is not ready")
    profile = second_brain.get("profile")
    _require(isinstance(profile, dict), "Second Brain profile is missing")
    _require(profile.get("exact_tag_observed") is True,
             "Second Brain exact tag was not observed")
    _require(profile.get("served_model") == profile.get("expected_model"),
             "Second Brain served tag differs from expected tag")
    memory = second_brain.get("memory")
    _require(isinstance(memory, dict) and memory.get("built") is True,
             "Second Brain memory is not built")
    training = second_brain.get("training_boundary")
    _require(isinstance(training, dict), "Second Brain training boundary is missing")
    _require(training.get("raw_brain_nodes_observed") == EXPECTED_BRAIN_HANDLE_COUNT,
             "Second Brain raw-node inventory is not 9,464")
    _require(isinstance(training.get("raw_brain_nodes_admitted_to_gradients"), int),
             "Second Brain gradient admission count is missing")

    binding_contract = http.json("GET", "/api/a11oy/v1/ayllu/model-binding")
    rag_status = http.json("GET", "/api/a11oy/code/rag/status")
    turns = []
    for persona, prompt in (("Maskaq", MASKAQ_PROMPT), ("Yupaq", YUPAQ_PROMPT)):
        response = http.json(
            "POST", "/api/a11oy/v1/ayllu/ask",
            {"persona": persona, "prompt": prompt},
        )
        turns.append(verify_turn(
            persona=persona,
            prompt=prompt,
            response=response,
            public_pem=public_pem,
            binding_contract=binding_contract,
        ))

    handle_plane = _handle_plane_observation(second_brain, rag_status)
    captured = (now or (lambda: dt.datetime.now(dt.timezone.utc)))()
    _require(captured.tzinfo is not None, "capture timestamp must be timezone-aware")
    return {
        "schema": SCHEMA,
        "verification_state": "PASS",
        "captured_at": captured.astimezone(dt.timezone.utc).isoformat(),
        "target": {
            "base_url": base_url.rstrip("/"),
            "network_scope": "LOOPBACK_ONLY",
        },
        "public_key": {
            "algorithm": "ECDSA-P256-SHA256",
            "verify_key_path": VERIFY_KEY_PATH,
            "key_scope": "PROCESS_BOOT_EPHEMERAL",
            "key_fingerprint_sha256": public_fingerprint,
        },
        "second_brain": {
            "schema": second_brain["schema"],
            "system_id": second_brain.get("system_id"),
            "state": second_brain.get("state"),
            "exact_served_model": profile.get("served_model"),
            "memory": {
                "document_count": memory.get("document_count"),
                "chunk_count": memory.get("chunk_count"),
                "node_count": memory.get("node_count"),
                "edge_count": memory.get("edge_count"),
            },
            "raw_brain_nodes_observed": training["raw_brain_nodes_observed"],
            "raw_brain_nodes_admitted_to_gradients": training[
                "raw_brain_nodes_admitted_to_gradients"
            ],
            "handle_plane": handle_plane,
        },
        "turns": turns,
        "privacy": {
            "contains_prompt_text": False,
            "contains_answer_text": False,
            "contains_private_key": False,
            "contains_credentials": False,
        },
    }


def write_content_addressed(summary: Mapping[str, Any], output_dir: Path) -> Path:
    """Atomically write exact canonical bytes under their SHA-256 address."""
    _require(summary.get("verification_state") == "PASS",
             "refusing to write a non-passing verification summary")
    body = _canonical_json(summary) + b"\n"
    digest = _sha256(body)
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"second-brain-live-{digest}.json"
    if target.exists():
        _require(target.read_bytes() == body, "content-address collision")
        return target
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".second-brain-live-", suffix=".tmp", dir=output_dir)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, target)
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
    return target


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--timeout", type=float, default=75.0)
    parser.add_argument(
        "--output-dir", type=Path,
        default=Path(".a11oy-state/attestations/second-brain"),
        help="gitignored output directory; created only after all checks pass",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        summary = verify_live(args.base_url, timeout_s=args.timeout)
        artifact = write_content_addressed(summary, args.output_dir)
    except VerificationError as exc:
        print(json.dumps({
            "schema": SCHEMA,
            "verification_state": "FAIL",
            "error": str(exc),
            "artifact_written": False,
        }, sort_keys=True), file=sys.stderr)
        return 1
    except Exception as exc:  # fail closed without dumping response bodies/secrets
        print(json.dumps({
            "schema": SCHEMA,
            "verification_state": "FAIL",
            "error": f"unexpected verifier error ({type(exc).__name__})",
            "artifact_written": False,
        }, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps({
        "schema": SCHEMA,
        "verification_state": "PASS",
        "artifact": str(artifact),
        "artifact_sha256": _sha256(artifact.read_bytes()),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
