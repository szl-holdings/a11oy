#!/usr/bin/env python3
"""Reconcile exact public HF source bytes and the derived Brain registry.

This bounded migration is executed once from an unprotected recovery branch.
It imports only an explicit allowlist from one immutable Hugging Face Space
revision, refreshes the registry from the repository's actual graph, and emits
a permanent machine-readable proof. The launcher removes this script before
committing the reconciled tree.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
HF_REMOTE = "https://huggingface.co/spaces/SZLHOLDINGS/a11oy.git"
HF_REVISION = "8bd83a12d69a24050bce9601b772eefb547e2927"
GITHUB_BASE = "9cbc318007e6751982bbf9e435bc46b8ae7a475d"
SOURCE_PATHS = (
    "pages/pricing.html",
    "serve.py",
    "static/3d/holographic.html",
    "static/3d/surfaces/braincite.js",
    "szl3d_holographic.py",
)
REGISTRY_PATH = Path("model_release/frontier-qualification/frontier-adoption.json")
PROOF_PATH = Path("docs/proofs/hf-source-brain-reconciliation-2026-08-31.json")
MAX_FILE_BYTES = 25 * 1024 * 1024


class ReconciliationError(RuntimeError):
    """Raised when immutable reconciliation cannot be proven."""


def _run(
    argv: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    allow_failure: bool = False,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        argv,
        cwd=str(cwd) if cwd else None,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode and not allow_failure:
        raise ReconciliationError(
            f"command failed ({result.returncode}): {argv!r}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return _sha256(payload)


def _clone_exact_revision(destination: Path) -> None:
    env = dict(os.environ)
    env["GIT_LFS_SKIP_SMUDGE"] = "1"
    _run(["git", "init", "-q", str(destination)], env=env)
    _run(["git", "-C", str(destination), "remote", "add", "origin", HF_REMOTE], env=env)

    direct = _run(
        ["git", "-C", str(destination), "fetch", "--depth=1", "origin", HF_REVISION],
        env=env,
        allow_failure=True,
    )
    if direct.returncode:
        fallback = _run(
            ["git", "-C", str(destination), "fetch", "--depth=250", "origin", "main"],
            env=env,
            allow_failure=True,
        )
        if fallback.returncode:
            raise ReconciliationError(
                "unable to fetch the immutable Hugging Face revision\n"
                f"direct stderr:\n{direct.stderr}\nfallback stderr:\n{fallback.stderr}"
            )

    exists = _run(
        ["git", "-C", str(destination), "cat-file", "-e", f"{HF_REVISION}^{{commit}}"],
        env=env,
        allow_failure=True,
    )
    if exists.returncode:
        raise ReconciliationError(f"immutable HF revision is not available: {HF_REVISION}")
    _run(["git", "-C", str(destination), "checkout", "-q", "--detach", HF_REVISION], env=env)
    observed = _run(
        ["git", "-C", str(destination), "rev-parse", "HEAD"], env=env
    ).stdout.strip()
    if observed != HF_REVISION:
        raise ReconciliationError(
            f"HF checkout mismatch: observed={observed!r} expected={HF_REVISION!r}"
        )


def _copy_source(hf_root: Path, relative: str) -> dict[str, Any]:
    listed = _run(
        ["git", "-C", str(hf_root), "ls-files", "--stage", "--", relative]
    ).stdout.strip()
    if not listed:
        raise ReconciliationError(f"allowlisted HF source path is absent: {relative}")
    mode = listed.split(None, 1)[0]
    if mode not in {"100644", "100755"}:
        raise ReconciliationError(f"refusing non-regular HF path {relative!r} with mode {mode!r}")

    source = hf_root / relative
    if source.is_symlink() or not source.is_file():
        raise ReconciliationError(f"allowlisted HF source is not a regular file: {relative}")
    data = source.read_bytes()
    if not data or len(data) > MAX_FILE_BYTES:
        raise ReconciliationError(
            f"HF source size outside policy for {relative!r}: {len(data)} bytes"
        )
    if b"\x00" in data:
        raise ReconciliationError(f"HF source contains a NUL byte: {relative}")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReconciliationError(f"HF source is not UTF-8: {relative}") from exc

    destination = ROOT / relative
    resolved_parent = destination.parent.resolve()
    if ROOT.resolve() not in {resolved_parent, *resolved_parent.parents}:
        raise ReconciliationError(f"destination escapes repository root: {relative}")
    old_data = destination.read_bytes() if destination.is_file() else None
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".partial",
        delete=False,
    ) as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, destination)
    return {
        "path": relative,
        "mode": mode,
        "bytes": len(data),
        "source_sha256": _sha256(data),
        "previous_sha256": _sha256(old_data) if old_data is not None else None,
        "changed": old_data != data,
    }


def _refresh_brain_registry() -> dict[str, Any]:
    sys.path.insert(0, str(ROOT))
    module = importlib.import_module("a11oy_brain_graph")
    graph = module.get_brain_graph(refresh=True)
    nodes = graph.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise ReconciliationError("current Brain graph did not return a non-empty node list")
    node_count = len(nodes)

    path = ROOT / REGISTRY_PATH
    registry = json.loads(path.read_text(encoding="utf-8"))
    truth = registry.get("brain_model_truth")
    if not isinstance(truth, dict):
        raise ReconciliationError("frontier adoption registry has no brain_model_truth object")
    previous_observed = truth.get("raw_nodes_observed")
    previous_available = truth.get("raw_nodes_available_to_retrieval_and_evaluation")
    truth["raw_nodes_observed"] = node_count
    truth["raw_nodes_available_to_retrieval_and_evaluation"] = node_count
    registry["as_of"] = "2026-08-31"
    path.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return {
        "path": str(REGISTRY_PATH),
        "previous_raw_nodes_observed": previous_observed,
        "previous_raw_nodes_available": previous_available,
        "current_raw_nodes": node_count,
        "graph_node_count": node_count,
    }


def main() -> int:
    if Path.cwd().resolve() != ROOT.resolve():
        raise ReconciliationError(f"run from repository root: {ROOT}")
    with tempfile.TemporaryDirectory(prefix="a11oy-hf-reconcile-") as tmp:
        hf_root = Path(tmp) / "space"
        _clone_exact_revision(hf_root)
        files = [_copy_source(hf_root, relative) for relative in SOURCE_PATHS]

    if not any(item["changed"] for item in files):
        raise ReconciliationError("immutable HF revision produced no source changes")
    brain = _refresh_brain_registry()
    proof: dict[str, Any] = {
        "schema": "a11oy.hf-source-brain-reconciliation/v1",
        "status": "RECONCILED",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "github_repository": "szl-holdings/a11oy",
        "github_base": GITHUB_BASE,
        "huggingface_repository": "SZLHOLDINGS/a11oy",
        "huggingface_remote": HF_REMOTE,
        "huggingface_revision": HF_REVISION,
        "source_policy": {
            "exact_allowlist": list(SOURCE_PATHS),
            "regular_files_only": True,
            "utf8_only": True,
            "max_file_bytes": MAX_FILE_BYTES,
            "git_lfs_smudge": False,
        },
        "files": files,
        "brain_registry": brain,
        "external_mutations": {
            "huggingface_written": False,
            "production_deployed": False,
            "model_weights_changed": False,
        },
        "honesty": (
            "This proof imports exact text bytes from one immutable public Space revision and "
            "refreshes a derived node count. It does not certify runtime behavior or authorize weights."
        ),
    }
    proof["proof_sha256"] = _canonical_digest(proof)
    destination = ROOT / PROOF_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(proof, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"RECONCILIATION BLOCKED: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
