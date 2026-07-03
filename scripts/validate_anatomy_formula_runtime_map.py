#!/usr/bin/env python3
"""Validate the anatomy/formula/runtime map.

The validator is intentionally lightweight and offline. It verifies that the
map has the expected structure, that referenced theorem-runtime IDs exist, and
that active local runtime/test paths are present in this checkout.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = REPO_ROOT / "docs" / "anatomy-formula-runtime-map.json"
THEOREM_MANIFEST_PATH = REPO_ROOT / "docs" / "theorem-runtime-manifest.json"

# --- stub / fake-runtime detection -----------------------------------------
#
# A `runtimeFile` that claims verified-runtime must resolve to REAL code, not a
# placeholder. History: amaru's /codex-loop aliased `@workspace/codex-kernel`
# (in organs/amaru/web/vite.config.ts) to a divergent look-alike stub under
# src/_stubs/ with a home-grown non-crypto `simpleHash`/`fullHash` and no proof
# ledger — a "verified" surface backed by a fake. The old validator only did a
# JSON-shape + Path.exists() check and could never have caught it.
#
# So: a runtimeFile may be a repo-relative path OR a TS module specifier that we
# resolve through the same alias tables the bundler uses (vite.config.ts
# resolve.alias + tsconfig compilerOptions.paths). Whatever it resolves to is
# then screened for stub markers.

# Substrings that only appear in the fake kernel, never in the attested one
# (which uses hashString / hashJson / chainHash). Precise on purpose so real
# gate code is never mislabelled.
STUB_CONTENT_DENYLIST = (
    "simpleHash",
    "fullHash",
    "FAKE_KERNEL",
    "MOCK_KERNEL",
    "mocked-receipt",
)
# A module whose meaningful (comment/space-stripped) body is shorter than this
# is treated as an empty/near-empty stub (e.g. `export {};`).
STUB_MIN_MEANINGFUL_CHARS = 24


def _strip_ts_noise(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    return re.sub(r"\s+", "", text)


def is_stub_module(path: Path) -> str | None:
    """Return a human-readable reason if `path` looks like a stub, else None."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    stripped = text.strip()
    if stripped in ("", "export {};", "export {}", "module.exports = {};"):
        return "empty stub"
    meaningful = _strip_ts_noise(text)
    if len(meaningful) < STUB_MIN_MEANINGFUL_CHARS:
        return "near-empty stub"
    for marker in STUB_CONTENT_DENYLIST:
        if marker in text:
            return f"contains stub/fake marker {marker!r}"
    return None


def _resolve_alias_target(config_dir: Path, target: str) -> Path | None:
    candidate = (config_dir / target).resolve()
    if candidate.is_file():
        return candidate
    ts = candidate.with_suffix(".ts")
    if ts.is_file():
        return ts
    index = candidate / "index.ts"
    if index.is_file():
        return index
    return None


def _parse_vite_aliases(repo_root: Path) -> dict[str, Path]:
    """Parse `resolve.alias` entries from every organs/*/web/vite.config.ts.

    Matches: '<alias>': path.resolve(import.meta.dirname, '<target>')."""
    aliases: dict[str, Path] = {}
    pattern = re.compile(
        r"""['"]([^'"]+)['"]\s*:\s*path\.resolve\(\s*import\.meta\.dirname\s*,\s*['"]([^'"]+)['"]\s*\)"""
    )
    for config in repo_root.glob("organs/*/web/vite.config.ts"):
        try:
            text = config.read_text(encoding="utf-8")
        except OSError:
            continue
        for alias, target in pattern.findall(text):
            resolved = _resolve_alias_target(config.parent, target)
            if resolved is not None:
                aliases.setdefault(alias, resolved)
    return aliases


def _parse_tsconfig_paths(repo_root: Path) -> dict[str, Path]:
    aliases: dict[str, Path] = {}
    for tsconfig in repo_root.glob("organs/*/web/tsconfig*.json"):
        try:
            raw = tsconfig.read_text(encoding="utf-8")
        except OSError:
            continue
        # tolerate trailing commas / comments only loosely — best effort
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        paths = (data.get("compilerOptions", {}) or {}).get("paths", {}) or {}
        for alias, targets in paths.items():
            if not targets:
                continue
            key = alias.rstrip("/*")
            resolved = _resolve_alias_target(tsconfig.parent, str(targets[0]).rstrip("*"))
            if resolved is not None:
                aliases.setdefault(key, resolved)
    return aliases


def resolve_runtime_target(runtime_file: str, repo_root: Path) -> Path | None:
    """Resolve a runtimeFile to a concrete file: first as a repo-relative path,
    then as a TS module specifier via vite/tsconfig alias tables."""
    direct = repo_root / runtime_file
    if direct.exists():
        return direct
    aliases = {**_parse_tsconfig_paths(repo_root), **_parse_vite_aliases(repo_root)}
    if runtime_file in aliases:
        return aliases[runtime_file]
    # allow `<alias>/sub/path` style specifiers
    for alias, base in aliases.items():
        if runtime_file.startswith(alias + "/"):
            return base
    return None

ALLOWED_CLAIM_STATUSES = {
    "verified-runtime",
    "release-payload",
    "lean-backed-current-green",
    "lean-backed-needs-upstream-ci",
    "lean-backed-needs-runtime",
    "thesis-anchor",
    "historical",
    "historical-roadmap",
    "roadmap",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []
    data = load_json(MAP_PATH)
    theorem_manifest = load_json(THEOREM_MANIFEST_PATH)
    theorem_ids = {entry["id"] for entry in theorem_manifest.get("entries", [])}

    required_top = {
        "schemaVersion",
        "generatedBy",
        "observedAt",
        "canonicalHub",
        "canonicalRule",
        "autonomousLearningDoctrine",
        "organs",
    }
    missing_top = sorted(required_top - data.keys())
    if missing_top:
        errors.append(f"missing top-level fields: {', '.join(missing_top)}")

    if data.get("canonicalHub") != "a11oy":
        errors.append("canonicalHub must be a11oy")

    doctrine = data.get("autonomousLearningDoctrine", {})
    if doctrine.get("promotionModel") != "human_promotion_required":
        errors.append("autonomousLearningDoctrine.promotionModel must require human promotion")
    forbidden_modes = set(doctrine.get("forbiddenModes", []))
    for mode in ["self_approve", "self_promote", "deploy", "publish"]:
        if mode not in forbidden_modes:
            errors.append(f"autonomousLearningDoctrine.forbiddenModes missing {mode}")

    organs = data.get("organs", [])
    if not isinstance(organs, list) or not organs:
        errors.append("organs must be a non-empty list")

    repos = set()
    required_organ = {
        "repo",
        "anatomyRole",
        "formulaRuntime",
        "theoremAnchors",
        "receiptSurface",
        "testEvidence",
        "udsStage",
        "hfStage",
        "claimStatus",
        "autonomousLearningRole",
        "gaps",
    }

    for organ in organs:
        repo = organ.get("repo", "<missing>")
        if repo in repos:
            errors.append(f"duplicate organ repo: {repo}")
        repos.add(repo)

        missing = sorted(required_organ - organ.keys())
        if missing:
            errors.append(f"{repo}: missing fields: {', '.join(missing)}")

        status = organ.get("claimStatus")
        if status not in ALLOWED_CLAIM_STATUSES:
            errors.append(f"{repo}: unsupported claimStatus {status!r}")

        for collection_name in [
            "formulaRuntime",
            "theoremAnchors",
            "receiptSurface",
            "testEvidence",
            "gaps",
        ]:
            if not isinstance(organ.get(collection_name), list):
                errors.append(f"{repo}: {collection_name} must be a list")

        for formula in organ.get("formulaRuntime", []):
            formula_status = formula.get("claimStatus")
            if formula_status not in ALLOWED_CLAIM_STATUSES:
                errors.append(
                    f"{repo}/{formula.get('formula', '<formula>')}: unsupported claimStatus {formula_status!r}"
                )

            manifest_id = formula.get("theoremRuntimeManifestId")
            if manifest_id is not None and manifest_id not in theorem_ids:
                errors.append(
                    f"{repo}/{formula.get('formula', '<formula>')}: unknown theoremRuntimeManifestId {manifest_id}"
                )

            runtime_file = formula.get("runtimeFile")
            if runtime_file:
                fname = formula.get("formula", "<formula>")
                resolved = resolve_runtime_target(runtime_file, REPO_ROOT)
                if resolved is None:
                    errors.append(
                        f"{repo}/{fname}: runtimeFile does not exist and no vite/tsconfig alias resolves it: {runtime_file}"
                    )
                else:
                    stub_reason = is_stub_module(resolved)
                    if stub_reason is not None:
                        rel = resolved
                        try:
                            rel = resolved.relative_to(REPO_ROOT)
                        except ValueError:
                            pass
                        # A verified-runtime claim backed by a stub is the exact
                        # amaru-fake failure mode — hard fail. Non-verified
                        # statuses are still flagged (a stub can never be the
                        # runtime for any live claim).
                        errors.append(
                            f"{repo}/{fname}: runtimeFile {runtime_file!r} resolves to a stub ({stub_reason}): {rel}"
                        )

    required_repos = {"a11oy", "lutar-lean", "ouroboros-thesis", "agi-forecast"}
    missing_repos = sorted(required_repos - repos)
    if missing_repos:
        errors.append(f"missing required organ repos: {', '.join(missing_repos)}")

    if errors:
        print("Anatomy/formula/runtime map validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"Validated {MAP_PATH.relative_to(REPO_ROOT)} ({len(organs)} organs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
