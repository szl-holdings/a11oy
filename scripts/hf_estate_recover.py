#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Recover the SZLHOLDINGS Hugging Face Space estate without reviving folds.

The operator is deliberately bounded:

* inventories every Space visible to the managed organization token;
* derives intentional FOLD/RETIRED assets from source-controlled policy;
* restarts sleeping, stopped, or paused non-folded Spaces;
* factory-reboots non-folded build/runtime/config failures;
* observes BUILDING states before declaring them stalled;
* dispatches only an explicit allowlist of existing HF recovery workflows;
* preserves a complete secret-free JSON and Markdown receipt;
* never changes hardware, visibility, secrets, files, or billing settings.

Exit codes: 0 = terminal green, 1 = residual Space failures, 2 = configuration
or inventory failure.  The token value is never printed or persisted.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Iterable
import urllib.error
import urllib.parse
import urllib.request

HF_ENDPOINT = "https://huggingface.co"
GH_ENDPOINT = "https://api.github.com"
DEFAULT_ORG = "SZLHOLDINGS"

HEALTHY_STAGES = {"RUNNING"}
RECOVERING_STAGES = {"BUILDING", "RUNNING_BUILDING", "CREATING", "STARTING"}
STANDARD_RESTART_STAGES = {"PAUSED", "SLEEPING", "STOPPED"}
FACTORY_REBOOT_STAGES = {"BUILD_ERROR", "RUNTIME_ERROR", "CONFIG_ERROR"}
TERMINAL_SOURCE_STAGES = {"NO_APP_FILE", "SPACE_NOT_FOUND", "DELETING", "DISABLED"}

RECOVERY_WORKFLOW_PATTERNS = (
    "hf-estate-ops",
    "hf-redeploy-kick",
    "hf-restart",
    "hf-unpause",
    "hf-runtime-recovery",
    "hf-space-recovery",
    "hf-space-redeploy",
    "hf-stage-matrix-refresh",
    "hf-ecosystem-manifest-refresh",
)


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stage_name(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("stage") or value.get("status")
    return str(value or "UNKNOWN").strip().upper().replace("-", "_").replace(" ", "_")


def slug_from_value(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip().strip("`[](){}<>.,:;")
    if not value:
        return None
    if "/" in value:
        value = value.rsplit("/", 1)[-1]
    value = value.strip().lower()
    return value if re.fullmatch(r"[a-z0-9][a-z0-9._-]*", value) else None


def _walk_fold_records(node: Any, out: set[str]) -> None:
    if isinstance(node, dict):
        policy = " ".join(
            str(node.get(key, ""))
            for key in ("action", "decision", "status", "lifecycle", "disposition", "mode")
        ).upper()
        if any(token in policy for token in ("FOLD", "RETIRED", "ARCHIVE", "DECOMMISSION")):
            for key in ("slug", "space", "space_id", "repo_id", "id", "name", "hf_space"):
                slug = slug_from_value(node.get(key))
                if slug:
                    out.add(slug)
        for value in node.values():
            _walk_fold_records(value, out)
    elif isinstance(node, list):
        for value in node:
            _walk_fold_records(value, out)


def discover_intentional_folds(repo_root: Path) -> tuple[set[str], list[str]]:
    folds = {"anatomy"}
    evidence = ["explicit safety floor: anatomy"]

    explicit = os.getenv("HF_INTENTIONAL_FOLDS", "")
    for raw in explicit.split(","):
        slug = slug_from_value(raw)
        if slug:
            folds.add(slug)
            evidence.append(f"HF_INTENTIONAL_FOLDS:{slug}")

    source_map = repo_root / "docs" / "huggingface-space-source-map-v1.json"
    if source_map.is_file():
        try:
            parsed = json.loads(source_map.read_text(encoding="utf-8"))
            before = set(folds)
            _walk_fold_records(parsed, folds)
            for slug in sorted(folds - before):
                evidence.append(f"{source_map.as_posix()}:{slug}")
        except (OSError, json.JSONDecodeError) as exc:
            evidence.append(f"policy-parse-warning:{source_map.as_posix()}:{type(exc).__name__}")

    python_policy = repo_root / "szl_spaces_surface.py"
    if python_policy.is_file():
        text = python_policy.read_text(encoding="utf-8", errors="replace")
        patterns = (
            r"\{[^{}]{0,1600}?[\"']slug[\"']\s*:\s*[\"']([^\"']+)[\"'][^{}]{0,1600}?[\"']action[\"']\s*:\s*[\"'](?:FOLD|RETIRED|ARCHIVE)[\"'][^{}]*\}",
            r"\{[^{}]{0,1600}?[\"']action[\"']\s*:\s*[\"'](?:FOLD|RETIRED|ARCHIVE)[\"'][^{}]{0,1600}?[\"']slug[\"']\s*:\s*[\"']([^\"']+)[\"'][^{}]*\}",
        )
        for pattern in patterns:
            for raw in re.findall(pattern, text, flags=re.IGNORECASE | re.DOTALL):
                slug = slug_from_value(raw)
                if slug and slug not in folds:
                    folds.add(slug)
                    evidence.append(f"{python_policy.as_posix()}:{slug}")

    consolidation = repo_root / "docs" / "series-a" / "HF_SPACE_CONSOLIDATION.md"
    if consolidation.is_file():
        for line in consolidation.read_text(encoding="utf-8", errors="replace").splitlines():
            if not re.search(r"\b(FOLD|RETIRED|ARCHIVE|DECOMMISSION)\b", line, re.IGNORECASE):
                continue
            for raw in re.findall(r"SZLHOLDINGS/([A-Za-z0-9._-]+)", line, re.IGNORECASE):
                slug = slug_from_value(raw)
                if slug and slug not in folds:
                    folds.add(slug)
                    evidence.append(f"{consolidation.as_posix()}:{slug}")

    return folds, evidence


class JsonHttp:
    def __init__(self, token: str | None, *, user_agent: str) -> None:
        self.token = token
        self.user_agent = user_agent

    def request(
        self,
        method: str,
        url: str,
        *,
        payload: dict[str, Any] | None = None,
        timeout: int = 45,
        accept: str = "application/json",
    ) -> tuple[int, Any]:
        headers = {"User-Agent": self.user_agent, "Accept": accept}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        body = None
        if payload is not None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read(2 * 1024 * 1024)
                status = int(response.status)
        except urllib.error.HTTPError as exc:
            raw = exc.read(64 * 1024)
            status = int(exc.code)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise RuntimeError(f"transport error: {type(exc).__name__}: {exc}") from exc
        if not raw:
            return status, None
        try:
            return status, json.loads(raw.decode("utf-8", "replace"))
        except json.JSONDecodeError:
            return status, {"text": raw.decode("utf-8", "replace")[:2000]}


class HfEstate:
    def __init__(self, token: str, org: str) -> None:
        self.org = org
        self.http = JsonHttp(token, user_agent="szl-hf-estate-recovery/1.0")

    def list_spaces(self) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode({"author": self.org, "limit": 100, "full": "true"})
        status, payload = self.http.request("GET", f"{HF_ENDPOINT}/api/spaces?{query}")
        if status != 200:
            raise RuntimeError(f"HF Space inventory failed with HTTP {status}")
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict):
            for key in ("items", "spaces", "results"):
                rows = payload.get(key)
                if isinstance(rows, list):
                    return [row for row in rows if isinstance(row, dict)]
        raise RuntimeError("HF Space inventory returned an unexpected payload")

    def runtime(self, repo_id: str) -> dict[str, Any]:
        encoded = urllib.parse.quote(repo_id, safe="/")
        status, payload = self.http.request("GET", f"{HF_ENDPOINT}/api/spaces/{encoded}/runtime")
        if status != 200 or not isinstance(payload, dict):
            return {"stage": "UNKNOWN", "http_status": status}
        return payload

    def restart(self, repo_id: str, *, factory_reboot: bool) -> tuple[bool, int, str]:
        encoded = urllib.parse.quote(repo_id, safe="/")
        status, payload = self.http.request(
            "POST",
            f"{HF_ENDPOINT}/api/spaces/{encoded}/restart",
            payload={"factoryReboot": bool(factory_reboot)},
            timeout=60,
        )
        detail = ""
        if isinstance(payload, dict):
            detail = str(payload.get("error") or payload.get("message") or payload.get("stage") or "")
        return 200 <= status < 300, status, detail[:500]

    def warm(self, item: dict[str, Any]) -> tuple[int | None, str]:
        host = item.get("host") or item.get("runtime", {}).get("host") if isinstance(item.get("runtime"), dict) else item.get("host")
        if not host:
            repo_id = str(item.get("id") or "")
            if "/" not in repo_id:
                return None, "host unavailable"
            owner, slug = repo_id.split("/", 1)
            host = f"{owner.lower()}-{slug.lower().replace('_', '-')}.hf.space"
        url = str(host)
        if not url.startswith("http"):
            url = "https://" + url
        request = urllib.request.Request(
            url.rstrip("/") + "/",
            headers={"User-Agent": "szl-hf-estate-recovery-warm/1.0", "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                response.read(4096)
                return int(response.status), ""
        except urllib.error.HTTPError as exc:
            return int(exc.code), "HTTP response"
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            return None, type(exc).__name__


def token_from_environment() -> tuple[str | None, str | None]:
    for key in (
        "HF_ORG_TOKEN",
        "HF_WRITE_TOKEN",
        "HF_TOKEN",
        "HUGGINGFACE_TOKEN",
        "HUGGING_FACE_HUB_TOKEN",
        "HF_READ_TOKEN",
    ):
        value = os.getenv(key)
        if value and value.strip():
            return value.strip(), key
    return None, None


def item_id(item: dict[str, Any]) -> str:
    return str(item.get("id") or item.get("repo_id") or item.get("name") or "").strip()


def item_stage(item: dict[str, Any], runtime: dict[str, Any] | None = None) -> str:
    if runtime:
        return stage_name(runtime)
    return stage_name(item.get("runtime") or item.get("stage"))


def dispatch_recovery_workflows(github_token: str | None) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    repository = os.getenv("GITHUB_REPOSITORY", "szl-holdings/a11oy")
    if not github_token or "/" not in repository:
        return actions
    api = JsonHttp(github_token, user_agent="szl-hf-estate-recovery-github/1.0")
    status, repo = api.request("GET", f"{GH_ENDPOINT}/repos/{repository}")
    if status != 200 or not isinstance(repo, dict):
        return [{"workflow": None, "result": "inventory_failed", "http_status": status}]
    default_branch = str(repo.get("default_branch") or "main")
    status, payload = api.request(
        "GET", f"{GH_ENDPOINT}/repos/{repository}/actions/workflows?per_page=100"
    )
    if status != 200 or not isinstance(payload, dict):
        return [{"workflow": None, "result": "inventory_failed", "http_status": status}]
    workflows = payload.get("workflows") or []
    for workflow in workflows:
        if not isinstance(workflow, dict):
            continue
        path = str(workflow.get("path") or "").lower()
        if path.endswith("hf-estate-recovery.yml"):
            continue
        if not any(pattern in path for pattern in RECOVERY_WORKFLOW_PATTERNS):
            continue
        wid = workflow.get("id")
        status, response = api.request(
            "POST",
            f"{GH_ENDPOINT}/repos/{repository}/actions/workflows/{wid}/dispatches",
            payload={"ref": default_branch},
        )
        actions.append(
            {
                "workflow": workflow.get("name"),
                "path": workflow.get("path"),
                "http_status": status,
                "result": "dispatched" if 200 <= status < 300 else "not_dispatched",
                "detail": (
                    str(response.get("message") or response.get("error") or "")[:300]
                    if isinstance(response, dict)
                    else ""
                ),
            }
        )
    return actions


def classify_action(stage: str) -> tuple[str, bool | None]:
    if stage in HEALTHY_STAGES:
        return "none", None
    if stage in STANDARD_RESTART_STAGES:
        return "restart", False
    if stage in FACTORY_REBOOT_STAGES:
        return "factory_reboot", True
    if stage in RECOVERING_STAGES:
        return "observe", None
    if stage in TERMINAL_SOURCE_STAGES:
        return "source_repair_required", None
    return "observe_unknown", None


def run_parallel_restarts(
    estate: HfEstate,
    candidates: Iterable[tuple[str, bool]],
) -> list[dict[str, Any]]:
    rows = list(candidates)
    results: list[dict[str, Any]] = []

    def one(repo_id: str, factory: bool) -> dict[str, Any]:
        started = utcnow()
        try:
            ok, status, detail = estate.restart(repo_id, factory_reboot=factory)
            return {
                "space": repo_id,
                "action": "factory_reboot" if factory else "restart",
                "started_at": started,
                "ok": ok,
                "http_status": status,
                "detail": detail,
            }
        except Exception as exc:  # receipt must survive one broken Space
            return {
                "space": repo_id,
                "action": "factory_reboot" if factory else "restart",
                "started_at": started,
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}"[:700],
            }

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, max(1, len(rows)))) as pool:
        future_map = {pool.submit(one, repo_id, factory): repo_id for repo_id, factory in rows}
        for future in concurrent.futures.as_completed(future_map):
            results.append(future.result())
    return sorted(results, key=lambda row: str(row.get("space")))


def poll_runtimes(
    estate: HfEstate,
    repo_ids: list[str],
    *,
    timeout_seconds: int,
    interval_seconds: int,
) -> dict[str, dict[str, Any]]:
    deadline = time.monotonic() + max(0, timeout_seconds)
    latest: dict[str, dict[str, Any]] = {}
    while True:
        for repo_id in repo_ids:
            latest[repo_id] = estate.runtime(repo_id)
        pending = [
            repo_id
            for repo_id, runtime in latest.items()
            if stage_name(runtime) in RECOVERING_STAGES
        ]
        if not pending or time.monotonic() >= deadline:
            return latest
        time.sleep(max(5, interval_seconds))


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# SZLHOLDINGS Hugging Face Estate Recovery Receipt",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Organization: `{report['org']}`",
        f"- Managed credential present: **{report['credential']['present']}**",
        f"- Credential source: `{report['credential'].get('source') or 'none'}`",
        f"- Spaces inventoried: **{len(report.get('spaces', []))}**",
        f"- Intentional folds preserved: **{len(report.get('intentional_folds_seen', []))}**",
        f"- Restart/reboot calls: **{len(report.get('actions', []))}**",
        f"- Residual non-folded failures: **{len(report.get('residual', []))}**",
        f"- Terminal green: **{report.get('terminal_green', False)}**",
        "",
        "## Space state",
        "",
        "| Space | Initial | Final | Policy | Action |",
        "|---|---:|---:|---|---|",
    ]
    action_by_space: dict[str, list[str]] = {}
    for action in report.get("actions", []):
        action_by_space.setdefault(str(action.get("space")), []).append(
            f"{action.get('action')}:{'ok' if action.get('ok') else 'failed'}"
        )
    for row in report.get("spaces", []):
        rid = str(row.get("space"))
        actions = ", ".join(action_by_space.get(rid, [])) or "none"
        lines.append(
            f"| `{rid}` | `{row.get('initial_stage')}` | `{row.get('final_stage')}` | "
            f"{row.get('policy')} | {actions} |"
        )
    lines += ["", "## Recovery-workflow dispatches", ""]
    if report.get("github_workflows"):
        for row in report["github_workflows"]:
            lines.append(
                f"- `{row.get('path') or row.get('workflow')}` — {row.get('result')} "
                f"(HTTP {row.get('http_status', 'n/a')})"
            )
    else:
        lines.append("- No allowlisted recovery workflow was dispatchable from this run.")
    lines += ["", "## Residual blockers", ""]
    if report.get("residual"):
        for row in report["residual"]:
            lines.append(
                f"- `{row.get('space')}` — `{row.get('stage')}`: {row.get('reason')}"
            )
    else:
        lines.append("- None. Every non-folded Space reached `RUNNING`.")
    lines += [
        "",
        "## Guardrails retained",
        "",
        "- No Space hardware, billing tier, visibility, files, variables, or secrets were changed.",
        "- Source-declared folds were not restarted.",
        "- Build/runtime/config errors used factory reboot; sleep/stop/pause used a normal restart.",
        "- `NO_APP_FILE`, disabled, deleting, and unknown states remain explicit source-level blockers.",
    ]
    return "\n".join(lines) + "\n"


def self_test() -> None:
    assert stage_name({"stage": "runtime-error"}) == "RUNTIME_ERROR"
    assert slug_from_value("SZLHOLDINGS/anatomy") == "anatomy"
    assert slug_from_value("bad space") is None
    assert classify_action("RUNNING") == ("none", None)
    assert classify_action("PAUSED") == ("restart", False)
    assert classify_action("BUILD_ERROR") == ("factory_reboot", True)
    assert classify_action("NO_APP_FILE") == ("source_repair_required", None)
    out: set[str] = set()
    _walk_fold_records({"slug": "legacy", "action": "FOLD"}, out)
    assert out == {"legacy"}
    print("hf_estate_recover self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org", default=DEFAULT_ORG)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--json-out", default="hf-recovery-report.json")
    parser.add_argument("--markdown-out", default="hf-recovery-report.md")
    parser.add_argument("--observe-seconds", type=int, default=int(os.getenv("HF_BUILD_OBSERVE_SECONDS", "360")))
    parser.add_argument("--settle-seconds", type=int, default=int(os.getenv("HF_RECOVERY_SETTLE_SECONDS", "900")))
    parser.add_argument("--poll-seconds", type=int, default=int(os.getenv("HF_RECOVERY_POLL_SECONDS", "45")))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    repo_root = Path(args.repo_root).resolve()
    token, token_source = token_from_environment()
    report: dict[str, Any] = {
        "schema": "SZL.HF.EstateRecovery.v1",
        "generated_at": utcnow(),
        "org": args.org,
        "credential": {"present": bool(token), "source": token_source},
        "policy_evidence": [],
        "intentional_folds": [],
        "intentional_folds_seen": [],
        "github_workflows": [],
        "actions": [],
        "spaces": [],
        "residual": [],
        "errors": [],
        "terminal_green": False,
    }

    json_out = Path(args.json_out)
    md_out = Path(args.markdown_out)

    def persist() -> None:
        json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        md_out.write_text(render_markdown(report), encoding="utf-8")

    if not token:
        report["errors"].append("No managed Hugging Face credential is available to the workflow.")
        persist()
        return 2

    folds, policy_evidence = discover_intentional_folds(repo_root)
    report["intentional_folds"] = sorted(folds)
    report["policy_evidence"] = policy_evidence
    report["github_workflows"] = dispatch_recovery_workflows(os.getenv("GITHUB_TOKEN"))

    estate = HfEstate(token, args.org)
    try:
        inventory = estate.list_spaces()
    except Exception as exc:
        report["errors"].append(f"{type(exc).__name__}: {exc}")
        persist()
        return 2

    by_id = {item_id(item): item for item in inventory if item_id(item)}
    runtime_initial: dict[str, dict[str, Any]] = {}
    immediate: list[tuple[str, bool]] = []
    observed_builds: list[str] = []

    for repo_id, item in sorted(by_id.items()):
        runtime = item.get("runtime") if isinstance(item.get("runtime"), dict) else None
        if not runtime or not runtime.get("stage"):
            runtime = estate.runtime(repo_id)
        runtime_initial[repo_id] = runtime
        stage = item_stage(item, runtime)
        slug = slug_from_value(repo_id) or repo_id.lower()
        folded = slug in folds
        disabled = bool(item.get("disabled"))
        if folded:
            report["intentional_folds_seen"].append(repo_id)
            continue
        if disabled:
            continue
        action, factory = classify_action(stage)
        if factory is not None:
            immediate.append((repo_id, factory))
        elif action == "observe" and stage in {"BUILDING", "RUNNING_BUILDING", "CREATING", "STARTING"}:
            observed_builds.append(repo_id)

    report["actions"].extend(run_parallel_restarts(estate, immediate))

    if observed_builds and args.observe_seconds > 0:
        time.sleep(args.observe_seconds)
        stuck: list[tuple[str, bool]] = []
        for repo_id in observed_builds:
            current = estate.runtime(repo_id)
            if stage_name(current) in RECOVERING_STAGES:
                stuck.append((repo_id, True))
        report["actions"].extend(run_parallel_restarts(estate, stuck))

    acted_ids = sorted({str(row.get("space")) for row in report["actions"] if row.get("space")})
    for repo_id in acted_ids:
        item = by_id.get(repo_id, {})
        warm_status, warm_error = estate.warm(item)
        report["actions"].append(
            {
                "space": repo_id,
                "action": "warm",
                "ok": warm_status is not None and 200 <= warm_status < 500,
                "http_status": warm_status,
                "detail": warm_error,
                "started_at": utcnow(),
            }
        )

    final_runtimes = poll_runtimes(
        estate,
        sorted(by_id),
        timeout_seconds=args.settle_seconds,
        interval_seconds=args.poll_seconds,
    )

    spaces: list[dict[str, Any]] = []
    residual: list[dict[str, Any]] = []
    for repo_id, item in sorted(by_id.items()):
        slug = slug_from_value(repo_id) or repo_id.lower()
        folded = slug in folds
        disabled = bool(item.get("disabled"))
        initial = stage_name(runtime_initial.get(repo_id, {}))
        final = stage_name(final_runtimes.get(repo_id, {}))
        if folded:
            policy = "intentional_fold_preserved"
        elif disabled:
            policy = "disabled_requires_owner_or_provider_review"
        elif final in HEALTHY_STAGES:
            policy = "running"
        elif final in RECOVERING_STAGES:
            policy = "recovery_in_progress"
        else:
            policy = "residual_failure"
        row = {
            "space": repo_id,
            "slug": slug,
            "private": bool(item.get("private")),
            "disabled": disabled,
            "sdk": item.get("sdk"),
            "initial_stage": initial,
            "final_stage": final,
            "policy": policy,
        }
        spaces.append(row)
        if not folded and final not in HEALTHY_STAGES:
            if disabled:
                reason = "Space is disabled; recovery operator will not override provider/owner enforcement."
            elif final in RECOVERING_STAGES:
                reason = "Build/start is still in progress after the bounded settle window."
            elif final == "NO_APP_FILE":
                reason = "No runnable app file; canonical source repair is required, not another reboot."
            elif final in FACTORY_REBOOT_STAGES:
                reason = "Factory reboot completed but the source still fails to build or run."
            elif final == "PAUSED":
                reason = "Managed restart did not lift the pause; account-level owner action may be required."
            else:
                reason = "Space did not reach RUNNING after bounded restart/reboot and verification."
            residual.append({"space": repo_id, "stage": final, "reason": reason})

    report["spaces"] = spaces
    report["residual"] = residual
    report["terminal_green"] = not residual and not report["errors"]
    report["completed_at"] = utcnow()
    persist()
    return 0 if report["terminal_green"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
