#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Run the bounded Atelier against an already installed, loopback Ollama model.

The operator token and persistent P-256 signer live together in a current-user
Windows DPAPI vault under LocalAppData. No model pull, provider key, remote
enrollment, browser launch, or secret-bearing command argument is performed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import socket
import stat
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import enroll_hf_atelier_operator as enroll


HOST = "127.0.0.1"
PORT = 19090
OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"
OLLAMA_CHAT_URL = "http://127.0.0.1:11434/api/chat"
OLLAMA_TAGS_TIMEOUT_S = 10.0
DEFAULT_MODEL = "qwen3:4b-instruct"
MIN_FREE_BYTES = 1_500_000_000
VAULT_MAGIC = b"A11OY-ATELIER-LOCAL-DPAPI-V1\x00"
MAX_VAULT_BYTES = 16_384
MAX_TAGS_BYTES = 1_048_576
_HEX_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_MODEL_TAG = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,79}\Z")
_TOKEN = re.compile(r"[A-Za-z0-9_-]{64}\Z")


class LocalHold(RuntimeError):
    """Fixed, secret-safe reason to stop local startup."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class StoragePaths:
    base: Path
    data: Path
    vault: Path
    ledger_dir: Path
    ledger: Path


def _is_link(path: Path) -> bool:
    """Detect symlinks and Windows junction/reparse points before file access."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    except OSError:
        raise LocalHold("LOCAL_STORAGE_UNAVAILABLE") from None
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _reject_links(path: Path) -> None:
    for component in (path, *path.parents):
        if _is_link(component):
            raise LocalHold("LOCAL_STORAGE_LINK_UNSAFE")


def _storage_paths(local_app_data: str | Path | None = None) -> StoragePaths:
    raw = os.environ.get("LOCALAPPDATA", "") if local_app_data is None else str(local_app_data)
    base = Path(raw)
    if not raw or not base.is_absolute() or not base.is_dir():
        raise LocalHold("LOCALAPPDATA_UNAVAILABLE")
    _reject_links(base)
    try:
        base = base.resolve(strict=True)
        repo = REPO_ROOT.resolve(strict=True)
    except OSError:
        raise LocalHold("LOCALAPPDATA_UNAVAILABLE") from None
    if base == repo or repo in base.parents:
        raise LocalHold("LOCAL_STORAGE_IN_REPOSITORY")
    data = base / "SZL Holdings" / "A11oy" / "Atelier Local"
    ledger_dir = data / "ledger"
    result = StoragePaths(base, data, data / "operator.dpapi", ledger_dir,
                          ledger_dir / "turns.jsonl")
    _reject_links(result.vault)
    _reject_links(result.ledger)
    return result


def _check_free_space(base: Path) -> None:
    try:
        if shutil.disk_usage(base).free < MIN_FREE_BYTES:
            raise LocalHold("LOCAL_STORAGE_LOW")
    except OSError:
        raise LocalHold("LOCAL_STORAGE_UNAVAILABLE") from None


def _prepare_storage(paths: StoragePaths) -> None:
    _check_free_space(paths.base)
    _reject_links(paths.vault)
    _reject_links(paths.ledger)
    try:
        paths.ledger_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise LocalHold("LOCAL_STORAGE_UNAVAILABLE") from None
    _reject_links(paths.vault)
    _reject_links(paths.ledger)
    if not paths.ledger_dir.is_dir() or paths.ledger.is_dir():
        raise LocalHold("LOCAL_STORAGE_UNAVAILABLE")


def _public_fingerprint(private_key: Any) -> str:
    from cryptography.hazmat.primitives import serialization

    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    return hashlib.sha256(public_pem).hexdigest()


def _new_record() -> dict[str, Any]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(serialization.Encoding.PEM,
                            serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode("ascii")
    token = secrets.token_urlsafe(48)
    return {"version": 1, "owner_id": "owner:local", "namespace": "a11oy",
            "key_id": "local-" + secrets.token_hex(8), "token": token,
            "token_sha256": hashlib.sha256(token.encode("ascii")).hexdigest(),
            "signer_pem": pem, "signer_public_sha256": _public_fingerprint(key)}


def _validate_record(value: Any) -> dict[str, Any]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    fields = {"version", "owner_id", "namespace", "key_id", "token",
              "token_sha256", "signer_pem", "signer_public_sha256"}
    if not isinstance(value, dict) or set(value) != fields or type(value["version"]) is not int \
            or value["version"] != 1 or value["owner_id"] != "owner:local" \
            or value["namespace"] != "a11oy":
        raise LocalHold("LOCAL_VAULT_MALFORMED")
    try:
        enroll._validate_key_id(value["key_id"])
        token = value["token"]
        if (not isinstance(token, str) or not _TOKEN.fullmatch(token)
                or value["token_sha256"] != hashlib.sha256(token.encode("ascii")).hexdigest()):
            raise ValueError("token")
        pem = value["signer_pem"]
        if not isinstance(pem, str) or not 150 <= len(pem) <= 4096:
            raise ValueError("signer")
        key = serialization.load_pem_private_key(pem.encode("ascii"), password=None)
        if not isinstance(key, ec.EllipticCurvePrivateKey) or key.curve.name != "secp256r1":
            raise ValueError("curve")
        if value["signer_public_sha256"] != _public_fingerprint(key):
            raise ValueError("public fingerprint")
    except (TypeError, ValueError, UnicodeError, enroll.EnrollmentHold):
        raise LocalHold("LOCAL_VAULT_MALFORMED") from None
    return value


def _read_vault(path: Path) -> dict[str, Any]:
    _reject_links(path)
    try:
        if not path.is_file() or not 0 < path.stat().st_size <= MAX_VAULT_BYTES:
            raise LocalHold("LOCAL_VAULT_MALFORMED")
        with path.open("rb") as stream:
            sealed = stream.read(MAX_VAULT_BYTES + 1)
        if len(sealed) > MAX_VAULT_BYTES or not sealed.startswith(VAULT_MAGIC) \
                or len(sealed) == len(VAULT_MAGIC):
            raise LocalHold("LOCAL_VAULT_MALFORMED")
        plain = enroll._dpapi_unprotect(sealed[len(VAULT_MAGIC):])
        return _validate_record(json.loads(plain))
    except (OSError, ValueError, UnicodeError, enroll.EnrollmentHold):
        raise LocalHold("LOCAL_VAULT_UNAVAILABLE") from None


def _ensure_vault(paths: StoragePaths) -> dict[str, Any]:
    _reject_links(paths.vault)
    if paths.vault.exists():
        return _read_vault(paths.vault)
    _check_free_space(paths.base)
    record = _new_record()
    sealed = VAULT_MAGIC + enroll._dpapi_protect(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    if len(sealed) > MAX_VAULT_BYTES:
        raise LocalHold("LOCAL_VAULT_MALFORMED")
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        descriptor = os.open(paths.vault, flags, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(sealed)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        # A concurrent first run can create the vault. Reuse only if valid.
        return _read_vault(paths.vault)
    except OSError:
        raise LocalHold("LOCAL_VAULT_WRITE_FAILED") from None
    return _read_vault(paths.vault)


def _validate_model_tag(model: str) -> str:
    if not isinstance(model, str) or not _MODEL_TAG.fullmatch(model) or "grok" in model.lower():
        raise LocalHold("LOCAL_MODEL_INVALID")
    return model


def _installed_model_digest(model: str, expected_digest: str | None = None,
                            opener: Any = None) -> str:
    """Inspect Ollama's local tags only; never request /api/pull or remote URLs."""
    model = _validate_model_tag(model)
    if expected_digest is not None and not _HEX_SHA256.fullmatch(expected_digest):
        raise LocalHold("EXPECTED_MODEL_DIGEST_INVALID")
    client = opener if opener is not None else urllib.request.build_opener(
        urllib.request.ProxyHandler({}))
    request = urllib.request.Request(OLLAMA_TAGS_URL, method="GET",
                                     headers={"Accept": "application/json"})
    try:
        with client.open(request, timeout=OLLAMA_TAGS_TIMEOUT_S) as response:
            if response.status != 200:
                raise LocalHold("OLLAMA_UNAVAILABLE")
            raw = response.read(MAX_TAGS_BYTES + 1)
        if len(raw) > MAX_TAGS_BYTES:
            raise LocalHold("OLLAMA_TAGS_INVALID")
        document = json.loads(raw)
    except (OSError, TimeoutError, ValueError, urllib.error.URLError):
        raise LocalHold("OLLAMA_UNAVAILABLE") from None
    if not isinstance(document, dict) or not isinstance(document.get("models"), list):
        raise LocalHold("OLLAMA_TAGS_INVALID")
    matches = [row for row in document["models"]
               if isinstance(row, dict) and row.get("name") == model]
    if len(matches) != 1:
        raise LocalHold("LOCAL_MODEL_NOT_INSTALLED")
    row = matches[0]
    digest = row.get("digest")
    if (row.get("model", model) != model or not isinstance(digest, str)
            or not _HEX_SHA256.fullmatch(digest)):
        raise LocalHold("OLLAMA_TAGS_INVALID")
    if expected_digest is not None and digest != expected_digest:
        raise LocalHold("LOCAL_MODEL_DIGEST_MISMATCH")
    return digest


def _configure_runtime(record: dict[str, Any], paths: StoragePaths, model: str,
                       model_digest: str, environ: dict[str, str] | None = None) -> None:
    """Load secrets only into this server process; registry contains a digest."""
    env = os.environ if environ is None else environ
    record = _validate_record(record)
    env["A11OY_ATELIER_CREDENTIALS_JSON"] = enroll._registry_json(
        record["token"], record["owner_id"], record["key_id"])
    env["A11OY_ATELIER_NAMESPACE"] = "a11oy"
    env["A11OY_ATELIER_LOCAL_URL"] = OLLAMA_CHAT_URL
    env["A11OY_ATELIER_LOCAL_MODEL"] = _validate_model_tag(model)
    if not _HEX_SHA256.fullmatch(model_digest):
        raise LocalHold("LOCAL_MODEL_DIGEST_INVALID")
    env["A11OY_ATELIER_LOCAL_MODEL_DIGEST"] = model_digest
    env["A11OY_ATELIER_LEDGER_PATH"] = str(paths.ledger)
    env["A11OY_ATELIER_REQUIRED_MOUNT"] = ""
    env["A11OY_COMMAND_CENTRE_PREVIEW"] = "1"
    env["SZL_COSIGN_PRIVATE_PEM"] = record["signer_pem"]
    env["A11OY_REQUIRE_PERSISTENT_SIGNING"] = "1"
    # This local process must never pick up an ambient xAI credential.
    env["A11OY_ATELIER_XAI_API_KEY"] = ""
    env["XAI_API_KEY"] = ""
    env["SZL_GROK_MODEL"] = ""
    env["A11OY_ATELIER_MODEL"] = ""
    # A local source tree may include uncommitted work; do not claim a commit.
    env["SZL_GIT_SHA"] = ""


def _build_app():
    from fastapi import FastAPI
    from routers import atelier_grok, command_centre

    app = FastAPI(title="A11oy Atelier Local", docs_url=None, redoc_url=None,
                  openapi_url=None)
    command_centre.register(app)
    atelier_grok.register(app)
    if atelier_grok.local_health().get("ready") is not True:
        raise LocalHold("LOCAL_BACKEND_NOT_READY")
    return app


def _reserve_listener() -> socket.socket:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind((HOST, PORT))
        listener.listen(128)
    except OSError:
        listener.close()
        raise LocalHold("LOCAL_PORT_IN_USE") from None
    return listener


def serve(model: str, expected_digest: str | None = None) -> None:
    if os.name != "nt":
        raise LocalHold("WINDOWS_DPAPI_REQUIRED")
    paths = _storage_paths()
    _check_free_space(paths.base)
    digest = _installed_model_digest(model, expected_digest)
    with _reserve_listener() as listener:
        _prepare_storage(paths)
        record = _ensure_vault(paths)
        _configure_runtime(record, paths, model, digest)
        app = _build_app()
        import uvicorn

        print(json.dumps({"state": "LOCAL_ATELIER_STARTING",
                          "url": f"http://{HOST}:{PORT}/a11oy/atelier",
                          "model": model, "observed_model_digest": digest,
                          "operator_token_printed": False}, sort_keys=True), flush=True)
        config = uvicorn.Config(app, host=HOST, port=PORT, log_level="warning",
                                access_log=False, proxy_headers=False)
        uvicorn.Server(config).run(sockets=[listener])


def copy_operator_token() -> None:
    if os.name != "nt":
        raise LocalHold("WINDOWS_DPAPI_REQUIRED")
    paths = _storage_paths()
    _prepare_storage(paths)
    record = _ensure_vault(paths)
    enroll._copy_to_clipboard(record["token"])
    print(json.dumps({"state": "OPERATOR_TOKEN_COPIED_TO_CLIPBOARD",
                      "transient_clipboard_exposure": True,
                      "operator_token_printed": False}, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--serve", action="store_true", help="Serve only on 127.0.0.1:19090")
    action.add_argument("--copy-operator-token", action="store_true",
                        help="Explicitly copy the local bearer to the Windows clipboard")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help="Exact Ollama model tag already installed locally")
    parser.add_argument("--expected-model-digest",
                        help="Optional exact 64-character SHA-256 digest from local Ollama tags")
    args = parser.parse_args(argv)
    try:
        if args.serve:
            serve(args.model, args.expected_model_digest)
        else:
            if args.model != DEFAULT_MODEL or args.expected_model_digest is not None:
                raise LocalHold("COPY_ARGUMENTS_INVALID")
            copy_operator_token()
        return 0
    except (LocalHold, enroll.EnrollmentHold) as exc:
        print(json.dumps({"state": "HOLD", "code": exc.code}, sort_keys=True))
        return 2
    except Exception:
        # Never include an exception message: dependencies can embed secret data.
        print(json.dumps({"state": "HOLD", "code": "LOCAL_ATELIER_UNAVAILABLE"}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
