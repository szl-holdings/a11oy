#!/usr/bin/env python3
"""Parameterize the Vessels retirement contract for any registered fold target.

The operation is intentionally narrow, one Space per dispatch, and irreversible
when not run with --dry-run. It never reads Space secrets or variables, never
mutates another repository, and refuses to delete unless every gate proves in
the same execution:

  1. --space-id is a pending target in publishing/space-fold-registry.json.
  2. --confirm equals FOLD-SZLHOLDINGS-<NAME-UPPERCASE> (typed confirmation).
  3. The Space is not a runtime or policy keep in szl_spaces_surface.py
     (runtime keep wins ONLY for listed keeps).
  4. publishing/hf-hub-ownership.json attributes no active in-repo writer.
  5. A declared fold destination (when one exists) answers HTTP < 400.
  6. The target exists and is captured (metadata + README digest) before a
     soft fold (pause + private) precedes the gated deletion.

"Fold" here means exactly what the Vessels pair did: capture, soft-fold
(pause + privatize), delete, verify absence, and issue a secret-free receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi, hf_hub_download

REGISTRY_PATH = Path("publishing") / "space-fold-registry.json"
OWNERSHIP_PATH = Path("publishing") / "hf-hub-ownership.json"
SURFACE_PATH = Path("szl_spaces_surface.py")
SPACE_ID_RE = re.compile(r"^SZLHOLDINGS/[A-Za-z0-9_.][A-Za-z0-9_.-]*[A-Za-z0-9_.]$")


class FoldError(RuntimeError):
    """Fail-closed fold error."""


def confirmation_for(space_id: str) -> str:
    """Typed confirmation required for a dispatch of this exact target."""
    return "FOLD-" + space_id.upper().replace("/", "-")


def _safe_error(exc: BaseException, token: str) -> str:
    text = " ".join(str(exc).split())[:4000]
    return text.replace(token, "<redacted>") if token else text


def _get(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url + ("&" if "?" in url else "?") + f"fold_proof={time.time_ns()}",
        headers={
            "Accept": "application/json,text/html,*/*",
            "Cache-Control": "no-cache, no-store",
            "Pragma": "no-cache",
            "User-Agent": "SZL-HF-SpaceFold/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return {"status": response.status}
    except urllib.error.HTTPError as exc:
        return {"status": exc.code}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"status": None, "error": type(exc).__name__}


def load_registry(root: Path) -> dict[str, Any]:
    path = root / REGISTRY_PATH
    if not path.is_file():
        raise FoldError(f"fold registry missing: {REGISTRY_PATH}")
    registry = json.loads(path.read_text(encoding="utf-8"))
    if registry.get("schema") != "szl.hf-space-fold-registry/v1":
        raise FoldError("unexpected fold registry schema")
    targets = registry.get("targets")
    if not isinstance(targets, list) or not targets:
        raise FoldError("fold registry carries no targets")
    return registry


def registry_entry(registry: dict[str, Any], space_id: str) -> dict[str, Any]:
    for target in registry["targets"]:
        if target.get("space_id") == space_id:
            return target
    raise FoldError(f"{space_id} is not a registered fold target")


def prove_keep_exclusion(root: Path, space_id: str) -> dict[str, Any]:
    """Runtime keep wins ONLY for keeps listed in szl_spaces_surface.py."""
    path = root / SURFACE_PATH
    if not path.is_file():
        raise FoldError("szl_spaces_surface.py missing; keep lists cannot be proved")
    sys.path.insert(0, str(root))
    try:
        import szl_spaces_surface as surface
    except Exception as exc:  # noqa: BLE001
        raise FoldError(f"szl_spaces_surface.py unimportable: {type(exc).__name__}") from exc
    finally:
        sys.path.remove(str(root))
    name = space_id.split("/", 1)[1]
    runtime_keeps = {sp["name"] for sp in surface.SPACES}
    policy_keeps = set(surface.PUBLIC_ORG_KEEP_POLICY)
    if name in runtime_keeps or name in policy_keeps:
        raise FoldError(
            f"{space_id} is a listed keep in szl_spaces_surface.py; runtime keep wins"
        )
    return {
        "runtime_keeps": sorted(runtime_keeps),
        "policy_keeps": sorted(policy_keeps),
        "target_is_not_keep": True,
    }


def prove_no_active_writer(root: Path, space_id: str) -> dict[str, Any]:
    path = root / OWNERSHIP_PATH
    if not path.is_file():
        raise FoldError(f"hub ownership manifest missing: {OWNERSHIP_PATH}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "szl.hf-hub-ownership/v1":
        raise FoldError("unexpected hub ownership manifest schema")
    entries = [t for t in manifest.get("targets", []) if t.get("repo_id") == space_id]
    for entry in entries:
        if isinstance(entry.get("writer"), dict):
            raise FoldError(
                f"{space_id} still has an active in-repo writer; retire the writer first"
            )
    return {"ownership_entries": len(entries), "no_active_writer": True}


def prove_destination(entry: dict[str, Any]) -> dict[str, Any]:
    destination = entry.get("destination")
    if not destination:
        return {"destination": None, "declared": False}
    record = _get(destination)
    status = record.get("status")
    if not (isinstance(status, int) and 200 <= status < 400):
        raise FoldError(f"declared fold destination failed: {destination} -> {status}")
    return {"destination": destination, "declared": True, "http_status": status}


def capture_target(api: HfApi, token: str, space_id: str) -> dict[str, Any]:
    if not api.repo_exists(space_id, repo_type="space"):
        return {"existed": False, "already_absent": True}

    info = api.space_info(space_id, token=token)
    record: dict[str, Any] = {
        "existed": True,
        "private": bool(getattr(info, "private", False)),
        "sdk": getattr(info, "sdk", None),
        "sha": getattr(info, "sha", None),
        "files": sorted(api.list_repo_files(space_id, repo_type="space", token=token)),
        "secret_values_read": False,
    }
    try:
        with tempfile.TemporaryDirectory(prefix="szl-fold-card-") as tmp:
            readme = hf_hub_download(
                repo_id=space_id,
                filename="README.md",
                repo_type="space",
                token=token,
                local_dir=tmp,
            )
            data = Path(readme).read_bytes()
            record["readme_sha256"] = hashlib.sha256(data).hexdigest()
            record["readme_bytes"] = len(data)
    except Exception as exc:  # noqa: BLE001
        record["readme_capture_warning"] = type(exc).__name__
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--space-id", required=True)
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    space_id = args.space_id.strip()
    report: dict[str, Any] = {
        "schema": "szl.hf-space-fold/v1",
        "target": space_id,
        "dry_run": args.dry_run,
        "status": "BLOCKED",
        "token_recorded": False,
        "secret_values_read": False,
        "deleted": False,
        "paused": False,
        "made_private": False,
    }
    token = (
        os.environ.get("HF_ORG_TOKEN")
        or os.environ.get("HF_WRITE_TOKEN")
        or os.environ.get("HF_TOKEN")
        or ""
    ).strip()

    try:
        if not SPACE_ID_RE.fullmatch(space_id):
            raise FoldError(f"invalid space id: {space_id!r}")
        if not token:
            raise FoldError("no organization-capable Hugging Face write token is configured")
        expected = confirmation_for(space_id)
        if args.confirm != expected:
            raise FoldError(f"confirmation must equal {expected}")

        root = args.repo_root.resolve()
        registry = load_registry(root)
        entry = registry_entry(registry, space_id)
        if entry.get("status") != "pending":
            raise FoldError(f"{space_id} registry status is {entry.get('status')!r}, not pending")
        report["registry_entry"] = {
            "class": entry.get("class"),
            "source_action": entry.get("source_action"),
            "review_gate": entry.get("review_gate"),
            "declared": entry.get("declared"),
        }
        report["local_controls"] = {
            "keep_exclusion": prove_keep_exclusion(root, space_id),
            "ownership": prove_no_active_writer(root, space_id),
            "destination": prove_destination(entry),
        }

        api = HfApi(token=token)
        report["target_before"] = capture_target(api, token, space_id)
        if report["target_before"].get("already_absent"):
            report["status"] = "ALREADY_ABSENT"
        elif args.dry_run:
            report["status"] = "VALIDATED"
        else:
            # Soft fold first (pause_and_private_then_gated_delete), then delete.
            report["fold_stage"] = "pause_and_private_then_gated_delete"
            api.pause_space(space_id, token=token)
            report["paused"] = True
            info = api.space_info(space_id, token=token)
            if not getattr(info, "private", False):
                api.update_repo_visibility(space_id, repo_type="space", private=True, token=token)
                report["made_private"] = True
            api.delete_repo(repo_id=space_id, repo_type="space", token=token)
            for _ in range(12):
                if not api.repo_exists(space_id, repo_type="space"):
                    break
                time.sleep(5)
            if api.repo_exists(space_id, repo_type="space"):
                raise FoldError("Hugging Face still reports the Space after deletion")
            report["deleted"] = True
            report["status"] = "FOLDED_VERIFIED"
        report["target_after_exists"] = bool(api.repo_exists(space_id, repo_type="space"))
    except Exception as exc:  # noqa: BLE001
        report["error"] = _safe_error(exc, token)
        report["status"] = "BLOCKED" if not report.get("deleted") else "VERIFY_FAILED"
        code = 1
    else:
        code = 0
    finally:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
