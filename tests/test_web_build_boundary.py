from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PLATFORM_SHA = "6e0dc7b423fbcfb2c165348e60b41cd55a9b9ace"


def _submodule_head() -> str:
    marker = (REPO_ROOT / "vendor" / "platform" / ".git").read_text(
        encoding="utf-8"
    )
    prefix = "gitdir: "
    assert marker.startswith(prefix)
    git_dir = (REPO_ROOT / "vendor" / "platform" / marker[len(prefix) :].strip()).resolve()
    head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
    if not head.startswith("ref: "):
        return head
    ref = head.removeprefix("ref: ")
    loose_ref = git_dir / ref
    if loose_ref.exists():
        return loose_ref.read_text(encoding="utf-8").strip()
    for line in (git_dir / "packed-refs").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith(("#", "^")):
            commit, name = line.split(" ", maxsplit=1)
            if name == ref:
                return commit
    raise AssertionError(f"missing submodule ref {ref}")


def test_canonical_web_source_is_pinned_and_initialized() -> None:
    gitmodules = (REPO_ROOT / ".gitmodules").read_text(encoding="utf-8")
    assert '[submodule "vendor/platform"]' in gitmodules
    assert "https://github.com/szl-holdings/platform.git" in gitmodules
    assert _submodule_head() == EXPECTED_PLATFORM_SHA


def test_web_build_scripts_use_the_pinned_platform_package_manager() -> None:
    package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    scripts = package["scripts"]
    assert scripts["web:source:verify"] == "node scripts/verify_web_source.mjs"
    assert "pnpm@10.26.1" in scripts["web:install"]
    assert "--frozen-lockfile" in scripts["web:install"]
    assert "vendor/platform" in scripts["build:web"]
    assert "@workspace/a11oy" in scripts["build:web"]


def test_legacy_mirror_is_not_the_declared_clean_build_target() -> None:
    package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    assert "pnpm --dir web build" not in package["scripts"]["build:web"]
