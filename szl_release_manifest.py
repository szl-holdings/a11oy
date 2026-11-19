# SPDX-License-Identifier: Apache-2.0
"""Release manifest: one machine-checkable identity for source and runtime.

Binds, for one A11oy build: the git commit, the frontend bundle hash, the API
contract hash, the HF model revision, the deployment ID and the rollback target.

* ``build_manifest`` fills every value from the tree or the environment at build
  time. Nothing is hardcoded; anything not supplied is reported ``UNKNOWN``.
* ``verify_manifest`` re-derives the tree-bound values and reports drift.
* ``compare_runtime`` compares a manifest with what a deployed runtime reports
  (the PUBLICATION_LAG class of failure seen on a11oy#3768).
* ``runtime_build_ids`` is the read-only view served at ``/api/build``.

Stdlib only; no network, no writes, no secrets. Values are accepted only in
strict, narrow formats so an arbitrary environment string cannot leak through.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

SCHEMA_ID = "szl.a11oy.release-manifest/v1"
DEFAULT_BUNDLE_ROOT = "console"
DEFAULT_ENTRY = "index.html"
DEFAULT_CONTRACT_INPUTS = ("docs/api-contract.md",)
DOCKERFILE_MODEL_REPO_ARG = "A11OY_ALLOY_GGUF_REPO"
DOCKERFILE_MODEL_REV_ARG = "A11OY_ALLOY_GGUF_REV"

SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
SHA_ANY = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
RELEASE_ID = re.compile(r"[0-9a-f]{12}\Z")
DEPLOY_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._\-]{0,63}\Z")
MODEL_REPO = re.compile(r"[A-Za-z0-9][A-Za-z0-9._\-]{0,95}/[A-Za-z0-9][A-Za-z0-9._\-]{0,95}\Z")
GIT_REF = re.compile(r"(?:[0-9a-f]{40}|v?\d+\.\d+\.\d+(?:[A-Za-z0-9._+\-]{0,32}))\Z")

# Fields that must all be known for a release build (see --require-complete).
REQUIRED_FIELDS = (
    "git.commit",
    "frontend.bundle_sha256",
    "api_contract.sha256",
    "model.revision",
    "deployment.id",
    "rollback.target",
)

_SKIP_DIRS = {"__pycache__", ".git", "node_modules"}
_SKIP_FILES = {".DS_Store"}


def _field(value: Optional[str], source: str) -> dict[str, Any]:
    if value:
        return {"value": value, "state": "SUPPLIED", "source": source}
    return {"value": None, "state": "UNKNOWN", "source": "UNKNOWN"}


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_tree(root: Path) -> tuple[str, int]:
    """Deterministic hash of a directory: sorted relative paths + file hashes."""
    entries: list[str] = []
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS)
        for name in sorted(files):
            if name in _SKIP_FILES:
                continue
            path = Path(current) / name
            if path.is_symlink() or not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            entries.append(f"{rel}\0{sha256_file(path)}\n")
    entries.sort()
    return hashlib.sha256("".join(entries).encode("utf-8")).hexdigest(), len(entries)


def hash_contract_files(root: Path, inputs: Iterable[str]) -> tuple[str, list[dict[str, str]]]:
    listed = []
    for rel in sorted(set(inputs)):
        path = (root / rel)
        listed.append({"path": rel, "sha256": sha256_file(path)})
    return hashlib.sha256(canonical_bytes(listed)).hexdigest(), listed


def hash_openapi_json(path: Path) -> str:
    """Hash an OpenAPI document by content (key order and whitespace ignored)."""
    return hashlib.sha256(canonical_bytes(json.loads(path.read_text(encoding="utf-8")))).hexdigest()


def _git(root: Path, *args: str) -> Optional[str]:
    try:
        res = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return res.stdout.strip() if res.returncode == 0 else None


def _dockerfile_arg(root: Path, name: str) -> Optional[str]:
    try:
        text = (root / "Dockerfile").read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(rf"^\s*ARG\s+{re.escape(name)}=(\S+)\s*$", text, re.M)
    return match.group(1) if match else None


def _valid(value: Optional[str], pattern: re.Pattern[str]) -> Optional[str]:
    value = (value or "").strip()
    return value if value and pattern.fullmatch(value) else None


def release_id_for(manifest: dict[str, Any]) -> str:
    """Stable ID: hash of every bound value; excludes time and the ID itself."""
    body = {k: v for k, v in manifest.items() if k not in {"release_id", "generated_at"}}
    return hashlib.sha256(canonical_bytes(body)).hexdigest()[:12]


def build_manifest(
    repo_root: Path,
    *,
    env: Optional[dict[str, str]] = None,
    git_commit: Optional[str] = None,
    bundle_root: str = DEFAULT_BUNDLE_ROOT,
    contract_inputs: Iterable[str] = DEFAULT_CONTRACT_INPUTS,
    openapi_json: Optional[Path] = None,
    generated_at: Optional[str] = None,
) -> dict[str, Any]:
    env = dict(os.environ if env is None else env)
    repo_root = Path(repo_root)

    commit, commit_source = _valid(git_commit, SHA40), "arg"
    if not commit:
        commit, commit_source = _valid(_git(repo_root, "rev-parse", "HEAD"), SHA40), "git:HEAD"
    if not commit:
        for name in ("A11OY_GIT_SHA", "GITHUB_SHA"):
            commit = _valid(env.get(name), SHA40)
            if commit:
                commit_source = f"env:{name}"
                break
    status = _git(repo_root, "status", "--porcelain", "--untracked-files=no")
    tree_state = "UNKNOWN" if status is None else ("DIRTY" if status else "CLEAN")

    bundle_dir = repo_root / bundle_root
    bundle_sha, file_count = hash_tree(bundle_dir)
    entry_path = bundle_dir / DEFAULT_ENTRY
    entry_sha = sha256_file(entry_path) if entry_path.is_file() else None

    if openapi_json is not None:
        contract = {"kind": "openapi-json", "inputs": [], "sha256": hash_openapi_json(openapi_json)}
    else:
        contract_sha, listed = hash_contract_files(repo_root, contract_inputs)
        contract = {"kind": "repo-files", "inputs": listed, "sha256": contract_sha}

    model_repo = _valid(env.get("A11OY_MODEL_REPO"), MODEL_REPO)
    model_repo_src = "env:A11OY_MODEL_REPO"
    if not model_repo:
        model_repo = _valid(_dockerfile_arg(repo_root, DOCKERFILE_MODEL_REPO_ARG), MODEL_REPO)
        model_repo_src = f"Dockerfile:ARG {DOCKERFILE_MODEL_REPO_ARG}"
    model_rev = _valid(env.get("A11OY_MODEL_REVISION"), SHA40)
    model_rev_src = "env:A11OY_MODEL_REVISION"
    if not model_rev:
        model_rev = _valid(_dockerfile_arg(repo_root, DOCKERFILE_MODEL_REV_ARG), SHA40)
        model_rev_src = f"Dockerfile:ARG {DOCKERFILE_MODEL_REV_ARG}"

    manifest: dict[str, Any] = {
        "schema": SCHEMA_ID,
        "release_id": "",
        "generated_at": generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git": {"commit": commit, "commit_source": commit_source if commit else "UNKNOWN", "tree_state": tree_state},
        "frontend": {
            "bundle_root": bundle_root,
            "bundle_sha256": bundle_sha,
            "entry": DEFAULT_ENTRY,
            "entry_sha256": entry_sha,
            "file_count": file_count,
        },
        "api_contract": contract,
        "model": {
            "repo": _field(model_repo, model_repo_src),
            "revision": _field(model_rev, model_rev_src),
        },
        "deployment": {"id": _field(_valid(env.get("A11OY_DEPLOYMENT_ID"), DEPLOY_ID), "env:A11OY_DEPLOYMENT_ID")},
        "rollback": {"target": _field(_valid(env.get("A11OY_ROLLBACK_TARGET"), GIT_REF), "env:A11OY_ROLLBACK_TARGET")},
        "honesty": {
            "values_are_declared_not_proven_deployed": True,
            "unknown_is_reported_not_guessed": True,
            "receipt_minted": False,
        },
    }
    manifest["release_id"] = release_id_for(manifest)
    return manifest


def unknown_fields(manifest: dict[str, Any]) -> list[str]:
    """Required fields that are not known (dotted names)."""
    def get(path: str) -> Any:
        node: Any = manifest
        for part in path.split("."):
            node = node.get(part) if isinstance(node, dict) else None
        if isinstance(node, dict) and "state" in node:
            return node.get("value")
        return node

    return [name for name in REQUIRED_FIELDS if not get(name)]


def build_args(manifest: dict[str, Any]) -> dict[str, str]:
    """Docker ``--build-arg`` values for the runtime ``/api/build`` view."""
    def val(node: Any) -> str:
        return str(node.get("value") or "") if isinstance(node, dict) else ""

    pairs = {
        "REVISION": str((manifest.get("git") or {}).get("commit") or ""),
        "A11OY_FRONTEND_BUNDLE_SHA256": str((manifest.get("frontend") or {}).get("bundle_sha256") or ""),
        "A11OY_FRONTEND_ENTRY_SHA256": str((manifest.get("frontend") or {}).get("entry_sha256") or ""),
        "A11OY_API_CONTRACT_SHA256": str((manifest.get("api_contract") or {}).get("sha256") or ""),
        "A11OY_MODEL_REVISION": val((manifest.get("model") or {}).get("revision")),
        "A11OY_DEPLOYMENT_ID": val((manifest.get("deployment") or {}).get("id")),
        "A11OY_ROLLBACK_TARGET": val((manifest.get("rollback") or {}).get("target")),
        "A11OY_RELEASE_ID": str(manifest.get("release_id") or ""),
    }
    return {k: v for k, v in pairs.items() if v}


def verify_manifest(manifest: dict[str, Any], repo_root: Path) -> list[dict[str, Any]]:
    """Re-derive the tree-bound values; return drift findings (empty = parity)."""
    repo_root = Path(repo_root)
    findings: list[dict[str, Any]] = []

    def add(code: str, expected: Any, observed: Any) -> None:
        findings.append({"code": code, "expected": expected, "observed": observed})

    if manifest.get("schema") != SCHEMA_ID:
        add("SCHEMA_MISMATCH", SCHEMA_ID, manifest.get("schema"))
    frontend = manifest.get("frontend") or {}
    root = repo_root / str(frontend.get("bundle_root") or DEFAULT_BUNDLE_ROOT)
    if root.is_dir():
        sha, _ = hash_tree(root)
        if sha != frontend.get("bundle_sha256"):
            add("BUNDLE_HASH_MISMATCH", frontend.get("bundle_sha256"), sha)
        entry = root / str(frontend.get("entry") or DEFAULT_ENTRY)
        if entry.is_file() and frontend.get("entry_sha256") != sha256_file(entry):
            add("ENTRY_HASH_MISMATCH", frontend.get("entry_sha256"), sha256_file(entry))
    else:
        add("BUNDLE_ROOT_MISSING", str(root), None)

    contract = manifest.get("api_contract") or {}
    if contract.get("kind") == "repo-files":
        try:
            sha, _ = hash_contract_files(repo_root, [i["path"] for i in contract.get("inputs") or []])
        except (OSError, KeyError, TypeError):
            add("CONTRACT_INPUT_MISSING", contract.get("inputs"), None)
        else:
            if sha != contract.get("sha256"):
                add("CONTRACT_HASH_MISMATCH", contract.get("sha256"), sha)

    head = _valid(_git(repo_root, "rev-parse", "HEAD"), SHA40)
    declared = (manifest.get("git") or {}).get("commit")
    if head and declared != head:
        add("COMMIT_MISMATCH", declared, head)

    if manifest.get("release_id") != release_id_for(manifest):
        add("RELEASE_ID_MISMATCH", manifest.get("release_id"), release_id_for(manifest))
    return findings


def compare_runtime(manifest: dict[str, Any], observed: dict[str, Any]) -> list[dict[str, Any]]:
    """Compare a manifest with what a deployed runtime reports about itself."""
    findings: list[dict[str, Any]] = []
    want = (manifest.get("git") or {}).get("commit")
    got = observed.get("revision")
    if not got:
        findings.append({"code": "RUNTIME_REVISION_UNKNOWN", "expected": want, "observed": None})
    elif want != got:
        findings.append({"code": "PUBLICATION_LAG", "expected": want, "observed": got})
    for key, path, code in (
        ("frontend_bundle_sha256", ("frontend", "bundle_sha256"), "FRONTEND_BUNDLE_MISMATCH"),
        ("api_contract_sha256", ("api_contract", "sha256"), "API_CONTRACT_MISMATCH"),
    ):
        if observed.get(key):
            node: Any = manifest
            for part in path:
                node = node.get(part) if isinstance(node, dict) else None
            if node != observed[key]:
                findings.append({"code": code, "expected": node, "observed": observed[key]})
    return findings


def runtime_build_ids(
    env: Optional[dict[str, str]] = None,
    *,
    commit: Optional[str] = None,
    commit_source: Optional[str] = None,
    static_dirs: Iterable[Path] = (),
) -> dict[str, Any]:
    """Read-only build-ID view. Allowlisted env names only; strict formats."""
    env = dict(os.environ if env is None else env)
    bundle = _valid(env.get("A11OY_FRONTEND_BUNDLE_SHA256"), SHA64)
    entry_declared = _valid(env.get("A11OY_FRONTEND_ENTRY_SHA256"), SHA64)
    contract = _valid(env.get("A11OY_API_CONTRACT_SHA256"), SHA64)
    model_rev = _valid(env.get("A11OY_MODEL_REVISION"), SHA40)
    deploy = _valid(env.get("A11OY_DEPLOYMENT_ID"), DEPLOY_ID)
    rollback = _valid(env.get("A11OY_ROLLBACK_TARGET"), GIT_REF)
    release = _valid(env.get("A11OY_RELEASE_ID"), RELEASE_ID)

    entry_observed = None
    for directory in static_dirs:
        candidate = Path(directory) / DEFAULT_ENTRY
        try:
            if candidate.is_file():
                entry_observed = sha256_file(candidate)
                break
        except OSError:
            continue

    unknown = [
        name
        for name, value in (
            ("git.commit", commit),
            ("frontend.bundle_sha256", bundle),
            ("api_contract.sha256", contract),
            ("model.revision", model_rev),
            ("deployment.id", deploy),
            ("rollback.target", rollback),
        )
        if not value
    ]
    declared_any = any((bundle, contract, model_rev, deploy, rollback, release))
    if entry_declared and entry_observed and entry_declared != entry_observed:
        status = "DRIFT"
    elif not declared_any:
        status = "UNDECLARED"
    elif unknown:
        status = "PARTIAL"
    else:
        status = "DECLARED"
    return {
        "schema": "szl.a11oy.build-ids/v1",
        "status": status,
        "release_id": release,
        "git": {"commit": commit, "source": commit_source or "UNKNOWN"},
        "frontend": {
            "bundle_sha256": bundle,
            "entry_sha256_declared": entry_declared,
            "entry_sha256_observed": entry_observed,
            "entry_matches": (entry_declared == entry_observed) if (entry_declared and entry_observed) else None,
        },
        "api_contract": {"sha256": contract},
        "model": {"revision": model_rev},
        "deployment": {"id": deploy},
        "rollback": {"target": rollback},
        "unknown_fields": unknown,
        "note": "declared at build time; not proof that this bundle is the one deployed. Compare with the release manifest.",
        "receipt_minted": False,
    }
