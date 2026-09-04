#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Canonical vertical estate publisher.

The established Domain Experience v4 implementation remains the renderer, but
the entrypoint admits only the four independent public vertical Spaces. Sentra
and Vessels are capability planes inside Killinchu and are filtered before any
Hugging Face mutation. The same single-writer job then publishes and attests the
combined six-engine frontier-v3 runtime from the exact merged vertical-services
revision.

This distinction is intentional: one public product surface does not require one
undifferentiated code module. Sentra and maritime contracts remain independently
testable engines inside the combined runtime while their public front door is
Killinchu.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

HERE = Path(__file__).resolve().parent
FLAGSHIP_IMPL = HERE / "hf_publish_vertical_flagships_v4_impl.py"
BASE_COMBINED_IMPL = HERE / "hf_publish_vertical_services.py"
COMBINED_IMPL = HERE / "hf_publish_vertical_services_frontier_v3.py"
FLAGSHIP_RECEIPT = Path("hf-vertical-flagships-receipt.json")
COMBINED_RECEIPT = Path("hf-vertical-services-receipt.json")

PUBLIC_FLAGSHIP_SLUGS = ("terra", "counsel", "finance", "lyte")
FOLDED_INTO_KILLINCHU = ("sentra", "vessels")
KILLINCHU_SPACE = "SZLHOLDINGS/killinchu"


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


def run_publisher(
    name: str,
    path: Path,
) -> tuple[int, str | None, tuple[str, ...] | None]:
    admitted: tuple[str, ...] | None = None
    try:
        module = load_module(name, path)
        if name == "szl_flagship_v4":
            admitted = constrain_public_flagships(module)
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


def main() -> int:
    flagship_code, flagship_error, admitted = run_publisher(
        "szl_flagship_v4",
        FLAGSHIP_IMPL,
    )

    try:
        secret_reader = ensure_space_secret_reader()
        combined_code, combined_error, _ = run_publisher(
            "szl_vertical_services_frontier_v3",
            COMBINED_IMPL,
        )
    except Exception as exc:
        secret_reader = "unavailable"
        combined_code = 1
        combined_error = f"{type(exc).__name__}: {exc}"

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

    combined["space_secret_reader"] = secret_reader
    combined["secret_values_readable"] = False
    flagship["estate_schema"] = "szl.hf-vertical-estate/v6"
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
