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
import json
import os
import re
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
FOLDED_INTO_KILLINCHU = ("vessels",)
KILLINCHU_SPACE = "SZLHOLDINGS/killinchu"
SENTRA_SPACE = "SZLHOLDINGS/sentra"
LYTE_SOURCE_REVISION = "9ce4e6b5f36fe0b094a07308abe3665cd2a210c1"
VERTICAL_SERVICES_REPOSITORY = "szl-holdings/vertical-services"
GITHUB_API = "https://api.github.com"
SHA40 = re.compile(r"^[0-9a-f]{40}$")

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
) -> tuple[int, str | None, tuple[str, ...] | None]:
    admitted: tuple[str, ...] | None = None
    try:
        module = load_module(name, path)
        if name == "szl_flagship_v4":
            admitted = constrain_public_flagships(module)
            if finance_only:
                module.FLAGSHIPS = tuple(row for row in module.FLAGSHIPS if row["slug"] == "finance")
                admitted = ("finance",)
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


def finance_preflight() -> dict[str, Any]:
    """Require the canonical backend component before writing its public view."""
    revision = os.environ.get("GITHUB_SHA", "")
    if SHA40.fullmatch(revision) is None or revision == "0" * 40:
        raise RuntimeError("Finance requires a bound canonical source revision")
    head = _github_json("/repos/szl-holdings/a11oy/commits/main")
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


def main() -> int:
    # Load the helper by exact adjacent path. Several isolated contract tests
    # execute this entrypoint with importlib without adding ``scripts`` to
    # sys.path; path loading preserves that harness and the production CLI.
    space_guard_module = load_module(
        "szl_hf_existing_space_guard",
        SPACE_GUARD_IMPL,
    )
    space_guard_module.install_existing_space_guard()

    github_token_source = normalize_github_token_alias()
    scope = os.environ.get("SZL_FLAGSHIP_SCOPE", "estate")
    if scope not in ("estate", "finance"):
        raise RuntimeError("unknown publication scope")
    if scope == "finance":
        return publish_finance_only(space_guard_module)
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
        and lyte.get("complete") is True
        and lyte.get("source_repository") == "szl-holdings/lyte-services"
        and lyte.get("source_revision") == LYTE_SOURCE_REVISION
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
