#!/usr/bin/env python3
# Copyright 2026 SZL Holdings - SPDX-License-Identifier: Apache-2.0
"""Shared bounds for the two admitted post-deploy live proofs.

Founder decision 2026-09-30 (wave 2 of the unfreeze) admits
``scripts/prove_hf_series_a_restart.py`` and ``scripts/prove_hf_gdw_runtime.py``
into ``hf-sync.yml``. The hold in ``docs/operations/series-a-github-public-read-binding.md``
named four concerns; each is closed here, structurally, for both proofs:

1. Destination. Only ``https://szlholdings-a11oy.hf.space`` (``CANONICAL_ORIGIN``)
   and ``https://huggingface.co/api/spaces/SZLHOLDINGS/a11oy`` (and sub-paths)
   are reachable. The network location is compared exactly (no case folding,
   ports, userinfo or trailing dots). Redirects are never followed: any 3xx
   is a hard ``REDIRECT_REJECTED`` failure.
2. Error text. Provider response bodies are never read on error and never
   copied into exceptions, logs or reports. Failures carry one fixed
   ``diagnostic_code`` from ``DIAGNOSTIC_CODES`` (plus an integer HTTP status
   where relevant). ``bounded_report`` additionally drops every string that is
   not a short, safe token before a report is written.
3. Drain/retry. Only HTTP 429/502/503/504 (transient admission) are retried,
   at most ``MAX_ATTEMPTS`` times inside ``RETRY_WINDOW_SECONDS`` and the
   proof-wide deadline. Everything else fails closed on the first response.
4. Effect scope. ``ScopedSpaceControl`` can only pause/restart (never factory
   reboot) and read the runtime of exactly ``SZLHOLDINGS/a11oy``. It has no
   secret, variable, volume, hardware, file or other-Space method. The GDW
   proof may only write inside namespace ``a11oy`` and must verify a signed
   receipt against the pinned runtime key
   ``ayllu/keys/council-runtime-2026-07-21.pub``.

This module never reads a credential from the environment; callers pass the
token in and it is only ever placed in an ``Authorization`` header.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

REPO_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_SPACE = "SZLHOLDINGS/a11oy"
CANONICAL_ORIGIN = "https://szlholdings-a11oy.hf.space"
CANONICAL_HOST = "szlholdings-a11oy.hf.space"
HF_API_HOST = "huggingface.co"
HF_SPACE_API_PATH = "/api/spaces/" + CANONICAL_SPACE
GDW_NAMESPACE = "a11oy"
PINNED_RUNTIME_KEY_PATH = "ayllu/keys/council-runtime-2026-07-21.pub"
# Independent copy of the pinned key's DER SHA-256 (same value as
# scripts/verify_installed_authority.py and check_hf_manual_prerequisites.py).
PINNED_RUNTIME_KEY_DER_SHA256 = (
    "8e2d106c6995e11dbf7cbedfa9e5800bb50c82a635756e40dcd330364f6ea8ba"
)
KHIPU_PAYLOAD_TYPE = "application/vnd.szl.khipu+json"

MAX_ATTEMPTS = 8
RETRY_WINDOW_SECONDS = 10 * 60
TRANSIENT_HTTP_STATUSES = frozenset({429, 502, 503, 504})
BACKOFF_BASE_SECONDS = 2.0
BACKOFF_CAP_SECONDS = 30.0
RETRY_AFTER_CAP_SECONDS = 60.0
REQUEST_TIMEOUT_SECONDS = 30.0
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_PIN_FILE_BYTES = 4 * 1024

DIAGNOSTIC_CODES = frozenset({
    "LIVE_PROOF_PASSED",
    "SETUP_REQUIRED",
    "DESTINATION_REJECTED",
    "REDIRECT_REJECTED",
    "HTTP_STATUS_REJECTED",
    "TRANSIENT_RETRY_EXHAUSTED",
    "DEADLINE_EXHAUSTED",
    "TRANSPORT_UNAVAILABLE",
    "RESPONSE_TOO_LARGE",
    "RESPONSE_NOT_JSON",
    "SPACE_SCOPE_REJECTED",
    "EFFECT_SCOPE_REJECTED",
    "NAMESPACE_SCOPE_REJECTED",
    "RESTART_PROOF_TIMEOUT",
    "RESTART_CONTRACT_FAILED",
    "GDW_CONTRACT_FAILED",
    "RECEIPT_UNSIGNED",
    "RECEIPT_SIGNATURE_INVALID",
    "PINNED_KEY_UNAVAILABLE",
    "INVALID_ARGUMENTS",
    "UNEXPECTED_FAILURE",
})
# Boundary failures that must never be absorbed by a polling loop.
HARD_CODES = frozenset({
    "DESTINATION_REJECTED",
    "REDIRECT_REJECTED",
    "SPACE_SCOPE_REJECTED",
    "EFFECT_SCOPE_REJECTED",
    "NAMESPACE_SCOPE_REJECTED",
    "DEADLINE_EXHAUSTED",
    "RESPONSE_TOO_LARGE",
    "RECEIPT_UNSIGNED",
    "RECEIPT_SIGNATURE_INVALID",
    "PINNED_KEY_UNAVAILABLE",
})

_SAFE_TEXT = re.compile(r"[A-Za-z0-9_.:/+@=-]{0,160}")
_ID_TOKEN = re.compile(r"[A-Za-z0-9._:-]{1,128}")


class ProofBoundaryError(RuntimeError):
    """A bounded failure that carries only a fixed diagnostic code."""

    def __init__(self, code: str, *, http_status: int | None = None) -> None:
        if code not in DIAGNOSTIC_CODES:
            code = "UNEXPECTED_FAILURE"
        self.code = code
        self.http_status = http_status if type(http_status) is int else None
        super().__init__(code if self.http_status is None else f"{code}:{self.http_status}")


def is_hard_failure(error: BaseException) -> bool:
    return isinstance(error, ProofBoundaryError) and error.code in HARD_CODES


def diagnostic_code(error: BaseException, default: str) -> str:
    code = getattr(error, "code", None)
    if isinstance(code, str) and code in DIAGNOSTIC_CODES:
        return code
    return default if default in DIAGNOSTIC_CODES else "UNEXPECTED_FAILURE"


def check_destination(url: str) -> str:
    """Return ``url`` unchanged when it targets an admitted destination."""

    if not isinstance(url, str) or len(url) > 2048:
        raise ProofBoundaryError("DESTINATION_REJECTED")
    try:
        parsed = urlsplit(url)
    except ValueError as exc:
        raise ProofBoundaryError("DESTINATION_REJECTED") from exc
    path = parsed.path
    if (
        parsed.scheme != "https"
        or parsed.fragment
        or any(ch in url for ch in "\\\r\n\t @")
        or "%" in path
        or "//" in path
        or any(segment in {".", ".."} for segment in path.split("/"))
    ):
        raise ProofBoundaryError("DESTINATION_REJECTED")
    if parsed.netloc == CANONICAL_HOST:
        if not path.startswith("/api/"):
            raise ProofBoundaryError("DESTINATION_REJECTED")
        return url
    if parsed.netloc == HF_API_HOST:
        if parsed.query or not (
            path == HF_SPACE_API_PATH or path.startswith(HF_SPACE_API_PATH + "/")
        ):
            raise ProofBoundaryError("DESTINATION_REJECTED")
        return url
    raise ProofBoundaryError("DESTINATION_REJECTED")


def require_canonical_origin(origin: str) -> str:
    if origin != CANONICAL_ORIGIN:
        raise ProofBoundaryError("DESTINATION_REJECTED")
    return origin


def require_canonical_space(repo_id: str) -> str:
    if repo_id != CANONICAL_SPACE:
        raise ProofBoundaryError("SPACE_SCOPE_REJECTED")
    return repo_id


class _RefuseRedirect(HTTPRedirectHandler):
    """Never follow a redirect; urllib then surfaces the 3xx as HTTPError."""

    def redirect_request(self, *_args, **_kwargs):  # noqa: D401
        return None


def default_opener():
    return build_opener(_RefuseRedirect())


def _retry_after(headers: Any) -> float | None:
    try:
        raw = headers.get("Retry-After") if headers is not None else None
        seconds = float(str(raw).strip()) if raw is not None else None
    except (AttributeError, TypeError, ValueError):
        return None
    if seconds is None or seconds < 0 or seconds != seconds:
        return None
    return min(seconds, RETRY_AFTER_CAP_SECONDS)


class BoundedTransport:
    """No-redirect, exact-destination JSON transport with a capped retry budget."""

    def __init__(
        self,
        *,
        deadline_seconds: float = RETRY_WINDOW_SECONDS,
        max_attempts: int = MAX_ATTEMPTS,
        opener: Any = None,
        sleep: Callable[[float], None] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if type(max_attempts) is not int or not 1 <= max_attempts <= MAX_ATTEMPTS:
            raise ProofBoundaryError("INVALID_ARGUMENTS")
        if not 0 < float(deadline_seconds) <= 3600:
            raise ProofBoundaryError("INVALID_ARGUMENTS")
        self.max_attempts = max_attempts
        self._opener = opener or default_opener()
        self._sleep = sleep or time.sleep
        self._clock = clock or time.monotonic
        self.deadline = self._clock() + float(deadline_seconds)
        self.log: list[dict[str, Any]] = []

    def remaining(self) -> float:
        return self.deadline - self._clock()

    def sleep(self, seconds: float) -> None:
        remaining = self.remaining()
        if remaining <= 0:
            raise ProofBoundaryError("DEADLINE_EXHAUSTED")
        self._sleep(min(max(0.0, float(seconds)), remaining))
        if self.remaining() <= 0:
            raise ProofBoundaryError("DEADLINE_EXHAUSTED")

    def _record(self, method: str, url: str, attempt: int, status: Any, outcome: str) -> None:
        # Only our own method, the admitted host/path and integers are kept.
        parsed = urlsplit(url)
        if len(self.log) < 200:
            self.log.append({
                "method": method, "host": parsed.netloc, "path": parsed.path[:160],
                "attempt": attempt, "http_status": status if type(status) is int else None,
                "outcome": outcome,
            })

    def request(
        self,
        method: str,
        url: str,
        *,
        token: str | None = None,
        headers: Mapping[str, str] | None = None,
        json_body: Any = None,
        attempts: int | None = None,
        retry: bool = True,
        expect_json: bool = True,
    ) -> tuple[int, Any]:
        if method not in {"GET", "POST"}:
            raise ProofBoundaryError("EFFECT_SCOPE_REJECTED")
        check_destination(url)
        request_headers = {"Accept": "application/json", "User-Agent": "szl-live-proof/1"}
        request_headers.update(dict(headers or {}))
        if token:
            request_headers["Authorization"] = f"Bearer {token}"
        data = None
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        budget = self.max_attempts if attempts is None else max(1, min(int(attempts), self.max_attempts))
        if not retry:
            budget = 1
        window_ends = self._clock() + RETRY_WINDOW_SECONDS
        for attempt in range(1, budget + 1):
            remaining = self.remaining()
            if remaining <= 0:
                raise ProofBoundaryError("DEADLINE_EXHAUSTED")
            request = Request(url, data=data, headers=request_headers, method=method)
            delay: float | None = None
            try:
                response = self._opener.open(
                    request, timeout=max(0.1, min(REQUEST_TIMEOUT_SECONDS, remaining))
                )
            except HTTPError as exc:
                status = int(getattr(exc, "code", 0) or 0)
                retry_after = _retry_after(getattr(exc, "headers", None))
                try:
                    exc.close()  # the provider body is never read
                except Exception:  # noqa: BLE001
                    pass
                if 300 <= status < 400:
                    self._record(method, url, attempt, status, "REDIRECT_REJECTED")
                    raise ProofBoundaryError("REDIRECT_REJECTED", http_status=status) from None
                if status not in TRANSIENT_HTTP_STATUSES:
                    self._record(method, url, attempt, status, "HTTP_STATUS_REJECTED")
                    raise ProofBoundaryError("HTTP_STATUS_REJECTED", http_status=status) from None
                self._record(method, url, attempt, status, "TRANSIENT")
                delay = retry_after
                if attempt >= budget or self._clock() >= window_ends:
                    raise ProofBoundaryError("TRANSIENT_RETRY_EXHAUSTED", http_status=status) from None
                self.sleep(delay if delay is not None else min(
                    BACKOFF_CAP_SECONDS, BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))))
                continue
            except (URLError, TimeoutError, OSError, ValueError):
                self._record(method, url, attempt, None, "TRANSPORT_UNAVAILABLE")
                raise ProofBoundaryError("TRANSPORT_UNAVAILABLE") from None
            with response:
                status = int(getattr(response, "status", 0) or 0)
                final_url = response.geturl() if hasattr(response, "geturl") else url
                if 300 <= status < 400 or final_url != url:
                    self._record(method, url, attempt, status, "REDIRECT_REJECTED")
                    raise ProofBoundaryError("REDIRECT_REJECTED", http_status=status)
                if not 200 <= status < 300:
                    self._record(method, url, attempt, status, "HTTP_STATUS_REJECTED")
                    raise ProofBoundaryError("HTTP_STATUS_REJECTED", http_status=status)
                body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                self._record(method, url, attempt, status, "RESPONSE_TOO_LARGE")
                raise ProofBoundaryError("RESPONSE_TOO_LARGE")
            self._record(method, url, attempt, status, "OK")
            if not expect_json:
                return status, body
            try:
                return status, json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, ValueError, RecursionError):
                raise ProofBoundaryError("RESPONSE_NOT_JSON") from None
        raise ProofBoundaryError("TRANSIENT_RETRY_EXHAUSTED")  # pragma: no cover


class ScopedSpaceControl:
    """The only provider control surface a live proof may hold.

    Method names mirror ``huggingface_hub.HfApi`` so the proof logic is
    unchanged, but every call is pinned to exactly ``SZLHOLDINGS/a11oy`` on
    ``https://huggingface.co/api/spaces/SZLHOLDINGS/a11oy``. There is no
    secret, variable, volume, hardware, upload or other-Space capability.
    """

    def __init__(self, transport: BoundedTransport, token: str, repo_id: str = CANONICAL_SPACE) -> None:
        self._transport = transport
        self._token = token
        self.repo_id = require_canonical_space(repo_id)
        self.effects: list[dict[str, Any]] = []

    def _scoped(self, repo_id: str) -> str:
        if repo_id != self.repo_id:
            raise ProofBoundaryError("SPACE_SCOPE_REJECTED")
        return "https://" + HF_API_HOST + HF_SPACE_API_PATH

    def get_space_runtime(self, *, repo_id: str) -> Any:
        base = self._scoped(repo_id)
        _status, value = self._transport.request("GET", base + "/runtime", token=self._token)
        if not isinstance(value, Mapping):
            raise ProofBoundaryError("RESPONSE_NOT_JSON")
        return value

    def pause_space(self, *, repo_id: str) -> Any:
        base = self._scoped(repo_id)
        self.effects.append({"effect": "pause_space", "repo_id": self.repo_id})
        _status, value = self._transport.request(
            "POST", base + "/pause", token=self._token, retry=False)
        return value if isinstance(value, Mapping) else {}

    def restart_space(self, *, repo_id: str, factory_reboot: bool = False) -> Any:
        base = self._scoped(repo_id)
        if factory_reboot is not False:
            raise ProofBoundaryError("EFFECT_SCOPE_REJECTED")
        self.effects.append({"effect": "restart_space", "repo_id": self.repo_id})
        _status, value = self._transport.request(
            "POST", base + "/restart", token=self._token, retry=False)
        return value if isinstance(value, Mapping) else {}

    def __getattr__(self, name: str) -> Any:
        # Any other HfApi capability (secrets, variables, volumes, uploads,
        # other Spaces) is structurally absent.
        raise ProofBoundaryError("EFFECT_SCOPE_REJECTED")


def _load_pinned_key_der(root: Path = REPO_ROOT) -> bytes:
    from cryptography.hazmat.primitives import serialization

    try:
        path = root / PINNED_RUNTIME_KEY_PATH
        with path.open("rb") as stream:
            raw = stream.read(MAX_PIN_FILE_BYTES + 1)
        if len(raw) > MAX_PIN_FILE_BYTES:
            raise ValueError("oversized pin")
        key = serialization.load_pem_public_key(raw)
        der = key.public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    except Exception as exc:  # noqa: BLE001 - fixed diagnostic only
        raise ProofBoundaryError("PINNED_KEY_UNAVAILABLE") from exc
    if hashlib.sha256(der).hexdigest() != PINNED_RUNTIME_KEY_DER_SHA256:
        raise ProofBoundaryError("PINNED_KEY_UNAVAILABLE")
    return der


def dsse_pae(payload_type: str, body: bytes) -> bytes:
    kind = payload_type.encode("utf-8")
    return b"DSSEv1 %d %s %d %s" % (len(kind), kind, len(body), body)


def verify_envelope_against_pinned_key(
    envelope: Any,
    *,
    root: Path = REPO_ROOT,
    public_key_der: bytes | None = None,
) -> dict[str, Any]:
    """Verify a DSSE envelope's ECDSA-P256 signature with the pinned key only.

    Every other trusted-key source (embedded fallback, runtime-published key,
    keyid hints) is ignored. Returns a secret-free, fixed-shape result or
    raises ``RECEIPT_UNSIGNED`` / ``RECEIPT_SIGNATURE_INVALID``.
    """

    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    der = public_key_der if public_key_der is not None else _load_pinned_key_der(root)
    if type(envelope) is not dict:
        raise ProofBoundaryError("RECEIPT_SIGNATURE_INVALID")
    signatures = envelope.get("signatures")
    if envelope.get("signed") is not True or type(signatures) is not list or not signatures:
        raise ProofBoundaryError("RECEIPT_UNSIGNED")
    if len(signatures) != 1 or type(signatures[0]) is not dict:
        raise ProofBoundaryError("RECEIPT_SIGNATURE_INVALID")
    if envelope.get("payloadType") != KHIPU_PAYLOAD_TYPE:
        raise ProofBoundaryError("RECEIPT_SIGNATURE_INVALID")
    try:
        body = base64.b64decode(str(envelope.get("payload") or ""), validate=True)
        signature = base64.b64decode(str(signatures[0].get("sig") or ""), validate=True)
        key = serialization.load_der_public_key(der)
        if not isinstance(key, ec.EllipticCurvePublicKey):
            raise ProofBoundaryError("PINNED_KEY_UNAVAILABLE")
        key.verify(signature, dsse_pae(KHIPU_PAYLOAD_TYPE, body), ec.ECDSA(hashes.SHA256()))
    except ProofBoundaryError:
        raise
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise ProofBoundaryError("RECEIPT_SIGNATURE_INVALID") from exc
    return {
        "signature_verified": True,
        "verified_against": PINNED_RUNTIME_KEY_PATH,
        "pinned_key_der_sha256": hashlib.sha256(der).hexdigest(),
        "payload_sha256": hashlib.sha256(body).hexdigest(),
    }


def bounded_report(value: Any, *, depth: int = 0) -> Any:
    """Return a copy holding only primitives and short safe tokens.

    Any string that could carry provider prose (spaces, quotes, brackets,
    newlines, long text) becomes ``"[REDACTED_TEXT]"``. Depth and width are
    capped so an evidence field can never grow a report without bound.
    """

    if depth > 8:
        return "[TRUNCATED]"
    if value is None or type(value) in (bool, int):
        return value
    if type(value) is float:
        return value if value == value and abs(value) < 1e15 else None
    if isinstance(value, str):
        return value if _SAFE_TEXT.fullmatch(value) else "[REDACTED_TEXT]"
    if isinstance(value, Mapping):
        result = {}
        for key, item in list(value.items())[:64]:
            if not isinstance(key, str) or not _ID_TOKEN.fullmatch(key):
                continue
            result[key] = bounded_report(item, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        return [bounded_report(item, depth=depth + 1) for item in list(value)[:32]]
    return "[REDACTED_TEXT]"


def bounds_record(*, deadline_seconds: float) -> dict[str, Any]:
    return {
        "max_attempts": MAX_ATTEMPTS,
        "retry_window_seconds": RETRY_WINDOW_SECONDS,
        "deadline_seconds": int(deadline_seconds),
        "transient_http_statuses": sorted(TRANSIENT_HTTP_STATUSES),
        "redirects_allowed": False,
        "destinations": [CANONICAL_ORIGIN, "https://" + HF_API_HOST + HF_SPACE_API_PATH],
    }


def write_json(path: Path, report: Mapping[str, Any]) -> str:
    encoded = json.dumps(dict(report), indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded, encoding="utf-8")
    return encoded
