#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Services: dated public provider observations and support-request evidence.

This catalog has no routing, qualification, promotion, or deployment authority.
Reads use committed source only. A separate explicit collector refreshes public
Hub metadata; it never requests inference or changes a provider.
"""

import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATUS_PATH = ROOT / "docs/model-inference-support.json"
INVENTORY_PATH = ROOT / "docs/huggingface-ecosystem-manifest.json"
SCHEMA = "szl.model-inference-support/v1"
NOTICE = "SPDX-License-Identifier: Apache-2.0; (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173"
MAX_BYTES = 512 * 1024
MAX_RESPONSE_BYTES = 256 * 1024
MAX_AGE_SECONDS = 86400
MODEL_ID = re.compile(r"SZLHOLDINGS/[A-Za-z0-9][A-Za-z0-9._-]{0,95}\Z")
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,79}\Z")
SUPPORT_PREFIX = "https://huggingface.co/spaces/huggingface/InferenceSupport/discussions/"
AUTHORITY = {
    "routing": False, "qualification": False, "promotion": False,
    "deployment": False,
}
ARTIFACT_CLASSES = {
    "gguf_bundle", "non_provider_artifact", "standalone_weight_bundle",
    "adapter_bundle", "kernel_library", "numpy_model_bundle",
}


class SupportDataError(ValueError):
    """The source does not satisfy the bounded observational contract."""


def _require(condition, message):
    if not condition:
        raise SupportDataError(message)


def _keys(value, expected):
    _require(isinstance(value, dict) and set(value) == set(expected), "invalid object fields")


def _text(value, limit=1000):
    _require(isinstance(value, str) and 0 < len(value) <= limit, "invalid bounded text")
    _require(all(ord(c) >= 32 or c == "\n" for c in value), "control character in text")
    return value


def _match(value, pattern):
    _require(isinstance(value, str) and pattern.fullmatch(value) is not None, "invalid identifier")
    return value


def _stamp(value):
    _text(value, 40)
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SupportDataError("invalid observation timestamp") from exc
    _require(stamp.tzinfo is not None and stamp.utcoffset().total_seconds() == 0, "UTC timestamp required")
    return stamp


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        _require(key not in value, "duplicate JSON key")
        value[key] = item
    return value


def decode_json(raw, limit=MAX_BYTES):
    _require(isinstance(raw, bytes) and len(raw) <= limit, "JSON size limit exceeded")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(SupportDataError("non-finite JSON")))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise SupportDataError("invalid JSON") from exc


def read_json(path):
    with Path(path).open("rb") as handle:
        return decode_json(handle.read(MAX_BYTES + 1))


def mapping_url(model_id):
    _match(model_id, MODEL_ID)
    return f"https://huggingface.co/api/models/{model_id}?expand[]=inferenceProviderMapping&expand[]=sha"


def _provider_rows(mapping):
    _require(isinstance(mapping, dict) and len(mapping) <= 80, "invalid provider mapping")
    rows = []
    for name, value in sorted(mapping.items()):
        _match(name, SLUG)
        _require(isinstance(value, dict), "invalid provider entry")
        status = value.get("status")
        _require(isinstance(status, str) and status in {"live", "staging"}, "unknown provider status")
        rows.append({
            "provider": name, "status": status,
            "task": _match(value.get("task"), SLUG),
            "provider_id": _text(value.get("providerId"), 256),
        })
    return rows


def _mapping_projection(model_id, revision, providers):
    return {"id": model_id, "sha": revision, "inferenceProviderMapping": {
        row["provider"]: {"status": row["status"], "task": row["task"], "providerId": row["provider_id"]}
        for row in providers
    }}


def observation_from_mapping(model_id, payload, observed_at):
    """Bind normalized public API fields, without pretending to hash wire bytes."""
    _stamp(observed_at)
    _require(isinstance(payload, dict) and payload.get("id") == model_id, "response identity mismatch")
    revision = _match(payload.get("sha"), SHA40)
    providers = _provider_rows(payload.get("inferenceProviderMapping"))
    projection = _mapping_projection(model_id, revision, providers)
    return {
        "state": "PROVIDER_MAPPING_REPORTED" if providers else "NO_PROVIDER_MAPPING",
        "providers": providers, "observed_at": observed_at, "hub_revision": revision,
        "source_url": mapping_url(model_id),
        "capture_sha256": hashlib.sha256(canonical_bytes(projection)).hexdigest(),
        "capture_kind": "NORMALIZED_PUBLIC_API_FIELDS_NOT_INDEPENDENT_ATTESTATION",
        "error": None,
    }


def unavailable_observation(model_id, observed_at, error):
    _stamp(observed_at)
    _require(isinstance(error, str) and error in {
        "HTTP_ERROR", "TIMEOUT", "NETWORK_ERROR", "INVALID_RESPONSE",
    }, "invalid observation error")
    return {
        "state": "UNAVAILABLE", "providers": [], "observed_at": observed_at,
        "hub_revision": None, "source_url": mapping_url(model_id),
        "capture_sha256": None,
        "capture_kind": "NORMALIZED_PUBLIC_API_FIELDS_NOT_INDEPENDENT_ATTESTATION",
        "error": error,
    }


def request_state(requests):
    if any(row["evidence_kind"] == "VERIFIED_SUBMISSION" for row in requests):
        return "REQUESTED"
    return "PRIOR_DISCUSSION_RECORDED" if requests else "NO_RECORDED_REQUEST"


def _validate_request(row, model_id=None):
    _keys(row, {
        "model_id", "discussion_number", "url", "author", "recorded_status",
        "evidence_kind", "model_revision", "requested_at", "readback_at",
        "body_sha256", "readback_body_sha256", "readback_normalization",
    })
    _match(row["model_id"], MODEL_ID)
    _require(model_id is None or row["model_id"] == model_id, "request model mismatch")
    num = row["discussion_number"]
    _require(type(num) is int and 0 < num < 1_000_000_000, "invalid discussion number")
    _require(row["url"] == SUPPORT_PREFIX + str(num), "request URL mismatch")
    _text(row["author"], 80)
    _require(isinstance(row["recorded_status"], str) and row["recorded_status"] in {"open", "closed"}, "invalid recorded status")
    kind = row["evidence_kind"]
    _require(isinstance(kind, str) and kind in {"VERIFIED_SUBMISSION", "PRIOR_DISCUSSION"}, "invalid request evidence kind")
    proof_fields = ("model_revision", "requested_at", "readback_at", "body_sha256",
                    "readback_body_sha256", "readback_normalization")
    if kind == "PRIOR_DISCUSSION":
        _require(all(row[key] is None for key in proof_fields), "prior discussion has invented submission proof")
    else:
        _match(row["model_revision"], SHA40)
        _require(_stamp(row["readback_at"]) >= _stamp(row["requested_at"]), "readback predates request")
        _match(row["body_sha256"], SHA256)
        _match(row["readback_body_sha256"], SHA256)
        normalization = row["readback_normalization"]
        _require(isinstance(normalization, str) and normalization in {
            "EXACT", "HUB_REMOVED_ONE_TERMINAL_NEWLINE",
        }, "unknown readback normalization")
        if normalization == "EXACT":
            _require(row["body_sha256"] == row["readback_body_sha256"], "exact readback digest mismatch")


def validate_document(document, inventory=None):
    _keys(document, {
        "$comment", "schema", "generated_at", "organization", "scope", "inventory_source",
        "max_observation_age_seconds", "authority", "models", "unmatched_prior_requests",
    })
    _require(document["schema"] == SCHEMA, "unsupported source schema")
    _require(document["$comment"] == NOTICE, "source notice missing")
    generated = _stamp(document["generated_at"])
    _require(document["organization"] == "SZLHOLDINGS", "wrong organization")
    _require(document["scope"] == "PUBLIC_MODEL_NAMESPACE_ONLY", "wrong namespace scope")
    _require(document["authority"] == AUTHORITY and all(v is False for v in document["authority"].values()), "provider metadata has no authority")
    _require(type(document["max_observation_age_seconds"]) is int and document["max_observation_age_seconds"] == MAX_AGE_SECONDS, "unexpected freshness policy")
    source = document["inventory_source"]
    _keys(source, {"path", "model_ids_sha256"})
    _require(source["path"] == "docs/huggingface-ecosystem-manifest.json", "wrong inventory source")
    _match(source["model_ids_sha256"], SHA256)
    models = document["models"]
    _require(isinstance(models, list) and 0 < len(models) <= 500, "invalid model count")
    ids, discussion_ids = [], set()
    for row in models:
        _keys(row, {"id", "repo_type", "assessment", "inference", "support"})
        model_id = _match(row["id"], MODEL_ID)
        ids.append(model_id)
        _require(row["repo_type"] == "model", "non-model namespace entry")
        assessment = row["assessment"]
        _keys(assessment, {"hub_revision", "observed_at", "source_url", "artifact_class",
                           "qualification_note", "request_disposition", "suggested_route"})
        revision = _match(assessment["hub_revision"], SHA40)
        _require(_stamp(assessment["observed_at"]) <= generated, "assessment after generation")
        _require(assessment["source_url"] == f"https://huggingface.co/{model_id}/blob/{revision}/README.md", "assessment source mismatch")
        _require(isinstance(assessment["artifact_class"], str) and assessment["artifact_class"] in ARTIFACT_CLASSES, "unknown artifact class")
        for key in ("qualification_note", "request_disposition", "suggested_route"):
            _text(assessment[key])
        obs = row["inference"]
        _keys(obs, {"state", "providers", "observed_at", "hub_revision", "source_url",
                    "capture_sha256", "capture_kind", "error"})
        _require(_stamp(obs["observed_at"]) <= generated, "provider observation after generation")
        if obs["state"] == "UNAVAILABLE":
            expected = unavailable_observation(model_id, obs["observed_at"], obs["error"])
        else:
            providers = obs["providers"]
            _require(isinstance(providers, list) and len(providers) <= 80, "invalid provider rows")
            names = []
            for provider in providers:
                _keys(provider, {"provider", "status", "task", "provider_id"})
                names.append(_match(provider["provider"], SLUG))
            _require(names == sorted(set(names)), "duplicate or unsorted providers")
            expected = observation_from_mapping(model_id, _mapping_projection(
                model_id, obs["hub_revision"], providers), obs["observed_at"])
        _require(obs == expected, "provider observation integrity mismatch")
        support = row["support"]
        _keys(support, {"state", "requests"})
        requests = support["requests"]
        _require(isinstance(requests, list) and len(requests) <= 32, "invalid requests")
        numbers = []
        for request in requests:
            _validate_request(request, model_id)
            num = request["discussion_number"]
            _require(num not in discussion_ids, "duplicate discussion")
            discussion_ids.add(num)
            numbers.append(num)
            if request["readback_at"] is not None:
                _require(_stamp(request["readback_at"]) <= generated, "request readback after generation")
        _require(numbers == sorted(numbers), "unsorted requests")
        _require(support["state"] == request_state(requests), "request state mismatch")
    _require(ids == sorted(set(ids)), "duplicate or unsorted model IDs")
    _require(source["model_ids_sha256"] == hashlib.sha256(canonical_bytes(ids)).hexdigest(),
             "inventory model identity digest mismatch")
    prior = document["unmatched_prior_requests"]
    _require(isinstance(prior, list) and len(prior) <= 100, "invalid unmatched discussions")
    for row in prior:
        _validate_request(row)
        _require(row["evidence_kind"] == "PRIOR_DISCUSSION" and row["model_id"] not in ids, "unmatched discussion identity mismatch")
        _require(row["discussion_number"] not in discussion_ids, "duplicate discussion")
        discussion_ids.add(row["discussion_number"])
    if inventory is not None:
        _require(isinstance(inventory, dict) and isinstance(inventory.get("inventory"), dict), "invalid inventory")
        inventory_models = inventory["inventory"].get("models")
        _require(isinstance(inventory_models, list), "model namespace inventory required")
        inventory_ids = []
        for row in inventory_models:
            _require(isinstance(row, dict) and row.get("repoType") == "model", "invalid inventory model")
            inventory_ids.append(_match(row.get("id"), MODEL_ID))
        _require(len(inventory_ids) == len(set(inventory_ids)) and set(ids) == set(inventory_ids), "inventory coverage differs; source review required")
    return document


def public_status(path=None, *, now=None, inventory_path=None):
    """Read-only projection. Expired evidence cannot advertise provider availability."""
    now = _stamp(now or utc_now())
    try:
        document = validate_document(read_json(path or STATUS_PATH), read_json(inventory_path or INVENTORY_PATH))
    except (OSError, SupportDataError, ValueError, TypeError, KeyError, AttributeError):
        return {"state": "UNAVAILABLE", "reason": "SOURCE_INVALID_OR_UNAVAILABLE",
                "models": [], "authority": dict(AUTHORITY)}
    output = copy.deepcopy(document)
    counts = {"model_namespace_repositories": len(output["models"]),
              "no_provider_mapping": 0, "provider_mapping_reported": 0,
              "unavailable": 0, "models_with_recorded_request": 0,
              "verified_submissions": 0, "prior_discussions": len(output["unmatched_prior_requests"])}
    for row in output["models"]:
        obs = row["inference"]
        age = (now - _stamp(obs["observed_at"])).total_seconds()
        obs["recorded_state"] = obs["state"]
        obs["age_seconds"] = max(0, int(age))
        obs["freshness"] = "WITHIN_OBSERVATION_WINDOW"
        if age < -300 or age > MAX_AGE_SECONDS:
            obs["last_observed_providers"] = obs["providers"]
            obs["providers"] = []
            obs["state"] = "UNAVAILABLE"
            obs["freshness"] = "CLOCK_MISMATCH" if age < -300 else "STALE_OBSERVATION"
        elif obs["state"] == "UNAVAILABLE":
            obs["freshness"] = "OBSERVATION_UNAVAILABLE"
        counts[obs["state"].lower()] += 1
        requests = row["support"]["requests"]
        counts["models_with_recorded_request"] += bool(requests)
        counts["verified_submissions"] += sum(r["evidence_kind"] == "VERIFIED_SUBMISSION" for r in requests)
        counts["prior_discussions"] += sum(r["evidence_kind"] == "PRIOR_DISCUSSION" for r in requests)
    output.update({"state": "SOURCE_OBSERVATIONS", "checked_at": now.isoformat(),
                   "source_path": "docs/model-inference-support.json", "summary": counts,
                   "runtime_qualification": "NOT_ASSESSED_BY_PROVIDER_STATUS"})
    return output
