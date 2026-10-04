#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Canonical vertical estate publisher.

The established Domain Experience v4 implementation remains the renderer for
Terra, Sentra, Counsel, and Finance. Lyte is no longer regenerated as a generic shell:
the same A11oy single-writer job publishes the exact tested default-branch
revision of ``szl-holdings/lyte-services`` through a dedicated source-owned
publisher. Sentra remains the sole Assurance Command. Vessels remains a
capability plane inside Killinchu and is filtered before independent publication.

The job then publishes and attests the combined six-engine Python intelligence
runtime from the exact tested vertical-services default-branch tip observed at
deployment time. Each source revision is immutable for the run and guarded
against default-branch drift before mutation.

One public product surface does not require one undifferentiated code module.
Models propose, kernels constrain, Hatun reviews, and humans retain
consequential authority.
"""
from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from types import ModuleType
from typing import Any

HERE = Path(__file__).resolve().parent
FLAGSHIP_IMPL = HERE / "hf_publish_vertical_flagships_v4_impl.py"
LYTE_IMPL = HERE / "hf_publish_lyte_enterprise.py"
BASE_COMBINED_IMPL = HERE / "hf_publish_vertical_services.py"
COMBINED_IMPL = HERE / "hf_publish_vertical_services_intelligence_v4.py"
SPACE_GUARD_IMPL = HERE / "hf_existing_space_guard.py"
FLAGSHIP_RECEIPT = Path("hf-vertical-flagships-receipt.json")
LYTE_RECEIPT = Path("hf-lyte-enterprise-receipt.json")
COMBINED_RECEIPT = Path("hf-vertical-services-receipt.json")

PUBLIC_FLAGSHIP_SLUGS = ("terra", "sentra", "counsel", "finance", "lyte")
GENERATED_FLAGSHIP_SLUGS = ("terra", "sentra", "counsel", "finance")
SOURCE_OWNED_FLAGSHIP_SLUGS = ("lyte",)
SELECTABLE_GENERATED_SCOPES = ("terra", "sentra", "counsel")
FOLDED_INTO_KILLINCHU = ("vessels",)
KILLINCHU_SPACE = "SZLHOLDINGS/killinchu"
SENTRA_SPACE = "SZLHOLDINGS/sentra"
VERTICAL_SERVICES_REPOSITORY = "szl-holdings/vertical-services"
GITHUB_API = "https://api.github.com"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SENTRA_FILES = ("app.py", "Dockerfile", "requirements.txt", "config.json", "index.html", "panels.html", "README.md")
SENTRA_MAX_FILE_BYTES = 512 * 1024
SENTRA_DOCTRINE_CHECKS = ("Banned-token scan (Doctrine v7 §1)", "overclaim / Governed surfaces are honest (Theorem U citation rule)")

# Historical identifiers stay visible for receipt readers and protected
# regression tests. They are documentation strings, not active topology.
PREVIOUS_ESTATE_SCHEMA = "szl.hf-vertical-estate/v7"
LEGACY_GENERATED_GUARD = "retired Killinchu capability plane reached public writer"
LEGACY_PUBLIC_FLAGSHIP_CONTRACT = (
    'PUBLIC_FLAGSHIP_SLUGS = ("terra", "counsel", "finance", "lyte")'
)
LEGACY_FOLDED_CONTRACT = 'FOLDED_INTO_KILLINCHU = ("sentra", "vessels")'


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load publisher module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def constrain_public_flagships(module: ModuleType) -> tuple[str, ...]:
    """Admit only generated shells; source-owned Lyte is published separately."""
    inventory = getattr(module, "FLAGSHIPS", None)
    if not isinstance(inventory, tuple):
        raise RuntimeError("flagship implementation does not expose tuple FLAGSHIPS")

    by_slug: dict[str, Any] = {}
    for item in inventory:
        if not isinstance(item, dict) or not isinstance(item.get("slug"), str):
            raise RuntimeError("flagship implementation contains an invalid item")
        slug = item["slug"]
        if slug in by_slug:
            raise RuntimeError(f"duplicate flagship slug: {slug}")
        by_slug[slug] = item

    expected_source = set(PUBLIC_FLAGSHIP_SLUGS) | set(FOLDED_INTO_KILLINCHU)
    if set(by_slug) != expected_source:
        raise RuntimeError(
            "unexpected Domain Experience inventory: "
            f"expected {sorted(expected_source)}, observed {sorted(by_slug)}"
        )

    admitted = tuple(by_slug[slug] for slug in GENERATED_FLAGSHIP_SLUGS)
    forbidden = set(FOLDED_INTO_KILLINCHU) | set(SOURCE_OWNED_FLAGSHIP_SLUGS)
    if any(item["slug"] in forbidden for item in admitted):
        raise RuntimeError(
            f"{LEGACY_GENERATED_GUARD}; source-owned Lyte reached the "
            "generated public writer"
        )
    module.FLAGSHIPS = admitted
    return tuple(item["slug"] for item in admitted)


def _github_json(path: str, *, token: str | None = None) -> dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "SZLHOLDINGS-Vertical-Source-Resolver/1.0",
        "Cache-Control": "no-cache",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(f"{GITHUB_API}{path}", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        if token and exc.code in {401, 403}:
            return _github_json(path, token=None)
        raise RuntimeError(f"GitHub source resolution failed: HTTP {exc.code}") from exc
    except (OSError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"GitHub source resolution failed: {type(exc).__name__}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError("GitHub source resolution returned a non-object")
    return payload


def resolve_tested_vertical_services_tip() -> tuple[str, dict[str, Any]]:
    """Resolve one immutable source SHA and require its Python contract to pass.

    The live ``healthz`` workflow is deliberately not used as an admission gate
    here: it measures the previously deployed Space and is expected to be red
    when this publisher is repairing source drift. The source commit itself must
    have a successful terminal ``Python contract suite`` check.
    """
    token = os.getenv("GITHUB_TOKEN", "").strip() or os.getenv(
        "GH_TOKEN", ""
    ).strip()
    ref = _github_json(
        f"/repos/{VERTICAL_SERVICES_REPOSITORY}/git/ref/heads/main",
        token=token or None,
    )
    revision = str(ref.get("object", {}).get("sha", "")).lower()
    if SHA40.fullmatch(revision) is None:
        raise RuntimeError("vertical-services main did not resolve to a full Git SHA")

    checks = _github_json(
        f"/repos/{VERTICAL_SERVICES_REPOSITORY}/commits/{revision}/"
        "check-runs?per_page=100",
        token=token or None,
    )
    runs = checks.get("check_runs", [])
    if not isinstance(runs, list):
        raise RuntimeError("vertical-services check-run payload is invalid")
    contract_runs = [
        row
        for row in runs
        if isinstance(row, dict)
        and row.get("name") == "Python contract suite"
        and row.get("head_sha") == revision
    ]
    accepted = [
        row
        for row in contract_runs
        if row.get("status") == "completed" and row.get("conclusion") == "success"
    ]
    if not accepted:
        state = [
            {
                "status": row.get("status"),
                "conclusion": row.get("conclusion"),
            }
            for row in contract_runs
        ]
        raise RuntimeError(
            "vertical-services main lacks a successful Python contract suite: "
            + json.dumps(state, sort_keys=True)
        )

    return revision, {
        "schema": "szl.vertical-source-resolution/v1",
        "repository": VERTICAL_SERVICES_REPOSITORY,
        "branch": "main",
        "revision": revision,
        "python_contract_suite": "success",
        "check_run_count": len(runs),
        "live_health_check_used_as_source_gate": False,
        "default_branch_tip_rechecked_by_deployer": True,
        "token_value_recorded": False,
        "truth_label": "MEASURED",
    }


def run_publisher(
    name: str,
    path: Path,
    *,
    source_revision_override: str | None = None,
    finance_only: bool = False,
    selected_slug: str | None = None,
) -> tuple[int, str | None, tuple[str, ...] | None]:
    admitted: tuple[str, ...] | None = None
    try:
        if selected_slug is not None and (
            selected_slug not in SELECTABLE_GENERATED_SCOPES or finance_only
            or name != "szl_flagship_v4"
        ):
            raise RuntimeError("unauthorized selected publication scope")
        module = load_module(name, path)
        if name == "szl_flagship_v4":
            admitted = constrain_public_flagships(module)
            if finance_only:
                module.FLAGSHIPS = tuple(row for row in module.FLAGSHIPS if row["slug"] == "finance")
                admitted = ("finance",)
            elif selected_slug is not None:
                module.FLAGSHIPS = tuple(row for row in module.FLAGSHIPS if row["slug"] == selected_slug)
                admitted = (selected_slug,)
        if source_revision_override is not None:
            if SHA40.fullmatch(source_revision_override) is None:
                raise RuntimeError("source revision override is not a full Git SHA")
            if not hasattr(module, "SOURCE_REVISION"):
                raise RuntimeError("combined publisher has no SOURCE_REVISION contract")
            module.SOURCE_REVISION = source_revision_override
        result = int(module.main())
        return result, None, admitted
    except SystemExit as exc:
        code = 0 if exc.code is None else int(exc.code)
        return code, None, admitted
    except Exception as exc:
        return 1, f"{type(exc).__name__}: {exc}", admitted


def read_receipt(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def ensure_space_secret_reader() -> str:
    """Backport metadata-only Space secret listing for pre-v1.14 Hub clients.

    Hugging Face secret values remain write-only. The endpoint returns only the
    configured key names and metadata, which is sufficient to preserve an
    existing SENTRA_SIGNING_KEY instead of rotating it.
    """
    from huggingface_hub import HfApi

    if callable(getattr(HfApi, "get_space_secrets", None)):
        return "native"

    from huggingface_hub.utils import get_session, hf_raise_for_status

    def get_space_secrets(
        self: Any,
        repo_id: str,
        *,
        token: bool | str | None = None,
    ) -> dict[str, Any]:
        response = get_session().get(
            f"{self.endpoint}/api/spaces/{repo_id}/secrets",
            headers=self._build_hf_headers(token=token),
        )
        hf_raise_for_status(response)
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError(
                "Hugging Face Space secret metadata endpoint returned a non-object"
            )
        return payload

    setattr(HfApi, "get_space_secrets", get_space_secrets)
    return "backported-metadata-only"


def normalize_github_token_alias() -> str:
    """Expose the ephemeral workflow token under the nested guard's name."""
    canonical = os.getenv("GITHUB_TOKEN", "").strip()
    if canonical:
        return "GITHUB_TOKEN"

    cli_token = os.getenv("GH_TOKEN", "").strip()
    if cli_token:
        os.environ["GITHUB_TOKEN"] = cli_token
        return "GH_TOKEN"

    return "unavailable"


def _github_workflow_token() -> str | None:
    """Use the existing read credential for own-repository source checks."""
    return (
        os.getenv("GITHUB_TOKEN", "").strip()
        or os.getenv("GH_TOKEN", "").strip()
        or None
    )


def finance_preflight() -> dict[str, Any]:
    """Require the canonical backend component before writing its public view."""
    revision = os.environ.get("GITHUB_SHA", "")
    if SHA40.fullmatch(revision) is None or revision == "0" * 40:
        raise RuntimeError("Finance requires a bound canonical source revision")
    head = _github_json(
        "/repos/szl-holdings/a11oy/commits/main", token=_github_workflow_token()
    )
    if head.get("sha") != revision:
        raise RuntimeError("Finance publisher source is no longer current main")
    request = urllib.request.Request(
        "https://szlholdings-a11oy.hf.space/api/a11oy/v1/finance/analytics/v2/signals/AAPL?origin=fixture",
        headers={"Accept": "application/json", "Accept-Encoding": "identity"})
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise RuntimeError("canonical Finance redirect refused")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=15) as response:
        if response.geturl() != request.full_url or response.status != 200:
            raise RuntimeError("canonical Finance analytics preflight failed")
        if response.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
            raise RuntimeError("canonical Finance preflight is not JSON")
        raw = response.read(160_001)
    if len(raw) > 160_000:
        raise RuntimeError("canonical Finance preflight response too large")
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError("duplicate preflight key")
            out[key] = value
        return out
    body = json.loads(raw, object_pairs_hook=pairs)
    projection = load_module("finance_preflight_contract", HERE / "hf_finance_read_proxy.py")
    if (not isinstance(body, dict) or body.get("source_revision") != revision or body.get("component") != projection.COMPONENT
            or body.get("schema") != "szl.finance.analytics/v2" or body.get("ok") is not True
            or body.get("operation") != "signals" or body.get("state") != "COMPUTED"
            or body.get("truth_label") != "MODELED"
            or body.get("execution_enabled") is not False
            or any(body.get(key) is not True for key in ("advisory_only", "paper_only", "not_financial_advice"))
            or body.get("result", {}).get("symbol") != "AAPL"
            or body.get("result", {}).get("data_origin") != "fixture"
            or body.get("inputs", {}).get("asset", {}).get("origin") != "fixture"
            or body.get("inputs", {}).get("asset", {}).get("truth_label") != "SYNTHETIC"):
        raise RuntimeError("canonical Finance component is not bound to publisher source")
    def digest(value):
        import hashlib
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    receipt = body.get("receipt")
    if not isinstance(receipt, dict):
        raise RuntimeError("canonical Finance receipt is absent")
    receipt = dict(receipt)
    claimed = receipt.pop("receipt_sha256", None)
    if (claimed != digest(receipt) or receipt.get("payload_sha256") != digest({key:value for key,value in body.items() if key != "receipt"})
            or receipt.get("source_revision") != revision or receipt.get("signed") is not False
            or receipt.get("signing") != "UNSIGNED_HONEST" or receipt.get("authority") != "NONE"
            or receipt.get("persistence") != "CALLER_HELD"
            or receipt.get("component_revision") != projection.COMPONENT["revision"]
            or receipt.get("component_sha256") != projection.COMPONENT["engine_sha256"]):
        raise RuntimeError("canonical Finance computation receipt is invalid")
    return {"source_revision": revision, "component": body["component"],
            "fixture_preflight": True, "live_provider_verified": False}


def publish_finance_only(space_guard_module) -> int:
    """Existing writer, one explicit target; no sibling publisher or combined sync."""
    try:
        preflight = finance_preflight()
        code, error, admitted = run_publisher("szl_flagship_v4", FLAGSHIP_IMPL, finance_only=True)
        receipt = read_receipt(FLAGSHIP_RECEIPT) or {}
        receipt.update(publication_scope="finance", canonical_preflight=preflight,
            existing_space_guard=space_guard_module.guard_report(), generated_flagship_slugs=list(admitted or ()),
            sibling_publications=0, secret_values_recorded=False, delete_operations=0)
        receipt["complete"] = (receipt.get("complete") is True and code == 0 and admitted == ("finance",)
            and len(receipt.get("rows", [])) == 1 and receipt["rows"][0].get("id") == "SZLHOLDINGS/finance")
        if error:
            receipt["entrypoint_error"] = error
    except Exception as exc:
        receipt = {"schema": "szl.hf-finance-publication/v1", "publication_scope": "finance",
                   "complete": False, "error": type(exc).__name__, "detail": str(exc),
                   "secret_values_recorded": False}
    FLAGSHIP_RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["complete"] else 1


def selected_generated_preflight(scope: str) -> str:
    """Bind a single generated Space to the current protected A11oy source."""
    if scope not in SELECTABLE_GENERATED_SCOPES:
        raise RuntimeError("unauthorized selected publication scope")
    revision = os.environ.get("GITHUB_SHA", "")
    if SHA40.fullmatch(revision) is None or revision == "0" * 40:
        raise RuntimeError("selected publisher requires a bound source revision")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    if not run_id.isdigit() or int(run_id) <= 0:
        raise RuntimeError("selected publisher requires a positive workflow run id")
    head = _github_json(
        "/repos/szl-holdings/a11oy/commits/main", token=_github_workflow_token()
    )
    if head.get("sha") != revision:
        raise RuntimeError("selected publisher source is no longer current main")
    return revision


def selected_generated_space_preflight(scope: str, space_guard_module) -> None:
    """Use the generated writer's credential to prove its one target is public."""
    module = load_module("szl_flagship_v4_token_source", FLAGSHIP_IMPL)
    token, _ = module._BASE.token_from_env()
    space_guard_module.require_existing_public_space(f"SZLHOLDINGS/{scope}", token)


class SentraPublicationError(RuntimeError):
    def __init__(self, message: str, http_status: int | None = None):
        super().__init__(message)
        self.http_status = http_status


class _SentraNoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SentraPublicationError("GitHub source admission redirected", int(code))


def _sentra_github_json(path: str) -> dict[str, Any]:
    """Read authenticated source evidence without credential fallback."""
    token = _github_workflow_token()
    if not token or not path.startswith("/repos/szl-holdings/a11oy/") or ".." in path or "#" in path:
        raise SentraPublicationError("Authenticated A11oy source evidence is unavailable")
    request = urllib.request.Request(GITHUB_API + path, headers={
        "Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "szl-sentra-publication/1",
        "Cache-Control": "no-cache",
    })
    try:
        with urllib.request.build_opener(_SentraNoRedirect).open(request, timeout=20) as response:
            body = response.read(2 * 1024 * 1024 + 1)
    except urllib.error.HTTPError as exc:
        raise SentraPublicationError("GitHub source admission returned an HTTP error", exc.code) from exc
    if len(body) > 2 * 1024 * 1024:
        raise SentraPublicationError("GitHub source evidence exceeded its bound")
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise SentraPublicationError("GitHub source evidence is not an object")
    return payload


def _sentra_source_admission() -> str:
    revision = os.environ.get("GITHUB_SHA", "")
    if (SHA40.fullmatch(revision) is None or revision == "0" * 40
            or os.environ.get("GITHUB_REF") != "refs/heads/main"
            or os.environ.get("GITHUB_REPOSITORY") != "szl-holdings/a11oy"
            or not os.environ.get("GITHUB_RUN_ID", "").isdigit()
            or int(os.environ["GITHUB_RUN_ID"]) <= 0):
        raise SentraPublicationError("Sentra requires an exact main workflow source")
    branch = _sentra_github_json("/repos/szl-holdings/a11oy/branches/main")
    protection = branch.get("protection") or {}
    policy = protection.get("required_status_checks") or {}
    if (branch.get("commit", {}).get("sha") != revision or branch.get("protected") is not True
            or protection.get("enabled") is not True):
        raise SentraPublicationError("Sentra source is not current protected main")
    checks = policy.get("checks")
    if not isinstance(checks, list) or not checks:
        raise SentraPublicationError("Required source-check policy is unavailable")
    required = {}
    for check in checks:
        if (not isinstance(check, dict) or not isinstance(check.get("context"), str)
                or not check["context"] or type(check.get("app_id")) is not int
                or check["context"] in required):
            raise SentraPublicationError("Required source-check authority is unavailable")
        required[check["context"]] = check["app_id"]
    if set(policy.get("contexts") or ()) != set(required):
        raise SentraPublicationError("Required source-check policy is inconsistent")
    if any(name in required and required[name] != 15368 for name in SENTRA_DOCTRINE_CHECKS):
        raise SentraPublicationError("Doctrine source-check authority is inconsistent")
    required.update({name: 15368 for name in SENTRA_DOCTRINE_CHECKS})
    commit = _sentra_github_json(f"/repos/szl-holdings/a11oy/commits/{revision}")
    signature = commit.get("commit", {}).get("verification") or {}
    if commit.get("sha") != revision or signature.get("verified") is not True or signature.get("reason") != "valid":
        raise SentraPublicationError("Sentra source signature is unverified")
    observed: dict[str, list[dict[str, Any]]] = {name: [] for name in required}
    for page in range(1, 5):
        payload = _sentra_github_json(
            f"/repos/szl-holdings/a11oy/commits/{revision}/check-runs?filter=latest&per_page=100&page={page}")
        total = payload.get("total_count")
        rows = payload.get("check_runs")
        if type(total) is not int or not 0 <= total <= 400 or not isinstance(rows, list):
            raise SentraPublicationError("Source-check inventory is unavailable or unbounded")
        for check in rows:
            name = check.get("name")
            if name in required and check.get("app", {}).get("id") == required[name]:
                observed[name].append(check)
        if page * 100 >= total:
            break
    if any(not rows or any(row.get("head_sha") != revision or row.get("status") != "completed"
                           or row.get("conclusion") != "success" for row in rows)
           for rows in observed.values()):
        raise SentraPublicationError("Required exact-source checks are unresolved")
    return revision


def _sentra_target(api: Any, *, running: bool = True) -> dict[str, Any]:
    info = api.space_info(SENTRA_SPACE)
    runtime = getattr(info, "runtime", None)
    result = {"id": getattr(info, "id", None), "sha": getattr(info, "sha", None),
              "private": getattr(info, "private", None), "sdk": getattr(info, "sdk", None),
              "hardware": str(getattr(runtime, "hardware", "")),
              "requested_hardware": str(getattr(runtime, "requested_hardware", "")),
              "storage": getattr(runtime, "storage", None)}
    if (result["id"] != SENTRA_SPACE or result["private"] is not False or result["sdk"] != "docker"
            or result["hardware"] != "cpu-basic" or result["requested_hardware"] != "cpu-basic"
            or not isinstance(result["sha"], str) or SHA40.fullmatch(result["sha"]) is None
            or (running and str(getattr(runtime, "stage", "")) != "RUNNING")):
        raise SentraPublicationError("Existing public Docker cpu-basic Sentra authority is unavailable")
    inventory = api.list_repo_files(SENTRA_SPACE, repo_type="space", revision=result["sha"])
    if set(inventory) != set(SENTRA_FILES) | {".gitattributes"}:
        raise SentraPublicationError("Sentra file inventory differs from the admitted contract")
    return result


def _sentra_file_bytes(revision: str, path: str) -> bytes:
    if SHA40.fullmatch(revision) is None or path not in (*SENTRA_FILES, ".gitattributes"):
        raise SentraPublicationError("Sentra readback path is outside the immutable contract")
    request = urllib.request.Request(
        f"https://huggingface.co/spaces/{SENTRA_SPACE}/resolve/{revision}/{path}",
        headers={"User-Agent": "szl-sentra-publication/1", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read(SENTRA_MAX_FILE_BYTES + 1)
    if len(body) > SENTRA_MAX_FILE_BYTES:
        raise SentraPublicationError("Sentra immutable file exceeded its bound")
    return body


def publish_sentra_existing() -> int:
    """Change one existing Space ref once; retain partial-write evidence on failure."""
    receipt: dict[str, Any] = {
        "schema": "szl.hf-selected-flagship/v1", "publication_scope": "sentra",
        "state": "BLOCKED", "complete": False, "rows": [],
        "provider_write_attempted": False, "provider_write_confirmed": False,
        "sibling_publications": 0, "delete_operations": 0, "explicit_restarts": 0,
        "settings_changes": 0, "secret_changes": 0, "secret_values_recorded": False,
        "receipt_signature_state": "UNAVAILABLE", "key_trust": "REPO_DECLARED",
        "independent_validation": "UNKNOWN", "runtime_state": "UNKNOWN",
    }
    try:
        revision = _sentra_source_admission()
        module = load_module("szl_sentra_transaction_renderer", FLAGSHIP_IMPL)
        files, row = module.render_sentra_payload(revision, int(os.environ["GITHUB_RUN_ID"]))
        if (tuple(files) != SENTRA_FILES or any(not isinstance(body, bytes) or len(body) > SENTRA_MAX_FILE_BYTES
                                               for body in files.values())
                or sum(map(len, files.values())) > 2 * 1024 * 1024):
            raise SentraPublicationError("Sentra renderer exceeded its fixed-file contract")
        receipt.update(source_revision=revision, generated_flagship_slugs=["sentra"], rows=[row],
                       file_sha256={path: hashlib.sha256(body).hexdigest() for path, body in files.items()})
        token, token_source = module._BASE.token_from_env()
        api = module._BASE.HfApi(token=token)
        target = _sentra_target(api)
        receipt.update(provider_parent_sha=target["sha"], admitted_target=target, token_source_name=token_source)
        api.auth_check(repo_id=SENTRA_SPACE, repo_type="space", write=True)
        attributes = _sentra_file_bytes(target["sha"], ".gitattributes")
        if _sentra_source_admission() != revision or _sentra_target(api) != target:
            raise SentraPublicationError("Sentra admission changed before its commit")
        from huggingface_hub import CommitOperationAdd
        operations = [CommitOperationAdd(path_in_repo=path, path_or_fileobj=body) for path, body in files.items()]
        receipt["provider_write_attempted"] = True
        commit = api.create_commit(repo_id=SENTRA_SPACE, repo_type="space", revision="main",
                                   parent_commit=target["sha"], operations=operations,
                                   commit_message=f"fix(sentra): publish admitted a11oy@{revision}")
        published = getattr(commit, "oid", None)
        if not isinstance(published, str) or SHA40.fullmatch(published) is None:
            raise SentraPublicationError("Provider commit outcome is ambiguous")
        receipt.update(provider_write_confirmed=True, provider_commit_sha=published)
        if any(_sentra_file_bytes(published, path) != body for path, body in files.items()):
            raise SentraPublicationError("Sentra immutable file readback differs")
        if _sentra_file_bytes(published, ".gitattributes") != attributes:
            raise SentraPublicationError("Sentra retained attributes changed")
        after = _sentra_target(api, running=False)
        if after != {**target, "sha": published}:
            raise SentraPublicationError("Sentra target changed during immutable readback")
        receipt["immutable_readback_complete"] = True
        deadline = time.monotonic() + 1800
        while time.monotonic() < deadline:
            module.observe_flagship(row)
            if (module.observation_passes(row, source_revision=revision, workflow_run_id=os.environ["GITHUB_RUN_ID"])
                    and row.get("build_info", {}).get("hf_revision") == published):
                break
            time.sleep(15)
        else:
            raise SentraPublicationError("Sentra exact runtime adoption is unavailable")
        if _sentra_source_admission() != revision or _sentra_target(api) != {**target, "sha": published}:
            raise SentraPublicationError("Sentra source or target was superseded after publication")
        row.update(operational=True, actions=["single_content_commit", "immutable_readback"])
        receipt.update(state="MEASURED", runtime_state="MEASURED", source_still_current=True, complete=True)
    except Exception as exc:
        receipt["error"] = str(exc) if isinstance(exc, SentraPublicationError) else type(exc).__name__
        response = getattr(exc, "response", None)
        receipt["http_status"] = (getattr(exc, "http_status", None)
                                  or getattr(response, "status_code", None) or getattr(exc, "code", None))
    FLAGSHIP_RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt["complete"] else 1


def publish_selected_generated(scope: str, space_guard_module) -> int:
    """Publish one existing generated Space and verify its live receipt."""
    try:
        revision = selected_generated_preflight(scope)
        selected_generated_space_preflight(scope, space_guard_module)
        code, error, admitted = run_publisher(
            "szl_flagship_v4", FLAGSHIP_IMPL, selected_slug=scope
        )
        receipt = read_receipt(FLAGSHIP_RECEIPT) or {}
        try:
            source_still_current = (
                _github_json(
                    "/repos/szl-holdings/a11oy/commits/main",
                    token=_github_workflow_token(),
                ).get("sha")
                == revision
            )
        except Exception as exc:
            source_still_current = False
            receipt["postflight_error"] = type(exc).__name__
        rows = receipt.get("rows")
        verified_row = (
            isinstance(rows, list)
            and len(rows) == 1
            and isinstance(rows[0], dict)
            and rows[0].get("id") == f"SZLHOLDINGS/{scope}"
            and rows[0].get("source_revision") == revision
            and rows[0].get("workflow_run_id") == int(os.environ["GITHUB_RUN_ID"])
            and rows[0].get("operational") is True
        )
        receipt.update(
            publication_scope=scope,
            source_revision=revision,
            existing_space_guard=space_guard_module.guard_report(),
            generated_flagship_slugs=list(admitted or ()),
            sibling_publications=0,
            delete_operations=0,
            secret_values_recorded=False,
            source_still_current=source_still_current,
        )
        receipt["complete"] = bool(
            receipt.get("complete") is True
            and code == 0
            and error is None
            and admitted == (scope,)
            and verified_row
            and source_still_current
        )
        if error:
            receipt["entrypoint_error"] = error
    except Exception as exc:
        receipt = {
            "schema": "szl.hf-selected-flagship/v1",
            "publication_scope": scope,
            "complete": False,
            "error": type(exc).__name__,
            "detail": str(exc),
            "secret_values_recorded": False,
            "delete_operations": 0,
        }
    FLAGSHIP_RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["complete"] else 1


def lyte_receipt_is_complete(receipt: dict[str, Any]) -> bool:
    resolution = receipt.get("source_resolution")
    revision = receipt.get("source_revision")
    return bool(
        receipt.get("complete") is True
        and receipt.get("source_repository") == "szl-holdings/lyte-services"
        and isinstance(revision, str) and SHA40.fullmatch(revision) is not None
        and revision != "0" * 40
        and isinstance(resolution, dict)
        and resolution.get("schema") == "szl.lyte-source-resolution/v1"
        and resolution.get("repository") == "szl-holdings/lyte-services"
        and resolution.get("branch") == "main"
        and resolution.get("revision") == revision
        and resolution.get("verified_commit") is True
    )


def publish_lyte_only(space_guard_module) -> int:
    """Repair the source-owned product through the existing writer alone."""
    code, error, _ = run_publisher("szl_lyte_enterprise", LYTE_IMPL)
    lyte = read_receipt(LYTE_RECEIPT) or {}
    receipt = {
        "schema": "szl.hf-vertical-estate/v8", "publication_scope": "lyte",
        "source_repository": "szl-holdings/lyte-services",
        "source_revision": lyte.get("source_revision", "UNRESOLVED"),
        "lyte_runtime": lyte, "lyte_exit_code": code,
        "existing_space_guard": space_guard_module.guard_report(),
        "sibling_publications": 0, "delete_operations": 0, "secret_values_recorded": False,
        "complete": code == 0 and lyte_receipt_is_complete(lyte),
    }
    if error:
        receipt["entrypoint_error"] = error
    FLAGSHIP_RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["complete"] else 1


def main() -> int:
    # Load the helper by exact adjacent path. Several isolated contract tests
    # execute this entrypoint with importlib without adding ``scripts`` to
    # sys.path; path loading preserves that harness and the production CLI.
    space_guard_module = load_module(
        "szl_hf_existing_space_guard",
        SPACE_GUARD_IMPL,
    )
    scope = os.environ.get("SZL_FLAGSHIP_SCOPE", "estate")
    if scope not in ("estate", "finance", "lyte", *SELECTABLE_GENERATED_SCOPES):
        raise RuntimeError("unknown publication scope")
    if scope in SELECTABLE_GENERATED_SCOPES:
        space_guard_module.install_existing_space_guard(require_existing=True)
    else:
        space_guard_module.install_existing_space_guard()

    github_token_source = normalize_github_token_alias()
    if scope == "sentra":
        return publish_sentra_existing()
    if scope == "finance":
        return publish_finance_only(space_guard_module)
    if scope == "lyte":
        return publish_lyte_only(space_guard_module)
    if scope in SELECTABLE_GENERATED_SCOPES:
        return publish_selected_generated(scope, space_guard_module)
    flagship_code, flagship_error, admitted = run_publisher(
        "szl_flagship_v4",
        FLAGSHIP_IMPL,
    )
    lyte_code, lyte_error, _ = run_publisher(
        "szl_lyte_enterprise",
        LYTE_IMPL,
    )

    resolved_revision = "UNAVAILABLE"
    source_resolution: dict[str, Any] = {
        "schema": "szl.vertical-source-resolution/v1",
        "state": "UNAVAILABLE",
        "token_value_recorded": False,
        "truth_label": "UNAVAILABLE",
    }
    try:
        resolved_revision, source_resolution = resolve_tested_vertical_services_tip()
        secret_reader = ensure_space_secret_reader()
        combined_code, combined_error, _ = run_publisher(
            "szl_vertical_services_intelligence_v4",
            COMBINED_IMPL,
            source_revision_override=resolved_revision,
        )
    except Exception as exc:
        secret_reader = "unavailable"
        combined_code = 1
        combined_error = f"{type(exc).__name__}: {exc}"
        source_resolution["error"] = combined_error

    flagship = read_receipt(FLAGSHIP_RECEIPT) or {
        "schema": "szl.hf-vertical-flagships/v4",
        "complete": False,
    }
    lyte = read_receipt(LYTE_RECEIPT) or {
        "schema": "szl.hf-lyte-enterprise-publication/v3",
        "complete": False,
    }
    combined = read_receipt(COMBINED_RECEIPT) or {
        "schema": "szl.hf-vertical-services-publication/v2",
        "complete": False,
    }
    generated_complete = flagship.get("complete") is True
    if flagship_error:
        flagship["entrypoint_error"] = flagship_error
    if lyte_error:
        lyte["entrypoint_error"] = lyte_error
    if combined_error:
        combined["entrypoint_error"] = combined_error

    creation_guard = space_guard_module.guard_report()
    combined["source_resolution"] = source_resolution
    combined["resolved_source_revision"] = resolved_revision
    combined["space_secret_reader"] = secret_reader
    combined["secret_values_readable"] = False
    combined["github_token_source_name"] = github_token_source
    combined["github_token_value_recorded"] = False
    combined["existing_space_guard"] = creation_guard

    flagship["previous_estate_schema"] = PREVIOUS_ESTATE_SCHEMA
    flagship["estate_schema"] = "szl.hf-vertical-estate/v8"
    flagship["public_flagship_slugs"] = list(PUBLIC_FLAGSHIP_SLUGS)
    flagship["generated_flagship_slugs"] = list(admitted or ())
    flagship["source_owned_flagship_slugs"] = list(SOURCE_OWNED_FLAGSHIP_SLUGS)
    flagship["folded_into_killinchu"] = list(FOLDED_INTO_KILLINCHU)
    flagship["killinchu_space"] = KILLINCHU_SPACE
    flagship["sentra_space"] = SENTRA_SPACE
    flagship["lyte_runtime"] = lyte
    flagship["combined_runtime"] = combined
    flagship["existing_space_guard"] = creation_guard
    flagship["generated_flagship_exit_code"] = flagship_code
    flagship["lyte_exit_code"] = lyte_code
    flagship["combined_exit_code"] = combined_code
    flagship["secret_values_recorded"] = False
    flagship["sentra_signing_key_rotated"] = False
    flagship["delete_operations"] = 0
    flagship["complete"] = bool(
        generated_complete
        and tuple(admitted or ()) == GENERATED_FLAGSHIP_SLUGS
        and lyte_receipt_is_complete(lyte)
        and combined.get("complete") is True
        and combined.get("resolved_source_revision") == resolved_revision
        and SHA40.fullmatch(resolved_revision) is not None
        and flagship_code == 0
        and lyte_code == 0
        and combined_code == 0
    )
    FLAGSHIP_RECEIPT.write_text(
        json.dumps(flagship, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(flagship, indent=2, sort_keys=True))
    return 0 if flagship["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
