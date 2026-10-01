#!/usr/bin/env python3
# Copyright 2026 SZL Holdings - SPDX-License-Identifier: Apache-2.0
"""Verify installed A11oy signing authority against the pinned runtime key.

Founder decision 2026-09-30: this module is the supported consumer of
installed credential authority for the hf-sync manual-prerequisite gate.

What it measures (all public, no secret value is read, printed or stored):

* ``{origin}/cosign.pub`` is fetched without redirects, bounded to 4 KiB and
  parsed as an ECDSA P-256 SubjectPublicKeyInfo. The runtime serves the public
  half derived from the private key its signer loaded (``a11oy_signing_key``:
  ``SZL_COSIGN_PRIVATE_PEM`` first, then configured persistent sources).
* The served key's DER SHA-256 must equal BOTH independent pins: the committed
  key ``ayllu/keys/council-runtime-2026-07-21.pub`` and the hardcoded
  fingerprint below. If the two pins disagree the result fails closed.
* The served key must NOT equal the static embedded fallback
  ``szl_dsse.COSIGN_PUBLIC_PEM`` (read from source, never imported); serving
  it means no private key is loaded (``SIGNING_KEY_NOT_INSTALLED``).
* ``GDW_CREDENTIALS_JSON`` must be present by name. Its live authority remains
  proven downstream by ``scripts/prove_hf_gdw_runtime.py``.
* The GitHub public reader is OPTIONAL: absent is honestly labelled
  ``PUBLIC_ANONYMOUS``; present by name is ``INSTALLED_NAME_ONLY``.

What it does NOT prove: no fresh signature is requested (the signing route is
operator-gated), so a hostile runtime that copied the public key could pass.
That residual is bounded by the exact-source, single-writer and live-proof
guards of hf-sync, not by this module.

Network access goes through an injectable ``get(url) -> (status, headers,
body)`` so tests are offline. ``huggingface_hub`` is never imported here.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA = "szl.hf-installed-authority/v1"
CANONICAL_ORIGIN = "https://szlholdings-a11oy.hf.space"
PINNED_SIGNING_PUBLIC_KEY_PATH = "ayllu/keys/council-runtime-2026-07-21.pub"
# Second, independent pin: DER SHA-256 of the pinned SubjectPublicKeyInfo.
PINNED_SIGNING_KEY_DER_SHA256 = "8e2d106c6995e11dbf7cbedfa9e5800bb50c82a635756e40dcd330364f6ea8ba"
STATIC_FALLBACK_SOURCE = "szl_dsse.py"
STATIC_FALLBACK_NAME = "COSIGN_PUBLIC_PEM"
PUBLIC_KEY_ROUTE = "/cosign.pub"
HONEST_ROUTE = "/api/a11oy/v1/honest"
MAX_PUBLIC_KEY_BYTES = 4 * 1024
MAX_HONEST_BYTES = 64 * 1024
MAX_PIN_FILE_BYTES = 4 * 1024
REQUEST_TIMEOUT_SECONDS = 15

SIGNING_SECRET = "SZL_COSIGN_PRIVATE_PEM"
GDW_SECRET = "GDW_CREDENTIALS_JSON"
GITHUB_PUBLIC_READ_SECRET = "A11OY_GITHUB_PUBLIC_READ_TOKEN"
REQUIRED_SECRET_NAMES = (SIGNING_SECRET, GDW_SECRET)
OPTIONAL_SECRET_NAMES = (GITHUB_PUBLIC_READ_SECRET,)

VERIFIED_PINNED_RUNTIME_KEY = "VERIFIED_PINNED_RUNTIME_KEY"
SIGNING_KEY_NOT_INSTALLED = "SIGNING_KEY_NOT_INSTALLED"
SIGNING_KEY_MISMATCH = "SIGNING_KEY_MISMATCH"
ORIGIN_UNAVAILABLE = "ORIGIN_UNAVAILABLE"
SIGNING_STATES = (VERIFIED_PINNED_RUNTIME_KEY, SIGNING_KEY_NOT_INSTALLED,
                  SIGNING_KEY_MISMATCH, ORIGIN_UNAVAILABLE)
GDW_NAME_PRESENT = "NAME_PRESENT_RUNTIME_PROVEN_DOWNSTREAM"
GDW_CREDENTIALS_MISSING = "GDW_CREDENTIALS_MISSING"
READER_PUBLIC_ANONYMOUS = "PUBLIC_ANONYMOUS"
READER_INSTALLED_NAME_ONLY = "INSTALLED_NAME_ONLY"

# Fixed public diagnostics. Nothing from a provider, response body or
# exception text is ever copied into a report.
DIAGNOSTIC_CODES = {
    "INSTALLED_AUTHORITY_VERIFIED", "INSTALLED_AUTHORITY_UNKNOWN",
    "AUTHORITY_ORIGIN_NOT_CANONICAL", "AUTHORITY_ORIGIN_UNAVAILABLE",
    "SIGNING_KEY_NOT_INSTALLED", "SIGNING_KEY_MISMATCH", "PINNED_KEY_INCONSISTENT",
    "SIGNING_SECRET_MISSING", "GDW_CREDENTIALS_MISSING", "PUBLIC_VARIABLE_COLLISION",
}

Getter = Callable[[str], tuple[int, Mapping[str, str], bytes]]


class _NoRedirect(Exception):
    pass


def default_get(url: str, *, max_bytes: int = MAX_PUBLIC_KEY_BYTES) -> tuple[int, Mapping[str, str], bytes]:
    """Unauthenticated GET, no redirects, bounded body. Never sends credentials."""
    from urllib import request
    from urllib.error import HTTPError

    class Handler(request.HTTPRedirectHandler):
        def redirect_request(self, *_args, **_kwargs):  # noqa: D401 - urllib hook
            return None  # a 3xx surfaces as HTTPError and is rejected by the caller

    opener = request.build_opener(Handler)
    req = request.Request(url, method="GET", headers={
        "Accept": "text/plain, application/json",
        "User-Agent": "SZL-Installed-Authority-Verifier/1.0",
        "Cache-Control": "no-cache",
    })
    try:
        with opener.open(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = response.read(max_bytes + 1)
            return int(response.status), dict(response.headers.items()), body
    except HTTPError as error:
        return int(error.code), dict(error.headers.items()) if error.headers else {}, b""


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _der_sha256_of_pem(pem: bytes) -> str:
    """Parse a PUBLIC ECDSA P-256 SPKI PEM and return its DER SHA-256."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key = serialization.load_pem_public_key(pem)
    if not isinstance(key, ec.EllipticCurvePublicKey) or getattr(key.curve, "name", "") != "secp256r1":
        raise ValueError("public key is not ECDSA P-256")
    der = key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return hashlib.sha256(der).hexdigest()


def pinned_fingerprint(pinned_pem_path: Path | str | None = None) -> str:
    """Return the pinned DER SHA-256 iff the pin file and hardcoded pin agree."""
    path = Path(pinned_pem_path) if pinned_pem_path is not None else REPO_ROOT / PINNED_SIGNING_PUBLIC_KEY_PATH
    with path.open("rb") as stream:
        raw = stream.read(MAX_PIN_FILE_BYTES + 1)
    if len(raw) > MAX_PIN_FILE_BYTES:
        raise ValueError("pinned key file is oversized")
    from_file = _der_sha256_of_pem(raw)
    if from_file != PINNED_SIGNING_KEY_DER_SHA256:
        raise ValueError("pinned key file disagrees with the hardcoded fingerprint")
    return from_file


def static_fallback_fingerprint(source_path: Path | str | None = None) -> str:
    """DER SHA-256 of ``szl_dsse.COSIGN_PUBLIC_PEM``, read statically (never imported)."""
    path = Path(source_path) if source_path is not None else REPO_ROOT / STATIC_FALLBACK_SOURCE
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values = [node.value.value for node in tree.body
              if isinstance(node, ast.Assign) and len(node.targets) == 1
              and isinstance(node.targets[0], ast.Name) and node.targets[0].id == STATIC_FALLBACK_NAME
              and isinstance(node.value, ast.Constant) and type(node.value.value) is str]
    if len(values) != 1:
        raise ValueError("static fallback public key is not uniquely defined")
    return _der_sha256_of_pem(values[0].strip().encode("ascii"))


def _canonical_origin(origin: str) -> str | None:
    value = (origin or "").strip().rstrip("/")
    return value if value == CANONICAL_ORIGIN else None


def verify_signing_authority(
    origin: str,
    get: Getter | None = None,
    pinned_pem_path: Path | str | None = None,
    *,
    static_source_path: Path | str | None = None,
) -> dict[str, Any]:
    """Compare the live runtime public key with both pins; never reads a secret."""
    result: dict[str, Any] = {
        "state": ORIGIN_UNAVAILABLE,
        "diagnostic_code": "AUTHORITY_ORIGIN_UNAVAILABLE",
        "route": PUBLIC_KEY_ROUTE,
        "pinned_key_path": PINNED_SIGNING_PUBLIC_KEY_PATH,
        "pinned_fingerprint_sha256": PINNED_SIGNING_KEY_DER_SHA256,
        "served_fingerprint_sha256": None,
        "fresh_signature_verified": False,
    }
    try:
        pinned = pinned_fingerprint(pinned_pem_path)
        static = static_fallback_fingerprint(static_source_path)
    except Exception:
        result.update(state=SIGNING_KEY_MISMATCH, diagnostic_code="PINNED_KEY_INCONSISTENT")
        return result
    if pinned == static:
        # A pin equal to the static fallback could never distinguish an
        # installed key from an absent one.
        result.update(state=SIGNING_KEY_MISMATCH, diagnostic_code="PINNED_KEY_INCONSISTENT")
        return result
    base = _canonical_origin(origin)
    if base is None:
        result["diagnostic_code"] = "AUTHORITY_ORIGIN_NOT_CANONICAL"
        return result
    get = get or default_get
    try:
        status, _headers, body = get(base + PUBLIC_KEY_ROUTE)
    except Exception:
        return result
    if type(status) is not int or status != 200 or not isinstance(body, (bytes, bytearray)):
        return result
    if len(body) > MAX_PUBLIC_KEY_BYTES or not body:
        return result
    try:
        served = _der_sha256_of_pem(bytes(body))
    except Exception:
        result.update(state=SIGNING_KEY_MISMATCH, diagnostic_code="SIGNING_KEY_MISMATCH")
        return result
    result["served_fingerprint_sha256"] = served
    if served == static:
        result.update(state=SIGNING_KEY_NOT_INSTALLED, diagnostic_code="SIGNING_KEY_NOT_INSTALLED")
    elif served == pinned == PINNED_SIGNING_KEY_DER_SHA256:
        result.update(state=VERIFIED_PINNED_RUNTIME_KEY, diagnostic_code="INSTALLED_AUTHORITY_VERIFIED")
    else:
        result.update(state=SIGNING_KEY_MISMATCH, diagnostic_code="SIGNING_KEY_MISMATCH")
    return result


def verify_gdw_authority(secret_names: Iterable[str]) -> dict[str, Any]:
    """Pre-deploy admission needs only the name; live proof stays downstream."""
    present = GDW_SECRET in set(secret_names)
    return {
        "state": GDW_NAME_PRESENT if present else GDW_CREDENTIALS_MISSING,
        "secret_name": GDW_SECRET,
        "blocking": not present,
        "live_proof": "scripts/prove_hf_gdw_runtime.py (post-deploy)",
    }


def github_public_reader_state(secret_names: Iterable[str]) -> dict[str, Any]:
    """Optional reader (founder decision): reported, never required."""
    present = GITHUB_PUBLIC_READ_SECRET in set(secret_names)
    return {
        "state": READER_INSTALLED_NAME_ONLY if present else READER_PUBLIC_ANONYMOUS,
        "secret_name": GITHUB_PUBLIC_READ_SECRET,
        "blocking": False,
        "value_verified": False,
    }


def read_live_git_sha(origin: str, get: Getter | None = None) -> str | None:
    """Informational: the runtime's self-reported source revision (public)."""
    base = _canonical_origin(origin)
    if base is None:
        return None
    try:
        status, _headers, body = (get or (lambda url: default_get(url, max_bytes=MAX_HONEST_BYTES)))(base + HONEST_ROUTE)
        if status != 200 or not isinstance(body, (bytes, bytearray)) or len(body) > MAX_HONEST_BYTES:
            return None
        value = json.loads(bytes(body).decode("utf-8")).get("git_sha")
    except Exception:
        return None
    return value if type(value) is str and re.fullmatch(r"[0-9a-f]{40}", value) else None


def verify_installed_authority(
    secret_names: Iterable[str],
    public_variable_names: Iterable[str] = (),
    *,
    origin: str = CANONICAL_ORIGIN,
    get: Getter | None = None,
    pinned_pem_path: Path | str | None = None,
    static_source_path: Path | str | None = None,
) -> dict[str, Any]:
    """Combine signing, GDW and reader evidence into one secret-free report."""
    names = {name for name in secret_names if type(name) is str}
    public_names = {name for name in public_variable_names if type(name) is str}
    started = _utc_now()
    signing = verify_signing_authority(origin, get, pinned_pem_path, static_source_path=static_source_path)
    gdw = verify_gdw_authority(names)
    reader = github_public_reader_state(names)
    collision = bool(set(REQUIRED_SECRET_NAMES + OPTIONAL_SECRET_NAMES) & public_names)
    signing_secret_present = SIGNING_SECRET in names

    if collision:
        state, diagnostic = "BLOCKED", "PUBLIC_VARIABLE_COLLISION"
    elif not signing_secret_present:
        state, diagnostic = "BLOCKED", "SIGNING_SECRET_MISSING"
    elif signing["state"] == ORIGIN_UNAVAILABLE:
        state, diagnostic = "UNKNOWN", signing["diagnostic_code"]
    elif signing["state"] != VERIFIED_PINNED_RUNTIME_KEY:
        state, diagnostic = "BLOCKED", signing["diagnostic_code"]
    elif gdw["blocking"]:
        state, diagnostic = "BLOCKED", "GDW_CREDENTIALS_MISSING"
    else:
        state, diagnostic = "VERIFIED", "INSTALLED_AUTHORITY_VERIFIED"
    if diagnostic not in DIAGNOSTIC_CODES:
        state, diagnostic = "UNKNOWN", "INSTALLED_AUTHORITY_UNKNOWN"

    return {
        "schema": SCHEMA,
        "origin": _canonical_origin(origin) or "NOT_CANONICAL",
        "observed_at_start": started,
        "observed_at_end": _utc_now(),
        "live_git_sha": read_live_git_sha(origin, get),
        "credential_authority_state": state,
        "diagnostic_code": diagnostic,
        "signing": signing,
        "signing_secret_name_present": signing_secret_present,
        "gdw": gdw,
        "github_public_reader": reader,
        "public_variable_collision": collision,
        "evidence_class": "measured-public-key-match",
        "proves": "the runtime's loaded signer derives the pinned public key",
        "does_not_prove": "fresh proof-of-possession (no signature requested)",
        "secret_values_read": False,
        "secret_values_written": False,
    }


def main(argv: list[str] | None = None) -> int:
    """Public-only CLI: checks the live key match (no provider metadata, no secrets)."""
    import argparse
    import os

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--origin", default=os.environ.get("CANONICAL_ORIGIN", CANONICAL_ORIGIN))
    args = parser.parse_args(argv)
    report = verify_signing_authority(args.origin)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["state"] == VERIFIED_PINNED_RUNTIME_KEY else 1


if __name__ == "__main__":
    raise SystemExit(main())
