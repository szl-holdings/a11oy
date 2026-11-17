# SPDX-License-Identifier: Apache-2.0
# (c) 2026 SZL Holdings
"""Manually replace one unusable email credential; preserve value-free evidence.

The secret PUT creates and deploys a version; no rollback, secret retrieval,
mail payload, separate deployment request, or automatic retry is performed.
Freshness is a request-dispatch bound, not provider-side compare-and-swap.
"""
from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import threading
import time
import tomllib
import urllib.error
import urllib.request
import uuid

WORKER = "szl-email-sender"
ORIGIN = "https://szl-email-sender.stephenlutar2.workers.dev"
SUBDOMAIN = "stephenlutar2"
REVISION_PATH = "/.well-known/szl-worker-revision"
REPOSITORY = "szl-holdings/a11oy"
CF_API = "https://api.cloudflare.com/client/v4"
GH_API = "https://api.github.com"
ROOT = Path(__file__).resolve().parents[1]
CONFIG = "ops/email-sender-worker/wrangler.toml"
SOURCE_FILES = (
    CONFIG, "ops/email-sender-worker/src/index.mjs",
    "ops/email-sender-worker/src/handler.mjs", "ops/email-sender-worker/src/mime.mjs",
)
CHECKS = frozenset((
    "secret_requirement_met", "sender_valid", "send_binding_callable", "email_message_available",
))
MAX_BODY = 65536
MAX_REQUESTS = 32
SOCKET_TIMEOUT = 10.0
TOTAL_SECONDS = 120.0
DISPATCH_SECONDS = 5.0
SHA = re.compile(r"[0-9a-f]{40}\Z")
ACCOUNT = re.compile(r"[0-9a-f]{32}\Z")
NEW_SECRET = re.compile(r"[A-Za-z0-9_-]{64}\Z")


class RepairError(Exception):
    """Only fixed internal diagnostic codes may reach the report."""

    def __init__(self, code, *, cloudflare_envelope=None):
        self.code = code
        self.cloudflare_envelope = cloudflare_envelope
        super().__init__(code)


def require(condition, code):
    if not condition:
        raise RepairError(code)


def finite_clock(clock):
    value = clock()
    require(type(value) in (int, float) and math.isfinite(value), "CLOCK_INVALID")
    return value


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "JSON_DUPLICATE_KEY")
            result[key] = value
        return result

    def number(value):
        parsed = float(value)
        require(math.isfinite(parsed), "JSON_NONFINITE")
        return parsed

    def integer(value):
        require(len(value) <= 20, "JSON_INTEGER_TOO_LARGE")
        return int(value)

    def constant(_value):
        raise RepairError("JSON_NONFINITE")

    require(type(raw) is bytes and 0 < len(raw) <= MAX_BODY, "RESPONSE_SIZE_INVALID")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                          parse_float=number, parse_int=integer, parse_constant=constant)
    except RepairError:
        raise
    except (ValueError, UnicodeError, RecursionError):
        raise RepairError("RESPONSE_JSON_INVALID") from None


def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, RecursionError):
        raise RepairError("METADATA_INVALID") from None


@dataclass(frozen=True)
class Response:
    status: int
    headers: dict
    body: bytes


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise RepairError("REDIRECT_REFUSED")


class Transport:
    """One attempt, no environment proxies, redirects, cookies, or shared auth."""

    def __call__(self, method, url, headers, body, timeout):
        request = urllib.request.Request(url, method=method, headers=headers, data=body)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        try:
            try:
                response = opener.open(request, timeout=timeout)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                raw = response.read(MAX_BODY + 1)
                require(len(raw) <= MAX_BODY, "RESPONSE_SIZE_INVALID")
                encoding = response.headers.get("Content-Encoding", "identity").strip().lower()
                require(encoding == "identity", "RESPONSE_ENCODING_REFUSED")
                content_types = response.headers.get_all("Content-Type", [])
                require(len(content_types) == 1, "RESPONSE_CONTENT_TYPE_INVALID")
                return Response(response.code, {"content-type": content_types[0]}, raw)
        except RepairError:
            raise
        except Exception:
            raise RepairError("TRANSPORT_UNAVAILABLE") from None


class Client:
    """Credential separation and the complete fixed network surface."""

    def __init__(self, cf_token, gh_token, candidate, *, transport=None, clock=time.monotonic):
        for token in (cf_token, gh_token):
            require(type(token) is str and bool(token) and not any(c in token for c in "\r\n\0"),
                    "CONTROL_CREDENTIAL_UNAVAILABLE")
        require(type(candidate) is str and NEW_SECRET.fullmatch(candidate) is not None,
                "REPLACEMENT_CREDENTIAL_INVALID")
        self.cf_token, self.gh_token, self.candidate = cf_token, gh_token, candidate
        self.transport = transport or Transport()
        self.clock = clock
        self.overall_deadline = finite_clock(clock) + TOTAL_SECONDS
        self.lock = threading.Lock()
        self.requests = 0
        self.attempted = False
        self.acknowledged = False
        self.put_used = False
        self.probes = 0

    def _call(self, channel, method, path, *, body=None, deadline=None):
        require(method in {"GET", "PUT", "POST"}, "METHOD_REFUSED")
        token = None
        if channel == "cf":
            permitted = method == "GET" and (
                path == "/accounts?page=1&per_page=5"
                or re.fullmatch(r"/accounts/[0-9a-f]{32}/workers/subdomain", path)
                or re.fullmatch(
                    r"/accounts/[0-9a-f]{32}/workers/scripts/szl-email-sender/"
                    r"(settings|secrets/API_SECRET|deployments\?page=1&per_page=1|"
                    r"versions\?page=1&per_page=1)", path))
            permitted = permitted or (method == "PUT" and re.fullmatch(
                r"/accounts/[0-9a-f]{32}/workers/scripts/szl-email-sender/secrets", path))
            require(bool(permitted), "CONTROL_TARGET_REFUSED")
            url, token = CF_API + path, self.cf_token
        elif channel == "github":
            permitted = method == "GET" and (
                path == "/repos/" + REPOSITORY + "/git/ref/heads/main"
                or any(path == "/repos/" + REPOSITORY + "/contents/" + name
                       + "?ref=" + revision
                       for name in SOURCE_FILES
                       for revision in [path.rsplit("?ref=", 1)[-1]]
                       if SHA.fullmatch(revision)))
            require(bool(permitted), "SOURCE_TARGET_REFUSED")
            url, token = GH_API + path, self.gh_token
        elif channel == "worker":
            require((method, path) in {("GET", REVISION_PATH), ("POST", "/send")},
                    "WORKER_TARGET_REFUSED")
            require(body is None or (method == "POST" and body == b""), "MAIL_PAYLOAD_REFUSED")
            url = ORIGIN + path
            if method == "POST":
                token = self.candidate
        else:
            raise RepairError("CHANNEL_REFUSED")
        require(deadline is None or (type(deadline) in (int, float)
                and math.isfinite(deadline)), "DEADLINE_INVALID")
        effective_deadline = min(self.overall_deadline,
                                 self.overall_deadline if deadline is None else deadline)
        remaining = effective_deadline - finite_clock(self.clock)
        require(remaining > 0, "DISPATCH_WINDOW_EXPIRED")
        with self.lock:
            require(self.requests < MAX_REQUESTS, "REQUEST_BUDGET_EXCEEDED")
            if method == "PUT":
                require(channel == "cf" and not self.put_used and deadline is not None,
                        "SECOND_MUTATION_REFUSED")
                require(body == json.dumps({
                    "name": "API_SECRET", "text": self.candidate, "type": "secret_text",
                }, separators=(",", ":")).encode(), "SECRET_PAYLOAD_REFUSED")
                self.put_used = True
            if method == "POST":
                require(channel == "worker" and self.probes == 0, "SECOND_PROBE_REFUSED")
                self.probes += 1
            self.requests += 1
        headers = {"Accept": "application/json", "Accept-Encoding": "identity",
                   "Cache-Control": "no-cache", "User-Agent": "a11oy-email-secret-repair/1"}
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        if method == "PUT":
            headers["Content-Type"] = "application/json"
        elif method == "POST":
            headers["Content-Type"] = "application/octet-stream"
        # Recheck after local preparation. This deadline is never renewed.
        remaining = effective_deadline - finite_clock(self.clock)
        require(remaining > 0, "DISPATCH_WINDOW_EXPIRED")
        if method == "PUT":
            self.attempted = True
        try:
            response = self.transport(method, url, headers, body, min(SOCKET_TIMEOUT, remaining))
        except RepairError:
            raise
        except Exception:
            raise RepairError("TRANSPORT_UNAVAILABLE") from None
        require(type(response) is Response and type(response.status) is int, "RESPONSE_INVALID")
        media = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        require(media == "application/json", "RESPONSE_CONTENT_TYPE_INVALID")
        require(not 300 <= response.status < 400, "REDIRECT_REFUSED")
        return response.status, decode(response.body)

    def cf_get(self, path, *, deadline=None, phase="INITIAL"):
        status, payload = self._call("cf", "GET", path, deadline=deadline)
        require(status == 200, "CLOUDFLARE_READ_FAILED")
        result = api_result(payload, route=cloudflare_route(path), phase=phase)
        if path.endswith("?page=1&per_page=1") and "result_info" in payload:
            info = payload["result_info"]
            require(type(info) is dict, "VERSION_PAGINATION_INVALID")
            for key in ("page", "per_page", "count"):
                require(key not in info or (type(info[key]) is int and info[key] == 1),
                        "VERSION_PAGINATION_INVALID")
            for key in ("total_count", "total_pages"):
                require(key not in info or (type(info[key]) is int and info[key] >= 1),
                        "VERSION_PAGINATION_INVALID")
        return result

    def github_get(self, path, *, deadline=None):
        status, payload = self._call("github", "GET", path, deadline=deadline)
        require(status == 200 and type(payload) is dict, "SOURCE_READ_FAILED")
        return payload

    def readiness(self, revision, *, deadline=None):
        status, payload = self._call("worker", "GET", REVISION_PATH, deadline=deadline)
        require(status == 200, "READINESS_UNAVAILABLE")
        return validate_readiness(payload, revision)

    def probe(self, *, deadline=None):
        status, payload = self._call("worker", "POST", "/send", body=b"", deadline=deadline)
        require(status == 415 and payload == {"error": "unsupported_media_type"},
                "CANDIDATE_AUTHENTICATION_UNPROVED")

    def put(self, target, deadline):
        payload = json.dumps({"name": "API_SECRET", "text": self.candidate, "type": "secret_text"},
                             separators=(",", ":")).encode()
        status, response = self._call("cf", "PUT", target + "/secrets",
                                      body=payload, deadline=deadline)
        require(status == 200, "SECRET_ACKNOWLEDGEMENT_INVALID")
        result = api_result(response, route="SECRET_UPDATE", phase="UPDATE_ACK")
        # The API may echo the submitted text. Never retain, compare, or report it.
        require(type(result) is dict and result.get("name") == "API_SECRET"
                and result.get("type") == "secret_text", "SECRET_ACKNOWLEDGEMENT_INVALID")
        require(set(result) <= {"name", "type", "text"}, "SECRET_ACKNOWLEDGEMENT_INVALID")
        self.acknowledged = True


def cloudflare_route(path):
    # _call has already admitted the complete fixed URL. Never export the path.
    if path == "/accounts?page=1&per_page=5":
        return "ACCOUNT_DISCOVERY"
    if path.endswith("/workers/subdomain"):
        return "ACCOUNT_SUBDOMAIN"
    return {
        "settings": "WORKER_SETTINGS",
        "API_SECRET": "SECRET_METADATA",
        "deployments?page=1&per_page=1": "ACTIVE_DEPLOYMENT",
        "versions?page=1&per_page=1": "LATEST_VERSION",
    }.get(path.rsplit("/", 1)[-1], "UNCLASSIFIED")


def api_result(payload, *, route, phase):
    require(route in {
        "ACCOUNT_DISCOVERY", "ACCOUNT_SUBDOMAIN", "WORKER_SETTINGS", "SECRET_METADATA",
        "ACTIVE_DEPLOYMENT", "LATEST_VERSION", "SECRET_UPDATE",
    } and phase in {"INITIAL", "FINAL", "UPDATE_ACK"}, "DIAGNOSTIC_CONTEXT_INVALID")
    is_object = type(payload) is dict

    def shape(field):
        if not is_object or field not in payload:
            return "ABSENT"
        value = payload[field]
        if value is None:
            return "NULL"
        if type(value) is list:
            return "NONEMPTY_LIST" if value else "EMPTY_LIST"
        return "OTHER"

    # Only fixed enums, a list length, and booleans enter the receipt. These facts
    # belong to this exception, so parallel reads cannot overwrite its route.
    facts = {
        "route": route, "phase": phase, "envelope_is_object": is_object,
        "errors_shape": shape("errors"), "messages_shape": shape("messages"),
        "errors_count": len(payload["errors"]) if is_object
        and type(payload.get("errors")) is list else None,
        "result_present": is_object and "result" in payload,
    }

    def admit(condition, code):
        if not condition:
            raise RepairError(code, cloudflare_envelope=facts)

    admit(is_object and payload.get("success") is True, "CLOUDFLARE_RESPONSE_UNSUCCESSFUL")
    # Observed latest-version GET convention; never extend this to update ACKs.
    latest_version_null_envelope = (
        route == "LATEST_VERSION" and phase in {"INITIAL", "FINAL"}
        and "errors" in payload and payload["errors"] is None
        and "messages" in payload and payload["messages"] is None
    )
    admit((payload.get("errors") == [] and type(payload.get("messages", [])) is list)
          or latest_version_null_envelope,
          "CLOUDFLARE_RESPONSE_INVALID")
    admit("result" in payload, "CLOUDFLARE_RESPONSE_INVALID")
    return payload["result"]


def resolve_account(client, configured):
    if configured:
        require(type(configured) is str and re.fullmatch(r"[0-9a-fA-F]{32}", configured),
                "ACCOUNT_INVALID")
        return configured.lower()
    status, payload = client._call("cf", "GET", "/accounts?page=1&per_page=5")
    require(status == 200, "ACCOUNT_DISCOVERY_UNAVAILABLE")
    accounts = api_result(payload, route="ACCOUNT_DISCOVERY", phase="INITIAL")
    require(type(accounts) is list and len(accounts) == 1 and type(accounts[0]) is dict,
            "SINGLE_ACCOUNT_REQUIRED")
    info = payload.get("result_info")
    if "result_info" in payload:
        require(type(info) is dict, "ACCOUNT_PAGINATION_INVALID")
        for key, expected in (("page", 1), ("per_page", 5), ("count", 1),
                              ("total_count", 1), ("total_pages", 1)):
            require(key not in info or (type(info[key]) is int and info[key] == expected),
                    "SINGLE_ACCOUNT_REQUIRED")
    value = accounts[0].get("id")
    require(type(value) is str and re.fullmatch(r"[0-9a-fA-F]{32}", value), "ACCOUNT_INVALID")
    return value.lower()


def uuid_text(value):
    require(type(value) is str and re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", value),
        "DEPLOYMENT_ID_INVALID")
    require(str(uuid.UUID(value)) == value, "DEPLOYMENT_ID_INVALID")
    return value


def serving_deployment(result):
    require(type(result) is dict and set(result) == {"deployments"}, "DEPLOYMENT_METADATA_INVALID")
    rows = result["deployments"]
    require(type(rows) is list and len(rows) == 1 and type(rows[0]) is dict,
            "SINGLE_LATEST_DEPLOYMENT_REQUIRED")
    current = rows[0]
    require(current.get("strategy") == "percentage", "DEPLOYMENT_STRATEGY_UNSUPPORTED")
    versions = current.get("versions")
    require(type(versions) is list and len(versions) == 1 and type(versions[0]) is dict,
            "SPLIT_DEPLOYMENT_REFUSED")
    version = versions[0]
    require(set(version) == {"version_id", "percentage"}
            and type(version["percentage"]) in (int, float)
            and version["percentage"] == 100, "SPLIT_DEPLOYMENT_REFUSED")
    return {"deployment_id": uuid_text(current.get("id")),
            "version_id": uuid_text(version.get("version_id"))}


def latest_version(result):
    require(type(result) is dict and set(result) == {"items"}, "LATEST_VERSION_METADATA_INVALID")
    items = result["items"]
    require(type(items) is list and len(items) == 1 and type(items[0]) is dict,
            "SINGLE_LATEST_VERSION_REQUIRED")
    return uuid_text(items[0].get("id"))


def repository_contract(root):
    files = {}
    for name in SOURCE_FILES:
        with (root / name).open("rb") as source:
            raw = source.read(MAX_BODY + 1)
        require(0 < len(raw) <= MAX_BODY, "REPOSITORY_SOURCE_INVALID")
        files[name] = raw
    config = tomllib.loads(files[CONFIG].decode("utf-8"))
    require(config.get("name") == WORKER and config.get("main") == "src/index.mjs"
            and config.get("workers_dev") is True and config.get("preview_urls") is False,
            "REPOSITORY_WORKER_CONTRACT_CHANGED")
    require(type(config.get("vars")) is dict and set(config["vars"]) == {"MAIL_FROM"},
            "REPOSITORY_BINDING_CONTRACT_CHANGED")
    require(config.get("send_email") == [{"name": "SEND_EMAIL"}],
            "REPOSITORY_BINDING_CONTRACT_CHANGED")
    sender = config["vars"]["MAIL_FROM"]
    require(type(sender) is str and re.fullmatch(
        r"[A-Za-z0-9.!#$%&'*+/=?^_{}|~+-]+@a-11-oy\.com", sender),
        "REPOSITORY_SENDER_INVALID")
    require(type(config.get("compatibility_date")) is str
            and re.fullmatch(r"\d{4}-\d{2}-\d{2}", config["compatibility_date"]),
            "REPOSITORY_COMPATIBILITY_INVALID")
    return config, files


def verify_sources(client, revision, files):
    for name, raw in files.items():
        result = client.github_get("/repos/" + REPOSITORY + "/contents/" + name + "?ref=" + revision)
        require(result.get("type") == "file" and result.get("path") == name
                and result.get("encoding") == "base64" and type(result.get("content")) is str
                and type(result.get("size")) is int and result["size"] == len(raw),
                "DEPLOYED_SOURCE_UNVERIFIED")
        try:
            observed = base64.b64decode(result["content"].replace("\n", ""), validate=True)
        except Exception:
            raise RepairError("DEPLOYED_SOURCE_UNVERIFIED") from None
        require(observed == raw, "DEPLOYED_SOURCE_DIFFERS_FROM_REVIEWED_WORKER")
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\x00" + raw).hexdigest()
        require(result.get("sha") == blob, "DEPLOYED_SOURCE_UNVERIFIED")


def require_current_main(client, expected, *, deadline=None):
    result = client.github_get("/repos/" + REPOSITORY + "/git/ref/heads/main", deadline=deadline)
    require(result.get("ref") == "refs/heads/main" and type(result.get("object")) is dict
            and result["object"].get("type") == "commit"
            and result["object"].get("sha") == expected, "CONTROL_SOURCE_NOT_CURRENT_MAIN")


def validate_readiness(value, revision):
    require(type(value) is dict and set(value) == {
        "worker", "source_revision", "ready", "readiness_checks"}, "READINESS_SCHEMA_INVALID")
    require(value["worker"] == WORKER and value["source_revision"] == revision,
            "DEPLOYED_REVISION_CHANGED")
    checks = value["readiness_checks"]
    require(type(checks) is dict and set(checks) == CHECKS
            and all(type(x) is bool for x in checks.values())
            and type(value["ready"]) is bool
            and value["ready"] == all(checks.values()), "READINESS_SCHEMA_INVALID")
    require(all(checks[key] for key in CHECKS - {"secret_requirement_met"}),
            "NON_SECRET_READINESS_FAILURE")
    return value["ready"]


def validate_settings(settings, secret, subdomain, config, revision):
    require(type(subdomain) is dict and subdomain.get("subdomain") == SUBDOMAIN,
            "ACCOUNT_WORKERS_ORIGIN_MISMATCH")
    require(type(secret) is dict and secret == {"name": "API_SECRET", "type": "secret_text"},
            "EXISTING_SECRET_METADATA_INVALID")
    require(type(settings) is dict and type(settings.get("bindings")) is list,
            "SETTINGS_INVALID")
    require(settings.get("compatibility_date") == config["compatibility_date"]
            and settings.get("compatibility_flags", []) == config.get("compatibility_flags", []),
            "WORKER_COMPATIBILITY_MISMATCH")
    expected = {
        "API_SECRET": {"name": "API_SECRET", "type": "secret_text"},
        "MAIL_FROM": {"name": "MAIL_FROM", "type": "plain_text", "text": config["vars"]["MAIL_FROM"]},
        "SOURCE_REVISION": {"name": "SOURCE_REVISION", "type": "plain_text", "text": revision},
        "SEND_EMAIL": {"name": "SEND_EMAIL", "type": "send_email"},
    }
    found = {}
    require(len(settings["bindings"]) == len(expected), "BINDING_SET_MISMATCH")
    for row in settings["bindings"]:
        require(type(row) is dict and type(row.get("name")) is str
                and row["name"] not in found, "BINDING_METADATA_INVALID")
        found[row["name"]] = row
    require(found == expected, "BINDING_SET_MISMATCH")


def snapshot(client, account, config, revision, expected_version_id, *, deadline=None,
             phase="INITIAL"):
    target = "/accounts/" + account + "/workers/scripts/" + WORKER
    calls = {
        "settings": lambda: client.cf_get(target + "/settings", deadline=deadline, phase=phase),
        "secret": lambda: client.cf_get(target + "/secrets/API_SECRET", deadline=deadline, phase=phase),
        "subdomain": lambda: client.cf_get("/accounts/" + account + "/workers/subdomain", deadline=deadline, phase=phase),
        "deployment": lambda: client.cf_get(target + "/deployments?page=1&per_page=1", deadline=deadline, phase=phase),
        "latest_version": lambda: client.cf_get(target + "/versions?page=1&per_page=1", deadline=deadline, phase=phase),
        "ready": lambda: client.readiness(revision, deadline=deadline),
    }
    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        futures = {name: pool.submit(call) for name, call in calls.items()}
        values = {name: future.result() for name, future in futures.items()}
    validate_settings(values["settings"], values["secret"], values["subdomain"], config, revision)
    values["recovery"] = serving_deployment(values["deployment"])
    require(values["recovery"]["version_id"] == expected_version_id,
            "EXPECTED_DEPLOYED_VERSION_CHANGED")
    require(latest_version(values["latest_version"]) == expected_version_id,
            "LATEST_VERSION_NOT_EXPECTED_ACTIVE_VERSION")
    return values


class Evidence:
    def __init__(self, directory, control_source, revision, expected_version_id):
        self.directory = directory
        self.directory.mkdir(mode=0o700, parents=False, exist_ok=False)
        self.path = directory / "receipt.jsonl"
        self.stream = self.path.open("x", encoding="utf-8", newline="\n")
        self.context = {"schema": "szl-email-secret-repair/v1", "worker": WORKER,
                        "control_source": control_source, "expected_deployed_revision": revision,
                        "expected_version_id": expected_version_id}
        self.records = []

    def emit(self, event, **fields):
        record = {**self.context, "event": event,
                  "observed_at": datetime.now(timezone.utc).isoformat(), **fields}
        encoded = json.dumps(record, sort_keys=True, allow_nan=False)
        self.stream.write(encoded + "\n")
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.records.append(record)
        print(encoded, flush=True)

    def finish(self, report):
        self.emit("OUTCOME", **report)
        with (self.directory / "report.json").open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps({**self.context, **report}, sort_keys=True, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def close(self):
        self.stream.close()


def repair(client, evidence, *, root, control_source, revision, expected_version_id,
           configured_account="", execute=False,
           run_attempt=1):
    report = {"status": "BLOCKED", "diagnostic_code": "NOT_STARTED",
              "mutation_attempted": False, "mutation_acknowledged": False,
              "readiness_verified": False, "candidate_authentication_verified": False,
              "automatic_retry": False, "email_delivery_proved": False,
              "dispatch_deadline_scope": "REQUEST_DISPATCH_NOT_PROVIDER_EXECUTION",
              "prior_deployment_id": None, "prior_version_id": None}
    try:
        require(type(control_source) is str and SHA.fullmatch(control_source), "CONTROL_SOURCE_INVALID")
        require(type(revision) is str and SHA.fullmatch(revision), "EXPECTED_REVISION_INVALID")
        uuid_text(expected_version_id)
        require(type(execute) is bool and type(run_attempt) is int and run_attempt >= 1,
                "EXECUTION_MODE_INVALID")
        require(not execute or run_attempt == 1, "RERUN_MUTATION_REFUSED")
        config, files = repository_contract(root)
        require_current_main(client, control_source)
        verify_sources(client, revision, files)
        account = resolve_account(client, configured_account)
        before = snapshot(client, account, config, revision, expected_version_id)
        report["prior_deployment_id"] = before["recovery"]["deployment_id"]
        report["prior_version_id"] = before["recovery"]["version_id"]
        evidence.emit("PRECONDITIONS", ready=before["ready"], **before["recovery"])
        # One fixed window covers all final observations, the final source read,
        # evidence fsync, and dispatch. Neither a slow read nor fsync renews it.
        deadline = min(client.overall_deadline, finite_clock(client.clock) + DISPATCH_SECONDS)
        final = snapshot(client, account, config, revision, expected_version_id,
                         deadline=deadline, phase="FINAL")
        require(canonical(final) == canonical(before), "WORKER_STATE_CHANGED")
        require_current_main(client, control_source, deadline=deadline)
        require(finite_clock(client.clock) < deadline, "DISPATCH_WINDOW_EXPIRED")
        if final["ready"]:
            client.probe(deadline=deadline)
            report.update(status="ALREADY_REPAIRED", diagnostic_code="SAME_CREDENTIAL_VERIFIED",
                          readiness_verified=True, candidate_authentication_verified=True)
        elif not execute:
            report.update(status="READY_FOR_EXECUTION", diagnostic_code="ONLY_SECRET_PREDICATE_FAILED")
        else:
            evidence.emit("PUT_INTENT", **before["recovery"],
                          automatic_retry=False, possible_submission_after_this_record=True)
            client.put("/accounts/" + account + "/workers/scripts/" + WORKER, deadline)
            evidence.emit("PUT_ACKNOWLEDGED", **before["recovery"])
            report["readiness_verified"] = client.readiness(revision)
            require(report["readiness_verified"], "ACKNOWLEDGED_READINESS_NOT_READY")
            client.probe()
            report.update(status="VERIFIED", diagnostic_code="REPLACEMENT_AUTHENTICATION_VERIFIED",
                          candidate_authentication_verified=True)
    except RepairError as error:
        report["diagnostic_code"] = error.code
        if error.cloudflare_envelope is not None:
            report["cloudflare_envelope"] = error.cloudflare_envelope
        report["status"] = ("ACKNOWLEDGED_NOT_VERIFIED" if client.acknowledged
                            else "WRITE_OUTCOME_UNCERTAIN" if client.attempted else "BLOCKED")
    except Exception:
        report["diagnostic_code"] = "UNEXPECTED_LOCAL_FAILURE"
        report["status"] = ("ACKNOWLEDGED_NOT_VERIFIED" if client.acknowledged
                            else "WRITE_OUTCOME_UNCERTAIN" if client.attempted else "BLOCKED")
    report["mutation_attempted"], report["mutation_acknowledged"] = client.attempted, client.acknowledged
    try:
        evidence.finish(report)
    except Exception:
        report["diagnostic_code"] = "EVIDENCE_WRITE_FAILED"
        if report["status"] in {"VERIFIED", "ALREADY_REPAIRED", "READY_FOR_EXECUTION"}:
            report["status"] = "ACKNOWLEDGED_NOT_VERIFIED" if client.acknowledged else "BLOCKED"
        print(json.dumps({"schema": "szl-email-secret-repair/v1", **report}, allow_nan=False), flush=True)
    return report


class Arguments(argparse.ArgumentParser):
    def error(self, _message):
        raise RepairError("ARGUMENTS_INVALID")


def main(argv=None):
    client = evidence = None
    try:
        parser = Arguments(description=__doc__)
        parser.add_argument("--control-source", required=True)
        parser.add_argument("--expect-revision", required=True)
        parser.add_argument("--expected-version-id", required=True)
        parser.add_argument("--output-directory", required=True, type=Path)
        parser.add_argument("--execute", action="store_true")
        args = parser.parse_args(argv)
        require(SHA.fullmatch(args.control_source) and SHA.fullmatch(args.expect_revision),
                "REVISION_ARGUMENT_INVALID")
        uuid_text(args.expected_version_id)
        require(os.environ.get("GITHUB_ACTIONS") == "true"
                and os.environ.get("GITHUB_REPOSITORY") == REPOSITORY
                and os.environ.get("GITHUB_REF") == "refs/heads/main"
                and os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
                and os.environ.get("GITHUB_SHA") == args.control_source
                and os.environ.get("REPAIR_ENVIRONMENT") == "cloudflare-production",
                "PROTECTED_MANUAL_CONTEXT_REQUIRED")
        raw_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
        require(re.fullmatch(r"[1-9][0-9]{0,5}", raw_attempt), "RUN_ATTEMPT_INVALID")
        evidence = Evidence(args.output_directory, args.control_source, args.expect_revision,
                            args.expected_version_id)
        client = Client(os.environ.get("CLOUDFLARE_API_TOKEN"), os.environ.get("GH_TOKEN"),
                        os.environ.get("EMAIL_SENDER_API_SECRET_V2"))
        result = repair(client, evidence, root=ROOT, control_source=args.control_source,
                        revision=args.expect_revision, expected_version_id=args.expected_version_id,
                        configured_account=os.environ.get("CLOUDFLARE_ACCOUNT_ID", ""),
                        execute=args.execute, run_attempt=int(raw_attempt))
        return 0 if result["status"] in {"VERIFIED", "ALREADY_REPAIRED", "READY_FOR_EXECUTION"} else 2
    except Exception as error:
        code = error.code if isinstance(error, RepairError) else "LOCAL_SETUP_FAILED"
        result = {"status": "BLOCKED", "diagnostic_code": code,
                  "mutation_attempted": bool(client and client.attempted),
                  "mutation_acknowledged": bool(client and client.acknowledged),
                  "automatic_retry": False, "email_delivery_proved": False}
        try:
            if evidence is not None:
                evidence.finish(result)
            else:
                print(json.dumps(result), flush=True)
        except Exception:
            print(json.dumps({**result, "diagnostic_code": "EVIDENCE_WRITE_FAILED"}), flush=True)
        return 2
    finally:
        if evidence is not None:
            try:
                evidence.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
