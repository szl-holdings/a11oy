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
# The canonical publisher replaces only this leading-dot placeholder with the
# GENERATED manifest at deploy time (szl-holdings/.github hf_deploy_from_dockerfile
# --release-manifest-file). The committed release-manifest.json stays the
# honest placeholder for constrained/local builds.
PUBLISHED_MANIFEST_NAME = ".szl-release-manifest.json"

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
_FULL_SHA_RE = re.compile(r"^(?!0{40}$)[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_IMMUTABLE_ID_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:/+-]{0,191}@"
    r"(?:sha256:(?!0{64}$)[0-9a-f]{64}|(?!0{40}$)[0-9a-f]{40})$"
)


_PLACEHOLDER_STATUS = "PLACEHOLDER_UNTIL_CI_GENERATED"
_GENERATED_STATUS = "GENERATED"


def _env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    return value if value else UNKNOWN


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
        if value and value != UNKNOWN:
            return value
    return UNKNOWN


def manifest_path() -> Path:
    configured = (os.getenv(MANIFEST_PATH_ENV) or "").strip()
    if configured:
        return Path(configured)
    published = Path(__file__).with_name(PUBLISHED_MANIFEST_NAME)
    if published.is_file():
        return published
    return Path(__file__).with_name(DEFAULT_MANIFEST_NAME)


def _is_unknown(value: Any) -> bool:
    if value is None:
        return True
    if type(value) is not str:
        return False
    text = value.strip()
    return text == "" or text.upper() == UNKNOWN


def _unique_json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate keys, including nested status/identity keys."""
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError("duplicate manifest key")
        output[key] = value
    return output


def _valid_runtime_value(key: str, value: Any) -> bool:
    """Syntax-only eligibility; verification of source bytes is external."""
    if (
        type(value) is not str
        or len(value) > 512
        or not value
        or value != value.strip()
        or _is_unknown(value)
    ):
        return False
    if key in ("served_frontend_sha256", "api_contract_sha256"):
        return _SHA256_RE.fullmatch(value) is not None and any(ch != "0" for ch in value)
    if key in ("model_identity", "deployment_identity"):
        return _IMMUTABLE_ID_RE.fullmatch(value) is not None
    return False


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
        raw = json.loads(
            target.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_json_pairs,
        )
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
    status = raw.get("status")
    if type(status) is not str or status not in {_PLACEHOLDER_STATUS, _GENERATED_STATUS}:
        result["reason"] = "manifest status invalid"
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
        evidence["_labels"][key] = (
            "MEASURED_ENV" if _valid_runtime_value(key, value) else UNKNOWN
        )
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

    if m_status == "UNAVAILABLE":
        findings.append(_finding(
            "MANIFEST_UNAVAILABLE", "error",
            "release manifest is absent or malformed; build identity cannot be checked"))
    if m_status == _PLACEHOLDER_STATUS:
        findings.append(_finding(
            "MANIFEST_PLACEHOLDER", "error",
            "release manifest is the committed placeholder; CI must generate it before promotion"))
    if type(m_status) is not str or m_status not in {_GENERATED_STATUS, _PLACEHOLDER_STATUS, "UNAVAILABLE"}:
        findings.append(_finding(
            "MANIFEST_STATUS_INVALID", "error",
            "manifest status is not an admitted release state"))

    commit_matches = False
    if _is_unknown(r_commit):
        findings.append(_finding(
            "SOURCE_COMMIT_UNKNOWN", "error",
            "runtime source commit is UNKNOWN; no commit-level check is possible"))
    elif _is_unknown(m_commit):
        findings.append(_finding(
            "MANIFEST_COMMIT_UNKNOWN", "error",
            "manifest carries no source commit; identity check is impossible"))
    elif (
        type(r_commit) is not str
        or type(m_commit) is not str
        or _FULL_SHA_RE.fullmatch(r_commit) is None
        or _FULL_SHA_RE.fullmatch(m_commit) is None
    ):
        findings.append(_finding(
            "SOURCE_COMMIT_FORMAT_INVALID", "error",
            "runtime and manifest commits must be full canonical 40-hex revisions"))
    elif r_commit == m_commit:
        commit_matches = True
        findings.append(_finding(
            "SOURCE_COMMIT_MATCH", "info",
            f"runtime commit {r_commit[:12]} matches the manifest"))
    else:
        findings.append(_finding(
            "SOURCE_COMMIT_MISMATCH", "error",
            f"runtime commit and manifest commit differ ({str(r_commit)[:12]} vs {str(m_commit)[:12]})"))

    missing_any = False
    mismatched_any = False
    invalid_any = False
    for key in REQUIRED_RUNTIME_EVIDENCE:
        run_value = runtime.get(key, UNKNOWN)
        man_value = m_runtime.get(key, UNKNOWN)
        if _is_unknown(run_value):
            missing_any = True
            findings.append(_finding(
                f"{key.upper()}_UNKNOWN", "error",
                f"required runtime evidence '{key}' is UNKNOWN (env {RUNTIME_ENV_NAMES[key]} unset)"))
        elif not _valid_runtime_value(key, run_value):
            invalid_any = True
            findings.append(_finding(
                f"{key.upper()}_INVALID", "error",
                f"runtime '{key}' is malformed or lacks a pinned identity"))
        elif _is_unknown(man_value):
            missing_any = True
            findings.append(_finding(
                f"MANIFEST_{key.upper()}_UNKNOWN", "error",
                f"runtime '{key}' is present but the manifest does not bind it"))
        elif not _valid_runtime_value(key, man_value):
            invalid_any = True
            findings.append(_finding(
                f"MANIFEST_{key.upper()}_INVALID", "error",
                f"manifest '{key}' is malformed or lacks a pinned identity"))
        elif run_value != man_value:
            mismatched_any = True
            findings.append(_finding(
                f"{key.upper()}_MISMATCH", "error",
                f"runtime '{key}' does not match the release manifest"))
        else:
            findings.append(_finding(
                f"{key.upper()}_MATCH", "info",
                f"runtime '{key}' matches the release manifest"))

    if commit_matches and (missing_any or mismatched_any or invalid_any):
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
        run_ok = _valid_runtime_value(key, runtime.get(key, UNKNOWN))
        man_ok = _valid_runtime_value(key, m_runtime.get(key, UNKNOWN))
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
        if not _valid_runtime_value(key, value):
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
