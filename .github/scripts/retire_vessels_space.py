#!/usr/bin/env python3
"""Retire the legacy SZLHOLDINGS/vessels Space after bounded replacement proof.

The operation is intentionally narrow and irreversible. It never reads Space
secrets or variables, never mutates another repository, and refuses to delete
unless source retention, anti-recreation controls, and the Killinchu maritime
replacement are all proven in the same execution.
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

TARGET = "SZLHOLDINGS/vessels"
CONFIRM = "RETIRE-SZLHOLDINGS-VESSELS"
REPLACEMENT_REPO = "SZLHOLDINGS/killinchu"
REPLACEMENT_SOURCE = "szl-holdings/killinchu"
REPLACEMENT_ORIGIN = "https://szlholdings-killinchu.hf.space"
REPLACEMENT_PATHS = ("/", "/maritime-intel", "/api/vessels/healthz", "/api/build-info")


class RetirementError(RuntimeError):
    """Fail-closed retirement error."""


def _safe_error(exc: BaseException, token: str) -> str:
    text = " ".join(str(exc).split())[:4000]
    return text.replace(token, "<redacted>") if token else text


def _get(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url + ("&" if "?" in url else "?") + f"retirement_proof={time.time_ns()}",
        headers={
            "Accept": "application/json,text/html,*/*",
            "Cache-Control": "no-cache, no-store",
            "Pragma": "no-cache",
            "User-Agent": "SZL-HF-Retirement/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read(262144)
            return {
                "status": response.status,
                "content_type": response.headers.get("content-type"),
                "body": body,
            }
    except urllib.error.HTTPError as exc:
        return {
            "status": exc.code,
            "content_type": exc.headers.get("content-type"),
            "body": exc.read(65536),
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"status": None, "body": b"", "error": type(exc).__name__}


def _json(record: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(record.get("body", b"").decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def prove_local_controls(root: Path) -> dict[str, Any]:
    wrapper_path = root / "scripts" / "hf_publish_vertical_flagships_v4.py"
    migration_path = root / "docs" / "estate" / "HF_FLAGSHIP_MIGRATION.md"
    consolidation_path = root / "config" / "flagship_tab_consolidation.json"
    packet8_path = root / ".github" / "scripts" / "publish_packet8_vertical_spaces.py"
    obsolete_writer = root / ".github" / "workflows" / "emergency-live-convergence-v1.yml"

    required_files = (wrapper_path, migration_path, consolidation_path, packet8_path)
    missing = [str(path.relative_to(root)) for path in required_files if not path.is_file()]
    if missing:
        raise RetirementError(f"required retirement control missing: {missing}")

    wrapper = wrapper_path.read_text(encoding="utf-8")
    migration = migration_path.read_text(encoding="utf-8")
    consolidation = json.loads(consolidation_path.read_text(encoding="utf-8"))
    packet8 = packet8_path.read_text(encoding="utf-8")

    if not re.search(
        r'PUBLIC_FLAGSHIP_SLUGS\s*=\s*\(\s*"terra",\s*"counsel",\s*"finance",\s*"lyte"\s*\)',
        wrapper,
        re.S,
    ):
        raise RetirementError("public flagship writer is not constrained to the four non-Killinchu verticals")
    if not re.search(
        r'FOLDED_INTO_KILLINCHU\s*=\s*\(\s*"sentra",\s*"vessels"\s*\)',
        wrapper,
        re.S,
    ):
        raise RetirementError("vessels is not declared folded into Killinchu")
    if "SZLHOLDINGS/vessels" not in migration or "REFERENCE_CLEANUP_REQUIRED" not in migration:
        raise RetirementError("migration ledger does not identify the legacy Vessels Space")
    if obsolete_writer.exists():
        raise RetirementError("obsolete duplicate Hugging Face writer still exists")

    active_packet8 = packet8.split("SPACES = [", 1)[-1]
    if '"space_id": "SZLHOLDINGS/vessels"' in active_packet8:
        raise RetirementError("Packet 8 publisher can recreate the Vessels Space")

    flagships = consolidation.get("flagships")
    if not isinstance(flagships, list):
        raise RetirementError("invalid flagship consolidation registry")
    killinchu = next(
        (row for row in flagships if isinstance(row, dict) and row.get("id") == "killinchu"),
        None,
    )
    if not isinstance(killinchu, dict):
        raise RetirementError("Killinchu is absent from the flagship consolidation registry")
    if "vessels" not in set(killinchu.get("consolidates") or []):
        raise RetirementError("Killinchu registry does not consolidate vessels")
    retirement = killinchu.get("legacy_space_retirement") or {}
    if "SZLHOLDINGS/vessels" not in retirement:
        raise RetirementError("Vessels retirement state is absent from Killinchu registry")

    return {
        "public_flagship_writer_constrained": True,
        "folded_into_killinchu": True,
        "obsolete_duplicate_writer_absent": True,
        "packet8_recreation_blocked": True,
        "migration_ledger_present": True,
        "killinchu_registry_present": True,
    }


def prove_replacement() -> dict[str, Any]:
    observations: dict[str, Any] = {}
    for path in REPLACEMENT_PATHS:
        record = _get(REPLACEMENT_ORIGIN + path)
        observations[path] = {
            "status": record.get("status"),
            "content_type": record.get("content_type"),
            "error": record.get("error"),
        }
        if record.get("status") != 200:
            raise RetirementError(f"Killinchu replacement route failed: {path} -> {record.get('status')}")
        if path == "/api/build-info":
            payload = _json(record)
            serialized = json.dumps(payload, sort_keys=True).lower()
            if "killinchu" not in serialized:
                raise RetirementError("Killinchu build-info does not identify the replacement source")
            observations[path]["source_identified"] = True
            for key in ("source_revision", "git_sha", "revision"):
                value = payload.get(key)
                if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value):
                    observations[path]["source_revision"] = value
                    break
            build = payload.get("build")
            if "source_revision" not in observations[path] and isinstance(build, dict):
                value = build.get("revision")
                if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value):
                    observations[path]["source_revision"] = value
    return {
        "repository": REPLACEMENT_REPO,
        "source_repository": REPLACEMENT_SOURCE,
        "origin": REPLACEMENT_ORIGIN,
        "routes": observations,
        "verified": True,
    }


def capture_target(api: HfApi, token: str) -> dict[str, Any]:
    if not api.repo_exists(TARGET, repo_type="space"):
        return {"existed": False, "already_absent": True}

    info = api.space_info(TARGET, token=token)
    record: dict[str, Any] = {
        "existed": True,
        "private": bool(getattr(info, "private", False)),
        "sdk": getattr(info, "sdk", None),
        "sha": getattr(info, "sha", None),
        "files": sorted(api.list_repo_files(TARGET, repo_type="space", token=token)),
        "secret_values_read": False,
    }
    try:
        with tempfile.TemporaryDirectory(prefix="szl-vessels-card-") as tmp:
            readme = hf_hub_download(
                repo_id=TARGET,
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
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    report: dict[str, Any] = {
        "schema": "szl.hf-space-retirement/v1",
        "target": TARGET,
        "replacement": REPLACEMENT_REPO,
        "dry_run": args.dry_run,
        "status": "BLOCKED",
        "token_recorded": False,
        "secret_values_read": False,
        "deleted": False,
    }
    token = (
        os.environ.get("HF_ORG_TOKEN")
        or os.environ.get("HF_WRITE_TOKEN")
        or os.environ.get("HF_TOKEN")
        or ""
    ).strip()

    try:
        if args.confirm != CONFIRM:
            raise RetirementError(f"confirmation must equal {CONFIRM}")
        if not token:
            raise RetirementError("no organization-capable Hugging Face write token is configured")

        root = args.repo_root.resolve()
        report["local_controls"] = prove_local_controls(root)
        report["replacement_proof"] = prove_replacement()

        api = HfApi(token=token)
        report["target_before"] = capture_target(api, token)
        if report["target_before"].get("already_absent"):
            report["status"] = "ALREADY_ABSENT"
        elif args.dry_run:
            report["status"] = "VALIDATED"
        else:
            api.delete_repo(repo_id=TARGET, repo_type="space", token=token)
            for _ in range(12):
                if not api.repo_exists(TARGET, repo_type="space"):
                    break
                time.sleep(5)
            if api.repo_exists(TARGET, repo_type="space"):
                raise RetirementError("Hugging Face still reports the Vessels Space after deletion")
            report["deleted"] = True
            report["status"] = "RETIRED_VERIFIED"
        report["target_after_exists"] = bool(api.repo_exists(TARGET, repo_type="space"))
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
