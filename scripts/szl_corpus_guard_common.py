#!/usr/bin/env python3
# Signed-off-by: Forge (Replit task agent) <forge@szl-holdings>
"""Shared helpers for the HF verifiable-corpus guard layer.

Pure stdlib (no third-party imports at module load) so the freshness / card /
chain-integrity checks and their self-tests run offline. The `cryptography`
dependency used by the re-verify guard is imported lazily, only inside the
signature-verification functions, so importing this module never requires it.

Exit-code convention shared by all three guards:
  0  ok (or honest soft-pass: empty corpus with no floor)
  1  guard violation (stale / floor regression / tamper / overclaim)
  2  operational error (auth 401/403, HF unreachable after retries, malformed)
Any non-zero exit is fail-loud and pages.
"""
from __future__ import annotations

import json
import hashlib
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_ERROR = 2


class AuthError(Exception):
    """HF returned 401/403 — auth failure must never be a silent green."""


class Unreachable(Exception):
    """HF unreachable / 5xx after retries — fail loud, not silent green."""


# --------------------------------------------------------------------------- #
# HTTP                                                                         #
# --------------------------------------------------------------------------- #
def http_get(url: str, token: str | None = None, retries: int = 3,
             timeout: int = 30):
    """GET a URL. Returns (status:int, body:bytes).

    Raises AuthError on 401/403 (never retried — auth won't fix itself).
    Raises Unreachable on network error / 5xx after `retries` attempts.
    Returns (404, b"") for a genuine not-found (caller decides if that is ok).
    """
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", "szl-corpus-guard/1.0")
        if token:
            req.add_header("Authorization", "Bearer " + token)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.getcode(), resp.read()
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise AuthError("auth failure %d for %s" % (e.code, url))
            if e.code == 404:
                return 404, b""
            last = "HTTP %d" % e.code
            if e.code < 500:
                # other 4xx: not retryable, surface as Unreachable (malformed req)
                raise Unreachable("%s for %s" % (last, url))
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = str(e)
        time.sleep(1.5 * (attempt + 1))
    raise Unreachable("unreachable after %d tries (%s): %s" % (retries, last, url))


def fetch_json(url: str, token: str | None = None):
    """Return parsed JSON, or None on 404. Raises AuthError/Unreachable."""
    status, body = http_get(url, token)
    if status == 404:
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        raise Unreachable("malformed JSON from %s: %s" % (url, e))


def fetch_text(url: str, token: str | None = None):
    """Return body text, or None on 404. Raises AuthError/Unreachable."""
    status, body = http_get(url, token)
    if status == 404:
        return None
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError as e:
        raise Unreachable("non-utf8 body from %s: %s" % (url, e))


def fetch_ndjson(url: str, token: str | None = None):
    """Return a list of parsed JSON records from an NDJSON file (None on 404)."""
    txt = fetch_text(url, token)
    if txt is None:
        return None
    out = []
    for ln in txt.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except ValueError as e:
            raise Unreachable("malformed NDJSON line in %s: %s" % (url, e))
    return out


def resolve_url(base_tmpl: str, repo_id: str, path: str) -> str:
    return base_tmpl.format(repo_id=repo_id, path=path)


# --------------------------------------------------------------------------- #
# Canonicalisation / hashing (matches szl_hf_bucket make_record)              #
# --------------------------------------------------------------------------- #
def canonical_bytes(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def content_address(source: str, kind: str, content) -> str:
    """Recompute a record id: sha256(canon({source,kind,content})).

    Mirrors szl_hf_bucket.make_record, where `content` is the record payload
    (dedup_key defaults to the payload).
    """
    return sha256_hex(canonical_bytes(
        {"source": source, "kind": kind, "content": content}))


# --------------------------------------------------------------------------- #
# DSSE PAE                                                                     #
# --------------------------------------------------------------------------- #
def dsse_pae(payload_type: str, payload_bytes: bytes) -> bytes:
    """Pre-Authentication Encoding (DSSEv1) over which signatures are made."""
    pt = payload_type.encode("utf-8")
    return (b"DSSEv1 " + str(len(pt)).encode() + b" " + pt + b" " +
            str(len(payload_bytes)).encode() + b" " + payload_bytes)


# --------------------------------------------------------------------------- #
# Time                                                                         #
# --------------------------------------------------------------------------- #
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso(ts: str) -> datetime:
    """Parse an ISO-8601 timestamp (tolerant of a trailing 'Z')."""
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def age_hours(ts: str, ref: datetime | None = None) -> float:
    ref = ref or now_utc()
    return (ref - parse_iso(ts)).total_seconds() / 3600.0
