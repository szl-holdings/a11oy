#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the HF free-tier recovery with an exact personal-runtime target.

The reviewed v4 publisher returns the frontier-v3 wrapper. That wrapper loads the
base publisher only when ``main`` executes, so assigning target fields directly
to the wrapper does not reach the base deployment module. This entrypoint binds
the personal repository, origin, and receipt path at that deferred load boundary
before any Hugging Face mutation occurs, then delegates all existing source,
health, receipt, and gateway checks to the canonical recovery implementation.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
RECOVERY_IMPL = ROOT / "scripts" / "hf_recover_vertical_estate_free_tier.py"


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def bind_deferred_personal_base(
    recovery: ModuleType,
    publisher: ModuleType,
    *,
    repo_id: str,
    origin: str,
) -> None:
    """Bind the target on the base module loaded later by frontier-v3 ``main``."""
    original_load_base: Callable[[], ModuleType] = publisher.load_base

    def load_personal_base() -> ModuleType:
        base = original_load_base()
        base.HF_REPOSITORY = repo_id
        base.ORIGIN = origin
        base.RECEIPT_PATH = recovery.RUNTIME_RECEIPT_PATH
        return base

    publisher.load_base = load_personal_base


def install_personal_runtime_deployer(recovery: ModuleType) -> ModuleType:
    """Replace only the incorrectly targeted runtime step; preserve all other logic."""
    original_loader = recovery.load_module

    def deploy_personal_runtime(token: str, owner: str) -> dict[str, Any]:
        wrapper = original_loader(
            recovery.INTELLIGENCE_PUBLISHER,
            "szl_hf_intelligence_v4_personal_runtime",
        )
        wrapper.SOURCE_REVISION = recovery.RUNTIME_SOURCE_REVISION
        wrapper.EXPECTED_VERSION = recovery.RUNTIME_VERSION
        publisher = wrapper.configure_v4(wrapper.load_v3())

        if publisher.SOURCE_REVISION != recovery.RUNTIME_SOURCE_REVISION:
            raise RuntimeError("configured publisher retained a stale source revision")
        if publisher.EXPECTED_VERSION != recovery.RUNTIME_VERSION:
            raise RuntimeError("configured publisher retained a stale runtime version")

        repo_id = f"{owner}/{recovery.RUNTIME_SLUG}"
        origin = recovery.space_origin(repo_id)
        publisher.USER_AGENT = recovery.USER_AGENT
        bind_deferred_personal_base(
            recovery,
            publisher,
            repo_id=repo_id,
            origin=origin,
        )

        # The nested canonical publisher obtains its token from the environment.
        # Preserve the admitted value without printing or persisting it.
        os.environ["HF_TOKEN"] = token
        exit_code = int(publisher.main())
        if not recovery.RUNTIME_RECEIPT_PATH.is_file():
            raise RuntimeError("personal runtime publisher did not emit its receipt")
        receipt = json.loads(
            recovery.RUNTIME_RECEIPT_PATH.read_text(encoding="utf-8")
        )
        if not isinstance(receipt, dict):
            raise RuntimeError("personal runtime receipt is not an object")
        if exit_code != 0 or receipt.get("complete") is not True:
            raise RuntimeError("personal vertical runtime did not pass exact-source live proof")
        if receipt.get("hf_repository") != repo_id:
            raise RuntimeError("personal runtime receipt names the wrong HF repository")
        if receipt.get("origin") != origin:
            raise RuntimeError("personal runtime receipt names the wrong public origin")
        if receipt.get("source_revision") != recovery.RUNTIME_SOURCE_REVISION:
            raise RuntimeError("personal runtime receipt names the wrong source revision")

        return {
            "repo_id": repo_id,
            "origin": origin,
            "source_revision": recovery.RUNTIME_SOURCE_REVISION,
            "version": recovery.RUNTIME_VERSION,
            "receipt": receipt,
        }

    recovery.deploy_personal_runtime = deploy_personal_runtime
    return recovery


def main() -> int:
    recovery = load_module(
        RECOVERY_IMPL,
        "szl_hf_free_tier_recovery_personal_runtime",
    )
    return int(install_personal_runtime_deployer(recovery).main())


if __name__ == "__main__":
    raise SystemExit(main())
