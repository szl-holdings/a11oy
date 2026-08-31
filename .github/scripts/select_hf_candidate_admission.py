#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Select the protected-base HF candidate admission authority by exact tree delta.

The selector itself executes from the immutable protected-base checkout. It
never imports candidate code. The narrow RFC 9116 successor is selected only
when `.well-known/security.txt` is the sole changed protected candidate input;
every other candidate remains delegated to the established controller.
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from types import ModuleType

SCRIPT_DIR = Path(__file__).resolve().parent
BASE_CONTROLLER_PATH = SCRIPT_DIR / "verify_hf_candidate_admission.py"
SECURITY_CONTROLLER_PATH = (
    SCRIPT_DIR / "verify_hf_security_candidate_admission.py"
)
SECURITY_PATH = ".well-known/security.txt"


class SelectionError(RuntimeError):
    """Raised when protected-base admission selection cannot be established."""


def _load(name: str, path: Path) -> ModuleType:
    if not path.is_file():
        raise SelectionError(f"protected-base admission module is absent: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SelectionError(f"cannot load protected-base admission module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_controllers() -> tuple[ModuleType, ModuleType]:
    return (
        _load("protected_base_hf_candidate_admission", BASE_CONTROLLER_PATH),
        _load("protected_base_hf_security_admission", SECURITY_CONTROLLER_PATH),
    )


def protected_delta(
    verifier: ModuleType,
    *,
    github_repo: str,
    base_ref: str,
    github_ref: str,
) -> list[str]:
    verifier.verify_ancestry(
        github_repo,
        base_ref=base_ref,
        github_ref=github_ref,
    )
    base_tree = verifier.github_blob_tree(github_repo, github_ref=base_ref)
    head_tree = verifier.github_blob_tree(github_repo, github_ref=github_ref)
    return sorted(
        path
        for path in tuple(verifier.PROTECTED_CANDIDATE_INPUTS)
        if base_tree.get(path) != head_tree.get(path)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tools-script", type=Path, required=True)
    parser.add_argument("--github-repo", required=True)
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--github-ref", required=True)
    parser.add_argument("--hf-repo", required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    args = parser.parse_args(argv)

    base_controller, security_controller = load_controllers()
    verifier = base_controller.load_verifier()
    changed = protected_delta(
        verifier,
        github_repo=args.github_repo,
        base_ref=args.base_ref,
        github_ref=args.github_ref,
    )
    delegated = [
        "--tools-script",
        str(args.tools_script),
        "--github-repo",
        args.github_repo,
        "--base-ref",
        args.base_ref,
        "--github-ref",
        args.github_ref,
        "--hf-repo",
        args.hf_repo,
        "--report-out",
        str(args.report_out),
    ]
    if changed == [SECURITY_PATH]:
        print(
            "HF candidate admission selector: exact protected security successor"
        )
        return security_controller.main(delegated)

    print(
        "HF candidate admission selector: established general controller "
        f"(protected_delta={changed!r})"
    )
    return base_controller.main(delegated)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)
