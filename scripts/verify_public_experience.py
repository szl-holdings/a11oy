#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Bounded release checks for the canonical public experience.

Only --exercise-simulation permits HTTP POSTs, limited to the five published
simulation scenarios. No response bodies, approval capabilities, command output,
credentials, or environment values enter the report. Source checks do not prove
browser behavior, deployment identity, persistent storage, or external authority.
"""

import argparse
import ast
import hashlib
import json
import re
import shlex
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


PREFIX = "/api/experience/v1"
ROUTES = {
    PREFIX + "/health": {"GET"},
    PREFIX + "/estate": {"GET"},
    PREFIX + "/scenarios": {"GET"},
    PREFIX + "/sessions": {"POST"},
    PREFIX + "/sessions/{session_id}": {"GET"},
    PREFIX + "/sessions/{session_id}/events": {"GET"},
    PREFIX + "/sessions/{session_id}/approve": {"POST"},
    PREFIX + "/receipts/{receipt_id}": {"GET"},
    PREFIX + "/receipts/{receipt_id}/verify": {"POST"},
}
SCENARIOS = {
    "investigate-outage", "screen-vessel", "review-property", "review-contract",
    "route-inference",
}
STAGES = {
    "CREATED", "PROPOSED", "EVIDENCE_BOUND", "QUALIFIED", "POLICY_EVALUATED",
    "APPROVAL_REQUIRED", "APPROVED", "EXECUTING", "VERIFIED", "RECEIPTED",
    "POLICY_DENIED", "BLOCKED", "VERIFICATION_FAILED", "RECOVERY_REQUIRED", "UNAVAILABLE",
}
TERMINAL = {
    "RECEIPTED", "POLICY_DENIED", "BLOCKED", "VERIFICATION_FAILED",
    "RECOVERY_REQUIRED", "UNAVAILABLE",
}
COPY = (
    "A11OY COMMAND FABRIC", "AI that proves what it did.",
    "Run a governed action. Inspect its evidence, policy, approval, execution, verification, and receipt.",
    "Run the demo", "Inspect a receipt",
)
ASSETS = {
    "/assets/a11oy-public-experience-v1.css": "console/assets/a11oy-public-experience-v1.css",
    "/assets/a11oy-public-experience-v1.js": "console/assets/a11oy-public-experience-v1.js",
    "/landing/app.js": "static/a11oy_landing.js",
}
MAX_RESPONSE_BYTES = 2_000_000


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    required: bool = True


@dataclass
class Element:
    tag: str
    attrs: dict
    children: list = field(default_factory=list)

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Element):
                yield from child.walk()

    def visible_text(self):
        classes = set(self.attrs.get("class", "").split())
        if (self.tag in {"script", "style", "template"}
                or "hidden" in self.attrs or self.attrs.get("aria-hidden") == "true"
                or classes & {"a11oy-visually-hidden", "sr-only"}):
            return ""
        return " ".join(
            child.visible_text() if isinstance(child, Element) else child
            for child in self.children
        )


class Document(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.root = Element("document", {})
        self.stack = [self.root]
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        node = Element(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def words(text):
    return re.findall(r"\b[\w’'-]+\b", text)


def hero_checks(source):
    document = Document(source)
    roots = [item for item in document.root.walk() if item.attrs.get("id") == "a11oy-experience"]
    if len(roots) != 1:
        return [Check("hero-source", False, "exactly one #a11oy-experience is required")]
    root = roots[0]
    blocks = [item for item in root.walk() if "a11oy-experience-copy" in item.attrs.get("class", "").split()]
    text = " ".join(blocks[0].visible_text().split()) if len(blocks) == 1 else ""
    ids = [item.attrs["id"] for item in root.walk() if "id" in item.attrs]
    return [
        Check("hero-source", len(blocks) == 1, "canonical copy block scoped inside #a11oy-experience"),
        Check("hero-copy", all(part in text for part in COPY), "five required copy fragments checked in visible copy"),
        Check("hero-word-budget", bool(text) and len(words(text)) <= 35, f"source hero words={len(words(text))}; budget=35; browser visibility checked separately"),
        Check("hero-unique-ids", len(ids) == len(set(ids)), "IDs are unique within canonical experience"),
    ]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def public_config_checks(registry, projection, scenarios):
    """Validate public projection against the committed allowlist, without discovery."""
    try:
        assert registry["schema"] == "szl.public-estate/v1"
        assert projection["schema"] == "a11oy.public-experience.estate-projection/v1"
        assert projection["source_manifest"] == "governance/public-estate.v1.json"
        assert scenarios["schema"] == "a11oy.public-experience.scenarios/v1"
        sources = registry["platforms"] + registry["public_products"]
        allowed = {item["id"]: item for item in sources}
        assert len(allowed) == len(sources) and sources
        assert all(item.get("public") is True and item.get("visibility") != "private" for item in sources)
        hosts = set(registry["allowed_hosts"])
        for item in sources:
            url = urlsplit(item["base_url"])
            assert url.scheme == "https" and url.hostname in hosts
            assert not url.username and not url.password and not url.query and not url.fragment
        definitions = scenarios["scenarios"]
        assert len(definitions) == 5 and {item["id"] for item in definitions} == SCENARIOS
        for item in definitions:
            assert item["data_state"] == "SIMULATION"
            assert item["action"].startswith("simulate.") and item["outcome"] in TERMINAL
            assert type(item["seed"]) is int and 0 <= item["seed"] <= 2_147_483_647
            assert type(item["approval_required"]) is bool
            assert bool(item["approval_scope"]) == item["approval_required"]
            assert 1 <= len(item["evidence"]) <= 8
            for evidence in item["evidence"]:
                assert evidence["source_class"] in {"SIMULATION", "SNAPSHOT", "UNAVAILABLE"}
                uri = evidence.get("uri")
                if uri is not None:
                    parsed = urlsplit(uri)
                    assert not parsed.username and not parsed.password
                    assert (uri.startswith("/") and not uri.startswith("//") and not parsed.netloc) or (parsed.scheme == "https" and parsed.hostname in hosts)
        assets = projection["assets"]
        assert assets and len({item["id"] for item in assets}) == len(assets)
        for item in assets:
            assert item["id"] in allowed and item["public"] is True and item["active"] is True
            assert item.get("visibility") != "private"
            assert len(words(item["summary"])) <= 18
            assert set(item["scenario_ids"]) <= SCENARIOS
            assert item["evidence_path"].startswith("/") and not item["evidence_path"].startswith("//")
        return [Check("public-config", True, f"{len(assets)} allowlisted public assets; five bounded scenarios")]
    except (AssertionError, KeyError, TypeError, ValueError):
        return [Check("public-config", False, "registry/projection/scenario schema, public-only binding, URL, or bounded simulation validation failed")]


def route_contract(tree):
    """Read one exact AST dictionary; do not import the server or evaluate its code."""
    fn = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == "_experience_route_contract")
    value = next(item.value for item in fn.body if isinstance(item, ast.Return))
    result = {}
    for key, methods in zip(value.keys, value.values):
        assert isinstance(key, ast.JoinedStr)
        parts = []
        for part in key.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                parts.append(part.value)
            else:
                assert isinstance(part, ast.FormattedValue) and isinstance(part.value, ast.Name) and part.value.id == "API_PREFIX"
                parts.append(PREFIX)
        assert isinstance(methods, ast.Call) and isinstance(methods.func, ast.Name) and methods.func.id == "frozenset"
        assert len(methods.args) == 1
        result["".join(parts)] = ast.literal_eval(methods.args[0])
    return result


def static_checks(root):
    checks = []
    try:
        source = (root / "a11oy_landing.html").read_text(encoding="utf-8")
        checks.extend(hero_checks(source))
        references = {node.attrs.get("src") or node.attrs.get("href") for node in Document(source).root.walk()}
        checks.append(Check("controller-css-bound", set(ASSETS) - {"/landing/app.js"} <= references, "canonical HTML binds controller and CSS"))
        checks.append(Check("local-assets", all((root / path).is_file() for path in ASSETS.values()), "controller, CSS, and lazy renderer exist locally"))
    except (OSError, ValueError):
        checks.append(Check("hero-source", False, "canonical landing could not be read"))
    try:
        checks.extend(public_config_checks(
            read_json(root / "governance/public-estate.v1.json"),
            read_json(root / "config/public-experience/estate-projection.v1.json"),
            read_json(root / "config/public-experience/scenarios.v1.json"),
        ))
    except (OSError, ValueError):
        checks.append(Check("public-config", False, "canonical JSON configuration could not be read"))
    try:
        tree = ast.parse((root / "a11oy_public_experience.py").read_text(encoding="utf-8"))
        checks.append(Check("nine-route-contract", route_contract(tree) == ROUTES, "all nine exact methods and paths checked in the service contract"))
        classes = {item.name: item for item in tree.body if isinstance(item, ast.ClassDef)}
        stages = {target.id for item in classes["ExperienceStage"].body if isinstance(item, ast.Assign) for target in item.targets if isinstance(target, ast.Name)}
        strict = classes["StrictModel"]
        strict_extra = any(isinstance(item, ast.keyword) and item.arg == "extra" and isinstance(item.value, ast.Constant) and item.value.value == "forbid" for item in ast.walk(strict))
        models = {"ExperienceEvent", "ExperienceReceipt", "SessionResponse", "HealthResponse", "ApproveSessionRequest", "EvidenceHandle"}
        checks.append(Check("typed-state-contract", stages == STAGES and strict_extra and models <= set(classes), "canonical states and strict typed model declarations present; behavioral validation is a separate test"))
        server = ast.parse((root / "serve.py").read_text(encoding="utf-8"))
        registrations = [node.lineno for node in ast.walk(server) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "_public_experience" and node.func.attr == "register"]
        catches = [node.lineno for node in ast.walk(server) if isinstance(node, ast.Call) and any(isinstance(arg, ast.Constant) and arg.value == "/{full_path:path}" for arg in node.args)]
        checks.append(Check("registration-order", bool(registrations and catches) and min(registrations) < min(catches), "registration precedes SPA catch-all in serve.py; HTTP content types prove actual route resolution"))
    except (OSError, SyntaxError, KeyError, TypeError, ValueError, AssertionError, StopIteration, AttributeError):
        checks.append(Check("python-contract", False, "exact service AST contract could not be validated"))
    try:
        docker = (root / "Dockerfile").read_text(encoding="utf-8")
        copied = set()
        for line in docker.splitlines():
            if line.strip().startswith("COPY "):
                fields = shlex.split(line.split("#", 1)[0])
                copied.update(field.rstrip("/") for field in fields[1:-1] if not field.startswith("--"))
        required = {"a11oy_public_experience.py", "config/public-experience", "console", "static/a11oy_landing.js", "a11oy_landing.html", "governance/public-estate.v1.json"}
        checks.append(Check("docker-inputs", required <= copied, "explicit module/config and containing asset/registry COPY inputs checked; no image build inferred"))
    except (OSError, ValueError):
        checks.append(Check("docker-inputs", False, "Docker COPY inputs could not be read"))
    return checks


class VerificationError(Exception):
    """Contains only a fixed report-safe message, never a response body."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def validated_base(value):
    parsed = urlsplit(value)
    if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"", "/"} or (parsed.scheme != "https" and not (
                parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}))):
        raise ValueError("base URL must be an HTTPS origin or HTTP loopback origin, without credentials, path, query, or fragment")
    return value.rstrip("/")


class HttpClient:
    def __init__(self, base_url, timeout=15):
        self.base_url = validated_base(base_url)
        self.timeout = timeout
        self.opener = build_opener(NoRedirect())

    def request(self, path, *, method="GET", payload=None, headers=None, media="application/json"):
        if not path.startswith("/") or path.startswith("//"):
            raise VerificationError("nonlocal request path rejected")
        fields = {"Accept": media, "User-Agent": "a11oy-public-experience-verifier/1.0"}
        fields.update(headers or {})
        body = None
        if payload is not None:
            fields.update({"Content-Type": "application/json", "Origin": self.base_url})
            body = json.dumps(payload).encode("utf-8")
        try:
            request = Request(self.base_url + path, data=body, method=method, headers=fields)
            with self.opener.open(request, timeout=self.timeout) as response:
                data = response.read(MAX_RESPONSE_BYTES + 1)
                if response.status not in {200, 201}:
                    raise VerificationError(f"unexpected HTTP status={response.status}")
                if response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != media:
                    raise VerificationError("unexpected response content type")
                if len(data) > MAX_RESPONSE_BYTES:
                    raise VerificationError("response exceeds bounded byte limit")
                if media == "text/event-stream":
                    return data.decode("utf-8")
                value = json.loads(data)
                if not isinstance(value, dict):
                    raise VerificationError("JSON response must be an object")
                return value
        except HTTPError as exc:
            raise VerificationError(f"HTTP status={exc.code}; response body withheld") from None
        except (URLError, TimeoutError, OSError, UnicodeError, ValueError):
            raise VerificationError("transport, timeout, encoding, or JSON parse failure; details withheld") from None


def require(condition, message):
    if not condition:
        raise VerificationError(message)


def canonical_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def parse_events(text):
    events = []
    ended = False
    for block in text.replace("\r\n", "\n").split("\n\n"):
        if not block.strip():
            continue
        fields = {}
        for line in block.splitlines():
            if line and not line.startswith(":"):
                name, separator, value = line.partition(":")
                require(bool(separator), "malformed event stream field")
                fields[name] = value.lstrip()
        if not fields:
            continue
        require(not ended, "event data after end marker")
        try:
            payload = json.loads(fields["data"])
            if fields.get("event") == "end":
                ended = True
            else:
                require(fields.get("event") == "experience", "unknown stream event type")
                require(int(fields["id"]) == payload["sequence"], "stream cursor differs from sequence")
                events.append(payload)
        except (KeyError, ValueError, TypeError):
            raise VerificationError("malformed event stream payload") from None
    require(ended, "event stream did not close with an end marker")
    return events


def validate_event_chain(events, session_id, scenario_id):
    require(bool(events), "empty lifecycle event chain")
    previous = "0" * 64
    for sequence, event in enumerate(events):
        require(event.get("sequence") == sequence, "noncontiguous lifecycle sequence")
        require(event.get("session_id") == session_id and event.get("scenario_id") == scenario_id, "event session/scenario binding failed")
        require(event.get("data_state") == "SIMULATION" and event.get("stage") in STAGES, "event simulation/state contract failed")
        require(event.get("previous_hash") == previous, "event chain previous hash failed")
        digest = canonical_digest({key: value for key, value in event.items() if key != "current_hash"})
        require(event.get("current_hash") == digest, "event digest failed")
        previous = digest
        for field_name in ("policy_result", "verification_result"):
            value = event.get(field_name)
            require(value is None or value.get("authoritative") is False, "simulation claimed external authority")
        effect = event.get("effect_result")
        require(effect is None or effect.get("state") == "SIMULATED_NO_EXTERNAL_EFFECT", "event claimed external effect")
    return previous


def validate_receipt(receipt, view, events):
    require(receipt.get("namespace") == "sim-experience" and receipt.get("data_state") == "SIMULATION", "receipt namespace or simulation label failed")
    require(receipt.get("effect_state") == "SIMULATED_NO_EXTERNAL_EFFECT", "receipt external effect boundary failed")
    require(receipt.get("session_id") == view["session_id"] and receipt.get("scenario_id") == view["scenario_id"], "receipt binding failed")
    require(receipt.get("final_stage") == view["stage"] and receipt.get("events") == events, "receipt final stage or event snapshot failed")
    require(receipt.get("previous_hash") == validate_event_chain(events, view["session_id"], view["scenario_id"]), "receipt chain root failed")
    excluded = {"receipt_digest", "current_hash", "chain_integrity", "signer_state", "verification_state", "envelope"}
    digest = canonical_digest({key: value for key, value in receipt.items() if key not in excluded})
    require(digest == receipt.get("receipt_digest") == receipt.get("current_hash"), "receipt digest failed")
    require(receipt.get("chain_integrity") == "INTACT", "receipt chain integrity failed")
    signatures = receipt.get("envelope", {}).get("signatures")
    signer = receipt.get("signer_state")
    require(signer in {"UNSIGNED", "UNAVAILABLE", "SIGNED_UNVERIFIED", "VERIFIED_SIGNATURE", "VERIFIED_EPHEMERAL", "VERIFIED_PERSISTENT"}, "unknown signer state")
    require(bool(signatures) or signer in {"UNSIGNED", "UNAVAILABLE"}, "receipt asserts signing without signatures")
    return digest


def exercise_scenario(client, scenario):
    scenario_id = scenario["id"]
    key = str(uuid.uuid4())
    created = client.request(PREFIX + "/sessions", method="POST", payload={"scenario_id": scenario_id}, headers={"Idempotency-Key": key})
    require(created.get("schema") == "a11oy.public-experience.session/v1" and created.get("data_state") == "SIMULATION", "session schema or data state failed")
    session_id = created.get("session_id", "")
    require(bool(re.fullmatch(r"exp_[0-9a-f]{32}", session_id)), "invalid opaque session ID")
    path = PREFIX + "/sessions/" + session_id
    replay = client.request(PREFIX + "/sessions", method="POST", payload={"scenario_id": scenario_id}, headers={"Idempotency-Key": key})
    require(replay.get("session_id") == session_id and replay.get("idempotent_replay") is True, "session idempotency failed")
    require(replay.get("replay") == created.get("replay"), "replay metadata changed")
    replay_info = created.get("replay") or {}
    require(replay_info.get("seed") == scenario["seed"] and replay_info.get("scenario_version") == scenario["version"], "replay seed/version differs from scenario")
    require(bool(re.fullmatch(r"[0-9a-f]{64}", replay_info.get("simulation_digest", ""))), "replay digest missing")
    view = client.request(path)
    require(view.get("approval_capability") is None, "read path exposed approval capability")
    if created.get("stage") == "APPROVAL_REQUIRED":
        capability = created.get("approval_capability") or {}
        require(capability.get("scope") == scenario["approval_scope"], "approval scope differs from allowlisted scenario")
        view = client.request(path + "/approve", method="POST", payload={
            "capability_token": capability["token"], "scope": capability["scope"],
            "expected_sequence": capability["issued_sequence"],
        })
    require(view.get("terminal") is True and view.get("stage") == scenario["outcome"], "terminal scenario outcome failed")
    events = parse_events(client.request(path + "/events", media="text/event-stream"))
    validate_event_chain(events, session_id, scenario_id)
    require(events[0]["stage"] == "CREATED" and events[-1]["stage"] == view["stage"], "event stream initial or terminal stage failed")
    resumed = parse_events(client.request(path + "/events?after=" + str(len(events) - 2), media="text/event-stream"))
    require(resumed == events[-1:], "SSE resume did not return exact remaining event")
    receipt_id = view.get("receipt_id", "")
    require(bool(re.fullmatch(r"sim-experience:[0-9a-f]{32}", receipt_id)), "invalid simulation receipt ID")
    receipt_path = PREFIX + "/receipts/" + receipt_id
    receipt = client.request(receipt_path)
    digest = validate_receipt(receipt, view, events)
    verified = client.request(receipt_path + "/verify", method="POST", payload={})
    require(verified.get("schema") == "a11oy.public-experience.receipt-verification/v1" and verified.get("ok") is True, "receipt verifier rejected its stored receipt")
    require(verified.get("chain_integrity") == "INTACT" and verified.get("effect_state") == "SIMULATED_NO_EXTERNAL_EFFECT", "verification truth axes failed")
    require(verified.get("signer_state") == receipt["signer_state"], "verification signer state differs")
    require(verified.get("verification_state") in {"VERIFIED", "PARTIAL"}, "receipt integrity verification failed")
    if receipt["signer_state"] in {"UNSIGNED", "UNAVAILABLE", "SIGNED_UNVERIFIED"}:
        require(verified["verification_state"] == "PARTIAL", "unsigned/unavailable signature incorrectly presented as fully verified")
    require(client.request(receipt_path) == receipt, "read or verify changed receipt")
    return f"stage={view['stage']}; events={len(events)}; digest={digest}; signer={receipt['signer_state']}; integrity={verified['verification_state']}; effect=SIMULATED_NO_EXTERNAL_EFFECT"


def http_checks(client, *, exercise=False):
    checks = []
    definitions = None
    for name, schema in (("health", "health"), ("estate", "estate"), ("scenarios", "scenario-list")):
        try:
            value = client.request(PREFIX + "/" + name)
            require(value.get("schema") == "a11oy.public-experience." + schema + "/v1", "unexpected API schema")
            if name == "health":
                require(value.get("data_state") == "SIMULATION" and value.get("external_authority_state") == "UNAVAILABLE", "health truth labels failed")
                require(value.get("status") == "READY", "experience reports degraded availability")
                require(set(value.get("endpoints", [])) == set(ROUTES), "health route set differs from required contract")
                require(value.get("storage", {}).get("state") == "EPHEMERAL", "unexpected storage state requires review")
            elif name == "estate":
                assets = value.get("assets", [])
                require(value.get("data_state") == "SNAPSHOT" and bool(assets), "estate snapshot missing")
                require(all(item.get("public") is True and item.get("active") is True for item in assets), "estate contains nonpublic or inactive asset")
            else:
                definitions = value.get("scenarios", [])
                require(value.get("data_state") == "SIMULATION", "scenario data label failed")
                require(len(definitions) == 5 and {item["id"] for item in definitions} == SCENARIOS, "scenario allowlist differs")
                require(all(item.get("data_state") == "SIMULATION" and item.get("action", "").startswith("simulate.") and item.get("outcome") in TERMINAL for item in definitions), "scenario simulation boundary failed")
            checks.append(Check("http:" + name, True, "HTTP JSON content type and public schema/labels validated"))
        except (VerificationError, KeyError, TypeError, ValueError) as exc:
            checks.append(Check("http:" + name, False, str(exc) if isinstance(exc, VerificationError) else "malformed response fields; values withheld"))
            if name == "scenarios":
                definitions = None
    if exercise:
        if not definitions or any(not check.ok for check in checks):
            checks.append(Check("http:simulation", False, "simulation probes withheld because read preflight failed"))
        else:
            for scenario in definitions:
                try:
                    detail = exercise_scenario(client, scenario)
                    checks.append(Check("simulation:" + scenario["id"], True, detail))
                except (VerificationError, KeyError, TypeError, ValueError) as exc:
                    checks.append(Check("simulation:" + scenario["id"], False, str(exc) if isinstance(exc, VerificationError) else "malformed response fields; values withheld"))
    return checks


def run_command(root, command, name):
    started = time.monotonic()
    try:
        result = subprocess.run(command, cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=900, check=False)
        return Check(name, result.returncode == 0, f"exit={result.returncode}; seconds={time.monotonic() - started:.2f}; command output withheld")
    except FileNotFoundError:
        return Check(name, False, "required build/test tool unavailable")
    except subprocess.TimeoutExpired:
        return Check(name, False, "command timed out after 900 seconds")


def build_checks(root):
    commands = [
        ([sys.executable, "-B", "-m", "py_compile", "a11oy_public_experience.py", "scripts/verify_public_experience.py"], "build:python-compile"),
        (["node", "--check", "console/assets/a11oy-public-experience-v1.js"], "build:controller-syntax"),
        (["node", "--check", "static/a11oy_landing.js"], "build:renderer-syntax"),
        ([sys.executable, "-B", "-m", "pytest", "-q", "tests/test_a11oy_public_experience.py", "tests/test_public_experience_frontend_v1.py", "tests/test_verify_public_experience.py"], "build:experience-tests"),
    ]
    return [run_command(root, command, name) for command, name in commands]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--base-url")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--run-build", action="store_true", help="Run experience Python/JavaScript compilation and focused tests; does not build a Docker image or the unrelated SPA.")
    parser.add_argument("--exercise-simulation", action="store_true", help="Explicitly permit five bounded demo lifecycles, including session and approval POSTs; requires --base-url.")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.exercise_simulation and not args.base_url:
        parser.error("--exercise-simulation requires --base-url")
    try:
        base_url = validated_base(args.base_url) if args.base_url else None
    except ValueError as exc:
        parser.error(str(exc))
    root = args.repo.resolve()
    checks = static_checks(root)
    if args.run_build:
        checks.extend(build_checks(root))
    if base_url:
        checks.extend(http_checks(HttpClient(base_url), exercise=args.exercise_simulation))
    failed = sum(not item.ok and item.required for item in checks)
    report = {
        "schema": "a11oy.public-experience.acceptance/v1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "repo": str(root), "base_url": base_url,
        "status": "FAILED" if failed else "PASS_FOR_REQUESTED_SCOPE",
        "strict": args.strict,
        "scope": {"static": "RUN", "experience_build_tests": "RUN" if args.run_build else "NOT_RUN", "http_reads": "RUN" if base_url else "NOT_RUN", "simulation_lifecycles": "RUN" if args.exercise_simulation else "NOT_RUN", "browser_accessibility_performance": "NOT_RUN", "production_image_build": "NOT_RUN", "deployment_identity": "NOT_VERIFIED", "external_authority": "NOT_EXERCISED"},
        "checks": [asdict(item) for item in checks],
        "passed": sum(item.ok for item in checks), "failed": failed,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 1 if args.strict and failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
