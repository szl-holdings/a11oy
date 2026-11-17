#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Observe fixed email-readiness predicates with one unauthenticated public GET.

This diagnostic does not replace the deployment's authoritative readiness gate.
A valid NOT_READY observation exits zero; unavailable or invalid evidence exits
two. No response body, URL, error text, credential, or measured secret length is
exported. The 15-second network timeout is a socket timeout, not a hard total
wall-clock deadline. A full 64-KiB read buffer is refused because EOF is unproved.
"""

from __future__ import annotations

import argparse
from contextlib import suppress
from datetime import datetime, timezone
from http.client import HTTPException
import json
import math
from pathlib import Path
import re
import sys
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

WORKER = "szl-email-sender"
REVISION_PATH = "/.well-known/szl-worker-revision"
MAX_RESPONSE_BYTES = 64 * 1024
TIMEOUT_SECONDS = 15
REVISION = re.compile(r"[0-9a-f]{40}\Z")
DEPLOYMENT_URL = re.compile(
    r"https://szl-email-sender\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.workers\.dev\Z"
)
CHECK_NAMES = (
    "secret_requirement_met",
    "sender_valid",
    "send_binding_callable",
    "email_message_available",
)
PAYLOAD_KEYS = {"worker", "source_revision", "ready", "readiness_checks"}


class DiagnosticError(ValueError):
    """An internal, fixed diagnostic reason; never provider exception text."""


class FixedArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise DiagnosticError("INVALID_ARGUMENTS")


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def public_opener():
    # Do not inherit proxy credentials, cookies, or authentication handlers.
    return build_opener(ProxyHandler({}), NoRedirectHandler())


def result(reason, *, revision=None, attempts=0, checks=None):
    valid_revision = (
        revision if type(revision) is str and REVISION.fullmatch(revision) else None
    )
    ready = all(checks.values()) if checks is not None else None
    return {
        "schema": "szl.email-worker-readiness/v1",
        "worker": WORKER,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "expected_source_revision": valid_revision,
        "state": ("READY" if ready else "NOT_READY") if checks is not None else "UNAVAILABLE",
        "reason": reason,
        "ready": ready,
        "source_revision_matched": True if checks is not None else None,
        "readiness_checks": checks,
        "failed_checks": (
            [name for name in CHECK_NAMES if not checks[name]] if checks is not None else None
        ),
        "http_get_attempts": attempts,
        "provider_writes": 0,
        "mail_sends": 0,
        "caller_authentication_proved": False,
        "email_delivery_proved": False,
    }


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def finite_float(raw):
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError("nonfinite JSON number")
    return value


def reject_constant(raw):
    raise ValueError("nonfinite JSON constant")


def assess(body, revision):
    if len(body) >= MAX_RESPONSE_BYTES:
        raise DiagnosticError("RESPONSE_TOO_LARGE")
    try:
        payload = json.loads(
            body.decode("utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
            parse_float=finite_float,
        )
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise DiagnosticError("INVALID_JSON") from None
    if type(payload) is not dict or set(payload) != PAYLOAD_KEYS:
        raise DiagnosticError("INVALID_SCHEMA")
    if payload["worker"] != WORKER:
        raise DiagnosticError("WORKER_MISMATCH")
    if payload["source_revision"] != revision:
        raise DiagnosticError("REVISION_MISMATCH")
    checks = payload["readiness_checks"]
    if (
        type(checks) is not dict
        or set(checks) != set(CHECK_NAMES)
        or any(type(checks[name]) is not bool for name in CHECK_NAMES)
        or type(payload["ready"]) is not bool
    ):
        raise DiagnosticError("INVALID_SCHEMA")
    if payload["ready"] != all(checks.values()):
        raise DiagnosticError("READINESS_INCOHERENT")
    return {name: checks[name] for name in CHECK_NAMES}


def observe(deployment_url, revision, *, opener=None):
    if type(revision) is not str or not REVISION.fullmatch(revision):
        return result("INVALID_EXPECTED_REVISION")
    if type(deployment_url) is not str or not DEPLOYMENT_URL.fullmatch(deployment_url):
        return result("INVALID_DEPLOYMENT_URL", revision=revision)
    url = deployment_url + REVISION_PATH
    request = Request(
        url,
        method="GET",
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "Cache-Control": "no-cache",
            "User-Agent": "szl-email-readiness-diagnostic/1",
        },
    )
    attempts = 0
    try:
        client = opener if opener is not None else public_opener()
        attempts = 1
        with client.open(request, timeout=TIMEOUT_SECONDS) as response:
            if response.status != 200:
                raise DiagnosticError("HTTP_STATUS_UNEXPECTED")
            if response.geturl() != url:
                raise DiagnosticError("RESPONSE_URL_MISMATCH")
            encoding = response.headers.get("Content-Encoding", "").strip().lower()
            if encoding not in {"", "identity"}:
                raise DiagnosticError("CONTENT_ENCODING_UNSUPPORTED")
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                raise DiagnosticError("CONTENT_TYPE_UNEXPECTED")
            # At most 64 KiB is read. Never consume an error body or overflow byte.
            body = response.read(MAX_RESPONSE_BYTES)
        checks = assess(body, revision)
    except HTTPError as error:
        reason = "REDIRECT_REFUSED" if 300 <= error.code < 400 else "HTTP_STATUS_UNEXPECTED"
        with suppress(Exception):
            error.close()
        return result(reason, revision=revision, attempts=attempts)
    except DiagnosticError as error:
        return result(str(error), revision=revision, attempts=attempts)
    except (HTTPException, OSError, ValueError):
        return result("TRANSPORT_UNAVAILABLE", revision=revision, attempts=attempts)
    return result(
        "OBSERVED_READY" if all(checks.values()) else "PREREQUISITES_NOT_MET",
        revision=revision,
        attempts=attempts,
        checks=checks,
    )


def parse_args(argv):
    parser = FixedArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--deployment-url", required=True)
    parser.add_argument("--expect-revision", required=True)
    parser.add_argument("--output", help="Create a new value-free JSON record exclusively.")
    return parser.parse_args(argv)


def main(argv=None):
    record = None
    try:
        args = parse_args(sys.argv[1:] if argv is None else argv)
    except DiagnosticError:
        observation = result("INVALID_ARGUMENTS")
    else:
        try:
            # Reserve before observing: an existing record is never overwritten.
            if args.output is not None:
                record = Path(args.output).open("x", encoding="utf-8", newline="\n")
        except (OSError, ValueError):
            observation = result("RECORD_UNAVAILABLE", revision=args.expect_revision)
        else:
            observation = observe(args.deployment_url, args.expect_revision)
    if record is not None:
        try:
            record.write(json.dumps(observation, sort_keys=True, allow_nan=False) + "\n")
            record.close()
        except (OSError, ValueError):
            with suppress(Exception):
                record.close()
            # This invocation created the file exclusively; discard partial output.
            with suppress(OSError):
                Path(args.output).unlink()
            observation = result(
                "RECORD_WRITE_FAILED",
                revision=observation["expected_source_revision"],
                attempts=observation["http_get_attempts"],
            )
    print(json.dumps(observation, sort_keys=True, allow_nan=False))
    return 0 if observation["state"] in {"READY", "NOT_READY"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
