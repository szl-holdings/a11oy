#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Manual, fail-closed enrollment for the canonical Atelier operator.

This is not a publisher or a rotation tool. It never reads an existing Space
secret value or prints the bearer. At rest, the bearer is in a user-bound
Windows DPAPI vault; the explicit copy command makes a transient clipboard
handoff only after fresh secret-name and publisher checks. The Space receives
only a SHA-256 credential registry. Hub secret writes have no compare-and-set;
prechecks cannot exclude a concurrent overwrite.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable


SPACE_ID = "SZLHOLDINGS/a11oy"
GITHUB_REPO = "szl-holdings/a11oy"
SECRET_NAME = "A11OY_ATELIER_CREDENTIALS_JSON"
NAMESPACE = "a11oy"
SCOPE = "atelier:write"
MIN_FREE_BYTES = 1_500_000_000
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9._:-]{0,127}\Z")
_FILE_KEY_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}\Z")
_WINDOWS_DEVICE_NAMES = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                         *(f"lpt{i}" for i in range(1, 10))}
_VAULT_MAGIC = b"A11OY-ATELIER-DPAPI-V1\x00"
_REPO_ROOT = Path(__file__).resolve().parents[1]
_PUBLISHER_HOLD_FILTERS = (
    "queued", "in_progress", "requested", "waiting", "pending", "action_required",
)


class EnrollmentHold(RuntimeError):
    """A fixed, credential-safe reason to stop without claiming enrollment."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _gh_json(args: list[str]) -> Any:
    try:
        result = subprocess.run(
            ["gh", *args], capture_output=True, text=True, timeout=30, check=False,
        )
        if result.returncode != 0 or len(result.stdout) > 1_000_000:
            raise EnrollmentHold("GITHUB_READ_UNAVAILABLE")
        return json.loads(result.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        raise EnrollmentHold("GITHUB_READ_UNAVAILABLE") from None


def _protected_main_sha(gh_json: Callable[[list[str]], Any]) -> str:
    commit = gh_json(["api", f"repos/{GITHUB_REPO}/commits/main"])
    main_sha = commit.get("sha") if isinstance(commit, dict) else None
    if not isinstance(main_sha, str) or not _SHA.fullmatch(main_sha):
        raise EnrollmentHold("PROTECTED_MAIN_UNKNOWN")
    return main_sha


def _workflow_run_page(
    gh_json: Callable[[list[str]], Any], query: str,
) -> tuple[int, list[dict[str, Any]]]:
    endpoint = f"repos/{GITHUB_REPO}/actions/workflows/hf-sync.yml/runs?per_page=1&{query}"
    response = gh_json(["api", endpoint])
    if not isinstance(response, dict):
        raise EnrollmentHold("PUBLISHER_STATE_UNKNOWN")
    count, runs = response.get("total_count"), response.get("workflow_runs")
    if (type(count) is not int or count < 0 or not isinstance(runs, list)
            or len(runs) != min(count, 1) or any(not isinstance(run, dict) for run in runs)):
        raise EnrollmentHold("PUBLISHER_STATE_UNKNOWN")
    return count, runs


def _github_snapshot(gh_json: Callable[[list[str]], Any] = _gh_json) -> str:
    main_sha = _protected_main_sha(gh_json)
    # Status-filtered searches are independent of the completed-run backlog.
    # A one-row page plus total_count detects matches without paginating it.
    for status in _PUBLISHER_HOLD_FILTERS:
        count, runs = _workflow_run_page(gh_json, f"status={status}")
        if count:
            run = runs[0]
            actual = run.get("conclusion") if status == "action_required" else run.get("status")
            if actual != status:
                raise EnrollmentHold("PUBLISHER_STATE_UNKNOWN")
            raise EnrollmentHold("PUBLISHER_NOT_IDLE")
    count, runs = _workflow_run_page(gh_json, f"head_sha={main_sha}&branch=main")
    if not count:
        raise EnrollmentHold("CURRENT_MAIN_NOT_PUBLISHED")
    # GitHub returns the newest matching run first. An older green attempt
    # cannot mask a newer failed attempt at the same protected revision.
    latest = runs[0]
    if latest.get("head_sha") != main_sha or latest.get("head_branch") != "main":
        raise EnrollmentHold("PUBLISHER_STATE_UNKNOWN")
    if latest.get("status") != "completed":
        raise EnrollmentHold("PUBLISHER_NOT_IDLE")
    if latest.get("conclusion") != "success":
        raise EnrollmentHold("CURRENT_MAIN_NOT_PUBLISHED")
    if _protected_main_sha(gh_json) != main_sha:
        raise EnrollmentHold("PROTECTED_MAIN_MOVED_DURING_SNAPSHOT")
    return main_sha


def _space_snapshot(api: Any, *, require_registry: bool = False) -> str:
    try:
        info = api.space_info(repo_id=SPACE_ID)
        secret_names = api.get_space_secrets(repo_id=SPACE_ID)
        variables = api.get_space_variables(repo_id=SPACE_ID)
    except Exception:
        raise EnrollmentHold("SPACE_READ_UNAVAILABLE") from None
    sha = getattr(info, "sha", None)
    if not isinstance(sha, str) or not _SHA.fullmatch(sha):
        raise EnrollmentHold("SPACE_REVISION_UNKNOWN")
    if not isinstance(secret_names, dict) or not isinstance(variables, dict):
        raise EnrollmentHold("SPACE_METADATA_UNKNOWN")
    if SECRET_NAME in variables:
        raise EnrollmentHold("SECRET_VARIABLE_COLLISION")
    if require_registry and SECRET_NAME not in secret_names:
        raise EnrollmentHold("REMOTE_REGISTRY_NOT_VISIBLE")
    if not require_registry and SECRET_NAME in secret_names:
        raise EnrollmentHold("EXISTING_REGISTRY_REQUIRES_ROTATION")
    return sha


def plan(api: Any, gh_json: Callable[[list[str]], Any] = _gh_json) -> dict[str, str]:
    """Read-only snapshot; a later apply must compare both immutable revisions."""
    main_sha = _github_snapshot(gh_json)
    space_sha = _space_snapshot(api)
    return {
        "state": "PRECHECK_PASS_NOT_INSTALLED",
        "repo_id": SPACE_ID,
        "protected_main_sha": main_sha,
        "space_sha": space_sha,
        "secret_name": SECRET_NAME,
        "secret_value_read": "false",
    }


def _installed_snapshot(
    api: Any, gh_json: Callable[[list[str]], Any],
) -> tuple[str, str]:
    """Read names and revisions only; a present name cannot verify its digest."""
    main_sha = _github_snapshot(gh_json)
    space_sha = _space_snapshot(api, require_registry=True)
    return main_sha, space_sha


def _validate_identifier(value: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise EnrollmentHold("CREDENTIAL_IDENTITY_INVALID")
    return value


def _validate_key_id(value: str) -> str:
    _validate_identifier(value)
    if (not _FILE_KEY_ID.fullmatch(value) or value.endswith(".")
            or value.split(".", 1)[0] in _WINDOWS_DEVICE_NAMES):
        raise EnrollmentHold("CREDENTIAL_KEY_ID_UNSAFE_FOR_VAULT")
    return value


def _registry_json(token: str, owner_id: str, key_id: str) -> str:
    record = {
        "owner_id": _validate_identifier(owner_id),
        "namespace": NAMESPACE,
        "key_id": _validate_key_id(key_id),
        "token_sha256": hashlib.sha256(token.encode("utf-8")).hexdigest(),
        "scopes": [SCOPE],
        "revoked": False,
    }
    registry = json.dumps({"version": 1, "credentials": [record]},
                          sort_keys=True, separators=(",", ":"))
    # Reuse the runtime's exact parser instead of assuming our JSON is accepted.
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    from gdw_auth import parse_credential_registry

    parse_credential_registry(registry)
    return registry


def _dpapi_protect(data: bytes) -> bytes:
    """Protect with the current Windows user, never machine scope."""
    if os.name != "nt":
        raise EnrollmentHold("WINDOWS_DPAPI_REQUIRED")

    class DataBlob(ctypes.Structure):
        _fields_ = [("cbData", ctypes.c_ulong),
                    ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

    source = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    plain = DataBlob(len(data), ctypes.cast(source, ctypes.POINTER(ctypes.c_ubyte)))
    sealed = DataBlob()
    crypt32 = ctypes.WinDLL("Crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("Kernel32", use_last_error=True)
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(DataBlob), ctypes.c_wchar_p, ctypes.POINTER(DataBlob),
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(DataBlob),
    ]
    crypt32.CryptProtectData.restype = ctypes.c_int
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    # CRYPTPROTECT_UI_FORBIDDEN; omitting CRYPTPROTECT_LOCAL_MACHINE binds the user.
    if not crypt32.CryptProtectData(ctypes.byref(plain), "A11oy Atelier operator",
                                    None, None, None, 0x1, ctypes.byref(sealed)):
        raise EnrollmentHold("DPAPI_PROTECTION_FAILED")
    try:
        return ctypes.string_at(sealed.pbData, sealed.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(sealed.pbData, ctypes.c_void_p))


def _dpapi_unprotect(data: bytes) -> bytes:
    if os.name != "nt":
        raise EnrollmentHold("WINDOWS_DPAPI_REQUIRED")

    class DataBlob(ctypes.Structure):
        _fields_ = [("cbData", ctypes.c_ulong),
                    ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

    source = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    sealed = DataBlob(len(data), ctypes.cast(source, ctypes.POINTER(ctypes.c_ubyte)))
    plain = DataBlob()
    crypt32 = ctypes.WinDLL("Crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("Kernel32", use_last_error=True)
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(DataBlob), ctypes.c_void_p, ctypes.POINTER(DataBlob),
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(DataBlob),
    ]
    crypt32.CryptUnprotectData.restype = ctypes.c_int
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    if not crypt32.CryptUnprotectData(ctypes.byref(sealed), None, None, None,
                                      None, 0x1, ctypes.byref(plain)):
        raise EnrollmentHold("LOCAL_VAULT_DECRYPT_FAILED")
    try:
        return ctypes.string_at(plain.pbData, plain.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(plain.pbData, ctypes.c_void_p))


def _copy_to_clipboard(value: str) -> None:
    """Opt-in handoff to the browser paste field; never via command arguments."""
    if os.name != "nt":
        raise EnrollmentHold("WINDOWS_CLIPBOARD_REQUIRED")
    encoded = (value + "\x00").encode("utf-16-le")
    kernel32 = ctypes.WinDLL("Kernel32", use_last_error=True)
    user32 = ctypes.WinDLL("User32", use_last_error=True)
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.restype = ctypes.c_int
    kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
    kernel32.GlobalFree.restype = ctypes.c_void_p
    user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    user32.OpenClipboard.restype = ctypes.c_int
    user32.EmptyClipboard.restype = ctypes.c_int
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p
    user32.CloseClipboard.restype = ctypes.c_int
    handle = kernel32.GlobalAlloc(0x2, len(encoded))  # GMEM_MOVEABLE
    if not handle:
        raise EnrollmentHold("CLIPBOARD_UNAVAILABLE")
    try:
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            raise EnrollmentHold("CLIPBOARD_UNAVAILABLE")
        try:
            ctypes.memmove(pointer, encoded, len(encoded))
        finally:
            kernel32.GlobalUnlock(handle)
        if not user32.OpenClipboard(None):
            raise EnrollmentHold("CLIPBOARD_UNAVAILABLE")
        try:
            if not user32.EmptyClipboard():
                raise EnrollmentHold("CLIPBOARD_UNAVAILABLE")
            if not user32.SetClipboardData(13, handle):  # CF_UNICODETEXT
                raise EnrollmentHold("CLIPBOARD_UNAVAILABLE")
            handle = None  # The clipboard now owns the allocation.
        finally:
            user32.CloseClipboard()
    finally:
        if handle:
            kernel32.GlobalFree(handle)


def _vault_path(key_id: str) -> Path:
    key_id = _validate_key_id(key_id)
    base_raw = os.environ.get("LOCALAPPDATA", "")
    base = Path(base_raw)
    if not base_raw or not base.is_absolute() or not base.is_dir():
        raise EnrollmentHold("LOCAL_VAULT_UNAVAILABLE")
    base = base.resolve(strict=True)
    if base == _REPO_ROOT or _REPO_ROOT in base.parents:
        raise EnrollmentHold("LOCAL_VAULT_IN_REPOSITORY")
    return base / "SZL Holdings" / "A11oy" / (key_id + ".dpapi")


def _vault_write(path: Path, sealed: bytes) -> None:
    if shutil.disk_usage(path.anchor).free < MIN_FREE_BYTES:
        raise EnrollmentHold("LOCAL_STORAGE_LOW")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise EnrollmentHold("LOCAL_VAULT_WRITE_FAILED") from None
    for component in (path.parent, *path.parent.parents):
        if component.is_symlink() or getattr(component, "is_junction", lambda: False)():
            raise EnrollmentHold("LOCAL_VAULT_LINK_UNSAFE")
    if path.is_symlink() or path.exists():
        raise EnrollmentHold("LOCAL_VAULT_ALREADY_EXISTS")
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            output.write(_VAULT_MAGIC + sealed)
            output.flush()
            os.fsync(output.fileno())
    except FileExistsError:
        raise EnrollmentHold("LOCAL_VAULT_ALREADY_EXISTS") from None
    except OSError:
        raise EnrollmentHold("LOCAL_VAULT_WRITE_FAILED") from None


def apply(
    api: Any, *, expected_main_sha: str, expected_space_sha: str,
    owner_id: str, key_id: str,
    gh_json: Callable[[list[str]], Any] = _gh_json,
    protect: Callable[[bytes], bytes] = _dpapi_protect,
    vault_path: Path | None = None,
    token_factory: Callable[[int], str] = secrets.token_urlsafe,
) -> dict[str, str]:
    """Install after absent-name prechecks; no Hub CAS or automatic retry."""
    if not _SHA.fullmatch(expected_main_sha) or not _SHA.fullmatch(expected_space_sha):
        raise EnrollmentHold("EXPECTED_REVISION_INVALID")
    owner_id, key_id = _validate_identifier(owner_id), _validate_key_id(key_id)
    first = plan(api, gh_json)
    if (first["protected_main_sha"] != expected_main_sha
            or first["space_sha"] != expected_space_sha):
        raise EnrollmentHold("PLAN_REVISION_CHANGED")
    path = vault_path if vault_path is not None else _vault_path(key_id)
    if path.exists() or path.is_symlink():
        raise EnrollmentHold("LOCAL_VAULT_ALREADY_EXISTS")
    if shutil.disk_usage(path.anchor).free < MIN_FREE_BYTES:
        raise EnrollmentHold("LOCAL_STORAGE_LOW")
    token = token_factory(48)
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{64}", token):
        raise EnrollmentHold("TOKEN_GENERATION_FAILED")
    registry = _registry_json(token, owner_id, key_id)
    payload = json.dumps({"version": 1, "repo_id": SPACE_ID,
                          "owner_id": owner_id, "key_id": key_id, "token": token,
                          "token_sha256": hashlib.sha256(token.encode()).hexdigest()},
                         sort_keys=True, separators=(",", ":")).encode("utf-8")
    sealed = protect(payload)
    token = None
    payload = None
    if not isinstance(sealed, bytes) or not sealed:
        raise EnrollmentHold("DPAPI_PROTECTION_FAILED")
    _vault_write(path, sealed)
    # A second read narrows the race with the sole publisher. It is a snapshot,
    # not a lock or CAS; a concurrent external writer can still be overwritten.
    second = plan(api, gh_json)
    if (second["protected_main_sha"] != expected_main_sha
            or second["space_sha"] != expected_space_sha):
        raise EnrollmentHold("PLAN_REVISION_CHANGED_AFTER_VAULT")
    try:
        api.add_space_secret(repo_id=SPACE_ID, key=SECRET_NAME, value=registry,
                             description="Atelier operator digest registry v1")
    except Exception:
        raise EnrollmentHold("HF_WRITE_OUTCOME_UNKNOWN_VAULT_RETAINED") from None
    registry = None
    try:
        names = api.get_space_secrets(repo_id=SPACE_ID)
    except Exception:
        raise EnrollmentHold("HF_READBACK_UNKNOWN_VAULT_RETAINED") from None
    if not isinstance(names, dict) or SECRET_NAME not in names:
        raise EnrollmentHold("HF_READBACK_UNKNOWN_VAULT_RETAINED")
    return {
        "state": "SECRET_NAME_PRESENT_DIGEST_UNVERIFIED",
        "repo_id": SPACE_ID,
        "secret_name": SECRET_NAME,
        "protected_main_sha": expected_main_sha,
        "vault_path": str(path),
        "bearer_disclosed": "false",
    }


def _read_vault_record(
    *, key_id: str, unprotect: Callable[[bytes], bytes],
    vault_path: Path | None = None,
) -> dict[str, Any]:
    key_id = _validate_key_id(key_id)
    path = vault_path if vault_path is not None else _vault_path(key_id)
    if path.is_symlink() or not path.is_file():
        raise EnrollmentHold("LOCAL_VAULT_UNAVAILABLE")
    try:
        if path.stat().st_size > 8192:
            raise EnrollmentHold("LOCAL_VAULT_MALFORMED")
        sealed = path.read_bytes()
    except OSError:
        raise EnrollmentHold("LOCAL_VAULT_UNAVAILABLE") from None
    if not sealed.startswith(_VAULT_MAGIC) or len(sealed) == len(_VAULT_MAGIC):
        raise EnrollmentHold("LOCAL_VAULT_MALFORMED")
    plain = unprotect(sealed[len(_VAULT_MAGIC):])
    try:
        record = json.loads(plain)
    except (TypeError, UnicodeDecodeError, ValueError):
        raise EnrollmentHold("LOCAL_VAULT_MALFORMED") from None
    if not isinstance(record, dict) or set(record) != {
        "version", "repo_id", "owner_id", "key_id", "token", "token_sha256",
    } or type(record["version"]) is not int or record["version"] != 1 \
            or record["repo_id"] != SPACE_ID or record["key_id"] != key_id \
            or type(record["owner_id"]) is not str \
            or not _IDENTIFIER.fullmatch(record["owner_id"]):
        raise EnrollmentHold("LOCAL_VAULT_MALFORMED")
    token = record["token"]
    if (not isinstance(token, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{64}", token)
            or record["token_sha256"] != hashlib.sha256(token.encode()).hexdigest()):
        raise EnrollmentHold("LOCAL_VAULT_MALFORMED")
    return record


def copy_for_browser(
    api: Any, *, key_id: str, acknowledged: bool,
    gh_json: Callable[[list[str]], Any] = _gh_json,
    unprotect: Callable[[bytes], bytes] = _dpapi_unprotect,
    clipboard_copy: Callable[[str], None] = _copy_to_clipboard,
    vault_path: Path | None = None,
) -> dict[str, str]:
    """Copy only after fresh name/publisher checks; digest remains unverified."""
    if acknowledged is not True:
        raise EnrollmentHold("CLIPBOARD_RISK_ACKNOWLEDGEMENT_REQUIRED")
    first = _installed_snapshot(api, gh_json)
    record = _read_vault_record(key_id=key_id, unprotect=unprotect,
                                vault_path=vault_path)
    second = _installed_snapshot(api, gh_json)
    if second != first:
        raise EnrollmentHold("REMOTE_REVISION_CHANGED_BEFORE_COPY")
    token = record["token"]
    clipboard_copy(token)
    token = None
    return {"state": "COPIED_TO_CLIPBOARD_TRANSIENT_RISK",
            "key_id": key_id, "bearer_printed": "false",
            "remote_registry": "NAME_PRESENT_DIGEST_UNVERIFIED",
            "protected_main_sha": second[0], "space_sha": second[1]}


def resume(
    api: Any, *, expected_main_sha: str, expected_space_sha: str, key_id: str,
    gh_json: Callable[[list[str]], Any] = _gh_json,
    unprotect: Callable[[bytes], bytes] = _dpapi_unprotect,
    vault_path: Path | None = None,
) -> dict[str, str]:
    """Explicitly retry after absent-name prechecks; no Hub CAS is available."""
    if not _SHA.fullmatch(expected_main_sha) or not _SHA.fullmatch(expected_space_sha):
        raise EnrollmentHold("EXPECTED_REVISION_INVALID")
    key_id = _validate_key_id(key_id)
    first = plan(api, gh_json)
    if (first["protected_main_sha"] != expected_main_sha
            or first["space_sha"] != expected_space_sha):
        raise EnrollmentHold("PLAN_REVISION_CHANGED")
    path = vault_path if vault_path is not None else _vault_path(key_id)
    if shutil.disk_usage(path.anchor).free < MIN_FREE_BYTES:
        raise EnrollmentHold("LOCAL_STORAGE_LOW")
    record = _read_vault_record(key_id=key_id, unprotect=unprotect, vault_path=path)
    registry = _registry_json(record["token"], record["owner_id"], key_id)
    record = None
    second = plan(api, gh_json)
    if (second["protected_main_sha"] != expected_main_sha
            or second["space_sha"] != expected_space_sha):
        raise EnrollmentHold("PLAN_REVISION_CHANGED_AFTER_VAULT")
    try:
        api.add_space_secret(repo_id=SPACE_ID, key=SECRET_NAME, value=registry,
                             description="Atelier operator digest registry v1")
    except Exception:
        raise EnrollmentHold("HF_WRITE_OUTCOME_UNKNOWN_VAULT_RETAINED") from None
    registry = None
    try:
        names = api.get_space_secrets(repo_id=SPACE_ID)
    except Exception:
        raise EnrollmentHold("HF_READBACK_UNKNOWN_VAULT_RETAINED") from None
    if not isinstance(names, dict) or SECRET_NAME not in names:
        raise EnrollmentHold("HF_READBACK_UNKNOWN_VAULT_RETAINED")
    return {
        "state": "SECRET_NAME_PRESENT_DIGEST_UNVERIFIED",
        "repo_id": SPACE_ID,
        "secret_name": SECRET_NAME,
        "protected_main_sha": expected_main_sha,
        "vault_path": str(path),
        "bearer_disclosed": "false",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("plan", help="Read-only source, Space and writer check")
    apply_parser = subcommands.add_parser("apply", help="Install one new digest-only registry")
    apply_parser.add_argument("--expected-main-sha", required=True)
    apply_parser.add_argument("--expected-space-sha", required=True)
    apply_parser.add_argument("--owner-id", default="owner:stephen")
    apply_parser.add_argument("--key-id", required=True)
    resume_parser = subcommands.add_parser("resume", help="Explicit same-vault retry after an ambiguous install")
    resume_parser.add_argument("--expected-main-sha", required=True)
    resume_parser.add_argument("--expected-space-sha", required=True)
    resume_parser.add_argument("--key-id", required=True)
    copy_parser = subcommands.add_parser("copy", help="Opt-in local copy for browser paste")
    copy_parser.add_argument("--key-id", required=True)
    copy_parser.add_argument("--acknowledge-clipboard-risk", action="store_true")
    arguments = parser.parse_args()
    try:
        if arguments.command == "copy" and not arguments.acknowledge_clipboard_risk:
            raise EnrollmentHold("CLIPBOARD_RISK_ACKNOWLEDGEMENT_REQUIRED")
        from huggingface_hub import HfApi

        api = HfApi(endpoint="https://huggingface.co", token=True)
        if arguments.command == "copy":
            report = copy_for_browser(
                api,
                key_id=arguments.key_id,
                acknowledged=arguments.acknowledge_clipboard_risk,
            )
        else:
            if arguments.command == "plan":
                report = plan(api)
            elif arguments.command == "apply":
                report = apply(
                    api, expected_main_sha=arguments.expected_main_sha,
                    expected_space_sha=arguments.expected_space_sha,
                    owner_id=arguments.owner_id, key_id=arguments.key_id)
            else:
                report = resume(
                    api, expected_main_sha=arguments.expected_main_sha,
                    expected_space_sha=arguments.expected_space_sha,
                    key_id=arguments.key_id)
    except EnrollmentHold as exc:
        report = {"state": "HOLD", "code": exc.code, "secret_value_read": "false"}
    except Exception:
        report = {"state": "HOLD", "code": "CONTROL_PLANE_UNAVAILABLE",
                  "secret_value_read": "false"}
    print(json.dumps(report, sort_keys=True))
    return 0 if report["state"] in {
        "PRECHECK_PASS_NOT_INSTALLED", "SECRET_NAME_PRESENT_DIGEST_UNVERIFIED",
        "COPIED_TO_CLIPBOARD_TRANSIENT_RISK",
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
