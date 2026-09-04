#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Canonical vertical estate publisher.

The established Domain Experience v4 implementation remains the renderer, but
the entrypoint admits only the four independent public vertical Spaces. Sentra
and Vessels are capability planes inside Killinchu and are filtered before any
Hugging Face mutation. The same single-writer job then publishes and attests the
combined six-engine Python intelligence runtime from the exact tested
vertical-services default-branch tip observed at deployment time.

The observed source revision is immutable for the run and the downstream
publisher still requires that revision to remain the repository default-branch
tip. If source advances during publication, the existing default-tip guard fails
closed rather than deploying a stale or mixed build.

This distinction is intentional: one public product surface does not require one
undifferentiated code module. Sentra and maritime contracts remain independently
testable engines inside the combined runtime while their public front door is
Killinchu. Models propose, kernels constrain, Hatun reviews, and humans retain
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
BASE_COMBINED_IMPL = HERE / "hf_publish_vertical_services.py"
COMBINED_IMPL = HERE / "hf_publish_vertical_services_intelligence_v4.py"
FLAGSHIP_RECEIPT = Path("hf-vertical-flagships-receipt.json")
COMBINED_RECEIPT = Path("hf-vertical-services-receipt.json")

PUBLIC_FLAGSHIP_SLUGS = ("terra", "counsel", "finance", "lyte")
FOLDED_INTO_KILLINCHU = ("sentra", "vessels")
KILLINCHU_SPACE = "SZLHOLDINGS/killinchu"
VERTICAL_SERVICES_REPOSITORY = "szl-holdings/vertical-services"
GITHUB_API = "https://api.github.com"
SHA40 = re.compile(r"^[0-9a-f]{40}$")


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load publisher module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def constrain_public_flagships(module: ModuleType) -> tuple[str, ...]:
    """Remove Killinchu capability planes before the provider writer can run."""
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

    admitted = tuple(by_slug[slug] for slug in PUBLIC_FLAGSHIP_SLUGS)
    if any(item["slug"] in FOLDED_INTO_KILLINCHU for item in admitted):
        raise RuntimeError("retired Killinchu capability plane reached public writer")
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
    token = os.getenv("GITHUB_TOKEN", "").strip() or os.getenv("GH_TOKEN", "").strip()
    ref = _github_json(
        f"/repos/{VERTICAL_SERVICES_REPOSITORY}/git/ref/heads/main",
        token=token or None,
    )
    revision = str(ref.get("object", {}).get("sha", "")).lower()
    if SHA40.fullmatch(revision) is None:
        raise RuntimeError("vertical-services main did not resolve to a full Git SHA")

    checks = _github_json(
        f"/repos/{VERTICAL_SERVICES_REPOSITORY}/commits/{revision}/check-runs?per_page=100",
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
) -> tuple[int, str | None, tuple[str, ...] | None]:
    admitted: tuple[str, ...] | None = None
    try:
        module = load_module(name, path)
        if name == "szl_flagship_v4":
            admitted = constrain_public_flagships(module)
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
    """Expose the ephemeral workflow token under the nested guard's name.

    The canonical workflow exports ``GH_TOKEN`` for GitHub CLI operations while
    the pinned exact-source deployment controller deliberately reads
    ``GITHUB_TOKEN`` for its default-branch-tip proof. Values never leave the
    current process and are never written to a receipt.
    """
    canonical = os.getenv("GITHUB_TOKEN", "").strip()
    if canonical:
        return "GITHUB_TOKEN"

    cli_token = os.getenv("GH_TOKEN", "").strip()
    if cli_token:
        os.environ["GITHUB_TOKEN"] = cli_token
        return "GH_TOKEN"

    return "unavailable"


def main() -> int:
    github_token_source = normalize_github_token_alias()
    flagship_code, flagship_error, admitted = run_publisher(
        "szl_flagship_v4",
        FLAGSHIP_IMPL,
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
    combined = read_receipt(COMBINED_RECEIPT) or {
        "schema": "szl.hf-vertical-services-publication/v2",
        "complete": False,
    }
    if flagship_error:
        flagship["entrypoint_error"] = flagship_error
    if combined_error:
        combined["entrypoint_error"] = combined_error

    combined["source_resolution"] = source_resolution
    combined["resolved_source_revision"] = resolved_revision
    combined["space_secret_reader"] = secret_reader
    combined["secret_values_readable"] = False
    combined["github_token_source_name"] = github_token_source
    combined["github_token_value_recorded"] = False
    flagship["estate_schema"] = "szl.hf-vertical-estate/v7"
    flagship["public_flagship_slugs"] = list(admitted or ())
    flagship["folded_into_killinchu"] = list(FOLDED_INTO_KILLINCHU)
    flagship["killinchu_space"] = KILLINCHU_SPACE
    flagship["combined_runtime"] = combined
    flagship["flagship_exit_code"] = flagship_code
    flagship["combined_exit_code"] = combined_code
    flagship["complete"] = bool(
        flagship.get("complete") is True
        and tuple(flagship.get("public_flagship_slugs", ()))
        == PUBLIC_FLAGSHIP_SLUGS
        and combined.get("complete") is True
        and combined.get("resolved_source_revision") == resolved_revision
        and SHA40.fullmatch(resolved_revision) is not None
        and flagship_code == 0
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
