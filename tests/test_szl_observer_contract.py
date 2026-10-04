#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Import, clock, safety and script-free UI contracts; not a browser audit."""

import base64
from datetime import datetime, timedelta, timezone
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

from szl_observer_contract import (MAX_REQUEST_BYTES, REPORT_SCHEMA, REQUEST_SCHEMA,
                                   capabilities, evaluate_import, render_import)
from szl_observer_kernel import DOMAIN_PROFILES


NOW = datetime(2026, 10, 2, 5, tzinfo=timezone.utc)


def request(domain="enterprise", kind="OBSERVATION"):
    rows = []
    for index, reading in enumerate((8, 9, 10, 11, 12, 30)):
        payload = json.dumps({"record_id": "source-" + str(index), "domain": domain,
                              "metric": "review-count", "unit": "count", "scope": "test-region",
                              "value": reading, "kind": kind,
                              "event_at": (NOW - timedelta(seconds=60 - index)).isoformat()},
                             separators=(",", ":")).encode()
        digest = hashlib.sha256(payload).hexdigest()
        rows.append({"payload_base64": base64.b64encode(payload).decode(),
                     "evidence_uri": "urn:sha256:" + digest, "evidence_digest": "sha256:" + digest,
                     "retrieved_at": NOW.isoformat(), "kind": kind})
    return {"schema": REQUEST_SCHEMA, "domain": domain, "metric": "review-count", "unit": "count",
            "scope": "test-region", "records": rows}


def encode(item):
    return json.dumps(item, separators=(",", ":"), allow_nan=False).encode()


def evaluate(item):
    return evaluate_import(encode(item), clock=lambda: NOW)


@pytest.mark.parametrize("domain", DOMAIN_PROFILES)
def test_exact_import_reviews_each_domain_without_creating_authority(domain):
    report = evaluate(request(domain))
    assert report["schema"] == REPORT_SCHEMA
    assert report["registration"] == "NOT_REGISTERED"
    assert report["evaluation_scope"] == "OFFLINE_DESCRIPTIVE_REVIEW"
    assert report["result"]["status"] == "RANKED"
    assert report["result"]["probability"] is None
    assert report["result"]["source_authenticity"] == "NOT_VERIFIED"
    assert report["result"]["external_writes"] == "DISABLED"
    json.dumps(report, allow_nan=False)


def test_capabilities_do_not_claim_live_connectors():
    info = capabilities()
    assert info["registration"] == "NOT_REGISTERED"
    assert info["external_writes"] == "DISABLED"
    assert {item["id"] for item in info["domains"]} == set(DOMAIN_PROFILES)
    assert all(item["connector"] == "NOT_CONNECTED" for item in info["domains"])


@pytest.mark.parametrize("raw", [b"", b"[]", b"null", b'\xff', b'{"schema":NaN}',
                                  b'{"schema":"a","schema":"b"}', b"x" * (MAX_REQUEST_BYTES + 1),
                                  "not-bytes", None],
                         ids=["empty", "array", "null", "utf8", "nan", "duplicate", "oversized", "string", "none"])
def test_bad_envelopes_fail_closed_with_no_score(raw):
    report = evaluate_import(raw, clock=lambda: NOW)
    assert report["result"]["status"] == "HOLD"
    assert report["result"]["score"] is None
    assert report["result"]["external_writes"] == "DISABLED"


@pytest.mark.parametrize("key,value", [("generated_at", NOW.isoformat()), ("now", NOW.isoformat()),
                                        ("max_age_seconds", 86400), ("url", "http://localhost/"),
                                        ("command", "restart"), ("schema", "other"),
                                        ("records", []), ("records", [None] * 257)])
def test_clock_policy_commands_and_schema_are_not_caller_controls(key, value):
    item = request(); item[key] = value
    assert evaluate(item)["result"]["status"] == "HOLD"


@pytest.mark.parametrize("key,value", [("payload_base64", "bad!"), ("payload_base64", "YWJj\n"),
                                        ("payload_base64", ""), ("payload_base64", "a" * 5465),
                                        ("payload_base64", 1), ("retrieved_at", 1),
                                        ("retrieved_at", "x" * 65), ("retrieved_at", "yesterday"),
                                        ("evidence_digest", "sha256:" + "0" * 64),
                                        ("evidence_uri", "http://localhost/secret"),
                                        ("kind", "MEASURED"), ("authorization", "approved")],
                         ids=["encoding", "whitespace", "empty", "oversized", "integer", "clock-integer",
                              "clock-length", "clock-invalid", "digest", "uri", "kind", "extra"])
def test_exact_record_schema_encoding_and_binding_cannot_be_bypassed(key, value):
    item = request(); item["records"][-1][key] = value
    assert evaluate(item)["result"]["status"] == "HOLD"


def test_noncanonical_padding_bits_are_rejected_before_schema_parsing():
    item = request()
    # Both decode to the same byte under validate=True, but only YQ== is canonical.
    assert base64.b64decode("YR==", validate=True) == b"a"
    item["records"][-1]["payload_base64"] = "YR=="
    assert evaluate(item)["result"]["reason"] == "INVALID_IMPORT_SCHEMA_OR_ENCODING"


def test_duplicate_outer_metadata_is_not_overwritten():
    raw = encode(request()).replace(b'"kind":"OBSERVATION"', b'"kind":"OBSERVATION","kind":"SIMULATION"', 1)
    assert evaluate_import(raw, clock=lambda: NOW)["result"]["status"] == "HOLD"


def test_latest_retrieval_cannot_freshen_sources_and_current_clock_is_independent():
    raw = encode(request())
    later = NOW + timedelta(seconds=901)
    result = evaluate_import(raw, clock=lambda: later)["result"]
    assert result["reason"] == "STALE_SOURCE"
    assert evaluate_import(raw, clock=lambda: NOW.replace(tzinfo=None))["result"]["reason"] == "INVALID_CLOCK"


def test_simulation_rewrapping_remains_a_digest_bound_conflict():
    item = request(kind="SIMULATION")
    assert evaluate(item)["result"]["label"] == "SAMPLE"
    for row in item["records"]:
        row["kind"] = "OBSERVATION"
    assert evaluate(item)["result"]["reason"] == "DATA_KIND_BINDING_CONFLICT"


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.text = []
        self.meta = []
        self.links = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        self.tags.append(tag)
        if "id" in attributes:
            self.ids.add(attributes["id"])
        if tag == "meta":
            self.meta.append(attributes)
        if tag == "a":
            self.links.append(attributes.get("href"))
        assert not any(name.startswith("on") for name in attributes)

    def handle_data(self, value):
        self.text.append(value)


@pytest.mark.parametrize("kind,expected", [("OBSERVATION", "SNAPSHOT"), ("SIMULATION", "SAMPLE")])
def test_readonly_report_projects_results_evidence_and_all_vertical_limits(kind, expected):
    raw = encode(request(kind=kind))
    html = render_import(raw, clock=lambda: NOW)
    page = Page(); page.feed(html)
    visible = " ".join(page.text)
    assert expected in visible
    assert "NOT_REGISTERED" in visible and "NOT_CONNECTED" in visible
    assert "NOT_VERIFIED" in visible and "NOT_EVALUATED" in visible
    assert "earthquake prediction" in visible
    assert "Reopening a saved report does not re-evaluate input freshness." in visible
    for domain in DOMAIN_PROFILES:
        assert domain.replace("-", " ").title() in visible
    assert not {"script", "iframe", "form", "input", "button"}.intersection(page.tags)
    assert "main" in page.ids and "#main" in page.links
    assert html.count("urn:sha256:") == 6
    csp = next(meta["content"] for meta in page.meta if meta.get("http-equiv") == "Content-Security-Policy")
    assert "script-src 'none'" in csp and "connect-src 'none'" in csp
    assert "/assets/szl/szl-design-system.css" in html


def test_untrusted_claims_html_commands_and_embedded_report_cannot_render():
    item = request(); item["status"] = "MEASURED"; item["claim"] = '<script>alert(1)</script>'
    html = render_import(encode(item), clock=lambda: NOW)
    assert '<h2 id="review">HOLD' in html
    assert "alert(1)" not in html
    assert "MEASURED" not in html
    assert "No admitted evidence series." in html


def test_report_uses_local_design_tokens_without_a_parallel_literal_palette():
    html = render_import(encode(request()), clock=lambda: NOW)
    styles = html.split("<style>", 1)[1].split("</style>", 1)[0]
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", styles)
    assert "system-ui" not in styles and "monospace" not in styles
    assert "font-family:var(--font-body)" in styles
    assert "font-family:var(--font-mono)" in styles


def test_hosted_observer_job_runs_the_exact_surface_without_provider_permissions():
    import yaml

    root = Path(__file__).resolve().parents[1]
    workflow = yaml.load((root / ".github/workflows/observer-contract-tests.yml").read_text(encoding="utf-8"),
                         Loader=yaml.BaseLoader)
    assert workflow["on"] == {"pull_request": {}, "push": {"branches": ["main"]}}
    assert workflow["permissions"] == {"contents": "read"}
    assert set(workflow["jobs"]) == {"observer-contract"}
    job = workflow["jobs"]["observer-contract"]
    assert set(job) == {"name", "runs-on", "timeout-minutes", "env", "steps"}
    assert job["timeout-minutes"] == "10"
    assert job["env"] == {"PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    steps = job["steps"]
    assert len(steps) == 4
    assert steps[0]["uses"] == "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
    assert steps[0]["with"] == {"persist-credentials": "false"}
    assert steps[1]["uses"] == "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97"
    assert steps[1]["with"] == {"python-version": "3.12"}
    assert steps[2]["run"] == "python -m pip install --require-hashes --no-deps --no-cache-dir -r .github/requirements/ci-core.txt"
    assert steps[3]["run"] == ("python -m pytest -p no:cacheprovider tests/test_szl_observer_kernel.py "
                               "tests/test_szl_observer_contract.py -q --tb=short")
    assert all(set(step) == {"name", "uses", "with"} for step in steps[:2])
    assert all(set(step) == {"name", "run"} for step in steps[2:])


def test_renderer_rechecks_hashes_and_currentness_instead_of_imported_result():
    item = request(); item["records"][-1]["evidence_digest"] = "sha256:" + "0" * 64
    assert '<h2 id="review">HOLD' in render_import(encode(item), clock=lambda: NOW)
    assert '<h2 id="review">HOLD' in render_import(encode(request()), clock=lambda: NOW + timedelta(seconds=901))


@pytest.mark.parametrize("html", [False, True], ids=["json", "html"])
@pytest.mark.parametrize("valid", [False, True], ids=["held", "ranked"])
def test_cli_is_bounded_readonly_and_has_honest_exit_disposition(monkeypatch, html, valid):
    import scripts.review_observer_import as cli

    class Input(io.BytesIO):
        def read(self, size=-1):
            assert size == MAX_REQUEST_BYTES + 1
            return super().read(size)

    calls = []
    def now(tz):
        calls.append(tz)
        return NOW

    source = encode(request(kind="SIMULATION")) if valid else b"{}"
    output = io.BytesIO()
    stdout = io.TextIOWrapper(output, encoding="cp1252", write_through=True)
    monkeypatch.setattr(cli, "datetime", SimpleNamespace(now=now))
    monkeypatch.setattr(cli.sys, "stdin", SimpleNamespace(buffer=Input(source)))
    monkeypatch.setattr(cli.sys, "stdout", stdout)
    monkeypatch.setattr(cli.sys, "argv", ["review_observer_import"] + (["--html"] if html else []))
    assert cli.main() == (0 if valid else 2)
    assert calls == [timezone.utc]
    emitted = output.getvalue().decode("utf-8")
    if html:
        assert ('<h2 id="review">RANKED' if valid else '<h2 id="review">HOLD') in emitted
        assert "script-src 'none'" in emitted
        assert "A11oy Observer · offline evidence review" in emitted
    else:
        assert json.loads(emitted)["result"]["status"] == ("RANKED" if valid else "HOLD")
