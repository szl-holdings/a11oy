#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Read bounded, unsigned provider timing observations for one fixed Worker.

Schema references and interpretation limits:
docs/operations/alert-relay-telemetry-observation.md
"""

import argparse
import datetime
import json
import math
import os
import queue
import re
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.cloudflare.com/client/v4"
SERVICE = "szl-alert-relay"
REPORT_FILE = "alert-relay-telemetry-observation.json"
DEFAULT_FROM = "2026-11-16T22:52:20Z"
DEFAULT_TO = "2026-11-16T22:54:20Z"
MAX_WINDOW_MS = 15 * 60 * 1000
MAX_BYTES = 256 * 1024
MAX_REQUESTS = 3
REQUEST_TIMEOUT = 12
DEADLINE_SECONDS = 45
REQUIRED_KEYS = {
    "$metadata.service": "string",
    "$workers.cpuTimeMs": "number",
    "$workers.wallTimeMs": "number",
}
KEY_PATTERN = r"^(\$metadata\.service|\$workers\.(cpuTimeMs|wallTimeMs))$"
CALCULATIONS = (
    ("matching_timing_events", "count", None),
    ("cpu_avg_ms", "avg", "$workers.cpuTimeMs"),
    ("cpu_max_ms", "max", "$workers.cpuTimeMs"),
    ("wall_avg_ms", "avg", "$workers.wallTimeMs"),
    ("wall_max_ms", "max", "$workers.wallTimeMs"),
    ("wall_p95_ms", "p95", "$workers.wallTimeMs"),
)
STAGES = frozenset({
    "INPUT", "ACCOUNT_DISCOVERY", "KEY_DISCOVERY", "AGGREGATE_QUERY",
    "RESPONSE_ADMISSION", "UNKNOWN",
})
REASONS = frozenset({
    "INVALID_INPUT", "MISSING_CREDENTIAL", "INVALID_CREDENTIAL",
    "INVALID_ACCOUNT", "ACCOUNT_UNRESOLVED", "ACCOUNT_DISCOVERY_PAGINATED",
    "SCOPE_REFUSED", "REDIRECT_REFUSED", "HTTP_REFUSED", "REQUEST_FAILED",
    "DEADLINE_EXCEEDED", "REQUEST_LIMIT", "RESPONSE_TOO_LARGE",
    "NON_JSON_RESPONSE", "MALFORMED_RESPONSE", "PROVIDER_REJECTED",
    "KEY_SCHEMA_UNSUPPORTED", "QUERY_NOT_COMPLETED", "QUERY_SCOPE_MISMATCH",
    "CALCULATION_SCHEMA_UNSUPPORTED", "NO_MATCHING_TIMING_EVENTS",
    "NUMERIC_AGGREGATES_OBSERVED", "UNEXPECTED_ERROR", "REPORT_WRITE_FAILED",
})


class ObservationError(Exception):
    def __init__(self, reason, http_status=None):
        self.reason = reason if reason in REASONS else "UNEXPECTED_ERROR"
        self.http_status = (
            http_status if type(http_status) is int and 100 <= http_status <= 599
            else None
        )
        super().__init__(self.reason)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ObservationError("REDIRECT_REFUSED", code) from None


class QuietParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse normally echoes invalid arguments; they may contain secrets.
        raise ObservationError("INVALID_INPUT") from None


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def parse_time(value):
    pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})"
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise ObservationError("INVALID_INPUT") from None
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        parsed = parsed.astimezone(datetime.timezone.utc)
        millis = int(parsed.timestamp() * 1000)
        if millis < 0:
            raise ValueError
        canonical = parsed.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        return millis, canonical
    except (ValueError, OverflowError, OSError):
        raise ObservationError("INVALID_INPUT") from None


def time_window(start, end):
    first, first_iso = parse_time(start)
    last, last_iso = parse_time(end)
    if not 0 < last - first <= MAX_WINDOW_MS:
        raise ObservationError("INVALID_INPUT") from None
    return {"from": first, "to": last}, {"from": first_iso, "to": last_iso}


def validate_token(token):
    if not isinstance(token, str) or not token:
        raise ObservationError("MISSING_CREDENTIAL") from None
    if not 16 <= len(token) <= 512 or any(not 33 <= ord(c) <= 126 for c in token):
        raise ObservationError("INVALID_CREDENTIAL") from None
    return token


def account_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-fA-F0-9]{32}", value):
        raise ObservationError("INVALID_ACCOUNT") from None
    return value.lower()


def numeric(value, minimum=0):
    if type(value) not in (int, float) or not math.isfinite(value) or value < minimum:
        raise ObservationError("CALCULATION_SCHEMA_UNSUPPORTED") from None
    return value


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ObservationError("MALFORMED_RESPONSE") from None
        result[key] = value
    return result


def reject_constant(value):
    raise ObservationError("MALFORMED_RESPONSE") from None


class Client:
    def __init__(self, token, opener=None, clock=time.monotonic, stop=None):
        self._token = validate_token(token)
        self._opener = opener or urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect()
        )
        self._clock = clock
        self._stop = stop or threading.Event()
        self._deadline = clock() + DEADLINE_SECONDS
        self.requests = 0
        self.http_status = None

    def remaining(self):
        remaining = self._deadline - self._clock()
        if remaining <= 0 or self._stop.is_set():
            raise ObservationError("DEADLINE_EXCEEDED") from None
        return remaining

    def request(self, method, path, payload=None):
        allowed_post = re.fullmatch(
            r"/accounts/[a-f0-9]{32}/workers/observability/telemetry/(keys|query)",
            path,
        )
        if not ((method == "GET" and path == "/accounts" and payload is None)
                or (method == "POST" and allowed_post and isinstance(payload, dict))):
            raise ObservationError("SCOPE_REFUSED") from None
        timeout = min(REQUEST_TIMEOUT, self.remaining())
        if self.requests >= MAX_REQUESTS:
            raise ObservationError("REQUEST_LIMIT") from None
        url = API + path
        body = None if payload is None else json.dumps(
            payload, allow_nan=False, separators=(",", ":")
        ).encode("utf-8")
        request = urllib.request.Request(
            url, data=body, method=method,
            headers={
                "Authorization": "Bearer " + self._token,
                "Accept": "application/json", "Content-Type": "application/json",
            },
        )
        self.requests += 1
        try:
            with self._opener.open(request, timeout=timeout) as response:
                status = response.getcode()
                self.http_status = status if type(status) is int and 100 <= status <= 599 else None
                if response.geturl() != url:
                    raise ObservationError("REDIRECT_REFUSED", self.http_status)
                if self.http_status != 200:
                    raise ObservationError("HTTP_REFUSED", self.http_status)
                media = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                if media != "application/json" and not (
                    media.startswith("application/") and media.endswith("+json")
                ):
                    raise ObservationError("NON_JSON_RESPONSE", status)
                declared = response.headers.get("Content-Length")
                if declared is not None and (
                    not declared.isdigit() or int(declared) > MAX_BYTES
                ):
                    raise ObservationError("RESPONSE_TOO_LARGE", status)
                raw = bytearray()
                reader = getattr(response, "read1", response.read)
                while True:
                    self.remaining()
                    chunk = reader(min(16384, MAX_BYTES + 1 - len(raw)))
                    self.remaining()
                    if not chunk:
                        break
                    raw.extend(chunk)
                    if len(raw) > MAX_BYTES:
                        raise ObservationError("RESPONSE_TOO_LARGE", status)
                data = json.loads(
                    raw.decode("utf-8"), object_pairs_hook=unique_object,
                    parse_constant=reject_constant,
                )
        except urllib.error.HTTPError as error:
            code = error.code
            error.close()
            self.http_status = code if type(code) is int and 100 <= code <= 599 else None
            reason = "REDIRECT_REFUSED" if self.http_status and 300 <= self.http_status < 400 else "HTTP_REFUSED"
            raise ObservationError(reason, self.http_status) from None
        except ObservationError:
            raise
        except (ValueError, UnicodeError, RecursionError):
            raise ObservationError("MALFORMED_RESPONSE", self.http_status) from None
        except Exception:
            raise ObservationError("REQUEST_FAILED", self.http_status) from None
        if not isinstance(data, dict) or data.get("success") is not True:
            raise ObservationError("PROVIDER_REJECTED", self.http_status) from None
        if data.get("errors", []) != [] or "result" not in data:
            raise ObservationError("PROVIDER_REJECTED", self.http_status) from None
        return data

    def resolve_account(self, configured):
        if configured:
            return account_id(configured)
        data = self.request("GET", "/accounts")
        accounts = data["result"]
        info = data.get("result_info", {})
        if not isinstance(accounts, list) or len(accounts) != 1 or not isinstance(accounts[0], dict):
            raise ObservationError("ACCOUNT_UNRESOLVED") from None
        if not isinstance(info, dict) or any(
            type(info.get(key)) is not int or info[key] != 1
            for key in ("page", "total_count", "count")
        ):
            raise ObservationError("ACCOUNT_DISCOVERY_PAGINATED") from None
        if "total_pages" in info and (type(info["total_pages"]) is not int or info["total_pages"] != 1):
            raise ObservationError("ACCOUNT_DISCOVERY_PAGINATED") from None
        if info.get("cursors") or info.get("next") or data.get("next"):
            raise ObservationError("ACCOUNT_DISCOVERY_PAGINATED") from None
        return account_id(accounts[0].get("id"))


def service_filter():
    return {
        "key": "$metadata.service", "operation": "eq",
        "type": "string", "value": SERVICE,
    }


def keys_payload(window):
    return {
        "from": window["from"], "to": window["to"], "limit": 10,
        "filters": [service_filter()],
        "keyNeedle": {"value": KEY_PATTERN, "isRegex": True, "matchCase": False},
    }


def verify_keys(data):
    rows = data["result"]
    if not isinstance(rows, list):
        raise ObservationError("KEY_SCHEMA_UNSUPPORTED") from None
    keys = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ObservationError("KEY_SCHEMA_UNSUPPORTED") from None
        key = row.get("key")
        if not isinstance(key, str) or key not in REQUIRED_KEYS or key in keys:
            raise ObservationError("KEY_SCHEMA_UNSUPPORTED") from None
        keys[key] = row.get("type")
    if keys != REQUIRED_KEYS:
        raise ObservationError("KEY_SCHEMA_UNSUPPORTED") from None


def query_payload(window):
    calculations = []
    for alias, operator, key in CALCULATIONS:
        calculation = {"operator": operator, "alias": alias}
        if key is not None:
            calculation.update({"key": key, "keyType": "number"})
        calculations.append(calculation)
    return {
        "queryId": "szl-alert-relay-readonly", "timeframe": window,
        "dry": True, "view": "calculations", "chartType": "aggregate",
        "ignoreSeries": True, "limit": 1,
        "parameters": {
            "filterCombination": "and", "limit": 1,
            "filters": [
                service_filter(),
                {"key": "$workers.cpuTimeMs", "operation": "exists", "type": "number"},
                {"key": "$workers.wallTimeMs", "operation": "exists", "type": "number"},
            ],
            "calculations": calculations,
        },
    }


def extract_aggregates(data, window):
    result = data["result"]
    if not isinstance(result, dict):
        raise ObservationError("CALCULATION_SCHEMA_UNSUPPORTED") from None
    run = result.get("run")
    if not isinstance(run, dict) or run.get("status") != "COMPLETED":
        raise ObservationError("QUERY_NOT_COMPLETED") from None
    if run.get("dry") is not True or run.get("timeframe") != window:
        raise ObservationError("QUERY_SCOPE_MISMATCH") from None
    rows = result.get("calculations")
    if rows == []:
        raise ObservationError("NO_MATCHING_TIMING_EVENTS") from None
    if not isinstance(rows, list) or len(rows) != len(CALCULATIONS):
        raise ObservationError("CALCULATION_SCHEMA_UNSUPPORTED") from None
    expected = {entry[0] for entry in CALCULATIONS}
    by_alias = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ObservationError("CALCULATION_SCHEMA_UNSUPPORTED") from None
        alias = row.get("alias")
        if not isinstance(alias, str) or alias not in expected or alias in by_alias:
            raise ObservationError("CALCULATION_SCHEMA_UNSUPPORTED") from None
        aggregates = row.get("aggregates")
        if not isinstance(aggregates, list) or len(aggregates) != 1:
            raise ObservationError("CALCULATION_SCHEMA_UNSUPPORTED") from None
        aggregate = aggregates[0]
        if not isinstance(aggregate, dict) or aggregate.get("groups", []) != []:
            raise ObservationError("CALCULATION_SCHEMA_UNSUPPORTED") from None
        by_alias[alias] = aggregate
    count = by_alias["matching_timing_events"]
    count_value = numeric(count.get("value"))
    count_total = numeric(count.get("count"))
    if count_value == 0 and count_total == 0:
        raise ObservationError("NO_MATCHING_TIMING_EVENTS") from None
    if count_value <= 0 or count_total <= 0 or count_value != count_total:
        raise ObservationError("CALCULATION_SCHEMA_UNSUPPORTED") from None
    clean = {}
    for alias, _, _ in CALCULATIONS:
        aggregate = by_alias[alias]
        clean[alias] = {
            "value": numeric(aggregate.get("value")),
            "count": numeric(aggregate.get("count"), minimum=1),
            "sampleInterval": numeric(aggregate.get("sampleInterval"), minimum=1),
        }
    return clean


def empty_report():
    return {
        "schema_version": 1, "service": SERVICE,
        "status": "UNAVAILABLE", "reason": "UNEXPECTED_ERROR", "stage": "INPUT",
        "evidence_basis": "PROVIDER_REPORTED_UNVERIFIED",
        "delivery_status": "UNVERIFIED",
        "count_basis": "ESTIMATED_MATCHING_TIMING_EVENTS",
        "observed_at": utc_now(), "window": None,
        "http_status": None, "request_count": None, "aggregates": {},
    }


def set_stage(report, stage):
    report["stage"] = stage if isinstance(stage, str) and stage in STAGES else "UNKNOWN"


def set_error(report, error):
    report["status"] = (
        "PERMISSION_BLOCKED" if error.http_status in (401, 403) else "UNAVAILABLE"
    )
    report["reason"] = error.reason
    report["http_status"] = error.http_status
    report["aggregates"] = {}
    return report


def observe(start, end, token, configured_account="", opener=None,
            clock=time.monotonic, stop=None):
    report = empty_report()
    client = None
    try:
        window, report["window"] = time_window(start, end)
        client = Client(token, opener=opener, clock=clock, stop=stop)
        if not configured_account:
            set_stage(report, "ACCOUNT_DISCOVERY")
        account = client.resolve_account(configured_account)
        prefix = f"/accounts/{account}/workers/observability/telemetry/"
        set_stage(report, "KEY_DISCOVERY")
        verify_keys(client.request("POST", prefix + "keys", keys_payload(window)))
        set_stage(report, "AGGREGATE_QUERY")
        data = client.request("POST", prefix + "query", query_payload(window))
        set_stage(report, "RESPONSE_ADMISSION")
        report["aggregates"] = extract_aggregates(data, window)
        report["status"] = "OBSERVED"
        report["reason"] = "NUMERIC_AGGREGATES_OBSERVED"
        report["http_status"] = client.http_status
    except ObservationError as error:
        if client is not None and error.http_status is None:
            error.http_status = client.http_status
        set_error(report, error)
    except Exception:
        set_error(report, ObservationError("UNEXPECTED_ERROR"))
    report["request_count"] = client.requests if client is not None else 0
    report["observed_at"] = utc_now()
    return report


def bounded_observe(start, end, token, configured_account, timeout=DEADLINE_SECONDS,
                    operation=observe):
    # Socket timeouts alone do not bound a response that trickles bytes.
    # Only this thread writes the report; a daemon cannot hold the CLI open.
    result = queue.Queue(maxsize=1)
    stop = threading.Event()

    def work():
        try:
            result.put(operation(start, end, token, configured_account, stop=stop))
        except Exception:
            report = set_error(empty_report(), ObservationError("UNEXPECTED_ERROR"))
            set_stage(report, "UNKNOWN")
            result.put(report)

    worker = threading.Thread(target=work, daemon=True, name="relay-telemetry-read")
    worker.start()
    try:
        return result.get(timeout=timeout)
    except queue.Empty:
        stop.set()
        report = set_error(empty_report(), ObservationError("DEADLINE_EXCEEDED"))
        set_stage(report, "UNKNOWN")
        try:
            _, report["window"] = time_window(start, end)
        except ObservationError:
            pass
        return report


def main(argv=None):
    report = empty_report()
    try:
        parser = QuietParser(description=__doc__)
        parser.add_argument("--from-utc", default=DEFAULT_FROM)
        parser.add_argument("--to-utc", default=DEFAULT_TO)
        args = parser.parse_args(argv)
        time_window(args.from_utc, args.to_utc)
        token = validate_token(os.environ.get("CLOUDFLARE_API_TOKEN", ""))
        configured = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
        if configured:
            account_id(configured)
        report = bounded_observe(args.from_utc, args.to_utc, token, configured)
    except ObservationError as error:
        report = set_error(report, error)
    except Exception:
        report = set_error(report, ObservationError("UNEXPECTED_ERROR"))
    try:
        Path(REPORT_FILE).write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
    except Exception:
        print('{"status":"UNAVAILABLE","reason":"REPORT_WRITE_FAILED","delivery_status":"UNVERIFIED"}')
        return 2
    print(json.dumps({
        "status": report["status"], "reason": report["reason"], "stage": report["stage"],
        "http_status": report["http_status"], "delivery_status": "UNVERIFIED",
    }, allow_nan=False))
    return 0 if report["status"] == "OBSERVED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
