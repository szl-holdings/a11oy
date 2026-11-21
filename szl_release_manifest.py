"""szl_release_manifest.py — one release manifest + fail-closed promotion gate.

Implements #3770: a single, machine-checkable release manifest binding the
source identity (git commit) to the runtime build evidence (served frontend
hash, API contract hash, model identity, deployment identity), plus a
promotion gate that BLOCKS when any required runtime evidence is missing or
UNKNOWN.

Doctrine (fixed in code, not prose):
  * Values are NEVER hardcoded. Every field comes from CI env, a measured
    file hash, or an explicit CLI argument. Anything absent is reported as the
    honest label "UNKNOWN"; nothing is ever invented or upgraded.
  * Fail closed: a matching git commit with NO runtime evidence is NOT "no
    findings". It is PUBLICATION_LAG (#3768 repro) and BLOCKS promotion.
  * The gate decision is mechanical evidence arithmetic, not a quality
    verdict: PASS == all four required runtime items present AND consistent
    with the manifest AND source commit present. Everything else is BLOCKED.

Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

UNKNOWN = "UNKNOWN"
KIND = "szl.release-manifest/v1"
BUILD_KIND = "szl.build/v1"
GATE_KIND = "szl.promotion-gate/v1"

MANIFEST_PATH_ENV = "SZL_RELEASE_MANIFEST_PATH"
DEFAULT_MANIFEST_NAME = "release-manifest.json"

# Required runtime evidence per #3770 (owner directive 2026-11-19): the hosted
# demo must not be promoted/routed when these are missing or UNKNOWN.
REQUIRED_RUNTIME_EVIDENCE: tuple[str, ...] = (
    "served_frontend_sha256",
    "api_contract_sha256",
    "model_identity",
    "deployment_identity",
)

RUNTIME_ENV_NAMES: dict[str, str] = {
    "served_frontend_sha256": "SZL_SERVED_FRONTEND_SHA256",
    "api_contract_sha256": "SZL_API_CONTRACT_SHA256",
    "model_identity": "SZL_MODEL_IDENTITY",
    "deployment_identity": "SZL_DEPLOYMENT_IDENTITY",
}

_COMMIT_ENV_NAMES = ("SZL_RELEASE_COMMIT", "A11OY_GIT_SHA", "SZL_GIT_SHA", "GITHUB_SHA")
_RELEASE_ID_ENV_NAMES = ("SZL_RELEASE_ID",)
_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_PLACEHOLDER_STATUS = "PLACEHOLDER_UNTIL_CI_GENERATED"
_GENERATED_STATUS = "GENERATED"
_RESERVED_EVIDENCE_VALUES = frozenset({
    "", UNKNOWN, "UNAVAILABLE", "UNDECLARED", "PLACEHOLDER",
    "MANIFEST_PLACEHOLDER", "MANIFEST_UNAVAILABLE", "NOT_CONFIGURED",
    "NONE", "NULL", "N/A", "TBD", _PLACEHOLDER_STATUS,
})


def _env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    return UNKNOWN if _is_unknown(value) else value


def source_commit() -> str:
    """Full 40-hex commit from runtime env. Anything else stays UNKNOWN."""
    for name in _COMMIT_ENV_NAMES:
        value = (os.getenv(name) or "").strip().lower()
        if _FULL_SHA_RE.fullmatch(value):
            return value
    return UNKNOWN


def release_id() -> str:
    for name in _RELEASE_ID_ENV_NAMES:
        value = (os.getenv(name) or "").strip()
        if not _is_unknown(value):
            return value
    return UNKNOWN


def manifest_path() -> Path:
    configured = (os.getenv(MANIFEST_PATH_ENV) or "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).with_name(DEFAULT_MANIFEST_NAME)


def _is_unknown(value: Any) -> bool:
    return not isinstance(value, str) or value.strip().upper() in _RESERVED_EVIDENCE_VALUES


def sha256_file(path: str | os.PathLike[str]) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """Load + structurally validate the manifest. Fail closed, never invent.

    Absent or malformed file → {"status": "UNAVAILABLE"} and the promotion
    gate blocks on MANIFEST_UNAVAILABLE. A committed placeholder (status
    PLACEHOLDER_UNTIL_CI_GENERATED) is surfaced honestly; its UNKNOWN values
    are never upgraded into evidence and the gate BLOCKS on it.
    """
    target = Path(path) if path else manifest_path()
    result: dict[str, Any] = {
        "kind": KIND,
        "status": "UNAVAILABLE",
        "reason": "manifest file absent or malformed",
        "path": str(target),
        "manifest": None,
    }
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        result["reason"] = f"{type(exc).__name__}: {exc}"[:200]
        return result
    if not isinstance(raw, dict) or raw.get("kind") != KIND:
        result["reason"] = "manifest kind mismatch"
        return result

    runtime = raw.get("runtime")
    runtime = runtime if isinstance(runtime, dict) else {}
    source = raw.get("source")
    source = source if isinstance(source, dict) else {}
    status = str(raw.get("status") or "").strip()

    if status not in (_PLACEHOLDER_STATUS, _GENERATED_STATUS):
        result["reason"] = "manifest generation status is absent or unrecognized"
        return result
    result["status"] = status
    result["manifest"] = raw
    result["source_commit"] = source.get("git_commit") or UNKNOWN
    result["runtime"] = {key: (runtime.get(key) or UNKNOWN) for key in REQUIRED_RUNTIME_EVIDENCE}
    result["release_id"] = raw.get("release_id") or UNKNOWN
    return result


def runtime_evidence() -> dict[str, Any]:
    """MEASURED runtime evidence from env. Absent → UNKNOWN, never invented."""
    evidence: dict[str, Any] = {
        "kind": BUILD_KIND,
        "source_commit": source_commit(),
        "release_id": release_id(),
        "_labels": {},
    }
    for key, env_name in RUNTIME_ENV_NAMES.items():
        value = _env(env_name)
        evidence[key] = value
        evidence["_labels"][key] = "MEASURED_ENV" if not _is_unknown(value) else UNKNOWN
    return evidence


def _finding(kind: str, severity: str, detail: str, **extra: Any) -> dict[str, Any]:
    finding: dict[str, Any] = {"kind": kind, "severity": severity, "detail": detail}
    finding.update(extra)
    return finding


def compare_runtime(manifest: dict[str, Any], runtime: dict[str, Any]) -> list[dict[str, Any]]:
    """Deterministic findings comparing manifest vs runtime.

    The finding list is empty ONLY when the manifest is available and
    generated, the source commit matches, and every required runtime evidence
    item is present and matches the manifest. The #3768 repro (matching git
    commit, NO runtime hashes reported) must never be empty: it is
    PUBLICATION_LAG and BLOCKS.
    """
    findings: list[dict[str, Any]] = []
    m_status = manifest.get("status", "UNAVAILABLE")
    m_runtime = manifest.get("runtime", {})
    m_runtime = m_runtime if isinstance(m_runtime, dict) else {}
    m_commit = manifest.get("source_commit", UNKNOWN)
    r_commit = runtime.get("source_commit", UNKNOWN)

    if m_status not in (_PLACEHOLDER_STATUS, _GENERATED_STATUS):
        findings.append(_finding(
            "MANIFEST_UNAVAILABLE", "error",
            "release manifest is absent or malformed; build identity cannot be checked"))
    if m_status == _PLACEHOLDER_STATUS:
        findings.append(_finding(
            "MANIFEST_PLACEHOLDER", "error",
            "release manifest is the committed placeholder; CI must generate it before promotion"))

    commit_matches = False
    if _is_unknown(r_commit):
        findings.append(_finding(
            "SOURCE_COMMIT_UNKNOWN", "error",
            "runtime source commit is UNKNOWN; no commit-level check is possible"))
    elif _is_unknown(m_commit):
        findings.append(_finding(
            "MANIFEST_COMMIT_UNKNOWN", "error",
            "manifest carries no source commit; identity check is impossible"))
    elif str(r_commit) == str(m_commit):
        commit_matches = True
        findings.append(_finding(
            "SOURCE_COMMIT_MATCH", "info",
            f"runtime commit {str(r_commit)[:12]} matches the manifest"))
    else:
        findings.append(_finding(
            "SOURCE_COMMIT_MISMATCH", "error",
            f"runtime commit and manifest commit differ ({str(r_commit)[:12]} vs {str(m_commit)[:12]})"))

    missing_any = False
    mismatched_any = False
    for key in REQUIRED_RUNTIME_EVIDENCE:
        run_value = runtime.get(key, UNKNOWN)
        man_value = m_runtime.get(key, UNKNOWN)
        if _is_unknown(run_value):
            missing_any = True
            findings.append(_finding(
                f"{key.upper()}_UNKNOWN", "error",
                f"required runtime evidence '{key}' is UNKNOWN (env {RUNTIME_ENV_NAMES[key]} unset)"))
        elif _is_unknown(man_value):
            findings.append(_finding(
                f"MANIFEST_{key.upper()}_UNKNOWN", "error",
                f"runtime '{key}' is present but the manifest does not bind it"))
        elif str(run_value) != str(man_value):
            mismatched_any = True
            findings.append(_finding(
                f"{key.upper()}_MISMATCH", "error",
                f"runtime '{key}' does not match the release manifest"))
        else:
            findings.append(_finding(
                f"{key.upper()}_MATCH", "info",
                f"runtime '{key}' matches the release manifest"))

    if commit_matches and (missing_any or mismatched_any):
        findings.append(_finding(
            "PUBLICATION_LAG", "error",
            "source commit is deployed but its build evidence was never published to the runtime; "
            "promote/route is denied until the manifest evidence ships with the deployment"))

    if missing_any and not commit_matches:
        findings.append(_finding(
            "REQUIRED_EVIDENCE_INCOMPLETE", "error",
            "required runtime evidence is incomplete; promotion gate fails closed"))
    return findings


def promotion_gate(manifest: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    """Fail-closed promotion gate (#3770 owner directive).

    Required to PASS: manifest available and generated, source commit present
    and matching, and ALL four required runtime evidence items present and
    matching the manifest. Anything else BLOCKS. UNKNOWN never passes.
    """
    findings = compare_runtime(manifest, runtime)
    blocking = [f for f in findings if f["severity"] == "error"]
    m_runtime = manifest.get("runtime", {})
    m_runtime = m_runtime if isinstance(m_runtime, dict) else {}
    checked: dict[str, Any] = {}
    for key in REQUIRED_RUNTIME_EVIDENCE:
        run_ok = not _is_unknown(runtime.get(key, UNKNOWN))
        man_ok = not _is_unknown(m_runtime.get(key, UNKNOWN))
        checked[key] = {
            "runtime": "MEASURED" if run_ok else UNKNOWN,
            "manifest": "MEASURED" if man_ok else UNKNOWN,
        }
    decision = "BLOCKED" if blocking else "PASS"
    return {
        "kind": GATE_KIND,
        "decision": decision,
        "fail_closed": True,
        "issue": "#3770",
        "blocking_findings": blocking,
        "checked": checked,
        "honesty": {
            "unknown_is_never_pass": True,
            "no_quality_verdict": True,
            "decision_is_evidence_arithmetic": True,
        },
    }


def build_payload(manifest: dict[str, Any] | None = None, runtime: dict[str, Any] | None = None) -> dict[str, Any]:
    """Assemble the read-only GET /api/build payload (also used by tests)."""
    manifest = manifest if manifest is not None else load_manifest()
    runtime = runtime if runtime is not None else runtime_evidence()
    findings = compare_runtime(manifest, runtime)
    gate = promotion_gate(manifest, runtime)
    r_id = runtime.get("release_id")
    resolved_release_id = r_id if not _is_unknown(r_id) else manifest.get("release_id", UNKNOWN)
    return {
        "kind": BUILD_KIND,
        "release_id": resolved_release_id,
        "manifest": {
            "status": manifest.get("status", "UNAVAILABLE"),
            "source_commit": manifest.get("source_commit", UNKNOWN),
            "runtime": manifest.get("runtime", {}),
        },
        "runtime": {k: v for k, v in runtime.items() if not k.startswith("_")},
        "findings": findings,
        "promotion_gate": gate,
        "honesty": {
            "labels": "MEASURED / UNKNOWN / UNAVAILABLE",
            "no_fabricated_values": True,
            "unknown_gate_state": "BLOCKED",
        },
    }


def generate_manifest(
    *,
    commit: str | None = None,
    git_ref: str | None = None,
    openapi_json_path: str | None = None,
    api_contract_doc_path: str | os.PathLike[str] | None = None,
    served_artifact_path: str | None = None,
    model_identity: str | None = None,
    deployment_identity: str | None = None,
    release_id_value: str | None = None,
    generated_at: str | None = None,
    status: str = _GENERATED_STATUS,
) -> tuple[dict[str, Any], list[str]]:
    """Build a manifest purely from measured/explicit inputs.

    Returns (manifest, missing) where missing lists REQUIRED_RUNTIME_EVIDENCE
    (and the source commit) that stayed UNKNOWN. Callers using
    --require-complete treat a non-empty missing list as a hard failure.
    """
    commit = (commit or os.getenv("GITHUB_SHA") or "").strip().lower() or UNKNOWN
    if commit != UNKNOWN and not _FULL_SHA_RE.fullmatch(commit):
        commit = UNKNOWN

    api_contract_sha = UNKNOWN
    api_contract_source = UNKNOWN
    if openapi_json_path:
        api_contract_sha = sha256_file(openapi_json_path)
        api_contract_source = "openapi_json"
    elif api_contract_doc_path:
        api_contract_sha = sha256_file(api_contract_doc_path)
        api_contract_source = "docs/api-contract.md"

    served_sha = sha256_file(served_artifact_path) if served_artifact_path else UNKNOWN

    model_identity = (model_identity or os.getenv("SZL_MODEL_IDENTITY") or "").strip() or UNKNOWN
    deployment_identity = (deployment_identity or os.getenv("SZL_DEPLOYMENT_IDENTITY") or "").strip() or UNKNOWN
    release_id_value = (release_id_value or os.getenv("SZL_RELEASE_ID") or "").strip() or UNKNOWN

    runtime: dict[str, Any] = {
        "served_frontend_sha256": served_sha,
        "api_contract_sha256": api_contract_sha,
        "model_identity": model_identity,
        "deployment_identity": deployment_identity,
    }
    missing: list[str] = []
    if commit == UNKNOWN:
        missing.append("source.git_commit")
    for key, value in runtime.items():
        if _is_unknown(value):
            missing.append(f"runtime.{key}")

    manifest: dict[str, Any] = {
        "kind": KIND,
        "status": status,
        "release_id": release_id_value,
        "generated_at": generated_at or UNKNOWN,
        "source": {"git_commit": commit, "git_ref": (git_ref or os.getenv("GITHUB_REF") or UNKNOWN)},
        "runtime": runtime,
        "api_contract_source": api_contract_source,
        "honesty": {
            "never_hardcoded": True,
            "missing_values_stay_unknown": True,
        },
    }
    return manifest, missing
