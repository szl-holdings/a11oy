#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Canonical vertical estate publisher.

The established Domain Experience v4 publisher runs unchanged first. The same
single-writer job then publishes and attests the combined six-engine runtime
from the exact merged vertical-services revision.
"""
from __future__ import annotations

import importlib.util
import json
import urllib.request
from pathlib import Path
from types import ModuleType
from typing import Any

HERE = Path(__file__).resolve().parent
FLAGSHIP_IMPL = HERE / "hf_publish_vertical_flagships_v4_impl.py"
COMBINED_IMPL = HERE / "hf_publish_vertical_services.py"
FLAGSHIP_RECEIPT = Path("hf-vertical-flagships-receipt.json")
COMBINED_RECEIPT = Path("hf-vertical-services-receipt.json")


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load publisher module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalize_space_secret_metadata(payload: Any) -> dict[str, Any]:
    """Normalize the Hub's metadata-only secret response without secret values."""
    if isinstance(payload, dict) and "secrets" in payload:
        payload = payload["secrets"]
    if isinstance(payload, dict):
        return {str(key): value for key, value in payload.items()}
    if isinstance(payload, list):
        normalized: dict[str, Any] = {}
        for item in payload:
            if isinstance(item, str):
                normalized[item] = {"key": item}
            elif isinstance(item, dict) and item.get("key"):
                normalized[str(item["key"])] = item
        return normalized
    raise RuntimeError("unexpected Hugging Face Space secret metadata response")


def install_hf_space_secret_metadata_compat() -> None:
    """Backport metadata-only secret listing for the pinned publisher client.

    `huggingface_hub` releases before 1.14.0 do not expose
    ``HfApi.get_space_secrets`` even though the authenticated Hub endpoint is
    available. The canonical writer pins an older client for reproducibility,
    so install a narrowly scoped compatibility method only when absent. The
    endpoint returns names/descriptions/timestamps; values remain write-only.
    """
    from huggingface_hub import HfApi

    if hasattr(HfApi, "get_space_secrets"):
        return

    def get_space_secrets(
        self: Any,
        repo_id: str,
        token: bool | str | None = None,
    ) -> dict[str, Any]:
        resolved = token if isinstance(token, str) else getattr(self, "token", None)
        if not isinstance(resolved, str) or not resolved.strip():
            raise RuntimeError("Space secret metadata listing requires authentication")
        endpoint = str(getattr(self, "endpoint", "https://huggingface.co")).rstrip("/")
        request = urllib.request.Request(
            f"{endpoint}/api/spaces/{repo_id}/secrets",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {resolved}",
                "Cache-Control": "no-cache",
                "User-Agent": "SZLHOLDINGS-Canonical-Vertical-Publisher/1.0",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status != 200:
                raise RuntimeError(
                    f"Space secret metadata request failed: HTTP {response.status}"
                )
            payload = json.loads(response.read())
        return normalize_space_secret_metadata(payload)

    setattr(HfApi, "get_space_secrets", get_space_secrets)


def run_publisher(name: str, path: Path) -> tuple[int, str | None]:
    try:
        module = load_module(name, path)
        result = int(module.main())
        return result, None
    except SystemExit as exc:
        code = 0 if exc.code is None else int(exc.code)
        return code, None
    except Exception as exc:
        return 1, f"{type(exc).__name__}: {exc}"


def read_receipt(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def main() -> int:
    install_hf_space_secret_metadata_compat()
    flagship_code, flagship_error = run_publisher("szl_flagship_v4", FLAGSHIP_IMPL)
    combined_code, combined_error = run_publisher("szl_vertical_services", COMBINED_IMPL)

    flagship = read_receipt(FLAGSHIP_RECEIPT) or {
        "schema": "szl.hf-vertical-flagships/v4",
        "complete": False,
    }
    combined = read_receipt(COMBINED_RECEIPT) or {
        "schema": "szl.hf-vertical-services-publication/v1",
        "complete": False,
    }
    if flagship_error:
        flagship["entrypoint_error"] = flagship_error
    if combined_error:
        combined["entrypoint_error"] = combined_error

    flagship["estate_schema"] = "szl.hf-vertical-estate/v5"
    flagship["combined_runtime"] = combined
    flagship["flagship_exit_code"] = flagship_code
    flagship["combined_exit_code"] = combined_code
    flagship["complete"] = bool(
        flagship.get("complete") is True
        and combined.get("complete") is True
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
