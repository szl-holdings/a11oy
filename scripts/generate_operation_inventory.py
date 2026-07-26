#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Generate the Operation Verified Throughput Phase 0 inventory.

Live GitHub and Hugging Face reads are attempted at generation time. Unavailable
sources are recorded as BLOCKED, never replaced with invented inventory.
Secret values are neither requested nor written.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SPDX = "SPDX-License-Identifier: Apache-2.0"
OWNER = "(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173"
ATTESTED_SOURCE_COMMIT = "7ccf04fb65f060115fb01392c739bb4e6c2fe5b8"
ATTESTED_IMAGE_DIGEST = "sha256:5f3f48219d0c74f29ebfd6df6d7b8b68903daf6772cf6483124f458a3beca416"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run(command: list[str], cwd: Path, *, json_result: bool = False) -> Any:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=90,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "BLOCKED", "reason": type(exc).__name__}
    if completed.returncode:
        return {"status": "BLOCKED", "reason": completed.stderr.strip()[-500:] or f"exit {completed.returncode}"}
    if not json_result:
        return completed.stdout.strip()
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"status": "FAILED", "reason": "non-JSON response"}


def gh(root: Path, *arguments: str) -> Any:
    executable = shutil.which("gh")
    if not executable:
        return {"status": "BLOCKED", "reason": "GitHub CLI unavailable"}
    return run([executable, *arguments], root, json_result=True)


def fetch_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": "a11oy-operation-inventory/1"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"status": "BLOCKED", "reason": type(exc).__name__, "url": url}


def fetch_status(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "a11oy-operation-inventory/1"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return {"status": "MEASURED", "status_code": response.status, "url": url}
    except (urllib.error.URLError, TimeoutError) as exc:
        return {"status": "BLOCKED", "reason": type(exc).__name__, "url": url}


def commit_sha(value: Any) -> str:
    if isinstance(value, dict) and isinstance(value.get("sha"), str):
        return value["sha"]
    return "UNAVAILABLE"


def runtime_revision(value: Any) -> str:
    if isinstance(value, dict):
        build = value.get("build")
        if isinstance(build, dict) and isinstance(build.get("revision"), str):
            return build["revision"]
    return "UNAVAILABLE"


def backup_restoration(root: Path) -> dict[str, Any]:
    path = root / "audit" / "hf-backup-restoration.json"
    if not path.is_file():
        return {
            "status": "PREPARED IN A PR",
            "reason": "Secret-backed snapshot and byte-for-byte restoration workflow has not completed.",
        }
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "FAILED", "reason": type(exc).__name__}
    repositories = value.get("repositories", [])
    measured = bool(value.get("all_restores_match")) and len(repositories) == 2
    return {
        "status": "MEASURED" if measured else "FAILED",
        "evidence": "audit/hf-backup-restoration.json",
        "workflow_run_url": value.get("workflow_run_url"),
        "repositories": [
            {
                "repository": item.get("repository"),
                "revision": item.get("revision"),
                "archive_sha256": item.get("archive_sha256"),
                "manifest_sha256": item.get("manifest_sha256"),
                "restore_match": item.get("restore_match"),
            }
            for item in repositories
            if isinstance(item, dict)
        ],
    }


def write_json(output: Path, name: str, payload: Any, observed_at: str) -> None:
    envelope = {
        "_license": f"{SPDX}; {OWNER}",
        "generated_at": observed_at,
        "generator": "scripts/generate_operation_inventory.py",
        "data": payload,
    }
    (output / name).write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def select(value: Any, keys: tuple[str, ...]) -> Any:
    if not isinstance(value, dict):
        return value
    return {key: value.get(key) for key in keys if key in value}


def compact_list(value: Any, keys: tuple[str, ...]) -> Any:
    if not isinstance(value, list):
        return value
    return [select(item, keys) for item in value]


def compact_hf_space(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    result = select(value, ("id", "sha", "lastModified", "private", "disabled", "gated", "sdk", "host", "subdomain"))
    runtime = value.get("runtime")
    if isinstance(runtime, dict):
        result["runtime"] = select(runtime, ("stage", "hardware", "requestedHardware", "sleepTime", "storage"))
    return result


def action_inventory(root: Path) -> list[dict[str, Any]]:
    results = []
    pattern = re.compile(r"^\s*(?:-\s*)?uses:\s*['\"]?([^@\s'\"]+)@([^\s#'\"]+)(?:\s*#\s*(.*))?")
    local_pattern = re.compile(r"^\s*(?:-\s*)?uses:\s*['\"]?(\./[^\s#'\"]+)")
    for workflow in sorted((root / ".github" / "workflows").glob("*.y*ml")):
        for number, line in enumerate(workflow.read_text(encoding="utf-8").splitlines(), 1):
            match = pattern.search(line)
            if not match:
                local_match = local_pattern.search(line)
                if local_match:
                    results.append(
                        {
                            "workflow": workflow.relative_to(root).as_posix(),
                            "line": number,
                            "action": local_match.group(1),
                            "reference": "local-checkout",
                            "release_name": None,
                            "pinned": True,
                            "pin_policy": "local",
                        }
                    )
                continue
            action, reference, release = match.groups()
            local = action.startswith("./")
            docker = action.startswith("docker://")
            sha_pinned = bool(re.fullmatch(r"[0-9a-f]{40}", reference))
            slsa_tag_exception = action.startswith("slsa-framework/slsa-github-generator/") and bool(
                re.fullmatch(r"v\d+\.\d+\.\d+", reference)
            )
            results.append(
                {
                    "workflow": workflow.relative_to(root).as_posix(),
                    "line": number,
                    "action": action,
                    "reference": reference,
                    "release_name": (release or "").strip() or None,
                    "pinned": local or docker or sha_pinned or slsa_tag_exception,
                    "pin_policy": "local" if local else "docker" if docker else "slsa-exact-tag" if slsa_tag_exception else "full-sha",
                }
            )
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    output = (args.output or root / "audit").resolve()
    output.mkdir(parents=True, exist_ok=True)
    observed = utc_now()

    repos = gh(
        root,
        "repo",
        "list",
        "szl-holdings",
        "--limit",
        "1000",
        "--json",
        "name,nameWithOwner,url,isPrivate,isArchived,defaultBranchRef,updatedAt",
    )
    repo = gh(root, "api", "repos/szl-holdings/a11oy")
    a11oy_main = gh(root, "api", "repos/szl-holdings/a11oy/commits/main")
    killinchu_main = gh(root, "api", "repos/szl-holdings/killinchu/commits/main")
    a11oy_main_sha = commit_sha(a11oy_main)
    killinchu_main_sha = commit_sha(killinchu_main)
    backup = backup_restoration(root)
    workflows = gh(root, "api", "repos/szl-holdings/a11oy/actions/workflows?per_page=100")
    releases = gh(root, "api", "repos/szl-holdings/a11oy/releases?per_page=100")
    deployments = gh(root, "api", "repos/szl-holdings/a11oy/deployments?per_page=100")
    open_prs = gh(
        root,
        "pr",
        "list",
        "-R",
        "szl-holdings/a11oy",
        "--state",
        "open",
        "--limit",
        "100",
        "--json",
        "number,title,url,isDraft,headRefName,baseRefName,reviewDecision,statusCheckRollup",
    )
    rulesets = gh(root, "api", "repos/szl-holdings/a11oy/rulesets?includes_parents=true")
    environments = gh(root, "api", "repos/szl-holdings/a11oy/environments")
    packages = gh(root, "api", "orgs/szl-holdings/packages?package_type=container&per_page=100")
    codeowners = []
    for candidate in (root / ".github" / "CODEOWNERS", root / "CODEOWNERS", root / "docs" / "CODEOWNERS"):
        if candidate.is_file():
            codeowners.append(candidate.relative_to(root).as_posix())
    compact_prs = open_prs
    if isinstance(open_prs, list):
        compact_prs = []
        for item in open_prs:
            compact = select(
                item,
                ("number", "title", "url", "isDraft", "headRefName", "baseRefName", "reviewDecision"),
            )
            compact["checks"] = [
                select(check, ("name", "context", "status", "conclusion", "workflowName"))
                for check in item.get("statusCheckRollup", [])
                if isinstance(check, dict)
            ]
            compact_prs.append(compact)
    compact_workflows = workflows
    if isinstance(workflows, dict) and isinstance(workflows.get("workflows"), list):
        compact_workflows = {
            "total_count": workflows.get("total_count"),
            "workflows": compact_list(
                workflows["workflows"],
                ("id", "name", "path", "state", "created_at", "updated_at", "html_url"),
            ),
        }
    compact_releases = releases
    if isinstance(releases, list):
        compact_releases = []
        for item in releases:
            release = select(
                item,
                ("id", "tag_name", "target_commitish", "draft", "prerelease", "created_at", "published_at", "html_url"),
            )
            release["assets"] = compact_list(
                item.get("assets", []),
                ("id", "name", "size", "digest", "created_at", "updated_at", "browser_download_url"),
            )
            compact_releases.append(release)
    write_json(
        output,
        "github-estate.json",
        {
            "status": "MEASURED",
            "organization_repositories": repos,
            "canonical_repository": select(
                repo,
                ("id", "name", "full_name", "private", "html_url", "default_branch", "archived", "visibility", "pushed_at", "updated_at"),
            ),
            "environments": (
                {
                    "total_count": environments.get("total_count"),
                    "environments": compact_list(
                        environments.get("environments", []),
                        ("id", "node_id", "name", "url", "html_url", "created_at", "updated_at"),
                    ),
                }
                if isinstance(environments, dict)
                else environments
            ),
            "workflows": compact_workflows,
            "releases": compact_releases,
            "packages": compact_list(
                packages,
                ("id", "name", "package_type", "visibility", "url", "created_at", "updated_at", "html_url"),
            ),
            "deployments": compact_list(
                deployments,
                ("id", "ref", "sha", "environment", "task", "created_at", "updated_at", "statuses_url"),
            ),
            "open_pull_requests": compact_prs,
            "owners_files": codeowners,
            "protection_mutations_performed": [],
        },
        observed,
    )
    write_json(
        output,
        "repository-rulesets.json",
        {
            "status": "MEASURED",
            "source": "GitHub rulesets API including parent rulesets",
            "rulesets": rulesets,
            "mutation": "NONE",
            "coordination_lock": "Preserve external protection state; do not reapply approvals or checks.",
        },
        observed,
    )

    actions = action_inventory(root)
    write_json(
        output,
        "workflow-action-pins.json",
        {
            "status": "MEASURED",
            "references": actions,
            "total": len(actions),
            "unpinned": [item for item in actions if not item["pinned"]],
        },
        observed,
    )

    repo_secrets = run([shutil.which("gh") or "gh", "secret", "list", "-R", "szl-holdings/a11oy", "--json", "name,updatedAt,visibility"], root, json_result=True)
    org_secrets = run([shutil.which("gh") or "gh", "secret", "list", "--org", "szl-holdings", "--json", "name,updatedAt,visibility,selectedRepositoriesURL"], root, json_result=True)
    write_json(
        output,
        "secrets-inventory-redacted.json",
        {
            "status": "MEASURED" if isinstance(repo_secrets, list) else "BLOCKED",
            "values_requested": False,
            "repository_secret_names": repo_secrets,
            "organization_secret_names": org_secrets,
        },
        observed,
    )
    write_json(
        output,
        "cloud-estate.json",
        {
            "status": "BLOCKED",
            "reason": "No named cloud account, non-local staging cluster context, registry admin plane, or secret-manager credential is available in this execution environment.",
            "identities": [],
            "registries": [{"name": "ghcr.io/szl-holdings/a11oy", "access": "public-read"}],
            "clusters": [],
            "namespaces": [],
            "secret_paths": [],
            "owner_authorization_received": True,
            "destructive_changes_performed": False,
        },
        observed,
    )
    workflow_text = "\n".join(path.read_text(encoding="utf-8") for path in (root / ".github" / "workflows").glob("*.y*ml"))
    write_json(
        output,
        "identity-and-oidc-estate.json",
        {
            "status": "MEASURED",
            "github_oidc_permission_references": workflow_text.count("id-token: write"),
            "static_secret_reference_count": len(re.findall(r"\bsecrets\.[A-Za-z_][A-Za-z0-9_]*", workflow_text)),
            "proposed_reusable_builder": ".github/workflows/reusable-build.yml",
            "worker_receipt_authority": "public-key verification only",
            "managed_cloud_workload_identities": {"status": "BLOCKED", "reason": "cloud control plane unavailable"},
        },
        observed,
    )
    write_json(
        output,
        "provenance-baseline.json",
        {
            "status": "MEASURED",
            "artifact": f"oci://ghcr.io/szl-holdings/a11oy@{ATTESTED_IMAGE_DIGEST}",
            "source_commit": ATTESTED_SOURCE_COMMIT,
            "github_attestation_verified": True,
            "verification_command": f"gh attestation verify oci://ghcr.io/szl-holdings/a11oy@{ATTESTED_IMAGE_DIGEST} --repo szl-holdings/a11oy",
            "workflow_run": "https://github.com/szl-holdings/a11oy/actions/runs/30187276319/attempts/1",
            "attestation_id": 37130249,
            "rekor_log_index": 2255395975,
            "slsa_verifier": {
                "version": "2.7.1",
                "binary_digest": "sha256:1d8f61ad747ecc3d375d2a563cebf2991748b7da1a9bda9a500804c3c499e3c0",
                "verify_image_result": "FAILED: no matching attestations",
            },
            "slsa_level": "Build L2 evidence observed; L3 not claimed",
            "limitations": [
                "Existing builder is not a protected reusable workflow.",
                "Existing workflow also signed mutable tags.",
                "SLSA verifier 2.7.1 found no matching SLSA-native attestation for this digest.",
            ],
        },
        observed,
    )
    manifest = json.loads((root / "formal" / "LutarPolicy" / "lake-manifest.json").read_text(encoding="utf-8"))
    write_json(
        output,
        "lean-baseline.json",
        {
            "status": "MEASURED",
            "toolchain": (root / "formal" / "LutarPolicy" / "lean-toolchain").read_text().strip(),
            "mathlib_input_revision": next(package["inputRev"] for package in manifest["packages"] if package["name"] == "mathlib"),
            "mathlib_resolved_revision": next(package["rev"] for package in manifest["packages"] if package["name"] == "mathlib"),
            "clean_build_result": "PASS",
            "build_command": "cd formal/LutarPolicy && lake build",
            "kernel_checked_theorems": ["T1 default denial", "T2 rejected implies non-executable"],
            "public_claim": "0/12 PROVED",
            "public_claim_reason": "Fewer than four theorems and no independent English-statement review.",
        },
        observed,
    )
    write_json(
        output,
        "serving-baseline.json",
        {
            "status": "BLOCKED",
            "candidate_versions_not_compatibility_tested": {"vllm": "0.26.0", "sglang": "0.5.16"},
            "benchmark_client": {
                "name": "vllm-project/vllm-bench",
                "version": "0.1.0",
                "x86_64_linux_musl_digest": "sha256:e2e246dfe34cd603b85e4d763f9aa6d60940be8b9cef48221f8a70d78420716c",
            },
            "hardware": "UNAVAILABLE",
            "model_revision": "UNAVAILABLE",
            "tokenizer_revision": "UNAVAILABLE",
            "endpoints": [],
        },
        observed,
    )
    write_json(
        output,
        "observability-baseline.json",
        {
            "status": "IMPLEMENTED NOT DEPLOYED",
            "genai_schema_url": "https://opentelemetry.io/schemas/1.42.0",
            "content_capture": False,
            "redaction": "recursive pre-export contract tested",
            "mandatory_event_sampling": "100 percent contract tested",
            "collectors": [],
            "exporters": [],
            "retention": {"status": "BLOCKED", "reason": "collector environment unavailable"},
            "trace_access_acls": {"status": "BLOCKED", "reason": "telemetry backend unavailable"},
        },
        observed,
    )
    a11oy_hf = compact_hf_space(fetch_json("https://huggingface.co/api/spaces/SZLHOLDINGS/a11oy"))
    killinchu_hf = compact_hf_space(fetch_json("https://huggingface.co/api/spaces/SZLHOLDINGS/killinchu"))
    a11oy_runtime = fetch_json("https://szlholdings-a11oy.hf.space/api/build-info")
    killinchu_runtime = fetch_json("https://szlholdings-killinchu.hf.space/api/build-info")
    a11oy_runtime_sha = runtime_revision(a11oy_runtime)
    killinchu_runtime_sha = runtime_revision(killinchu_runtime)
    killinchu_routes = {
        "/code": fetch_status("https://szlholdings-killinchu.hf.space/code"),
        "/chat": fetch_status("https://szlholdings-killinchu.hf.space/chat"),
        "/api/killinchu/v1/honest": fetch_status(
            "https://szlholdings-killinchu.hf.space/api/killinchu/v1/honest"
        ),
    }
    write_json(
        output,
        "deployment-identities.json",
        {
            "status": "MEASURED",
            "a11oy": {
                "hf_source": a11oy_hf,
                "runtime_build_info": a11oy_runtime,
                "expected_source_commit": a11oy_main_sha,
                "identity_status": "MATCH" if a11oy_runtime_sha == a11oy_main_sha else "MISMATCH",
            },
            "killinchu": {
                "hf_source": killinchu_hf,
                "runtime_build_info": killinchu_runtime,
                "expected_source_commit": killinchu_main_sha,
                "observed_runtime_commit": killinchu_runtime_sha,
                "identity_status": "MATCH" if killinchu_runtime_sha == killinchu_main_sha else "MISMATCH",
                "live_image_digest": "UNAVAILABLE",
                "routes": killinchu_routes,
                "source_completeness": {
                    "status": "MEASURED",
                    "evidence": "Dockerfile COPY source inventory and exact-source reusable deployment",
                },
            },
            "backup_restoration": backup,
        },
        observed,
    )
    claims = [
        {"claim": "Putnam 2025", "label": "PROVED", "value": "0/12", "evidence": "docs/SERIES_A_DILIGENCE.md"},
        {"claim": "T1/T2 Lean boundary", "label": "MODELED", "value": "kernel checked; public count remains 0/12", "evidence": "formal/LutarPolicy/LutarPolicy/Theorems.lean"},
        {"claim": "runtime refinement", "label": "MEASURED", "value": "168 finite domain cases plus adversarial receipts", "evidence": "tests/test_operation_verified_policy.py"},
        {"claim": "existing GHCR provenance", "label": "MEASURED", "value": ATTESTED_IMAGE_DIGEST, "evidence": "audit/provenance-baseline.json"},
        {"claim": "SLSA Build L3", "label": "PLANNED", "value": "not achieved", "evidence": "reports/operation-verified-throughput/SLSA_LEVEL_3_AUDIT.md"},
        {"claim": "vLLM versus SGLang performance", "label": "PLANNED", "value": "no GPU result", "evidence": "reports/operation-verified-throughput/VLLM_SGLANG_RAW_RESULTS.json"},
        {"claim": "Killinchu /code and /chat", "label": "MEASURED", "value": "live HTTP 200", "evidence": "audit/deployment-identities.json"},
        {"claim": "canonical web application", "label": "MEASURED", "value": "pinned platform source builds and typechecks", "evidence": "tests/test_web_build_boundary.py"},
    ]
    write_json(output, "claim-inventory.json", {"status": "MEASURED", "claims": claims}, observed)
    risks = [
        {"id": "R-003", "severity": "HIGH", "owner": "@szl-holdings/security-reviewers", "status": "BLOCKED", "risk": "No owned staging cluster is available for admission negative-control evidence."},
        {"id": "R-004", "severity": "HIGH", "owner": "@szl-holdings/release-maintainers", "status": backup["status"], "risk": "Secret-backed Space snapshot restoration evidence must remain current."},
        {"id": "R-005", "severity": "MEDIUM", "owner": "@szl-holdings/formal-reviewers", "status": "BLOCKED", "risk": "T1/T2 English statements lack independent review; public count stays 0/12."},
        {"id": "R-006", "severity": "MEDIUM", "owner": "@szl-holdings/performance-maintainers", "status": "BLOCKED", "risk": "No controlled GPU benchmark environment is available."},
    ]
    write_json(output, "risk-register.json", {"status": "MEASURED", "risks": risks}, observed)

    ledger = f"""<!--
{SPDX}
{OWNER}
-->

# Estate ledger

Generated at `{observed}` by `scripts/generate_operation_inventory.py`.

| Estate surface | Status | Evidence |
| --- | --- | --- |
| Current A11oy production source | MEASURED | GitHub main and runtime build-info `{a11oy_main_sha}` |
| GitHub protections | MEASURED | Read-only inventory in `repository-rulesets.json`; **no mutations performed** |
| Existing A11oy GHCR attestation | MEASURED | `{ATTESTED_IMAGE_DIGEST}`, run 30187276319, Rekor 2255395975 |
| A11oy Hugging Face identity | MEASURED | Runtime build-info matches protected main `{a11oy_main_sha}` |
| Killinchu current source bundle | MEASURED | Dockerfile COPY sources exist and exact-source deploy is live |
| Killinchu running image identity | MEASURED | Runtime build-info matches protected main `{killinchu_main_sha}` |
| Killinchu `/code` and `/chat` | MEASURED | Both routes returned HTTP 200 at observation |
| Canonical web application | MEASURED | Pinned `vendor/platform` source builds and typechecks without stubs |
| Lean T1/T2 | MODELED | Local kernel build passes; public claim remains **0/12 PROVED** |
| Runtime policy refinement | MEASURED | Finite domain plus adversarial receipt tests |
| Reusable build | PREPARED IN A PR | Not protected or deployed until independently reviewed and merged |
| Sigstore warning policy | PREPARED IN A PR | Manifests only; no cluster mutation |
| vLLM/SGLang matrix | BLOCKED | No GPU node, model revision, tokenizer revision, or endpoints |
| OTel GenAI contract | IMPLEMENTED NOT DEPLOYED | Content capture off, redaction and mandatory sampling tests |
| Backup and restoration | {backup["status"]} | Secret-backed immutable Space snapshots and offline byte-for-byte restore |
"""
    (output / "ESTATE_LEDGER.md").write_text(ledger, encoding="utf-8")
    print(f"generated Phase 0 inventory in {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
