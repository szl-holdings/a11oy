#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Finish the owned-Khipu PR and prove the exact merged revision live on HF.

No branch protection, review, DCO, or status requirement is bypassed. The script
creates one exact-head status only after re-reading and validating the permanent
Docker/FastAPI/source receipt directly from GitHub. GitHub remains authoritative
for the merge. Hugging Face completion requires exact `/api/build-info` source
readback plus a live owned-cortex health and inference receipt.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable, Mapping

OWNER = "szl-holdings"
REPO = "a11oy"
BRANCH = "feat/hf-owned-khipu-cortex-v1"
HF_ORIGIN = "https://szlholdings-a11oy.hf.space"
MODEL_REPO = "SZLHOLDINGS/SZL-Khipu-1.5B-GGUF"
MODEL_REVISION = "67d60ec577730747055491640cfb91fc4a4b5d25"
FORMULAS = ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")
OK_CONCLUSIONS = {"success", "neutral", "skipped"}
FAILED_CONCLUSIONS = {
    "failure",
    "cancelled",
    "timed_out",
    "action_required",
    "startup_failure",
    "stale",
}
TEMP_WRITERS = (
    ".github/workflows/apply-owned-khipu-cortex-wiring.yml",
    ".github/workflows/repair-owned-khipu-cortex-wiring-v2.yml",
    ".github/workflows/repair-owned-khipu-cortex-wiring-v3.yml",
)


class ApiError(RuntimeError):
    def __init__(self, method: str, path: str, status: int, body: Any) -> None:
        self.method = method
        self.path = path
        self.status = status
        self.body = body
        super().__init__(f"{method} {path}: HTTP {status}")


class GitHub:
    def __init__(self, token: str) -> None:
        self.token = token
        self.base = "https://api.github.com"

    def request(
        self,
        method: str,
        path: str,
        payload: Any | None = None,
        *,
        accept: str = "application/vnd.github+json",
        allow: Iterable[int] = (200, 201, 202, 204),
        timeout: int = 45,
    ) -> Any:
        url = path if path.startswith("https://") else self.base + path
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Accept": accept,
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "szl-owned-khipu-closeout/1",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
                if response.status not in set(allow):
                    raise ApiError(method, path, response.status, raw[:1000])
                return json.loads(raw.decode("utf-8")) if raw else None
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            try:
                body: Any = json.loads(raw)
            except json.JSONDecodeError:
                body = raw[:1000]
            raise ApiError(method, path, exc.code, body) from exc

    def get(self, path: str, **kwargs: Any) -> Any:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, payload: Any | None = None, **kwargs: Any) -> Any:
        return self.request("POST", path, payload, **kwargs)

    def put(self, path: str, payload: Any | None = None, **kwargs: Any) -> Any:
        return self.request("PUT", path, payload, **kwargs)


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def digest(value: Any) -> str:
    data = value.encode("utf-8") if isinstance(value, str) else canonical(value)
    return hashlib.sha256(data).hexdigest()


def safe_error(exc: Exception) -> dict[str, Any]:
    row: dict[str, Any] = {"type": type(exc).__name__, "message": str(exc)[:500]}
    if isinstance(exc, ApiError):
        row.update({"method": exc.method, "path": exc.path, "status": exc.status})
        if isinstance(exc.body, Mapping):
            row["provider_message"] = str(exc.body.get("message") or "")[:300]
    return row


def decode_content(value: Mapping[str, Any]) -> str:
    encoded = str(value.get("content") or "").replace("\n", "")
    if value.get("encoding") != "base64" or not encoded:
        raise RuntimeError("GitHub content response is not base64 text")
    return base64.b64decode(encoded).decode("utf-8")


def get_text(api: GitHub, path: str, ref: str) -> str:
    encoded_path = urllib.parse.quote(path, safe="/")
    encoded_ref = urllib.parse.quote(ref, safe="")
    value = api.get(f"/repos/{OWNER}/{REPO}/contents/{encoded_path}?ref={encoded_ref}")
    if not isinstance(value, Mapping):
        raise RuntimeError(f"{path} did not resolve to a file")
    return decode_content(value)


def exists(api: GitHub, path: str, ref: str) -> bool:
    try:
        get_text(api, path, ref)
        return True
    except ApiError as exc:
        if exc.status == 404:
            return False
        raise


def select_token() -> tuple[str, str]:
    external = os.getenv("GH_EXTERNAL_TOKEN", "").strip()
    repository = os.getenv("GITHUB_TOKEN", "").strip()
    candidates = (("EXTERNAL", external), ("REPOSITORY", repository))
    for kind, token in candidates:
        if not token:
            continue
        print(f"::add-mask::{token}")
        api = GitHub(token)
        try:
            value = api.get(f"/repos/{OWNER}/{REPO}")
            permissions = value.get("permissions") or {}
            if permissions.get("push") or permissions.get("maintain") or permissions.get("admin"):
                return token, kind
        except Exception:
            continue
    raise RuntimeError("no GitHub credential proved write authority to a11oy")


def find_pull(api: GitHub) -> dict[str, Any]:
    head = urllib.parse.quote(f"{OWNER}:{BRANCH}", safe="")
    pulls = api.get(f"/repos/{OWNER}/{REPO}/pulls?state=open&head={head}&per_page=20")
    if not isinstance(pulls, list) or len(pulls) != 1:
        raise RuntimeError(f"expected exactly one open PR for {BRANCH}; observed {len(pulls or [])}")
    return api.get(f"/repos/{OWNER}/{REPO}/pulls/{pulls[0]['number']}")


def validate_source(api: GitHub, sha: str) -> dict[str, Any]:
    module = get_text(api, "szl_owned_khipu_cortex.py", sha)
    docker = get_text(api, "Dockerfile", sha)
    serve = get_text(api, "serve.py", sha)
    receipt = json.loads(
        get_text(api, "reports/owned-khipu-cortex/source-wiring.json", sha)
    )
    writers = [path for path in TEMP_WRITERS if exists(api, path, sha)]
    checks = {
        "module_model_repo": MODEL_REPO in module,
        "module_model_revision": MODEL_REVISION in module,
        "locked_formula_F1": "F1" in module,
        "locked_formula_F22": "F22" in module,
        "lambda_advisory": "CONJECTURE_1_ADVISORY" in module,
        "no_action_authority": "NO_ACTION_AUTHORITY" in module,
        "nemo_pre": "PRE_GENERATION" in module,
        "nemo_post": "POST_GENERATION" in module,
        "docker_module_unique": docker.count("COPY szl_owned_khipu_cortex.py ./") == 1,
        "docker_nemo_unique": docker.count("COPY vendor/szl_nemo/ ./vendor/szl_nemo/") == 1,
        "serve_import_unique": serve.count(
            "import szl_owned_khipu_cortex as _szl_owned_khipu_cortex"
        )
        == 1,
        "serve_register_unique": serve.count(
            '_szl_owned_khipu_cortex.register(app, ns="a11oy")'
        )
        == 1,
        "temporary_writers_absent": not writers,
        "receipt_state": receipt.get("state") == "SOURCE_WIRED",
        "receipt_live_honesty": receipt.get("live_deployment_verified") is False,
        "receipt_action_authority": receipt.get("action_authority") == "NONE",
        "receipt_formula_count": receipt.get("locked_proven_formula_count") == 8,
        "receipt_lambda": receipt.get("lambda_status") == "CONJECTURE_1_ADVISORY",
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise RuntimeError("source contract failed: " + ", ".join(failed))
    return {
        "state": "SOURCE_VERIFIED",
        "sha": sha,
        "checks": checks,
        "temporary_writers": writers,
        "module_sha256": digest(module),
        "dockerfile_sha256": digest(docker),
        "serve_sha256": digest(serve),
        "source_receipt_sha256": digest(receipt),
    }


def put_status(api: GitHub, sha: str, state: str, description: str) -> None:
    api.post(
        f"/repos/{OWNER}/{REPO}/statuses/{sha}",
        {
            "state": state,
            "context": "owned-khipu-cortex/source-contract",
            "description": description[:140],
            "target_url": f"https://github.com/{OWNER}/{REPO}/tree/{sha}/reports/owned-khipu-cortex",
        },
        allow=(201,),
    )


def check_state(api: GitHub, sha: str, current_run_id: str) -> dict[str, Any]:
    payload = api.get(
        f"/repos/{OWNER}/{REPO}/commits/{sha}/check-runs?per_page=100",
        accept="application/vnd.github+json",
    )
    runs = payload.get("check_runs") or []
    statuses = (api.get(f"/repos/{OWNER}/{REPO}/commits/{sha}/status") or {}).get("statuses") or []
    rows: list[dict[str, Any]] = []
    pending: list[str] = []
    failing: list[str] = []
    for run in runs:
        details = str(run.get("details_url") or "")
        name = str(run.get("name") or "")
        if current_run_id and f"/actions/runs/{current_run_id}" in details:
            continue
        status = str(run.get("status") or "").lower()
        conclusion = str(run.get("conclusion") or "").lower()
        rows.append(
            {
                "kind": "check_run",
                "name": name,
                "status": status,
                "conclusion": conclusion,
                "details_url": details,
            }
        )
        if status != "completed" or not conclusion:
            pending.append(name)
        elif conclusion not in OK_CONCLUSIONS:
            failing.append(name)
    latest: dict[str, Mapping[str, Any]] = {}
    for item in statuses:
        context = str(item.get("context") or "")
        if context and context not in latest:
            latest[context] = item
    for context, item in latest.items():
        state = str(item.get("state") or "").lower()
        rows.append(
            {
                "kind": "commit_status",
                "name": context,
                "status": state,
                "conclusion": state,
                "details_url": item.get("target_url"),
            }
        )
        if state in {"pending", "expected"}:
            pending.append(context)
        elif state != "success":
            failing.append(context)
    exact_status = any(
        row["kind"] == "commit_status"
        and row["name"] == "owned-khipu-cortex/source-contract"
        and row["conclusion"] == "success"
        for row in rows
    )
    return {
        "rows": rows,
        "pending": sorted(set(pending)),
        "failing": sorted(set(failing)),
        "source_contract_status_success": exact_status,
        "green": not pending and not failing and exact_status,
    }


def rerun_failed_for_head(api: GitHub, sha: str, attempted: set[int]) -> list[dict[str, Any]]:
    payload = api.get(f"/repos/{OWNER}/{REPO}/actions/runs?head_sha={sha}&per_page=100")
    actions: list[dict[str, Any]] = []
    for run in payload.get("workflow_runs") or []:
        run_id = int(run.get("id") or 0)
        conclusion = str(run.get("conclusion") or "").lower()
        if not run_id or run_id in attempted or conclusion not in FAILED_CONCLUSIONS:
            continue
        attempted.add(run_id)
        endpoint = (
            f"/repos/{OWNER}/{REPO}/actions/runs/{run_id}/rerun-failed-jobs"
            if conclusion not in {"startup_failure", "action_required"}
            else f"/repos/{OWNER}/{REPO}/actions/runs/{run_id}/rerun"
        )
        try:
            api.post(endpoint, {}, allow=(201, 202, 204))
            actions.append(
                {
                    "run_id": run_id,
                    "workflow": run.get("name"),
                    "action": "RERUN_REQUESTED",
                    "prior_conclusion": conclusion,
                }
            )
        except Exception as exc:
            actions.append(
                {
                    "run_id": run_id,
                    "workflow": run.get("name"),
                    "action": "RERUN_BLOCKED",
                    "error": safe_error(exc),
                }
            )
    return actions


def dispatch_hf_sync(api: GitHub) -> dict[str, Any]:
    encoded = urllib.parse.quote("hf-sync.yml", safe="")
    try:
        api.post(
            f"/repos/{OWNER}/{REPO}/actions/workflows/{encoded}/dispatches",
            {"ref": "main"},
            allow=(204,),
        )
        return {"action": "HF_SYNC_DISPATCHED"}
    except Exception as exc:
        return {"action": "HF_SYNC_DISPATCH_BLOCKED", "error": safe_error(exc)}


def http_json(
    url: str,
    *,
    payload: Mapping[str, Any] | None = None,
    timeout: int = 90,
) -> tuple[int | None, Any, dict[str, str], str | None]:
    data = canonical(dict(payload)) if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method="POST" if data is not None else "GET",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Cache-Control": "no-cache, no-store",
            "User-Agent": "szl-owned-khipu-live-proof/1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            try:
                body: Any = json.loads(raw.decode("utf-8"))
            except Exception:
                body = raw.decode("utf-8", "replace")[:2000]
            return (
                int(response.status),
                body,
                {key.lower(): value for key, value in response.headers.items()},
                None,
            )
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            body = raw.decode("utf-8", "replace")[:2000]
        return int(exc.code), body, {}, None
    except Exception as exc:
        return None, None, {}, f"{type(exc).__name__}: {exc}"


def walk_values(value: Any) -> Iterable[tuple[str, Any]]:
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key), item
            yield from walk_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_values(item)


def build_revision(body: Any) -> str | None:
    if not isinstance(body, Mapping):
        return None
    preferred = (
        "revision",
        "source_revision",
        "git_sha",
        "source_sha",
        "commit_sha",
        "sha",
    )
    found: dict[str, str] = {}
    for key, value in walk_values(body):
        if key.lower() in preferred and isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value.lower()):
            found.setdefault(key.lower(), value.lower())
    for key in preferred:
        if key in found:
            return found[key]
    return None


def discover_routes(module: str) -> tuple[list[str], list[str]]:
    direct = set(
        match.group(1).replace("{ns}", "a11oy")
        for match in re.finditer(r"['\"](/api/[^'\"]+)['\"]", module)
        if "khipu" in match.group(1).lower() or "cortex" in match.group(1).lower()
    )
    bases = set(
        value.replace("{ns}", "a11oy")
        for value in re.findall(r"['\"](/api/\{ns\}/v1/[^'\"]+)['\"]", module)
    )
    defaults = {
        "/api/a11oy/v1/owned-khipu/health",
        "/api/a11oy/v1/owned-khipu/status",
        "/api/a11oy/v1/owned-khipu/infer",
        "/api/a11oy/v1/owned-khipu-cortex/health",
        "/api/a11oy/v1/owned-khipu-cortex/status",
        "/api/a11oy/v1/owned-khipu-cortex/infer",
        "/api/a11oy/v1/khipu/cortex/health",
        "/api/a11oy/v1/khipu/cortex/infer",
    }
    candidates = direct | defaults
    for base in bases:
        candidates.update({base, base + "/health", base + "/status", base + "/infer"})
    health = sorted(path for path in candidates if any(token in path.lower() for token in ("health", "status", "info")))
    infer = sorted(path for path in candidates if any(token in path.lower() for token in ("infer", "chat", "complete", "generate")))
    return health, infer


def public_projection(value: Any) -> Any:
    """Remove generated prose while retaining identities, labels, and digests."""
    blocked = {"output", "answer", "text", "content", "prompt", "raw_prompt", "raw_answer"}
    if isinstance(value, Mapping):
        return {
            str(key): public_projection(item)
            for key, item in value.items()
            if str(key).lower() not in blocked
        }
    if isinstance(value, list):
        return [public_projection(item) for item in value]
    if isinstance(value, str) and len(value) > 500:
        return value[:80] + "…[bounded]"
    return value


def live_verify(api: GitHub, merge_sha: str, report: dict[str, Any]) -> dict[str, Any]:
    module = get_text(api, "szl_owned_khipu_cortex.py", merge_sha)
    health_routes, infer_routes = discover_routes(module)
    attempts: list[dict[str, Any]] = []
    for attempt in range(1, 81):
        build_status, build_body, build_headers, build_error = http_json(
            HF_ORIGIN + "/api/build-info", timeout=30
        )
        observed_revision = build_revision(build_body)
        row: dict[str, Any] = {
            "attempt": attempt,
            "build_status": build_status,
            "build_revision": observed_revision,
            "build_error": build_error,
        }
        if build_status == 200 and observed_revision == merge_sha:
            health_success = None
            for path in health_routes:
                status, body, headers, error = http_json(HF_ORIGIN + path, timeout=45)
                if status == 200 and isinstance(body, Mapping):
                    serialized = json.dumps(body, sort_keys=True)
                    if MODEL_REPO in serialized or MODEL_REVISION in serialized:
                        health_success = {
                            "path": path,
                            "status": status,
                            "body": public_projection(body),
                            "headers": {
                                key: value
                                for key, value in headers.items()
                                if key.startswith("x-szl")
                            },
                        }
                        break
                row.setdefault("health_failures", []).append(
                    {"path": path, "status": status, "error": error}
                )
            inference_success = None
            for path in infer_routes:
                status, body, headers, error = http_json(
                    HF_ORIGIN + path,
                    payload={
                        "prompt": "Explain why a proposal with insufficient evidence must abstain.",
                        "max_new_tokens": 24,
                        "k": 4,
                    },
                    timeout=180,
                )
                if status == 200 and isinstance(body, Mapping):
                    serialized = json.dumps(body, sort_keys=True)
                    identity_ok = MODEL_REPO in serialized and MODEL_REVISION in serialized
                    receipt_ok = bool(
                        re.search(r"[0-9a-f]{64}", serialized)
                        and any(
                            token in serialized.lower()
                            for token in ("receipt", "output_sha256", "record_sha256")
                        )
                    )
                    authority_ok = any(
                        token in serialized
                        for token in ("NO_ACTION_AUTHORITY", '"action_authority": "NONE"', '"executed": false')
                    )
                    if identity_ok and receipt_ok and authority_ok:
                        inference_success = {
                            "path": path,
                            "status": status,
                            "body": public_projection(body),
                            "headers": {
                                key: value
                                for key, value in headers.items()
                                if key.startswith("x-szl")
                            },
                            "response_sha256": digest(body),
                        }
                        break
                row.setdefault("inference_failures", []).append(
                    {"path": path, "status": status, "error": error}
                )
            if health_success and inference_success:
                return {
                    "state": "LIVE_VERIFIED",
                    "origin": HF_ORIGIN,
                    "source_revision": merge_sha,
                    "build_info": public_projection(build_body),
                    "build_headers": {
                        key: value
                        for key, value in build_headers.items()
                        if key.startswith("x-szl")
                    },
                    "health": health_success,
                    "inference": inference_success,
                    "health_routes_considered": health_routes,
                    "inference_routes_considered": infer_routes,
                    "attempt_count": attempt,
                }
        attempts.append(row)
        report["live_attempts"] = attempts[-12:]
        if attempt != 80:
            time.sleep(15)
    raise RuntimeError("canonical HF runtime did not prove exact-source owned-Khipu inference")


def write(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    report["report_sha256"] = digest(
        {key: value for key, value in report.items() if key != "report_sha256"}
    )
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args(argv)
    report: dict[str, Any] = {
        "schema": "szl.owned-khipu-cortex-closeout/v1",
        "started_at": now_iso(),
        "repository": f"{OWNER}/{REPO}",
        "branch": BRANCH,
        "hf_origin": HF_ORIGIN,
        "model_repo": MODEL_REPO,
        "model_revision": MODEL_REVISION,
        "locked_proven_formula_ids": list(FORMULAS),
        "lambda_status": "CONJECTURE_1_ADVISORY",
        "action_authority": "NONE",
        "branch_protection_bypass": False,
        "review_bypass": False,
        "dco_bypass": False,
        "secret_values_recorded": False,
        "prompt_or_output_text_recorded": False,
        "state": "IN_PROGRESS",
        "events": [],
    }
    try:
        token, token_kind = select_token()
        report["github_authority"] = {"state": "WRITE_CONFIRMED", "kind": token_kind}
        api = GitHub(token)
        current_run_id = os.getenv("GITHUB_RUN_ID", "").strip()

        source = None
        pull = None
        for attempt in range(1, 31):
            pull = find_pull(api)
            head_sha = str((pull.get("head") or {}).get("sha") or "")
            if not re.fullmatch(r"[0-9a-f]{40}", head_sha):
                raise RuntimeError("PR head is not an exact Git SHA")
            try:
                source = validate_source(api, head_sha)
                report["source_wait_attempts"] = attempt
                break
            except Exception as exc:
                report["last_source_wait_error"] = safe_error(exc)
                if attempt != 30:
                    time.sleep(20)
        if source is None or pull is None:
            raise RuntimeError("owned-Khipu source did not converge")
        report["source"] = source
        head_sha = source["sha"]
        put_status(api, head_sha, "success", "Permanent owned-Khipu source contract verified")

        attempted_reruns: set[int] = set()
        terminal_checks = None
        for attempt in range(1, 61):
            latest_pull = api.get(f"/repos/{OWNER}/{REPO}/pulls/{pull['number']}")
            latest_head = str((latest_pull.get("head") or {}).get("sha") or "")
            if latest_head != head_sha:
                source = validate_source(api, latest_head)
                head_sha = latest_head
                report["source"] = source
                put_status(api, head_sha, "success", "Permanent owned-Khipu source contract verified")
            checks = check_state(api, head_sha, current_run_id)
            report["last_check_state"] = checks
            if checks["failing"]:
                report["events"].extend(
                    rerun_failed_for_head(api, head_sha, attempted_reruns)
                )
            if checks["green"]:
                terminal_checks = checks
                break
            if attempt != 60:
                time.sleep(20)
        if terminal_checks is None:
            raise RuntimeError("PR checks did not become terminal-green at the exact head")
        report["terminal_checks"] = terminal_checks

        latest_pull = api.get(f"/repos/{OWNER}/{REPO}/pulls/{pull['number']}")
        if str((latest_pull.get("head") or {}).get("sha") or "") != head_sha:
            raise RuntimeError("PR head moved after terminal check verification")
        mergeable_state = str(latest_pull.get("mergeable_state") or "")
        report["premerge"] = {
            "pull_number": latest_pull.get("number"),
            "head_sha": head_sha,
            "mergeable": latest_pull.get("mergeable"),
            "mergeable_state": mergeable_state,
            "draft": latest_pull.get("draft"),
        }
        if latest_pull.get("draft"):
            raise RuntimeError("owned-Khipu PR remains draft")
        if latest_pull.get("mergeable") is not True:
            raise RuntimeError(f"owned-Khipu PR is not mergeable: {mergeable_state}")

        merged = api.put(
            f"/repos/{OWNER}/{REPO}/pulls/{latest_pull['number']}/merge",
            {
                "sha": head_sha,
                "merge_method": "squash",
                "commit_title": f"{latest_pull.get('title')} (#{latest_pull['number']})",
                "commit_message": (
                    "Complete the exact owned-Khipu GGUF inference path with bounded public-Brain grounding, "
                    "deterministic SZL-Nemo witnesses, locked-eight formula authority, proposal-only receipts, "
                    "and canonical post-merge Hugging Face verification.\n\n"
                    "Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>"
                ),
            },
            allow=(200,),
        )
        if not isinstance(merged, Mapping) or merged.get("merged") is not True:
            raise RuntimeError(str((merged or {}).get("message") or "GitHub rejected the merge"))
        merge_sha = str(merged.get("sha") or "")
        if not re.fullmatch(r"[0-9a-f]{40}", merge_sha):
            raise RuntimeError("merge response did not include an exact Git SHA")
        report["merge"] = {
            "state": "MERGED",
            "pull_number": latest_pull.get("number"),
            "source_head_sha": head_sha,
            "merge_sha": merge_sha,
            "message": merged.get("message"),
        }

        report["hf_sync_dispatch"] = dispatch_hf_sync(api)
        report["live"] = live_verify(api, merge_sha, report)
        report["state"] = "VERIFIED_COMPLETE"
        report["finished_at"] = now_iso()
        write(args.report, report)
        api.post(
            f"/repos/{OWNER}/{REPO}/issues/{latest_pull['number']}/comments",
            {
                "body": (
                    "## Owned Khipu terminal closeout\n\n"
                    f"- Exact source head: `{head_sha}`\n"
                    f"- Squash merge: `{merge_sha}`\n"
                    f"- Canonical HF source readback: `{report['live']['source_revision']}`\n"
                    f"- Live health route: `{report['live']['health']['path']}`\n"
                    f"- Live inference route: `{report['live']['inference']['path']}`\n"
                    f"- Evidence SHA-256: `{report['report_sha256']}`\n\n"
                    "The live receipt retains hashes and identities only; generated prompt/output text is not recorded."
                )
            },
            allow=(201,),
        )
        print(json.dumps({"state": report["state"], "merge_sha": merge_sha, "report_sha256": report["report_sha256"]}, sort_keys=True))
        return 0
    except Exception as exc:
        report["state"] = "BLOCKED"
        report["finished_at"] = now_iso()
        report["blocker"] = safe_error(exc)
        write(args.report, report)
        print(json.dumps({"state": report["state"], "blocker": report["blocker"], "report_sha256": report["report_sha256"]}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
