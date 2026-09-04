#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Recover the HF vertical estate when org Docker Spaces are plan-gated.

One canonical GitHub workflow publishes the exact vertical-services source to a
personal public Docker Space, then converts the five SZLHOLDINGS entry Spaces to
free static gateways. No source, receipt, or authority check is weakened.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INTELLIGENCE_PUBLISHER = ROOT / "scripts" / "hf_publish_vertical_services_intelligence_v4.py"
RUNTIME_SOURCE_REVISION = "c24ef61716f173e48d95dad61408d9fa065f0204"
RUNTIME_VERSION = "2.2.0"
RUNTIME_SLUG = "szl-vertical-services-runtime"
ORG = "SZLHOLDINGS"
RECEIPT_PATH = Path("hf-free-tier-recovery-receipt.json")
RUNTIME_RECEIPT_PATH = Path("hf-personal-vertical-runtime-receipt.json")
USER_AGENT = "SZL-HF-Free-Tier-Recovery/1.0"
TOKEN_NAMES = (
    "HF_ORG_TOKEN", "HF_WRITE_TOKEN", "HF_TOKEN",
    "HUGGINGFACE_TOKEN", "HUGGING_FACE_HUB_TOKEN",
)
STATIC_SPACES = {
    "vertical-services": ("SZL Vertical Services", "Six governed engines, one operational fabric", "/"),
    "terra": ("Terra", "Parcel-to-portfolio real-estate intelligence", "/experience/terra"),
    "counsel": ("PRISM Counsel", "Evidence-linked legal matter intelligence", "/experience/prism"),
    "finance": ("PURIQ Finance", "Provenance-first financial intelligence", "/experience/puriq"),
    "lyte": ("Lyte", "Business and agent observability command", "/experience/lyte"),
}
DELETE_DYNAMIC_FILES = (
    "Dockerfile", "Dockerfile.dockerignore", "app.py", "requirements.txt", "config.json",
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def token_from_env() -> tuple[str, str]:
    for name in TOKEN_NAMES:
        value = os.getenv(name, "").strip()
        if value:
            return value, name
    raise RuntimeError("no Hugging Face write token available")


def owner_from_identity(identity: Any) -> str:
    if not isinstance(identity, dict):
        raise RuntimeError("Hugging Face identity response was not an object")
    owner = str(identity.get("name") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}", owner):
        raise RuntimeError("Hugging Face token owner is unavailable or malformed")
    if owner.casefold() == ORG.casefold():
        raise RuntimeError("write token resolved to the organization, not a personal owner")
    return owner


def space_origin(repo_id: str) -> str:
    owner, slug = repo_id.split("/", 1)
    host = f"{owner}-{slug}".lower().replace("_", "-").replace(".", "-")
    return f"https://{host}.hf.space"


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load publisher: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def deploy_personal_runtime(token: str, owner: str) -> dict[str, Any]:
    wrapper = load_module(INTELLIGENCE_PUBLISHER, "szl_hf_intelligence_v4_recovery")
    publisher = wrapper.configure_v4(wrapper.load_v3())
    repo_id = f"{owner}/{RUNTIME_SLUG}"
    origin = space_origin(repo_id)
    publisher.HF_REPOSITORY = repo_id
    publisher.ORIGIN = origin
    publisher.RECEIPT_PATH = RUNTIME_RECEIPT_PATH
    publisher.USER_AGENT = USER_AGENT
    exit_code = int(publisher.main())
    receipt = json.loads(RUNTIME_RECEIPT_PATH.read_text(encoding="utf-8"))
    complete = bool(receipt.get("complete") is True and exit_code == 0)
    if not complete:
        raise RuntimeError("personal vertical runtime did not pass exact-source live proof")
    if receipt.get("source_revision") != RUNTIME_SOURCE_REVISION:
        raise RuntimeError("personal runtime receipt names the wrong source revision")
    return {
        "repo_id": repo_id,
        "origin": origin,
        "source_revision": RUNTIME_SOURCE_REVISION,
        "version": RUNTIME_VERSION,
        "receipt": receipt,
    }


def static_card(title: str, description: str) -> str:
    return (
        "---\n"
        f"title: {title}\n"
        "emoji: 🧬\ncolorFrom: gray\ncolorTo: indigo\n"
        "sdk: static\napp_file: index.html\npinned: false\nlicense: apache-2.0\n"
        f"short_description: {description[:60]}\n"
        "---\n\n"
        "# " + title + "\n\n"
        "Static public entry surface backed by the exact-source SZL governed runtime.\n"
        "The runtime remains proposal-only, deny-by-default, human-authorized, and receipted.\n"
    )


def static_page(title: str, description: str, target: str, build: dict[str, Any]) -> str:
    target_json = json.dumps(target)
    build_json = json.dumps(build, sort_keys=True, separators=(",", ":"))
    return f'''<!doctype html>
<html lang="en" data-szl-domain-experience-v4="true">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{title} · SZL Holdings</title><style>
:root{{color-scheme:dark;font-family:Inter,ui-sans-serif,system-ui;background:#07090d;color:#f4f7fb}}
*{{box-sizing:border-box}}body{{min-height:100vh;margin:0;display:grid;place-items:center;padding:24px;background:radial-gradient(circle at 20% 10%,#19203a 0,transparent 38%),#07090d}}
main{{width:min(760px,100%);padding:clamp(28px,6vw,72px);border:1px solid #30384d;border-radius:24px;background:#0c1019e8;box-shadow:0 24px 90px #0009}}
.kicker{{font:700 12px/1.2 ui-monospace,monospace;letter-spacing:.16em;color:#9eb4ff}}h1{{font-size:clamp(40px,9vw,84px);line-height:.92;margin:18px 0}}p{{font-size:clamp(16px,2.5vw,20px);line-height:1.6;color:#c3cbe0}}
a{{display:inline-grid;place-items:center;min-height:48px;min-width:48px;margin-top:20px;padding:0 22px;border-radius:999px;background:#f4f7fb;color:#080a10;text-decoration:none;font-weight:800}}
small{{display:block;margin-top:24px;color:#7f8ba8;overflow-wrap:anywhere}}@media(prefers-reduced-motion:reduce){{*{{scroll-behavior:auto!important}}}}@media(forced-colors:active){{main,a{{border:1px solid CanvasText}}}}
</style></head><body><main><div class="kicker">SZL HOLDINGS · SOURCE-BOUND ENTRY</div><h1>{title}</h1><p>{description}. Opening the live governed engine.</p><a id="open" href="{target}">Open live engine</a><small>Source {RUNTIME_SOURCE_REVISION[:12]} · Runtime {RUNTIME_VERSION} · Human authority required</small></main>
<script>const target={target_json};setTimeout(()=>location.replace(target+location.search+location.hash),900);</script>
<script type="application/json" id="szl-build-info">{build_json}</script></body></html>'''


def anonymous_html(url: str, attempts: int = 30) -> tuple[int, str]:
    last_status = 0
    for attempt in range(attempts):
        request = urllib.request.Request(
            f"{url}?szl_static_verify={time.time_ns()}",
            headers={"Cache-Control": "no-cache", "User-Agent": USER_AGENT},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                text = response.read(1_000_000).decode("utf-8", "replace")
                if response.status == 200 and 'data-szl-domain-experience-v4="true"' in text:
                    return response.status, text
                last_status = response.status
        except urllib.error.HTTPError as exc:
            last_status = exc.code
        except urllib.error.URLError:
            last_status = 0
        time.sleep(min(20, 2 + attempt))
    return last_status, ""


def publish_static_gateway(api: Any, token: str, slug: str, meta: tuple[str, str, str], runtime: dict[str, Any]) -> dict[str, Any]:
    from huggingface_hub import CommitOperationAdd, CommitOperationDelete
    title, description, path = meta
    repo_id = f"{ORG}/{slug}"
    try:
        files = set(api.list_repo_files(repo_id=repo_id, repo_type="space", token=token))
    except Exception:
        api.create_repo(repo_id=repo_id, repo_type="space", space_sdk="static", exist_ok=True, private=False, token=token)
        files = set()
    target = runtime["origin"].rstrip("/") + path
    build = {
        "schema": "szl.static-runtime-gateway/v1",
        "generated_at": utc_now(),
        "hf_repository": repo_id,
        "deployment_mode": "STATIC_ORG_GATEWAY_PERSONAL_DYNAMIC_RUNTIME",
        "gateway_source_revision": os.getenv("GITHUB_SHA") or "UNAVAILABLE",
        "runtime_repository": runtime["repo_id"],
        "runtime_source_revision": runtime["source_revision"],
        "runtime_version": runtime["version"],
        "runtime_target": target,
        "provider_constraint": "HF_ORG_DYNAMIC_REQUIRES_TEAM_OR_ENTERPRISE",
        "effectors_enabled": False,
        "human_approval_required": True,
    }
    payloads = {
        "README.md": static_card(title, description).encode(),
        "index.html": static_page(title, description, target, build).encode(),
        "build-info.json": (json.dumps(build, indent=2) + "\n").encode(),
        ".well-known/szl-source.json": (json.dumps(build, indent=2) + "\n").encode(),
    }
    operations: list[Any] = [CommitOperationAdd(path_in_repo=path, path_or_fileobj=data) for path, data in payloads.items()]
    operations.extend(CommitOperationDelete(path_in_repo=path) for path in DELETE_DYNAMIC_FILES if path in files)
    commit = api.create_commit(
        repo_id=repo_id, repo_type="space", operations=operations,
        commit_message=f"ops: convert {slug} to source-bound static gateway", token=token,
    )
    origin = space_origin(repo_id)
    status, _ = anonymous_html(origin)
    return {
        "repo_id": repo_id,
        "origin": origin,
        "target": target,
        "commit": str(getattr(commit, "oid", "") or getattr(commit, "commit_url", "")),
        "http_status": status,
        "operational": status == 200,
        "deleted_dynamic_files": sorted(path for path in DELETE_DYNAMIC_FILES if path in files),
    }


def main() -> int:
    report: dict[str, Any] = {
        "schema": "szl.hf-free-tier-recovery/v1",
        "started_at": utc_now(),
        "provider_constraint": "HF_ORG_DYNAMIC_REQUIRES_TEAM_OR_ENTERPRISE",
        "token_value_recorded": False,
        "complete": False,
    }
    exit_code = 1
    try:
        from huggingface_hub import HfApi
        token, token_name = token_from_env()
        api = HfApi(token=token)
        owner = owner_from_identity(api.whoami(token=token))
        runtime = deploy_personal_runtime(token, owner)
        rows = [publish_static_gateway(api, token, slug, meta, runtime) for slug, meta in STATIC_SPACES.items()]
        complete = all(row["operational"] for row in rows)
        report.update({
            "token_source_name": token_name,
            "personal_owner": owner,
            "runtime": {key: runtime[key] for key in ("repo_id", "origin", "source_revision", "version")},
            "gateways": rows,
            "gateways_operational": sum(1 for row in rows if row["operational"]),
            "gateways_total": len(rows),
            "complete": complete,
        })
        exit_code = 0 if complete else 1
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {str(exc)[:1000]}"
    report["finished_at"] = utc_now()
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    report["receipt_sha256"] = hashlib.sha256(canonical).hexdigest()
    RECEIPT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
