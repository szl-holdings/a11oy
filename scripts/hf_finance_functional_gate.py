# SPDX-License-Identifier: Apache-2.0
"""Bounded public witness for the existing Finance projection, never a writer.

The gate runs the emitted projection's exact validators against actual public
responses. Synthetic calculations and live Coinbase observations are separate.
Only fixed public requests are sent; no credentials or receipt signing occurs.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import urllib.error
import urllib.request

ORIGIN = "https://szlholdings-finance.hf.space"
PREFIX = "/api/finance/"
CANONICAL_ORIGIN = "https://szlholdings-a11oy.hf.space"
CANONICAL_PREFIX = "/api/a11oy/v1/finance/"
MAX_BYTES = 4_000_000
# Caller-supplied SAMPLE records: deterministic and provider-free.
RESEARCH_SAMPLE = {"as_of": "2024-12-31", "records": [
    {"entity": "A", "period": 2023, "value": 0, "state": "observed", "available_at": "2024-01-01"},
    {"entity": "B", "period": 2023, "value": 0, "state": "suppressed", "available_at": "2024-01-01"}]}


def _projection():
    spec = importlib.util.spec_from_file_location(
        "finance_functional_contract", Path(__file__).with_name("hf_finance_read_proxy.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _read(origin, path, content):
    """One size-bounded public request, no environment proxies or redirects."""
    request = urllib.request.Request(origin + path,
        data=None if content is None else json.dumps(content, allow_nan=False).encode(),
        headers={"Accept": "application/json", "Accept-Encoding": "identity",
                 "Content-Type": "application/json", "Cache-Control": "no-cache",
                 "User-Agent": "SZL-Finance-Functional-Witness/1.0"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    try:
        response = opener.open(request, timeout=20)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        mime = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if mime != "application/json" or response.headers.get("Content-Encoding", "identity") not in ("", "identity"):
            raise ValueError("NON_JSON_OR_ENCODED_RESPONSE")
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("RESPONSE_TOO_LARGE")
        return response.status, raw, {key.lower(): value for key, value in response.headers.items()}


def read(path, content=None):
    status, raw, _ = _read(ORIGIN, path, content)
    return status, raw


def read_canonical(path, content=None):
    """The same bounded request against canonical A11oy; headers carry the contract."""
    return _read(CANONICAL_ORIGIN, path, content)


def _prober(validators, request, prefix, *, canonical):
    rows = []

    def probe(label, kind, *, content=None, query=(), operation=None, check=None, path=None, validate=None):
        target = path or prefix + (kind if canonical else kind.replace("analytics/v2/", "v2/", 1))
        if query:
            from urllib.parse import urlencode
            target += "?" + urlencode(query)
        row = {"label": label, "path": target, "method": "GET" if content is None else "POST", "accepted": False}
        body = None
        try:
            reply = request(target, content)
            status, raw = reply[0], reply[1]
            row.update(http_status=status, response_sha256=hashlib.sha256(raw).hexdigest(), response_bytes=len(raw))
            headers = reply[2] if canonical else {}
            if canonical:
                # The projection refuses any canonical answer without a supported contract.
                failure = validators["_finance_contract_error"](headers)
                if failure:
                    row["response_error"] = failure[0]["error"]
                    raise ValueError("CONTRACT_NOT_SUPPORTED")
            body = validators["_finance_json"](raw)
            if not isinstance(body, dict):
                raise ValueError("NON_OBJECT_RESPONSE")
            if body.get("error"):
                error = body["error"]
                row["response_error"] = error if isinstance(error, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", error) else "UNEXPECTED_ERROR"
                boundary = body.get("upstream_response")
                if isinstance(boundary, dict):
                    status_code = boundary.get("http_status")
                    media = boundary.get("media_type")
                    host = boundary.get("redirect_host")
                    if type(status_code) is int and 100 <= status_code <= 599:
                        row["upstream_http_status"] = status_code
                    if media in ("JSON", "HTML", "TEXT", "OTHER", "MISSING"):
                        row["upstream_media_type"] = media
                    if isinstance(host, str) and len(host) <= 253 and re.fullmatch(r"[a-z0-9.-]+", host):
                        row["upstream_redirect_host"] = host
            if validate is not None:
                validate(status, body, headers)
            elif kind.startswith("signed-prices/"):
                if status != 200:
                    raise ValueError("SIGNED_PRICE_UNAVAILABLE")
                validators["_finance_check_signed"](body, kind)
            elif operation:
                if status != 200:
                    raise ValueError("ANALYTICS_UNAVAILABLE")
                validators["_finance_check_analytics"](body, kind, list(query), row["method"])
            elif kind == "providers":
                validators["_finance_validate"](body, kind, status)
            if check is not None and not check(status, body):
                raise ValueError("FUNCTIONAL_RESULT_MISMATCH")
            row["accepted"] = True
            row["source_revision"] = body.get("source_revision")
        except Exception as exc:
            # No exception messages, URLs or arbitrary upstream response bodies;
            # only this module's and the validators' fixed reason codes.
            row["failure_type"] = type(exc).__name__
            if re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", str(exc)):
                row["failure_code"] = str(exc)
        rows.append(row)
        return body if row["accepted"] else None

    return probe, rows


def _data_probes(probe, rows):
    """Routes both surfaces serve: one list, so the pre-write sweep and the
    post-write gate exercise the same answers through the same validators."""
    probe("providers", "providers", check=lambda status, body: len(body.get("sources", [])) == 16)
    fixture = probe("synthetic-signals", "analytics/v2/signals/AAPL", operation="signals", query=(("origin", "fixture"),))
    probe("synthetic-quote", "analytics/v2/quote/AAPL", operation="quote", query=(("origin", "fixture"),))
    probe("caller-portfolio", "analytics/v2/portfolio", operation="portfolio",
          content={"holdings": {"TEST": [100, 110, 99]}, "periods_per_year": 252},
          check=lambda status, body: abs(body["result"]["per_asset"]["TEST"]["max_drawdown"] + .1) < 1e-12
              and body.get("inputs", {}).get("truth_label") == "UNVERIFIED")
    if fixture is not None:
        probe("valid-receipt", "analytics/v2/receipts/verify", operation="receipt-verification", content=fixture,
              check=lambda status, body: body["result"].get("verified") is True
                  and body["result"].get("state") == "INTEGRITY_VALID"
                  and body["result"].get("authenticity_established") is False)
        changed = deepcopy(fixture)
        changed["result"]["verdict"] = "TAMPERED"
        probe("tampered-receipt", "analytics/v2/receipts/verify", operation="receipt-verification", content=changed,
              check=lambda status, body: body["result"].get("verified") is False
                  and body["result"].get("state") == "INVALID"
                  and body["result"].get("authenticity_established") is False)
    else:
        rows.extend({"label": label, "accepted": False, "failure_type": "FixtureUnavailable"}
                    for label in ("valid-receipt", "tampered-receipt"))
    live = probe("coinbase-signals", "analytics/v2/signals/BTC-USD", operation="signals")
    signed = probe("signed-price-btc", "signed-prices/BTC",
        check=lambda status, body: body.get("state") == "REVIEW")
    probe("signed-price-model", "signed-prices/model",
        check=lambda status, body: body["result"]["cases"]["correlated_venue_cluster"]["reference_price_usd"] == "100.5")
    return fixture, live, signed


def observe_finance(revision, *, request=read):
    if not isinstance(revision, str) or re.fullmatch(r"[0-9a-f]{40}", revision) is None or revision == "0" * 40:
        raise ValueError("Finance functional gate requires an exact source revision")
    validators = _projection().validation_namespace(revision)
    probe, rows = _prober(validators, request, PREFIX, canonical=False)
    probe("source-binding", "build", path="/api/build-info",
          check=lambda status, body: status == 200 and body.get("schema") == "szl.build-info/v1"
              and body.get("source_repository") == "szl-holdings/a11oy"
              and body.get("source_revision") == revision and body.get("hf_repository") == "SZLHOLDINGS/finance")
    probe("version", "version", path="/version",
          check=lambda status, body: status == 200 and body.get("schema") == "szl.finance.version/v1"
              and body.get("version") == revision and body.get("source_revision") == revision
              and body.get("source_repository") == "szl-holdings/a11oy"
              and body.get("hf_repository") == "SZLHOLDINGS/finance"
              and "model_revision" in body and body["model_revision"] is None
              and body.get("execution_enabled") is False)
    fixture, live, signed = _data_probes(probe, rows)
    probe("private-source-denied", "observations/fred-series", query=(("series_id", "GDP"),),
          check=lambda status, body: status == 403 and body.get("error") == "USE_PRIVATE_CANONICAL_SOURCE_ENDPOINT"
              and body.get("execution_enabled") is False and "data" not in body)
    return {"schema": "szl.finance.public-functional-witness/v1",
            "observed_at": datetime.now(timezone.utc).isoformat(), "source_revision": revision,
            "complete": all(row["accepted"] for row in rows), "probes": rows,
            "synthetic_fixture_verified": fixture is not None, "live_coinbase_verified": live is not None,
            "signed_price_review_verified": signed is not None,
            "execution_enabled": False, "receipt_authenticity_established": False,
            "credentials_sent": False, "provider_mutations": 0}


def observe_canonical(revision, *, request=read_canonical):
    """Pre-write witness: would a projection built from ``revision`` accept what
    the running canonical A11oy serves, on every route the projection forwards?

    Each answer must declare a supported contract and pass the emitted
    validators; the contract must also declare the exact analytics and
    signed-price components this build pins. Read-only, credential-free.
    """
    if not isinstance(revision, str) or re.fullmatch(r"[0-9a-f]{40}", revision) is None or revision == "0" * 40:
        raise ValueError("canonical compatibility witness requires an exact projection revision")
    validators = _projection().validation_namespace(revision)
    probe, rows = _prober(validators, request, CANONICAL_PREFIX, canonical=True)
    header = validators["_FINANCE_CONTRACT"]["header"]

    def contract(status, body, headers):
        if status != 200:
            raise ValueError("CONTRACT_UNAVAILABLE")
        validators["_finance_check_contract"](body, validators["_finance_served_versions"](headers.get(header)))
        if body["components"] != {"analytics": validators["_FINANCE_COMPONENT"],
                                  "signed_price": validators["_FINANCE_SIGNED_COMPONENT"]}:
            raise ValueError("CANONICAL_COMPONENT_MISMATCH")

    def source_view(kind):
        return lambda status, body, headers: validators["_finance_validate"](body, kind, status)

    def research(status, body, headers):
        if status != 200:
            raise ValueError("RESEARCH_UNAVAILABLE")
        validators["_finance_check_research"](body, deepcopy(RESEARCH_SAMPLE))

    declared = probe("contract", "contract", validate=contract)
    _data_probes(probe, rows)
    probe("overview", "overview", validate=source_view("overview"))
    probe("public-observation", "observations/coinbase-ticker", query=(("product", "BTC-USD"),),
          validate=source_view("observations/coinbase-ticker"))
    probe("receipt-capability", "analytics/v2/receipts", operation="receipts")
    probe("receipt-verification-contract", "analytics/v2/receipts/verify", operation="receipt-verification-contract")
    probe("research-audit", "research/audit", content=RESEARCH_SAMPLE, validate=research)
    return {"schema": "szl.finance.canonical-compatibility-witness/v1",
            "observed_at": datetime.now(timezone.utc).isoformat(), "projection_source_revision": revision,
            "canonical_origin": CANONICAL_ORIGIN, "complete": all(row["accepted"] for row in rows), "probes": rows,
            "served_versions": declared["versions"] if declared else None,
            "canonical_runtime_revisions": sorted({row["source_revision"] for row in rows
                                                   if row["accepted"] and isinstance(row.get("source_revision"), str)}),
            "canonical_runtime_revision_role": "EVIDENCE_NOT_COMPATIBILITY_KEY",
            "execution_enabled": False, "credentials_sent": False, "provider_mutations": 0}