#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Post-deploy readback: prove a live Worker endpoint reports one exact commit.

The deploy workflows inject the full 40-character ``github.sha`` as the
``SOURCE_REVISION`` var. Each Worker serves it, unauthenticated and read-only,
at ``/.well-known/szl-worker-revision``. This check passes only when that live
endpoint answers ``{"worker": <name>, "source_revision": <sha>}`` for the exact
SHA (and ``"ready": true`` when ``--require-ready`` is set).

Refusals are reported as observed, never retried into a pass. HTTP 402 does
not establish a payment provider, protocol, or charge. A 403 carrying
``cf-mitigated: challenge`` identifies a Cloudflare Challenge Page, not the
product or rule that generated it. Correlate request context with provider
logs before changing policy; this readback does not authorize an exemption.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from http.client import HTTPException
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_RESPONSE_BYTES = 64 * 1024
REVISION = re.compile(r"[0-9a-f]{40}\Z")
WORKER_NAME = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
USER_AGENT = "szl-worker-revision-readback/1"
CF_RAY = re.compile(r"[0-9a-fA-F]{16}(?:-[A-Za-z]{3})?\Z")
REVISION_PATH = "/.well-known/szl-worker-revision"


class NoRedirectHandler(HTTPRedirectHandler):
    """A redirect is an answer from somewhere else; never follow it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class Observation:
    ok: bool
    category: str
    detail: str
    retryable: bool


def validate_url(value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.hostname:
        raise ValueError("readback URL must be an https URL with a host")
    if parts.username or parts.password or parts.fragment:
        raise ValueError("readback URL must not carry credentials or a fragment")
    return value


def edge_refusal(status: int, headers) -> Observation | None:
    if status == 402:
        return Observation(
            False,
            "EDGE_PAYWALL",
            "HTTP 402 Payment Required: provider and payment protocol are not established "
            "by this readback; no charge or settlement is verified",
            False,
        )
    if status == 403 and (headers.get("cf-mitigated") or "").lower() == "challenge":
        return Observation(
            False,
            "EDGE_CHALLENGE",
            "HTTP 403 with cf-mitigated: challenge identifies a Cloudflare Challenge Page; "
            "the generating product and rule are not established; correlate the request "
            "with Security Events before changing policy",
            False,
        )
    return None


def assess(
    status: int,
    headers,
    body: bytes,
    *,
    worker: str,
    revision: str,
    require_ready: bool,
) -> Observation:
    refusal = edge_refusal(status, headers)
    if refusal is not None:
        return refusal
    if status != 200:
        retryable = status >= 500 or status in {404, 421, 425, 429}
        return Observation(False, "HTTP_STATUS", f"status={status}", retryable)
    if len(body) > MAX_RESPONSE_BYTES:
        return Observation(False, "RESPONSE_TOO_LARGE", "body exceeds 64 KiB", False)
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        # A propagating custom domain can still answer from the previous version.
        return Observation(False, "INVALID_RESPONSE", "body is not JSON", True)
    if not isinstance(payload, dict):
        return Observation(False, "INVALID_RESPONSE", "body is not a JSON object", True)
    observed_worker = payload.get("worker")
    if observed_worker != worker:
        return Observation(
            False, "WORKER_MISMATCH", f"worker={observed_worker!r} expected={worker!r}", True
        )
    observed = payload.get("source_revision")
    if observed != revision:
        return Observation(
            False, "REVISION_MISMATCH", f"live={observed!r} expected={revision!r}", True
        )
    if require_ready and payload.get("ready") is not True:
        return Observation(
            False,
            "NOT_READY",
            "the Worker reports ready=false (secret, binding, or sender misconfigured)",
            False,
        )
    return Observation(True, "LIVE_REVISION_MATCH", f"live={observed}", False)


def with_request_context(observation: Observation, url: str, headers, observed_at: str) -> Observation:
    if observation.ok:
        return observation
    parts = urlsplit(url)
    path = parts.path or "/"
    ray = (headers.get("cf-ray") or "") if headers is not None else ""
    context = {
        "observed_at_utc": observed_at,
        "method": "GET",
        "hostname": (parts.hostname or "")[:253],
        "path": path if path == REVISION_PATH else "[REDACTED]",
        "path_sha256": hashlib.sha256(path.encode("utf-8")).hexdigest(),
        "cf_ray": ray if CF_RAY.fullmatch(ray) else None,
    }
    # Other paths can be opaque credentials; omit queries, userinfo, bodies and other headers.
    return replace(observation, detail=f"{observation.detail}; request={json.dumps(context, sort_keys=True)}")


def observe(url: str, *, worker: str, revision: str, require_ready: bool, timeout: float) -> Observation:
    observed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "User-Agent": USER_AGENT,
        },
        method="GET",
    )
    try:
        with build_opener(NoRedirectHandler()).open(request, timeout=timeout) as response:
            status = response.status
            headers = response.headers
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as error:
        try:
            body = error.read(MAX_RESPONSE_BYTES + 1)
        except (HTTPException, OSError, ValueError):
            body = b""
        status = error.code
        headers = error.headers
    except (HTTPException, OSError, ValueError) as error:
        result = Observation(False, "TRANSPORT_ERROR", type(error).__name__, True)
        return with_request_context(result, url, None, observed_at)
    result = assess(status, headers, body, worker=worker, revision=revision, require_ready=require_ready)
    return with_request_context(result, url, headers, observed_at)


def verify(
    url: str,
    *,
    worker: str,
    revision: str,
    require_ready: bool = False,
    attempts: int = 12,
    interval: float = 5.0,
    timeout: float = 10.0,
    observe_once: Callable[..., Observation] = observe,
    sleep: Callable[[float], None] = time.sleep,
) -> Observation:
    last = Observation(False, "NOT_ATTEMPTED", "no attempt ran", False)
    for attempt in range(1, attempts + 1):
        last = observe_once(
            url, worker=worker, revision=revision, require_ready=require_ready, timeout=timeout
        )
        if last.ok or not last.retryable:
            return last
        if attempt < attempts:
            sleep(interval)
    return last


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", required=True)
    parser.add_argument("--worker", required=True)
    parser.add_argument("--expect-revision", required=True)
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--attempts", type=int, default=12)
    parser.add_argument("--interval", type=float, default=5.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        url = validate_url(args.url)
    except ValueError as error:
        print(f"::error::Worker revision readback refused: {error}.", file=sys.stderr)
        return 2
    if WORKER_NAME.fullmatch(args.worker) is None:
        print("::error::Worker revision readback refused: invalid worker name.", file=sys.stderr)
        return 2
    if REVISION.fullmatch(args.expect_revision) is None:
        print(
            "::error::Worker revision readback refused: expected revision must be a full "
            "40-character lowercase commit SHA.",
            file=sys.stderr,
        )
        return 2
    if not 1 <= args.attempts <= 60 or not 0 <= args.interval <= 60:
        print("::error::Worker revision readback refused: attempts/interval out of range.", file=sys.stderr)
        return 2

    result = verify(
        url,
        worker=args.worker,
        revision=args.expect_revision,
        require_ready=args.require_ready,
        attempts=args.attempts,
        interval=args.interval,
    )
    host = urlsplit(url).hostname
    if result.ok:
        print(f"{args.worker} on {host} serves {args.expect_revision} ({result.category}).")
        return 0
    # GitHub annotations decode percent escapes; do not interpret URL data as controls.
    detail = result.detail.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(
        f"::error::{args.worker} on {host} did not prove the deployed revision: "
        f"{result.category}: {detail}.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
