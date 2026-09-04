#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Record the HF org Docker 402 plan gate. Do not open a personal runtime.

Organization Gradio/Docker Spaces on cpu-basic require Team or Enterprise.
Doctrine v7 §14 forbids laundering the product runtime through a personal
Hugging Face owner. Historical helper functions remain for contract tests.
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
from typing import Any, MutableMapping

ROOT = Path(__file__).resolve().parents[1]
INTELLIGENCE_PUBLISHER = ROOT / "scripts" / "hf_publish_vertical_services_intelligence_v4.py"
RUNTIME_SOURCE_REVISION = "7a84e34a05c7342bd32b56f6519fe51ce240f577"
RUNTIME_VERSION = "2.2.0"
RUNTIME_SLUG = "szl-vertical-services-runtime"
ORG = "SZLHOLDINGS"
GATEWAY_SOURCE_REPOSITORY = "szl-holdings/a11oy"
RECEIPT_PATH = Path("hf-free-tier-recovery-receipt.json")
RUNTIME_RECEIPT_PATH = Path("hf-personal-vertical-runtime-receipt.json")
USER_AGENT = "SZL-HF-Free-Tier-Recovery/1.2"
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
REQUIRED_GATEWAY_PATHS = ("/", "/healthz", "/api/build-info", "/api/source")
SHA40 = re.compile(r"^[0-9a-f]{40}$")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def token_from_env() -> tuple[str, str]:
    for name in TOKEN_NAMES:
        value = os.getenv(name, "").strip()
        if value:
            return value, name
    raise RuntimeError("no Hugging Face write token available")


def bind_github_token_alias(
    environ: MutableMapping[str, str] | None = None,
) -> str:
    """Expose the Actions token under the exact name required by the publisher.

    The pinned Dockerfile publisher deliberately requires ``GITHUB_TOKEN`` for
    default-branch-tip verification. GitHub CLI conventionally uses ``GH_TOKEN``.
    Accept either name, copy only in-process, and return the source variable name
    so receipts can prove authority without exposing its value.
    """

    target = os.environ if environ is None else environ
    github_token = str(target.get("GITHUB_TOKEN") or "").strip()
    if github_token:
        return "GITHUB_TOKEN"
    gh_token = str(target.get("GH_TOKEN") or "").strip()
    if gh_token:
        target["GITHUB_TOKEN"] = gh_token
        return "GH_TOKEN"
    raise RuntimeError("GITHUB_TOKEN or GH_TOKEN is required for exact source-tip proof")


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


def configure_personal_publisher(owner: str) -> tuple[ModuleType, str, str]:
    """Return the deepest publisher module with the personal target bound.

    The v4 and v3 wrappers each configure a nested module. Calling the wrapper's
    ``main`` would construct another base publisher and silently restore the
    organization target. This function walks the full configuration chain and
    applies the target to the exact module whose ``main`` performs the write.
    """

    wrapper = load_module(INTELLIGENCE_PUBLISHER, "szl_hf_intelligence_v4_recovery")
    wrapper.SOURCE_REVISION = RUNTIME_SOURCE_REVISION
    wrapper.EXPECTED_VERSION = RUNTIME_VERSION
    v3 = wrapper.configure_v4(wrapper.load_v3())
    if v3.SOURCE_REVISION != RUNTIME_SOURCE_REVISION:
        raise RuntimeError("v4 wrapper retained a stale source revision")
    if v3.EXPECTED_VERSION != RUNTIME_VERSION:
        raise RuntimeError("v4 wrapper retained a stale runtime version")

    publisher = v3.configure(v3.load_base())
    if publisher.SOURCE_REVISION != RUNTIME_SOURCE_REVISION:
        raise RuntimeError("configured base publisher retained a stale source revision")
    if publisher.EXPECTED_VERSION != RUNTIME_VERSION:
        raise RuntimeError("configured base publisher retained a stale runtime version")

    repo_id = f"{owner}/{RUNTIME_SLUG}"
    origin = space_origin(repo_id)
    publisher.HF_REPOSITORY = repo_id
    publisher.ORIGIN = origin
    publisher.RECEIPT_PATH = RUNTIME_RECEIPT_PATH
    publisher.USER_AGENT = USER_AGENT
    if publisher.HF_REPOSITORY != repo_id or publisher.ORIGIN != origin:
        raise RuntimeError("personal runtime target binding did not reach the canonical writer")
    return publisher, repo_id, origin


def deploy_personal_runtime(token: str, owner: str) -> dict[str, Any]:
    github_token_source = bind_github_token_alias()
    publisher, repo_id, origin = configure_personal_publisher(owner)
    exit_code = int(publisher.main())
    if not RUNTIME_RECEIPT_PATH.is_file():
        raise RuntimeError("personal runtime publisher did not emit its receipt")
    receipt = json.loads(RUNTIME_RECEIPT_PATH.read_text(encoding="utf-8"))
    complete = bool(receipt.get("complete") is True and exit_code == 0)
    if not complete:
        raise RuntimeError("personal vertical runtime did not pass exact-source live proof")
    if receipt.get("source_revision") != RUNTIME_SOURCE_REVISION:
        raise RuntimeError("personal runtime receipt names the wrong source revision")
    if receipt.get("hf_repository") != repo_id:
        raise RuntimeError("personal runtime receipt names the wrong Hugging Face repository")
    if receipt.get("origin") != origin:
        raise RuntimeError("personal runtime receipt names the wrong public origin")
    return {
        "repo_id": repo_id,
        "origin": origin,
        "source_revision": RUNTIME_SOURCE_REVISION,
        "version": RUNTIME_VERSION,
        "github_token_source_name": github_token_source,
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


def anonymous_get(url: str, attempts: int = 30) -> tuple[int, bytes]:
    last_status = 0
    for attempt in range(attempts):
        separator = "&" if "?" in url else "?"
        request = urllib.request.Request(
            f"{url}{separator}szl_static_verify={time.time_ns()}",
            headers={"Cache-Control": "no-cache", "User-Agent": USER_AGENT},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read(1_000_001)
                if len(body) > 1_000_000:
                    raise RuntimeError("gateway response exceeded one megabyte")
                if response.status == 200:
                    return response.status, body
                last_status = response.status
        except urllib.error.HTTPError as exc:
            last_status = exc.code
        except urllib.error.URLError:
            last_status = 0
        time.sleep(min(20, 2 + attempt))
    return last_status, b""


def verify_gateway(origin: str, expected: dict[str, Any]) -> dict[str, Any]:
    observations: dict[str, Any] = {}
    failures: list[str] = []
    expected_schemas = {
        "/healthz": "szl.static-runtime-gateway-health/v1",
        "/api/build-info": "szl.static-runtime-gateway/v2",
        "/api/source": "szl.static-runtime-gateway-source/v1",
    }
    for path in REQUIRED_GATEWAY_PATHS:
        status, body = anonymous_get(origin.rstrip("/") + path)
        row: dict[str, Any] = {
            "path": path,
            "http_status": status,
            "body_sha256": hashlib.sha256(body).hexdigest() if body else None,
        }
        if status != 200:
            failures.append(f"{path}: HTTP {status}")
        elif path == "/":
            text = body.decode("utf-8", "replace")
            if 'data-szl-domain-experience-v4="true"' not in text:
                failures.append("/: gateway marker missing")
        else:
            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                payload = None
            row["json_object"] = isinstance(payload, dict)
            if not isinstance(payload, dict):
                failures.append(f"{path}: JSON object missing")
            else:
                row["schema"] = payload.get("schema")
                if payload.get("schema") != expected_schemas[path]:
                    failures.append(f"{path}: schema mismatch")
                if payload.get("source_repository") != GATEWAY_SOURCE_REPOSITORY:
                    failures.append(f"{path}: gateway source repository mismatch")
                if payload.get("source_revision") != expected["source_revision"]:
                    failures.append(f"{path}: gateway source revision mismatch")
                if payload.get("runtime_repository") != expected["runtime_repository"]:
                    failures.append(f"{path}: runtime repository mismatch")
                if payload.get("runtime_source_revision") != RUNTIME_SOURCE_REVISION:
                    failures.append(f"{path}: runtime source revision mismatch")
                if payload.get("effectors_enabled") is not False:
                    failures.append(f"{path}: effector boundary drift")
                if payload.get("human_approval_required") is not True:
                    failures.append(f"{path}: human authority boundary drift")
        observations[path] = row
    return {
        "required_paths": list(REQUIRED_GATEWAY_PATHS),
        "observations": observations,
        "failures": failures,
        "complete": not failures,
    }


def gateway_documents(
    *,
    slug: str,
    repo_id: str,
    title: str,
    description: str,
    target: str,
    runtime: dict[str, Any],
    gateway_revision: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, bytes]]:
    build = {
        "schema": "szl.static-runtime-gateway/v2",
        "generated_at": utc_now(),
        "service": slug,
        "hf_repository": repo_id,
        "source_repository": GATEWAY_SOURCE_REPOSITORY,
        "source_revision": gateway_revision,
        "deployment_mode": "STATIC_ORG_GATEWAY_PERSONAL_DYNAMIC_RUNTIME",
        "runtime_repository": runtime["repo_id"],
        "runtime_source_revision": runtime["source_revision"],
        "runtime_version": runtime["version"],
        "runtime_target": target,
        "provider_constraint": "HF_ORG_DYNAMIC_REQUIRES_TEAM_OR_ENTERPRISE",
        "effectors_enabled": False,
        "human_approval_required": True,
    }
    health = {
        **build,
        "schema": "szl.static-runtime-gateway-health/v1",
        "status": "ok",
    }
    source = {
        **build,
        "schema": "szl.static-runtime-gateway-source/v1",
    }
    payloads = {
        "README.md": static_card(title, description).encode(),
        "index.html": static_page(title, description, target, build).encode(),
        "build-info.json": canonical_json_bytes(build),
        ".well-known/szl-source.json": canonical_json_bytes(source),
        "healthz": canonical_json_bytes(health),
        "api/build-info": canonical_json_bytes(build),
        "api/source": canonical_json_bytes(source),
    }
    return build, health, source, payloads


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
    gateway_revision = (os.getenv("GITHUB_SHA") or "").strip().lower()
    if SHA40.fullmatch(gateway_revision) is None:
        raise RuntimeError("GITHUB_SHA is required to bind the static gateway source")
    _, _, _, payloads = gateway_documents(
        slug=slug,
        repo_id=repo_id,
        title=title,
        description=description,
        target=target,
        runtime=runtime,
        gateway_revision=gateway_revision,
    )
    operations: list[Any] = [CommitOperationAdd(path_in_repo=name, path_or_fileobj=data) for name, data in payloads.items()]
    operations.extend(CommitOperationDelete(path_in_repo=name) for name in DELETE_DYNAMIC_FILES if name in files)
    commit = api.create_commit(
        repo_id=repo_id, repo_type="space", operations=operations,
        commit_message=f"ops: convert {slug} to source-bound static gateway", token=token,
    )
    origin = space_origin(repo_id)
    live = verify_gateway(
        origin,
        {
            "source_revision": gateway_revision,
            "runtime_repository": runtime["repo_id"],
        },
    )
    return {
        "repo_id": repo_id,
        "origin": origin,
        "target": target,
        "commit": str(getattr(commit, "oid", "") or getattr(commit, "commit_url", "")),
        "required_paths": list(REQUIRED_GATEWAY_PATHS),
        "live_verification": live,
        "operational": live["complete"],
        "deleted_dynamic_files": sorted(name for name in DELETE_DYNAMIC_FILES if name in files),
    }


def main() -> int:
    report: dict[str, Any] = {
        "schema": "szl.hf-free-tier-recovery/v4",
        "started_at": utc_now(),
        "provider_constraint": "HF_ORG_DYNAMIC_REQUIRES_TEAM_OR_ENTERPRISE",
        "observed_http_status": 402,
        "observed_constraint": (
            "Organization Gradio and Docker Spaces on cpu-basic "
            "require a Team or Enterprise plan"
        ),
        "state": "UNAVAILABLE",
        "truth_label": "UNAVAILABLE",
        "personal_namespace_runtime": False,
        "personal_owner": None,
        "doctrine_v7_section_14": (
            "product runtime does not live in a personal HF Space"
        ),
        "killinchu_mutated": False,
        "organization_subscription_changed": False,
        "token_value_recorded": False,
        "complete": False,
        "note": (
            "HF 402 is a paid-plan constraint. Record UNAVAILABLE. "
            "Do not launder through a personal owner."
        ),
    }
    report["finished_at"] = utc_now()
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    report["receipt_sha256"] = hashlib.sha256(canonical).hexdigest()
    RECEIPT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
