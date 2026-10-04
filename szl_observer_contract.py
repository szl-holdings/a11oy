#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Bounded import/report contract for services/provenance, with no network or writes.

This is an offline adapter, not a registered A11oy route. Freshness uses the
adapter's clock, never a caller-supplied generated_at. Hash binding is not trust.
"""

import base64
import binascii
from datetime import datetime, timezone
from html import escape
import json

from szl_observer_kernel import DOMAIN_PROFILES, EvidenceInput, review_series


REQUEST_SCHEMA = "szl.observer-import/v1"
REPORT_SCHEMA = "szl.observer-report/v1"
MAX_REQUEST_BYTES = 2 * 1024 * 1024
MAX_ENCODED_PAYLOAD = 5464  # canonical base64 length for at most 4096 raw bytes
_REQUEST_KEYS = frozenset({"schema", "domain", "metric", "unit", "scope", "records"})
_RECORD_KEYS = frozenset({"payload_base64", "evidence_uri", "evidence_digest", "retrieved_at", "kind"})


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("non-finite JSON constant")


def _held(reason):
    return {
        "status": "HOLD", "reason": reason, "score": None, "label": "UNAVAILABLE",
        "decision": "REVIEW_ONLY", "probability": None, "source_authenticity": "NOT_VERIFIED",
        "scientific_validation": "NOT_EVALUATED", "external_writes": "DISABLED",
    }


def capabilities():
    """Describe implemented contracts without pretending their connectors exist."""
    return {
        "schema": "szl.observer-capabilities/v1", "registration": "NOT_REGISTERED",
        "operation": "OFFLINE_IMPORT_REVIEW", "external_writes": "DISABLED",
        "request_schema": REQUEST_SCHEMA, "report_schema": REPORT_SCHEMA,
        "max_request_bytes": MAX_REQUEST_BYTES, "max_records": 256,
        "max_payload_bytes": 4096, "freshness_seconds": 900,
        "domains": [{"id": key, "workflow": value[0], "limit": value[1],
                     "connector": "NOT_CONNECTED"} for key, value in DOMAIN_PROFILES.items()],
    }


def evaluate_import(raw, *, clock=None):
    """Review exact imported bytes. ``clock`` is internal test injection, not input.

    HTTP integration must supply bounded bytes after its own authentication and
    transport admission. It must not expose clock injection or accept redirects,
    URLs to fetch, commands, or a caller-defined freshness policy.
    """
    now = datetime.now(timezone.utc) if clock is None else clock()
    result = None
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_REQUEST_BYTES:
        result = _held("UNBOUNDED_OR_EMPTY_IMPORT")
    else:
        try:
            item = json.loads(raw.decode("utf-8"), object_pairs_hook=_object,
                              parse_constant=_reject_constant)
            if not isinstance(item, dict) or set(item) != _REQUEST_KEYS or item["schema"] != REQUEST_SCHEMA:
                raise ValueError("invalid request schema")
            if not isinstance(item["records"], list) or not 6 <= len(item["records"]) <= 256:
                raise ValueError("invalid record count")
            records = []
            for row in item["records"]:
                if not isinstance(row, dict) or set(row) != _RECORD_KEYS:
                    raise ValueError("invalid record schema")
                encoded = row["payload_base64"]
                if not isinstance(encoded, str) or not 1 <= len(encoded) <= MAX_ENCODED_PAYLOAD:
                    raise ValueError("unbounded encoded payload")
                payload = base64.b64decode(encoded, validate=True)
                if base64.b64encode(payload).decode("ascii") != encoded:
                    raise ValueError("noncanonical base64")
                stamp = row["retrieved_at"]
                if not isinstance(stamp, str) or not 1 <= len(stamp) <= 64:
                    raise ValueError("invalid retrieval clock")
                retrieved = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                records.append(EvidenceInput(payload, row["evidence_uri"], row["evidence_digest"],
                                             retrieved, row["kind"]))
            result = review_series(records, domain=item["domain"], metric=item["metric"],
                                   unit=item["unit"], scope=item["scope"], now=now)
        except (ValueError, TypeError, UnicodeError, OverflowError, RecursionError, binascii.Error):
            result = _held("INVALID_IMPORT_SCHEMA_OR_ENCODING")
    return {
        "schema": REPORT_SCHEMA, "registration": "NOT_REGISTERED",
        "evaluation_scope": "OFFLINE_DESCRIPTIVE_REVIEW", "result": result,
        "limitations": ["Digest agreement is not source authenticity.",
                        "A rank is not a probability, policy approval, or a safety verdict.",
                        "No live connector, model training, signing, or external action was used."],
    }


def render_import(raw, *, clock=None):
    """Produce a script-free report directly from re-evaluation, not imported claims."""
    report = evaluate_import(raw, clock=clock)
    result = report["result"]
    text = lambda value: escape(str(value), quote=True)
    score = "Not ranked" if result["score"] is None else format(result["score"], ".6g")
    facts = [("Input kind", result["label"]), ("Disposition", result["decision"]),
             ("Source authenticity", result["source_authenticity"]),
             ("Scientific validation", result["scientific_validation"]),
             ("External actions", result["external_writes"])]
    if result["status"] == "RANKED":
        facts += [("Domain", result["domain"]), ("Metric / unit", result["metric"] + " / " + result["unit"]),
                  ("Scope", result["scope"]), ("Source event", result["event_at"]),
                  ("Evaluated at", result["evaluated_at"]), ("History records", result["history_count"])]
    fact_html = "".join("<dt>" + text(key) + "</dt><dd>" + text(value) + "</dd>" for key, value in facts)
    evidence_html = "".join("<li><code>" + text(row["evidence_uri"]) + "</code><br><code>"
                            + text(row["evidence_digest"]) + "</code></li>"
                            for row in result.get("evidence", [])) or "<li>No admitted evidence series.</li>"
    domains_html = "".join("<article><h3>" + text(key.replace("-", " ").title()) + "</h3><p>"
                           + text(value[0]) + "</p><p class='note'>" + text(value[1])
                           + " · connector NOT_CONNECTED</p></article>"
                           for key, value in DOMAIN_PROFILES.items())
    return """<!doctype html>
<html lang="en" data-surface="light"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'self' 'unsafe-inline'; font-src 'self'; script-src 'none'; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'">
<title>A11oy Observer · offline evidence review</title>
<link rel="stylesheet" href="/assets/szl/szl-design-system.css">
<style>
body{margin:0;background:var(--bg);color:var(--text);font-family:var(--font-body);font-size:1rem;line-height:1.6}
main,header,footer{max-width:72rem;margin:auto;padding:1.5rem clamp(1rem,4vw,3rem)}
header,section,footer{border-bottom:1px solid var(--border)}
h1{font-size:clamp(2.2rem,6vw,4.5rem);line-height:1.1;max-width:19ch}
h2{font-size:1.5rem}h3{margin:0}a{color:var(--link);min-height:48px;display:inline-flex;align-items:center;padding:0 .5rem}
a:focus-visible{outline:3px solid var(--focus);outline-offset:4px}
.skip{position:absolute;top:-5rem;background:var(--bg)}.skip:focus{top:0}
.eyebrow,.note{color:var(--text-sub)}.eyebrow{font-family:var(--font-mono)}
section{padding-block:2rem}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,16rem),1fr));gap:1rem}
article{border:1px solid var(--border);border-radius:1rem;padding:1rem;min-width:0}
dl{display:grid;grid-template-columns:minmax(8rem,1fr) minmax(0,3fr);gap:.75rem}dd{margin:0;min-width:0}
code,dd{overflow-wrap:anywhere}code{font-family:var(--font-mono);font-size:.8rem;line-height:1.5}li{margin-block:1rem}
@media(max-width:600px){dl{grid-template-columns:1fr;gap:.25rem}dd{margin-bottom:.75rem}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
</style></head><body><a class="skip" href="#main">Skip to review</a>
<header><a href="https://a-11-oy.com/">A11oy</a> / Observer · local report, not a deployed surface</header>
<main id="main"><p class="eyebrow">OFFLINE_DESCRIPTIVE_REVIEW · NOT_REGISTERED</p>
<h1>Evidence before decisions.</h1><p>Independent SZL review prototype. No live connector or external action.</p>
<p class="note">This is a dated result. Reopening a saved report does not re-evaluate input freshness.</p>
<section aria-labelledby="review"><h2 id="review">""" + text(result["status"]) + " · " + text(score) + """</h2>
<p>""" + text(result["reason"]) + """</p><p class="note">Median/MAD ranking is descriptive, not a calibrated probability. No policy approval is implied.</p>
<dl>""" + fact_html + """</dl></section><section aria-labelledby="evidence"><h2 id="evidence">Source-byte bindings</h2>
<p class="note">These content-addressed identifiers bind the bytes reviewed here; they do not authenticate their producer.</p>
<ul>""" + evidence_html + """</ul></section><section aria-labelledby="verticals"><h2 id="verticals">Seven review contracts</h2>
<p class="note">Shared evidence checks, distinct domain limits. These are not seven qualified products.</p><div class="cards">""" + domains_html + """</div></section>
</main><footer>Hash consistency is not truth. Seismic review is not earthquake prediction or a safety alert. No signature or model qualification is claimed.</footer>
</body></html>"""
