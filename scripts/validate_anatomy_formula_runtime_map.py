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
    # `wired-shared`: the organ references a SHARED a11oy hub gate/witness file for
    # compatibility, but its own production runtime lives upstream and is not
    # verified in this checkout. This is the honest label for a cross-repo organ
    # that would otherwise borrow an a11oy `packages/*` gate to look verified.
    "wired-shared",
    "release-payload",
    "lean-backed-current-green",
    "lean-backed-needs-upstream-ci",
    "lean-backed-needs-runtime",
    "thesis-anchor",
    "historical",
    "historical-roadmap",
    "roadmap",
}

# --- RULE 1: own-repo / no-borrowing ---------------------------------------
#
# Cross-repo organs (rosie, amaru, sentra, ...) historically claimed
# `verified-runtime` while pointing `runtimeFile` at a11oy's OWN shared gate
# tree (packages/policy/*_gate.ts, packages/qec-integrity/*.ts). Path.exists()
# passed because the file is a11oy's — the organ borrowed a hub file to look
# wired. A verified-runtime claim must resolve to code the organ actually owns:
# its own subtree under organs/<repo>/ (for in-repo subtree organs) or its own
# upstream repo (a genuinely cross-repo file we cannot borrow from here). A
# runtimeFile that lands in a11oy's shared hub library tree is "borrowed".
SHARED_HUB_LIBRARY_DIRS = ("packages",)

# --- RULE 2: earned status needs a live route ------------------------------
#
# Files that actually register the served HTTP routes. A `verified-runtime`
# organ must declare a `live_route`, and that route must appear in one of these
# routers (offline grep — no network calls). Route literals are namespace
# templated in code (Route("/api/%s/v1/agent/cycle" % ns, ...)), so the hub
# segment is matched flexibly.
ROUTER_FILE_CANDIDATES = (
    "serve.py",
    "szl_agentic_loop.py",
    "szl_ken.py",
)
ROUTER_GLOB_CANDIDATES = (
    "organs/*/serve.py",
    "*_router.py",
)

# --- RULE 3: receipt-flow (advisory) ---------------------------------------
#
# A verified-runtime organ SHOULD emit/record a receipt (szl-receipt / szl-lake
# / a DSSE sign path). Advisory only: if no receipt evidence is found the map is
# annotated `receipt: none` (warning) so the body honestly shows which organs
# are receipted — it never hard-fails.
RECEIPT_MARKERS = (
    "receipt",
    "dsse",
    "szl-receipt",
    "szl-lake",
    "sign",
    "khipu",
)


def _organ_own_subtree(repo: str, repo_root: Path) -> Path | None:
    subtree = repo_root / "organs" / repo
    return subtree if subtree.is_dir() else None


def is_borrowed_hub_file(resolved: Path, repo: str, repo_root: Path) -> bool:
    """True if a non-a11oy organ's runtimeFile lands in a11oy's shared hub
    library tree instead of the organ's own subtree/repo (RULE 1 borrowing)."""
    if repo == "a11oy":
        return False  # the hub owns its shared gates
    try:
        rel = resolved.resolve().relative_to(repo_root.resolve())
    except ValueError:
        # Resolves outside this checkout -> a genuinely cross-repo own file,
        # not something borrowed from a11oy here.
        return False
    own = _organ_own_subtree(repo, repo_root)
    if own is not None:
        try:
            resolved.resolve().relative_to(own.resolve())
            return False  # under the organ's own subtree -> not borrowed
        except ValueError:
            pass
    return rel.parts and rel.parts[0] in SHARED_HUB_LIBRARY_DIRS


def _router_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for name in ROUTER_FILE_CANDIDATES:
        p = repo_root / name
        if p.is_file():
            files.append(p)
    for pattern in ROUTER_GLOB_CANDIDATES:
        for p in repo_root.glob(pattern):
            if p.is_file() and "node_modules" not in p.parts:
                files.append(p)
    return files


def _route_regex(live_route: str) -> re.Pattern[str]:
    """Match a declared route allowing the hub segment to be templated in code:
    literal `a11oy`, printf `%s`, f-string `{ns}`/`{flagship}`, JS `'+NS+'`, or
    `<ns>`.  e.g. Route("/api/%s/v1/agent/cycle" % ns) matches
    live_route="/api/a11oy/v1/agent/cycle"."""
    escaped = re.escape(live_route)
    hub_alt = r"(?:a11oy|%s|\{[^}]+\}|'\s*\+\s*[A-Za-z_]+\s*\+\s*'|<[^>]+>)"
    # re.escape leaves bare word chars (incl. "a11oy") untouched.
    escaped = escaped.replace("a11oy", hub_alt, 1)
    return re.compile(escaped)


def route_is_served(live_route: str, repo_root: Path) -> bool | None:
    """Return True/False if `live_route` is/ isn't found in the served router
    code, or None when there are no router files to grep (offline bare repo)."""
    routers = _router_files(repo_root)
    if not routers:
        return None
    pattern = _route_regex(live_route)
    for router in routers:
        try:
            text = router.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if pattern.search(text):
            return True
    return False


def organ_has_receipt(organ: dict) -> bool:
    receipt = organ.get("receipt")
    if isinstance(receipt, str) and receipt.strip() and receipt.strip().lower() != "none":
        return True
    haystack = " ".join(organ.get("receiptSurface", []) or []).lower()
    return any(marker in haystack for marker in RECEIPT_MARKERS)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
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
                    # RULE 1 (own-repo / no-borrowing): a verified-runtime claim
                    # must resolve to code the organ OWNS, never a borrowed a11oy
                    # shared hub gate. Non-verified statuses (e.g. wired-shared)
                    # may honestly reference a shared gate.
                    claims_verified = (
                        formula_status == "verified-runtime"
                        or status == "verified-runtime"
                    )
                    if claims_verified and is_borrowed_hub_file(resolved, repo, REPO_ROOT):
                        rel = resolved
                        try:
                            rel = resolved.relative_to(REPO_ROOT)
                        except ValueError:
                            pass
                        errors.append(
                            f"{repo}/{fname}: verified-runtime borrows a11oy hub file {rel} "
                            f"(not under organs/{repo}/ or its own repo); point at the organ's "
                            f"own runtime or downgrade to 'wired-shared'"
                        )

        # RULE 2 (earned status needs a live route): a verified-runtime organ
        # must declare a `live_route`, and — when router code is present in this
        # checkout — that route must actually be registered there. Missing or
        # unserved => the claim is not earned; downgrade to wired-shared/roadmap.
        if status == "verified-runtime":
            live_route = organ.get("live_route")
            if not (isinstance(live_route, str) and live_route.strip()):
                errors.append(
                    f"{repo}: verified-runtime organ must declare a served 'live_route' "
                    f"(none found); downgrade to 'wired-shared' if there is no live endpoint"
                )
            else:
                served = route_is_served(live_route, REPO_ROOT)
                if served is False:
                    errors.append(
                        f"{repo}: live_route {live_route!r} is not registered in any served "
                        f"router ({', '.join(ROUTER_FILE_CANDIDATES)}, organs/*/serve.py); "
                        f"downgrade this organ or fix the route"
                    )

            # RULE 3 (receipt-flow, advisory): warn — never fail — when a
            # verified-runtime organ shows no receipt/DSSE path, so the map
            # honestly annotates which organs are receipted.
            if not organ_has_receipt(organ):
                warnings.append(
                    f"{repo}: verified-runtime organ has no receipt evidence "
                    f"(receipt: none) — add a szl-receipt/DSSE path or a `receipt` field"
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

    for warning in warnings:
        print(f"  ! (advisory) {warning}")
    print(f"Validated {MAP_PATH.relative_to(REPO_ROOT)} ({len(organs)} organs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
