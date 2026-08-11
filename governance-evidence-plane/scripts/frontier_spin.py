#!/usr/bin/env python3
"""Frontier spin-up probe for szl-holdings estate.

This is a single, read-only executor that:
1. Probes live public signal for GitHub org, Hugging Face org, and product domains.
2. Captures hard evidence (status + payload snippets) without guessing.
3. Emits a Markdown report and JSON snapshot into the root `outputs/` folder.
"""

from __future__ import annotations

import json
import re
import ssl
import urllib.error
import urllib.request
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = WORKSPACE_ROOT / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SCRIPT_START = datetime.now(tz=timezone.utc)

TIMEOUT_SECONDS = 15
UA = "Mozilla/5.0 szl-frontier-spin/1.0"
GITHUB_ORG = "szl-holdings"
HF_ORG = "SZLHOLDINGS"
A11OY_DOMAIN = "https://a-11-oy.com"
A11OY_NET_DOMAIN = "https://a11oy.net"

REPO_PROBE_LIST = [
    "a11oy",
    "platform",
    "a11oy-net",
    "szl-substrate",
    "docs-site",
]


def _http_request(url: str, method: str = "GET") -> dict:
    req = urllib.request.Request(
        url,
        method=method,
        headers={"User-Agent": UA, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS, context=ssl.create_default_context()) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            headers = dict(resp.headers)
            status = getattr(resp, "status", None) or getattr(resp, "code", 0)
            return {
                "ok": True,
                "status": status,
                "body": raw,
                "headers": headers,
            }
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "status": exc.code,
            "error": str(exc),
            "body": exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else "",
            "headers": dict(getattr(exc, "headers", {}) or {}),
        }
    except Exception as exc:
        return {"ok": False, "status": 0, "error": str(exc), "body": "", "headers": {}}


def _safe_json(raw: str) -> tuple[bool, object | dict]:
    try:
        return True, json.loads(raw)
    except Exception as exc:
        return False, {"error": str(exc), "raw_prefix": raw[:200]}


def _probe_github_org() -> dict:
    org_url = f"https://api.github.com/orgs/{GITHUB_ORG}"
    org_resp = _http_request(org_url)
    org = {"url": org_url, "request": org_resp}

    if org_resp["ok"]:
        parsed_ok, payload = _safe_json(org_resp["body"])
        if parsed_ok and isinstance(payload, dict):
            org["payload"] = {k: payload.get(k) for k in ("login", "name", "public_repos", "followers", "created_at", "location", "blog")}
        else:
            org["payload"] = {"parse_error": payload}

    repos_url = f"https://api.github.com/orgs/{GITHUB_ORG}/repos?per_page=100&type=public"
    repos_resp = _http_request(repos_url)
    repos_payload = []
    if repos_resp["ok"]:
        parsed_ok, payload = _safe_json(repos_resp["body"])
        if parsed_ok and isinstance(payload, list):
            repos_payload = [r.get("name") for r in payload if isinstance(r, dict)]
    org["repos_sampled"] = repos_payload

    repo_status = []
    for repo in REPO_PROBE_LIST:
        branch_url = f"https://api.github.com/repos/{GITHUB_ORG}/{repo}/branches/main"
        branch_resp = _http_request(branch_url)
        protected = None
        if branch_resp["ok"]:
            parse_ok, branch_payload = _safe_json(branch_resp["body"])
            if parse_ok and isinstance(branch_payload, dict):
                protected = branch_payload.get("protected")
        elif branch_resp["status"] in (401, 403):
            protected = "unknown_auth_gate"
        repo_status.append({
            "repo": repo,
            "protected": protected,
            "status": branch_resp["status"],
            "status_error": branch_resp.get("error"),
        })

    org["branch_main_protection"] = repo_status
    return org


def _probe_hf() -> dict:
    assets = {}
    for resource in ("models", "datasets", "spaces"):
        api_url = f"https://huggingface.co/api/{resource}?author={HF_ORG}&limit=100"
        resp = _http_request(api_url)
        parsed_ok = False
        payload = {}
        count = None
        sample_ids: list[str] = []
        if resp["ok"]:
            parsed_ok, payload = _safe_json(resp["body"])
            if isinstance(payload, list):
                count = len(payload)
                sample_ids = [item.get("id") for item in payload[:3] if isinstance(item, dict) and item.get("id")]
            elif isinstance(payload, dict):
                results = payload.get("results", [])
                count = payload.get("count")
                if isinstance(results, list):
                    sample_ids = [item.get("id") for item in results[:3] if isinstance(item, dict) and item.get("id")]
                elif count is None:
                    count = len(results)
            else:
                payload = {}
                parsed_ok = False
            if not count and isinstance(payload, dict):
                count = payload.get("count")
                parsed_ok = True if payload else False
            else:
                parsed_ok = True
        assets[resource] = {
            "url": api_url,
            "status": resp["status"],
            "ok": resp["ok"],
            "parse_ok": parsed_ok,
            "payload": payload,
            "count": count,
            "sample_ids": sample_ids,
            "error": resp.get("error"),
        }
    return {
        "urls": assets,
        "org_page": f"https://huggingface.co/{HF_ORG}",
    }


def _probe_http_endpoints(base: str, endpoints: list[str]) -> list[dict]:
    out = []
    for path in endpoints:
        url = f"{base.rstrip('/')}{path}"
        resp = _http_request(url)
        entry = {"path": path, "url": url, "status": resp["status"], "ok": resp["ok"]}
        if resp["ok"]:
            parsed_ok, payload = _safe_json(resp["body"])
            if parsed_ok:
                if isinstance(payload, dict):
                    entry["json_keys"] = sorted(payload.keys())[:25]
                    entry["snippet"] = {k: payload[k] for k in payload if k in ("status", "lambda_status", "assurance", "count", "commit", "status_text", "message")}
                else:
                    entry["json_keys"] = []
                    entry["snippet"] = {}
            else:
                entry["snippet"] = payload
        else:
            entry["error"] = resp.get("error", "")
            if resp["body"]:
                parsed_ok, payload = _safe_json(resp["body"])
                if parsed_ok:
                    entry["json_keys"] = sorted(payload.keys()) if isinstance(payload, dict) else []
        out.append(entry)
    return out


def _probe_headers(base: str) -> dict:
    return _http_request(base, method="HEAD")


def _render_markdown(snapshot: dict) -> str:
    gh = snapshot["github"]
    hf = snapshot["huggingface"]
    a11oy = snapshot["a11oy_com"]
    front = snapshot["a11oy_net"]

    gh_payload = gh["org"].get("payload") if gh["org"]["ok"] else {"parse_error": "unreadable"}
    known_public = gh_payload.get("public_repos", "unknown")

    lines = []
    lines.append(f"# SZL frontier probe run at `{snapshot['run_at_utc']}`")
    lines.append("")
    lines.append("## Scope")
    lines.append(f"- GitHub org: `{GITHUB_ORG}`")
    lines.append(f"- Hugging Face org: `{HF_ORG}`")
    lines.append(f"- Domains: `{A11OY_DOMAIN}`, `{A11OY_NET_DOMAIN}`")
    lines.append("")
    lines.append("## GitHub estate (public API only)")
    lines.append(f"- Public repos reported by org endpoint: `{known_public}`")
    lines.append(f"- Repos sampled: `{len(gh['repos_sampled'])}`")
    lines.append("")
    lines.append("### Branch protection probe (`main`)")
    for row in gh["branch_main_protection"]:
        status = row["protected"]
        if status is None:
            status = "unknown"
        lines.append(f"- `{row['repo']}`: `{status}` (HTTP {row['status']}{' - ' + str(row['status_error']) if row['status_error'] else ''})")
    lines.append("")
    lines.append("## Hugging Face estate")
    for key in ("models", "datasets", "spaces"):
        item = hf["urls"][key]
        if item["parse_ok"]:
            count = item.get("count")
            if count is None:
                count = "unknown"
            top_ids = item.get("sample_ids", [])
        else:
            count = "unknown"
            top_ids = []
        lines.append(f"- {key.capitalize()}: `{count}` (sample IDs: {', '.join(str(i) for i in top_ids) if top_ids else 'none'})")

    lines.append("")
    lines.append(f"## a-11-oy.com API posture (`{A11OY_DOMAIN}`)")
    for row in a11oy:
        if isinstance(row.get("snippet"), dict):
            snippet = json.dumps(row["snippet"], sort_keys=True)
            if len(snippet) > 240:
                snippet = snippet[:240] + "..."
        else:
            snippet = str(row.get("snippet", ""))
        lines.append(f"- `{row['path']}` => {row['status']} { 'ok' if row['ok'] else 'not ok'} {snippet}")
    lines.append("")
    lines.append(f"## a11oy.net API posture (`{A11OY_NET_DOMAIN}`)")
    for row in front:
        if isinstance(row.get("snippet"), dict):
            snippet = json.dumps(row["snippet"], sort_keys=True)
            if len(snippet) > 220:
                snippet = snippet[:220] + "..."
        else:
            snippet = str(row.get("snippet", ""))
        lines.append(f"- `{row['path']}` => {row['status']} { 'ok' if row['ok'] else 'not ok'} {snippet}")
    lines.append("")
    lines.append("## Security header snapshot")
    a11oy_header_keys = ", ".join(_sorted_header_keys(snapshot["a11oy_headers"].get("headers", {})))
    a11oy_net_header_keys = ", ".join(_sorted_header_keys(snapshot["a11oy_net_headers"].get("headers", {})))
    lines.append(f"- `{A11OY_DOMAIN}` response snippet keys: `{a11oy_header_keys}`")
    lines.append(f"- `{A11OY_NET_DOMAIN}` response snippet keys: `{a11oy_net_header_keys}`")
    lines.append("")
    lines.append("## Frontier blockers (live, non-hypothetical)")
    blockers = []
    if any(item["status"] in (404, 503) and item["path"].startswith("/api/") for item in front):
        blockers.append(f"{A11OY_NET_DOMAIN} does not expose the same `/api/a11oy/v1/...` runtime routes as `{A11OY_DOMAIN}`.")
    if any(item["status"] in (0, 404) and item["path"] in ("/api/a11oy/v1/honest", "/api/a11oy/v1/ledger") for item in a11oy):
        blockers.append(f"{A11OY_DOMAIN} runtime endpoints are partially unavailable and need triage before any production claim expansion.")
    if not blockers:
        blockers.append("No hard blockers found in this read; continue to deeper policy/evidence checks.")
    for item in blockers:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Next frontier moves (ranked)")
    lines.append("1. Publish this report as part of your public evidence page and link it to `/api/assurance` responses.")
    lines.append("2. Convert `a11oy.net` into an explicit registry + index front door and keep runtime plane on `a-11-oy.com`, with no claim of equivalence.")
    lines.append("3. Add a scheduled CI step that runs this script and stores the JSON snapshot for audit continuity.")
    lines.append("4. Move from sample placeholders to signed fixtures tied to this fixture bundle (`sample_receipt_fail.json`, `sample_replay.json`).")
    return "\n".join(lines) + "\n"


def _sorted_header_keys(headers: dict) -> list[str]:
    normalized = []
    for key in headers:
        if re.search(r"(?i)^strict-transport-security|content-security-policy|cross-origin|x-frame-options|referrer-policy|cache-control|content-type$", key):
            normalized.append(key.lower())
    return sorted(set(normalized))


def main() -> int:
    github = _probe_github_org()
    hf = _probe_hf()
    a11oy = _probe_http_endpoints(
        A11OY_DOMAIN,
        [
            "/healthz",
            "/api/a11oy/v1/honest",
            "/api/a11oy/v1/ledger",
            "/api/a11oy/v1/assurance/fit",
            "/api/a11oy/v1/assurance/matrix",
            "/api/a11oy/v1/observability/summary",
            "/api/a11oy/v1/observability/business",
            "/api/a11oy/v1/mesh/state",
            "/api/a11oy/v1/lambda",
        ],
    )
    a11oy_net = _probe_http_endpoints(
        A11OY_NET_DOMAIN,
        [
            "/",
            "/api/a11oy/v1/honest",
            "/api/a11oy/v1/healthz",
            "/api/a11oy/v1/assurance/matrix",
        ],
    )
    a11oy_headers = _probe_headers(A11OY_DOMAIN)
    a11oy_net_headers = _probe_headers(A11OY_NET_DOMAIN)

    snapshot = {
        "run_at_utc": SCRIPT_START.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "github": {
            "org": {
                "url": github["url"] if isinstance(github, dict) else "",
                "ok": github["request"]["ok"],
                "status": github["request"]["status"],
                "error": github["request"].get("error"),
                "payload": github.get("payload"),
            },
            "repos_sampled": github.get("repos_sampled", []),
            "branch_main_protection": github.get("branch_main_protection", []),
        },
        "huggingface": {
            "urls": {
                key: {
                    "status": value.get("status"),
                    "ok": value.get("ok"),
                    "error": value.get("error"),
                    "count": value.get("count"),
                    "sample_ids": value.get("sample_ids"),
                    "parse_ok": value.get("parse_ok"),
                }
                for key, value in hf["urls"].items()
            },
            "org_page": hf["org_page"],
        },
        "a11oy_com": a11oy,
        "a11oy_net": a11oy_net,
        "a11oy_headers": a11oy_headers,
        "a11oy_net_headers": a11oy_net_headers,
    }

    snapshot_path = OUTPUT_DIR / f"frontier_snapshot_{SCRIPT_START.strftime('%Y%m%dT%H%M%SZ')}.json"
    report_path = OUTPUT_DIR / f"frontier_report_{SCRIPT_START.strftime('%Y%m%dT%H%M%SZ')}.md"
    snapshot_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(_render_markdown(snapshot), encoding="utf-8")
    print(f"frontier_snapshot={snapshot_path}")
    print(f"frontier_report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
