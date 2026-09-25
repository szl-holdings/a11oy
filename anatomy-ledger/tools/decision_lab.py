#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Bounded counterfactual inspection and unsigned replay of advisory decisions."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MAX_SCENARIOS = 16
MAX_PATCHES = 12
MAX_INPUT_BYTES = 128 * 1024
MAX_CAPSULE_BYTES = 192 * 1024
MAX_OUTPUT_BYTES = 512 * 1024
MAX_DEPTH = 20
MAX_NODES = 12000
MAX_STRING_BYTES = 16384
MAX_LONG = 2**63 - 1
SCHEMA = "szl.anatomy.decision-lab.v1"
CAPSULE_SCHEMA = "szl.anatomy.replay.v1"
REPLAY_SCHEMA = "szl.anatomy.replay-result.v1"
EXECUTED_FILES = (
    "tools/decision_lab.py",
    "tools/authorize_intent.py",
    "tools/bind_anatomy.py",
    "tools/evaluate_supply_chain.py",
    "tools/verify_release.py",
)
REFERENCE_FILES = (
    "policy/cedar/intent-auth.cedar",
    "policy/cedar/intent-auth.cedarschema",
    "policy/cedar/intent-auth.schema.json",
    "policy/rego/supply_chain.rego",
)
ALLOWED_CHANGES = {
    "context.humanApproval": "bool",
    "context.mfa": "bool",
    "context.networkZone": "string",
    "context.riskScore": "long",
    "context.purpose": "string",
    "context.intendedEffect": "string",
    "context.evidenceDigest": "string",
    "principal.attrs.disabled": "bool",
    "principal.attrs.assurance": "long",
    "principal.attrs.tenantId": "string",
    "resource.attrs.requiredAssurance": "long",
    "resource.attrs.maxRisk": "long",
    "resource.attrs.requiresApproval": "bool",
    "resource.attrs.tenantId": "string",
    "resource.attrs.allowedPurposes": "strings",
    "resource.attrs.allowedEffects": "strings",
}
REASON_CODES = {
    "humanApproval required": "HUMAN_APPROVAL_REQUIRED",
    "mfa required": "MFA_REQUIRED",
    "evidenceDigest required": "EVIDENCE_DIGEST_REQUIRED",
    "evidenceDigest must be a SHA-256 digest": "INVALID_EVIDENCE_DIGEST",
    "principal is disabled": "PRINCIPAL_DISABLED",
    "principal.tenantId != resource.tenantId": "TENANT_MISMATCH",
    "context.riskScore exceeds resource.maxRisk": "RISK_LIMIT_EXCEEDED",
    "assurance below requiredAssurance": "ASSURANCE_INSUFFICIENT",
    "purpose is not in resource.allowedPurposes": "PURPOSE_NOT_ALLOWED",
    "intendedEffect is not in resource.allowedEffects": "EFFECT_NOT_ALLOWED",
    "approval-required action from untrusted networkZone": "UNTRUSTED_NETWORK",
    "unknown action or action type": "UNKNOWN_ACTION",
    "cryptographic verification has not been proven": "VERIFICATION_UNPROVEN",
    "OPA unavailable; policy not evaluated": "NATIVE_EVIDENCE_POLICY_NOT_EXECUTED",
    "context.evidenceDigest does not bind this statement": "STATEMENT_DIGEST_MISMATCH",
    "context.evidenceDigest must be a SHA-256 digest": "INVALID_BINDING_DIGEST",
    "evidence statement is required": "EVIDENCE_REQUIRED",
    "local advisory policy conditions satisfied": "ADVISORY_INTENT_CONDITIONS_SATISFIED",
}
DISCLOSURE = (
    "Independent hypothetical changes to caller-supplied metadata; changing an approval, "
    "identity, or network field is not real approval, authentication, or a network change. "
    "Python advisory evaluators execute locally; native Cedar and OPA are not executed here. "
    "Replay hashes establish reproducible internal consistency only. Capsules are unsigned, "
    "unauthenticated, and editable; a self-consistent rewrite cannot establish authorship."
)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _source_bytes() -> dict[str, bytes]:
    try:
        return {
            name: (ROOT / name).read_bytes()
            for name in (*EXECUTED_FILES, *REFERENCE_FILES)
        }
    except OSError as exc:
        raise ValueError("policy source is unavailable") from exc


def _describe_sources(sources: dict[str, bytes]) -> dict[str, Any]:
    files = {
        name: hashlib.sha256(source).hexdigest() for name, source in sources.items()
    }
    descriptor = {
        "files": files,
        "executedPython": list(EXECUTED_FILES),
        "referenceOnly": list(REFERENCE_FILES),
    }
    return {
        **descriptor,
        "digest": _digest(descriptor),
        "engine": "python-advisory",
        "algorithm": "sha256-exact-source-bytes-and-sorted-compact-utf8-json-v1",
        "nativeCedarExecuted": False,
        "nativeOpaExecuted": False,
    }


def _snapshot() -> dict[str, Any]:
    return _describe_sources(_source_bytes())


def _compile_source(name: str, relative_path: str, sources: dict[str, bytes]):
    module = ModuleType(name)
    module.__file__ = str(ROOT / relative_path)
    exec(compile(sources[relative_path], module.__file__, "exec"), module.__dict__)
    return module


def _load_binder(sources: dict[str, bytes]):
    verifier = _compile_source(
        "decision_lab_verifier", "tools/verify_release.py", sources
    )
    intent = _compile_source(
        "decision_lab_intent", "tools/authorize_intent.py", sources
    )
    evidence = _compile_source(
        "decision_lab_evidence", "tools/evaluate_supply_chain.py", sources
    )
    binder = _compile_source("decision_lab_binder", "tools/bind_anatomy.py", sources)
    # Keep this dependency graph private; API input can never provide verifier proof.
    evidence.proof_metadata = verifier.proof_metadata
    binder.INTENT_EVALUATOR, binder.EVIDENCE_EVALUATOR = intent, evidence
    return binder


_SOURCES_AT_LOAD = _source_bytes()
POLICY_AT_LOAD = _describe_sources(_SOURCES_AT_LOAD)
BIND = _load_binder(_SOURCES_AT_LOAD)
if _snapshot()["digest"] != POLICY_AT_LOAD["digest"]:
    raise ValueError("policy source changed while loading; restart before evaluation")


def _bounded_copy(value: Any, limit: int, *, envelope: bool = False) -> Any:
    stack, count = [(value, 0)], 0
    max_depth, max_nodes = MAX_DEPTH + int(envelope), MAX_NODES + (8 if envelope else 0)
    while stack:
        item, depth = stack.pop()
        count += 1
        if count > max_nodes or depth > max_depth:
            raise ValueError("JSON depth or node limit exceeded")
        kind = type(item)
        if kind is dict:
            if len(item) > max_nodes - count:
                raise ValueError("JSON node limit exceeded")
            for key, child in item.items():
                if type(key) is not str or len(key.encode("utf-8")) > 256:
                    raise ValueError("JSON object keys must be bounded strings")
                stack.append((child, depth + 1))
        elif kind is list:
            if len(item) > max_nodes - count:
                raise ValueError("JSON node limit exceeded")
            stack.extend((child, depth + 1) for child in item)
        elif kind is str:
            if len(item.encode("utf-8")) > MAX_STRING_BYTES:
                raise ValueError("JSON string limit exceeded")
        elif kind is float:
            if not math.isfinite(item):
                raise ValueError("JSON numbers must be finite")
        elif kind is int:
            if item.bit_length() > 128:
                raise ValueError("JSON integer limit exceeded")
        elif item is not None and kind is not bool:
            raise ValueError("only JSON values are accepted")
    try:
        raw = _canonical(value)
    except (UnicodeError, TypeError, ValueError, RecursionError) as exc:
        raise ValueError("invalid JSON value") from exc
    if len(raw) > limit:
        raise ValueError("JSON byte limit exceeded")
    return json.loads(raw)


def _patch_type(value: Any, kind: str) -> bool:
    if kind == "bool":
        return type(value) is bool
    if kind == "long":
        return type(value) is int and -(2**63) <= value <= MAX_LONG
    if kind == "string":
        return type(value) is str and len(value.encode("utf-8")) <= 1024
    return (
        type(value) is list
        and len(value) <= 64
        and all(
            type(item) is str and len(item.encode("utf-8")) <= 256 for item in value
        )
    )


def _node_at(command: dict, path: str) -> tuple[dict, str]:
    parts = path.split(".")
    node = command
    for part in parts[:-1]:
        if type(node.get(part)) is not dict:
            raise ValueError(f"change path does not exist: {path}")
        node = node[part]
    if parts[-1] not in node:
        raise ValueError(f"change path does not exist: {path}")
    return node, parts[-1]


def _validate(payload: Any) -> dict:
    value = _bounded_copy(payload, MAX_INPUT_BYTES)
    if type(value) is not dict or set(value) - {
        "command",
        "statement",
        "verification",
        "scenarios",
    }:
        raise ValueError(
            "analyze accepts command, statement, verification, and scenarios only"
        )
    if type(value.get("command")) is not dict:
        raise ValueError("command must be an object")
    for key in ("statement", "verification"):
        if key in value and value[key] is not None and type(value[key]) is not dict:
            raise ValueError(f"{key} must be an object or null")
    if "scenarios" in value:
        if (
            type(value["scenarios"]) is not list
            or len(value["scenarios"]) > MAX_SCENARIOS
        ):
            raise ValueError("scenarios must be a list of at most 16 items")
        identifiers = set()
        for scenario in value["scenarios"]:
            if type(scenario) is not dict or set(scenario) != {
                "id",
                "label",
                "changes",
            }:
                raise ValueError("scenario must contain id, label, and changes")
            identifier, label = scenario["id"], scenario["label"]
            if (
                type(identifier) is not str
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", identifier)
                or identifier in identifiers
            ):
                raise ValueError(
                    "scenario id must be unique and contain 1-64 letters, digits, underscores, or hyphens"
                )
            identifiers.add(identifier)
            if (
                type(label) is not str
                or not label.strip()
                or len(label.encode("utf-8")) > 256
            ):
                raise ValueError("scenario label must be a nonempty bounded string")
            changes = scenario["changes"]
            if type(changes) is not dict or not 1 <= len(changes) <= MAX_PATCHES:
                raise ValueError("each scenario requires 1-12 changes")
            for path, changed in changes.items():
                if path not in ALLOWED_CHANGES:
                    raise ValueError(f"change path is not allowed: {path}")
                if not _patch_type(changed, ALLOWED_CHANGES[path]):
                    raise ValueError(f"change has an invalid type or bound: {path}")
                _node_at(value["command"], path)
    return value


def _defaults(command: dict) -> list[dict]:
    context = command.get("context")
    resource = command.get("resource")
    attrs = resource.get("attrs") if isinstance(resource, dict) else None
    if not isinstance(context, dict):
        return []
    scenarios = []
    for field, label in (
        ("humanApproval", "Toggle claimed human approval"),
        ("mfa", "Toggle claimed MFA"),
    ):
        if type(context.get(field)) is bool:
            scenarios.append(
                {
                    "id": field + "-toggle",
                    "label": label,
                    "changes": {"context." + field: not context[field]},
                }
            )
    if type(context.get("networkZone")) is str:
        zone = (
            "untrusted"
            if context["networkZone"] in BIND.INTENT_EVALUATOR.TRUSTED_ZONES
            else "trusted-ci"
        )
        scenarios.append(
            {
                "id": "network-toggle",
                "label": "Toggle claimed network zone",
                "changes": {"context.networkZone": zone},
            }
        )
    max_risk = attrs.get("maxRisk") if isinstance(attrs, dict) else None
    if type(max_risk) is int and 0 <= max_risk <= MAX_LONG and "riskScore" in context:
        scenarios.append(
            {
                "id": "risk-at-limit",
                "label": "Set claimed risk to the resource limit",
                "changes": {"context.riskScore": max_risk},
            }
        )
        if max_risk < MAX_LONG:
            scenarios.append(
                {
                    "id": "risk-above-limit",
                    "label": "Set claimed risk above the resource limit",
                    "changes": {"context.riskScore": max_risk + 1},
                }
            )
    return scenarios


def _apply(command: dict, requested: dict) -> tuple[dict, list[dict]]:
    changed = copy.deepcopy(command)
    changes = []
    for path, value in sorted(requested.items()):
        node, key = _node_at(changed, path)
        before = copy.deepcopy(node[key])
        if _canonical(before) == _canonical(value):
            continue
        node[key] = copy.deepcopy(value)
        changes.append(
            {
                "path": path,
                "before": before,
                "after": copy.deepcopy(value),
                "kind": "requested",
            }
        )
        parts = path.split(".")
        if len(parts) == 3 and parts[1] == "attrs":
            entity = changed[parts[0]]
            if key in entity and _canonical(entity[key]) == _canonical(before):
                entity[key] = copy.deepcopy(value)
                changes.append(
                    {
                        "path": parts[0] + "." + key,
                        "before": before,
                        "after": copy.deepcopy(value),
                        "kind": "compatibility-alias",
                    }
                )
    return changed, changes


def _stable(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                sorted(child)
                if key in {"deny", "forbids", "review", "reasons"}
                and isinstance(child, list)
                and all(isinstance(item, str) for item in child)
                else _stable(child)
            )
            for key, child in sorted(value.items())
        }
    if isinstance(value, list):
        return [_stable(child) for child in value]
    return value


def _trace(result: dict) -> list[dict]:
    trace = []
    for stage, section in (
        ("intent", result["intent"]),
        ("evidence", result["evidence"]),
    ):
        if section is None:
            trace.append(
                {
                    "stage": stage,
                    "source": "lab.evidence-presence",
                    "code": "EVIDENCE_MISSING",
                    "detail": "No evidence statement was submitted.",
                    "evaluator": "decision-lab",
                }
            )
            continue
        fields = (
            ("deny", "review") if section.get("outcome") != "ALLOW" else ("reasons",)
        )
        for field in fields:
            for detail in section.get(field, []):
                trace.append(
                    {
                        "stage": stage,
                        "source": stage + "." + field,
                        "code": REASON_CODES.get(
                            detail, stage.upper() + "_" + field.upper()
                        ),
                        "detail": detail,
                        "evaluator": section.get("evaluator", "python-advisory"),
                    }
                )
    binding = result["evidenceBinding"]
    for detail in binding["reasons"]:
        trace.append(
            {
                "stage": "binding",
                "source": "evidenceBinding.reasons",
                "code": REASON_CODES.get(detail, "EVIDENCE_BINDING_REJECTED"),
                "detail": detail,
                "evaluator": "bind-anatomy",
            }
        )
    if binding["valid"]:
        trace.append(
            {
                "stage": "binding",
                "source": "evidenceBinding.valid",
                "code": "STATEMENT_DIGEST_MATCHED",
                "detail": "The supplied digest matches this statement; this does not verify its signature.",
                "evaluator": "bind-anatomy",
            }
        )
    trace.append(
        {
            "stage": "execution",
            "source": "executionAuthority",
            "code": "EVALUATION_ONLY",
            "detail": result["disclosure"],
            "evaluator": "bind-anatomy",
        }
    )
    return trace


def _evaluate(command: dict, payload: dict) -> dict:
    result = _stable(
        BIND.bind(
            command=command,
            statement=payload.get("statement"),
            verification=payload.get("verification"),
        )
    )
    # Source invariants are checked rather than relabelling a future unsafe result.
    if (
        result.get("executable") is not False
        or result.get("evaluationOnly") is not True
        or result.get("executionAuthority") != "none"
        or result["intent"].get("cedarExecuted") is not False
        or result["intent"].get("identityAuthenticated") is not False
        or (result["evidence"] and result["evidence"].get("verified") is not False)
    ):
        raise ValueError("advisory evaluator trust invariant failed")
    intent = result["intent"]["outcome"]
    evidence = result["evidence"]
    combined = (
        "BLOCK"
        if intent == "BLOCK"
        or (
            evidence
            and (
                evidence["outcome"] == "BLOCK" or not result["evidenceBinding"]["valid"]
            )
        )
        else "REVIEW"
    )
    return {
        "command": command,
        "intentOutcome": intent,
        "combinedOutcome": combined,
        "evaluationOnly": True,
        "executable": False,
        "executionAuthority": "none",
        "result": result,
        "trace": _trace(result),
    }


def _delta(base: dict, scenario: dict) -> dict:
    before_evidence, after_evidence = (
        base["result"]["evidence"],
        scenario["result"]["evidence"],
    )
    pairs = {
        "intent": (base["intentOutcome"], scenario["intentOutcome"]),
        "combined": (base["combinedOutcome"], scenario["combinedOutcome"]),
        "evidence": (
            before_evidence["outcome"] if before_evidence else "MISSING",
            after_evidence["outcome"] if after_evidence else "MISSING",
        ),
        "policyEligible": (
            base["result"]["policyEligible"],
            scenario["result"]["policyEligible"],
        ),
    }
    return {
        key: {"before": before, "after": after, "changed": before != after}
        for key, (before, after) in pairs.items()
    }


def analyze(payload: Any) -> dict[str, Any]:
    value = _validate(payload)
    policy = _snapshot()
    if policy["digest"] != POLICY_AT_LOAD["digest"]:
        raise ValueError(
            "policy source changed since service startup; restart before evaluation"
        )
    base = _evaluate(value["command"], value)
    scenarios = []
    expanded_bytes = len(_canonical(value)) + len(_canonical(base))
    for scenario in value.get("scenarios", _defaults(value["command"])):
        command, changes = _apply(value["command"], scenario["changes"])
        evaluated = _evaluate(command, value)
        item = {
            "id": scenario["id"],
            "label": scenario["label"],
            "requestedChanges": scenario["changes"],
            "changes": changes,
            **evaluated,
            "outcomeDelta": _delta(base, evaluated),
        }
        expanded_bytes += len(_canonical(item))
        if expanded_bytes > MAX_OUTPUT_BYTES:
            raise ValueError(
                "expanded decision report exceeds output limit; reduce input or scenario count"
            )
        scenarios.append(item)
    core = {
        "schema": SCHEMA,
        "evaluationOnly": True,
        "executable": False,
        "executionAuthority": "none",
        "semantics": "independent-counterfactuals",
        "inputDigest": _digest(value),
        "policy": policy,
        "base": base,
        "scenarios": scenarios,
        "traceCodeAuthority": "Local labels for exact evaluator reasons; not native Cedar policy identifiers.",
        "transformationDisclosure": "Consistent inline compatibility aliases are synchronized and every change is listed. Conflicting aliases are preserved.",
        "disclosure": DISCLOSURE,
    }
    result_digest = _digest(core)
    capsule = {
        "schema": CAPSULE_SCHEMA,
        "unsigned": True,
        "input": value,
        "inputDigest": core["inputDigest"],
        "policyDigest": policy["digest"],
        "resultDigest": result_digest,
    }
    report = {
        **core,
        "resultDigest": result_digest,
        "replayCapsule": capsule,
        "replayCapsuleJson": _canonical(capsule).decode("utf-8"),
    }
    if len(_canonical(report)) > MAX_OUTPUT_BYTES:
        raise ValueError(
            "expanded decision report exceeds output limit; reduce input or scenario count"
        )
    if _snapshot()["digest"] != policy["digest"]:
        raise ValueError(
            "policy source changed during evaluation; restart before evaluation"
        )
    return report


def replay(capsule: Any) -> dict[str, Any]:
    output = {
        "schema": REPLAY_SCHEMA,
        "valid": False,
        "issues": [],
        "current": None,
        "inputMatch": False,
        "policyMatch": False,
        "resultMatch": False,
        "unsigned": True,
        "authentic": False,
        "trust": "unsigned-untrusted",
        "evaluationOnly": True,
        "executable": False,
        "executionAuthority": "none",
        "disclosure": DISCLOSURE,
    }
    try:
        value = _bounded_copy(capsule, MAX_CAPSULE_BYTES, envelope=True)
        required = {
            "schema",
            "unsigned",
            "input",
            "inputDigest",
            "policyDigest",
            "resultDigest",
        }
        if (
            type(value) is not dict
            or set(value) != required
            or value["schema"] != CAPSULE_SCHEMA
            or value["unsigned"] is not True
            or any(
                type(value[key]) is not str
                or not re.fullmatch(r"[0-9a-f]{64}", value[key])
                for key in ("inputDigest", "policyDigest", "resultDigest")
            )
        ):
            raise ValueError("invalid replay capsule structure")
        output["inputMatch"] = _digest(value["input"]) == value["inputDigest"]
        if not output["inputMatch"]:
            output["issues"].append(
                {
                    "code": "INPUT_DIGEST_MISMATCH",
                    "detail": "Capsule input does not match its recorded digest.",
                }
            )
        policy = _snapshot()
        output["policyMatch"] = policy["digest"] == value["policyDigest"]
        if not output["policyMatch"]:
            output["issues"].append(
                {
                    "code": "POLICY_DRIFT",
                    "detail": "Current policy sources differ from this capsule.",
                }
            )
        if policy["digest"] != POLICY_AT_LOAD["digest"]:
            output["issues"].append(
                {
                    "code": "POLICY_RUNTIME_STALE",
                    "detail": "On-disk policy changed after loading; restart before replay.",
                }
            )
            return output
        current = analyze(value["input"])
        output["current"] = current
        output["resultMatch"] = current["resultDigest"] == value["resultDigest"]
        if not output["resultMatch"]:
            output["issues"].append(
                {
                    "code": "RESULT_DIGEST_MISMATCH",
                    "detail": "Fresh complete evaluation differs from the recorded result digest.",
                }
            )
        output["valid"] = not output["issues"]
        if len(_canonical(output)) > MAX_OUTPUT_BYTES:
            output.update(valid=False, current=None)
            output["issues"].append(
                {
                    "code": "OUTPUT_LIMIT_EXCEEDED",
                    "detail": "Expanded replay report exceeds the output limit.",
                }
            )
        return output
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        output["issues"].append({"code": "CAPSULE_INVALID", "detail": str(exc)})
        return output


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON keys are not accepted")
        value[key] = item
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", action="store_true")
    args = parser.parse_args()
    limit = MAX_CAPSULE_BYTES if args.replay else MAX_INPUT_BYTES
    raw = sys.stdin.buffer.read(limit + 1)
    if len(raw) > limit:
        raise SystemExit("JSON byte limit exceeded")
    payload = json.loads(raw, object_pairs_hook=_unique_object)
    result = replay(payload) if args.replay else analyze(payload)
    sys.stdout.buffer.write(_canonical(result) + b"\n")


if __name__ == "__main__":
    main()
