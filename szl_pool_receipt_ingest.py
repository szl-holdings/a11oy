# SPDX-License-Identifier: Apache-2.0
"""Fail-closed ingestion surface for compute-pool/v1 inference receipts.

The compute-pool/v1 contract (szl_compute_pool_contract) promotes a node above
REACHABLE only when a fresh, bounded, pool-attester-signed DSSE inference
receipt is present in A11OY_COMPUTE_POOL_RECEIPT_DIR.  Until now the estate had
a verifier but no authorized transport for getting a receipt INTO the running
Space: the minter lives on the sovereign laptop, the receipts are short-lived
(freshness window defaults to 300 s), and a redeploy per receipt is absurd.

This module adds exactly one route (POST /api/{ns}/v1/compute-pool/receipts)
with fail-closed semantics end to end:

  * no A11OY_POOL_RECEIPT_INGEST_TOKEN configured  -> 503, nothing accepted;
  * wrong or absent bearer                         -> 403 (constant-time compare);
  * envelope larger than the contract bound        -> 413, nothing stored;
  * pool trust root (A11OY_POOL_RECEIPT_PUBLIC_KEY_PEM + ...SHA256) absent or
    mismatched                                    -> 503, nothing accepted;
  * signature/schema invalid (reuse of the contract verifier — single source
    of verification truth)                        -> 422, nothing stored;
  * A11OY_COMPUTE_POOL_RECEIPT_DIR not a safe directory -> 503.

Accepted, verified envelopes are stored atomically (tmp + os.replace) under a
forward-sortable receipt filename, as the EXACT bytes that were received, and
the receipt directory is pruned (this module's filename pattern only) so the
newest-at-most-_MAX_RECEIPTS files always fit under the contract's
glob("*.dsse.json")[:_MAX_RECEIPTS] newest-selection window.  Nothing here can
promote a node by itself: promotion still requires the contract verifier to
re-verify the stored bytes against the pinned pool key on read.

The route intentionally has NO GET twin: verification/readback is the
contract's job, so storage stays write-only here.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Request
from fastapi.responses import JSONResponse

import szl_compute_pool_contract as pool_contract

INGEST_TOKEN_ENV = "A11OY_POOL_RECEIPT_INGEST_TOKEN"
_DIGEST_DIR_ENV = "A11OY_COMPUTE_POOL_RECEIPT_DIR"
_MAX_ENVELOPE_BYTES = pool_contract._MAX_RECEIPT_BYTES
_MAX_FILES = pool_contract._MAX_RECEIPTS
# Forward-sortable receipt filename: seconds-since-epoch + receipt digest head.
# Only files matching this pattern are ever pruned by this module.
_RECEIPT_NAME_RE = re.compile(r"^[0-9]{10}-[0-9a-f]{16}\.dsse\.json$")


def _json_error(status: int, error: str, **extra: Any) -> JSONResponse:
    return JSONResponse({"error": error, **extra}, status_code=status, headers={"Cache-Control": "no-store"})


def _ingest_token() -> Optional[str]:
    raw = os.environ.get(INGEST_TOKEN_ENV) or ""
    raw = raw.strip()
    return raw or None


def _bearer_authorized(request: Request, token: str) -> bool:
    header = request.headers.get("authorization") or ""
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return False
    return hmac.compare_digest(value.strip().encode("utf-8"), token.encode("utf-8"))


def _safe_receipt_root() -> Optional[Path]:
    configured = (os.environ.get(_DIGEST_DIR_ENV) or "").strip()
    if not configured:
        return None
    root = Path(configured)
    try:
        os.makedirs(root, exist_ok=True)
    except OSError:
        return None
    try:
        info = os.lstat(root)
        if stat.S_ISLNK(info.st_mode) or pool_contract._is_reparse(info):
            return None
        if not stat.S_ISDIR(info.st_mode):
            return None
    except OSError:
        return None
    return root


def _epoch_seconds(observed_at: str) -> Optional[int]:
    parsed = pool_contract._iso(observed_at)
    if parsed is None:
        return None
    return int(parsed.timestamp())


def _atomic_store(root: Path, raw: bytes, payload: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    observed_at = str(payload.get("observed_at") or "")
    epoch = _epoch_seconds(observed_at)
    if epoch is None:  # defensive: the contract verifier already parsed it
        return False, None
    digest = hashlib.sha256(raw).hexdigest()
    name = f"{epoch:010d}-{digest[:16]}.dsse.json"
    final_path = root / name
    fd, tmp_name = tempfile.mkstemp(prefix=".ingest-", suffix=".tmp", dir=str(root))
    try:
        try:
            # mkstemp already creates the file owner-only (0o600 on POSIX,
            # O_EXCL everywhere); os.fchmod is POSIX-only and would crash
            # this otherwise-portable surface on Windows dev machines.
            # Write ALL bytes or none: os.write may be short (disk full/quota)
            # and a truncated envelope must never be acknowledged as stored.
            written = 0
            while written < len(raw):
                count = os.write(fd, raw[written:])
                if count <= 0:
                    raise OSError("short write to receipt file")
                written += count
        finally:
            os.close(fd)
        os.replace(tmp_name, final_path)
    except OSError:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        return False, None
    return True, name


def _prune(root: Path) -> None:
    """Keep only the newest _MAX_FILES receipts written by this surface.

    Pruning is pattern-scoped: foreign *.dsse.json files (hand-placed, another
    writer) are never touched, and the pool contract keeps its own exact
    glob/bounds semantics.  Files are ranked newest-first by filename, which
    for this module's pattern is observed-received order.
    """
    try:
        names = [item.name for item in os.scandir(root) if item.is_file() and _RECEIPT_NAME_RE.match(item.name)]
    except OSError:
        return
    if len(names) <= _MAX_FILES:
        return
    for stale in sorted(names, reverse=True)[_MAX_FILES:]:
        try:
            (root / stale).unlink()
        except OSError:
            continue


async def _ingest(request: Request) -> JSONResponse:  # noqa: ANN401
    token = _ingest_token()
    if token is None:
        return _json_error(503, "receipt ingestion not configured (missing ingest token)")
    if not _bearer_authorized(request, token):
        return _json_error(403, "not authorized")
    try:
        content_length = int(request.headers.get("content-length") or "0")
    except ValueError:
        content_length = 0
    if content_length > _MAX_ENVELOPE_BYTES:
        return _json_error(413, "envelope too large", limit_bytes=_MAX_ENVELOPE_BYTES)
    # Bounded read: a chunked body or a lying Content-Length must never
    # buffer more than the envelope bound -- request.body() materializes
    # the whole stream first, so stream incrementally and abort at the
    # first byte past the bound. Nothing beyond the limit is ever buffered.
    chunks: List[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > _MAX_ENVELOPE_BYTES:
            return _json_error(413, "envelope too large", limit_bytes=_MAX_ENVELOPE_BYTES)
        chunks.append(chunk)
    raw = b"".join(chunks)
    if len(raw) <= 0:
        return _json_error(413, "envelope too large", limit_bytes=_MAX_ENVELOPE_BYTES)
    verifier = pool_contract._pool_verifier()
    if verifier is None:
        return _json_error(503, "pool trust root not configured or mismatched")
    try:
        envelope = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _json_error(422, "envelope is not valid JSON")
    payload = pool_contract._verify_pool_envelope(envelope, verifier)
    if payload is None:
        return _json_error(422, "envelope failed pool verification (signature or payload contract)")
    root = _safe_receipt_root()
    if root is None:
        return _json_error(503, "receipt directory not configured or unsafe")
    stored, name = _atomic_store(root, raw, payload)
    if not stored:
        return _json_error(500, "atomic receipt storage failed")
    _prune(root)
    return JSONResponse(
        {
            "accepted": True,
            "node_id": payload.get("node_id"),
            "observed_at": payload.get("observed_at"),
            "receipt_sha256": hashlib.sha256(raw).hexdigest(),
            "stored_as": name,
        },
        status_code=202,
        headers={"Cache-Control": "no-store"},
    )


def register(app: Any, ns: str = "a11oy") -> List[str]:
    route = f"/api/{ns}/v1/compute-pool/receipts"
    existing = {getattr(item, "path", None) for item in app.router.routes}
    if route in existing:
        return []

    @app.post(route)
    async def ingest_pool_receipt(request: Request) -> JSONResponse:  # noqa: ANN202
        return await _ingest(request)

    return [route]


__all__ = ["INGEST_TOKEN_ENV", "register"]
