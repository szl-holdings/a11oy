#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Execute the served Frontier renderer against readiness contract edge cases."""

import json
import shutil
import subprocess
from html.parser import HTMLParser

import a11oy_frontier_page as frontier


SCHEMA = "szl.frontier.capability-readiness.v1"


def _module_script() -> str:
    return frontier._page_html("a11oy").split('<script type="module">', 1)[1].split("</script>", 1)[0]


def _node(expression: str, payload):
    node = shutil.which("node")
    assert node, "Node is required to execute the served Frontier renderer"
    script = _module_script()
    helpers = script[script.index("const LABEL_CLASS ="):script.index("// ---- three.js")]
    renderers = script[script.index("function provHtml("):script.index("function fail(")]
    program = (
        "const MANIFEST_EP = '/api/a11oy/v1/frontier/manifest';\n"
        + helpers + renderers
        + "\nconst payload = " + json.dumps(payload) + ";\n"
        + "process.stdout.write(JSON.stringify(" + expression + "));\n"
    )
    result = subprocess.run(
        [node], input=program, text=True, encoding="utf-8",
        capture_output=True, timeout=15, check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _contract(**changes):
    result = {
        "schema": SCHEMA,
        "state": "READY",
        "ready": True,
        "predicate": "signed receipt exists and its signature verifies",
        "reasons": [],
        "source_reachable": True,
    }
    result.update(changes)
    return result


def _tile(contract):
    return {
        "name": "Receipt ledger",
        "category": "provenance",
        "label": "MEASURED",
        "status": "source reports healthy",
        "source_ok": True,
        "operational_evidence": {"predicate": "legacy evidence", "satisfied": True},
        "operational_readiness": contract,
        "provenance": {"inspect": "/api/a11oy/v1/provenance/chain"},
    }


def _cards(contracts):
    return _node("payload.map(tileCard)", [_tile(value) for value in contracts])


def test_ready_card_renders_the_backend_decision_and_evidence_pointer():
    card = _cards([_contract()])[0]
    assert 'data-readiness-state="READY"' in card
    assert "<dt>Source availability (reported)</dt><dd>AVAILABLE</dd>" in card
    assert "<dt>Operational readiness</dt><dd>READY</dd>" in card
    assert "signed receipt exists and its signature verifies" in card
    assert "No unmet conditions reported." in card
    assert "Evidence pointers" in card
    assert 'href="/api/a11oy/v1/provenance/chain"' in card
    assert "proof" not in card.lower()


def test_available_source_does_not_upgrade_not_ready_or_hide_blockers():
    reasons = ["signature_unverified", "persistent_store_unavailable", "chain_empty"]
    card = _cards([_contract(state="NOT_READY", ready=False, reasons=reasons)])[0]
    assert "<dt>Source availability (reported)</dt><dd>AVAILABLE</dd>" in card
    assert "<dt>Operational readiness</dt><dd>NOT_READY</dd>" in card
    assert 'data-readiness-state="READY"' not in card
    assert "source reports healthy" in card
    assert "Signature unverified" in card
    for reason in reasons:
        assert "<code>" + reason + "</code>" in card
    assert card.count("<li>") == len(reasons)


def test_missing_nullable_predicate_is_preserved_for_not_ready():
    card = _cards([_contract(
        state="NOT_READY", ready=False, predicate=None, source_reachable=False,
        reasons=["missing_positive_operational_evidence", "source_unavailable"],
    )])[0]
    assert "<dt>Source availability (reported)</dt><dd>UNAVAILABLE</dd>" in card
    assert "<dt>Operational readiness</dt><dd>NOT_READY</dd>" in card
    assert "UNAVAILABLE — no predicate supplied." in card
    assert "<code>missing_positive_operational_evidence</code>" in card


def test_malformed_unsupported_or_contradictory_contracts_fail_unavailable():
    invalid = [
        None, [], "READY", {}, _contract(schema="szl.frontier.capability-readiness.v2"),
        _contract(state="UNKNOWN"), _contract(ready="true"),
        _contract(source_reachable=1), _contract(reasons="none"),
        _contract(reasons=[12]), _contract(reasons=[""]), _contract(reasons=["  "]),
        _contract(predicate=""), _contract(predicate="  "), _contract(predicate=7),
        _contract(state="NOT_READY"), _contract(ready=False),
        _contract(reasons=["signature_unverified"]),
        _contract(predicate=None), _contract(source_reachable=False),
        _contract(state="NOT_READY", ready=False, reasons=[]),
    ]
    for key in _contract():
        missing = _contract()
        del missing[key]
        invalid.append(missing)
    cards = _cards(invalid)
    assert len(cards) == len(invalid)
    for card in cards:
        assert 'data-readiness-state="UNAVAILABLE"' in card
        assert "<dt>Operational readiness</dt><dd>UNAVAILABLE</dd>" in card
        assert "<dt>Source availability (reported)</dt><dd>UNAVAILABLE</dd>" in card
        assert "Readiness contract missing, unsupported, or inconsistent." in card
        assert 'href="/api/a11oy/v1/frontier/manifest"' in card
        assert "<dd>READY</dd>" not in card


def test_missing_projection_never_infers_ready_from_legacy_positive_fields():
    tile = _tile(_contract())
    del tile["operational_readiness"]
    card = _node("tileCard(payload)", tile)
    assert 'data-readiness-state="UNAVAILABLE"' in card
    assert "<dd>READY</dd>" not in card
    assert "MEASURED" in card
    assert "source reports healthy" in card


def test_all_reason_codes_and_long_predicates_remain_inspectable():
    predicate = "receipt-" + "x" * 16000
    reasons = ["condition_" + str(index) for index in range(80)] + ["dependency_" + "y" * 800]
    card = _cards([_contract(
        state="NOT_READY", ready=False, predicate=predicate, reasons=reasons,
    )])[0]
    assert predicate in card
    assert card.count("<li>") == len(reasons)
    for reason in reasons:
        assert "<code>" + reason + "</code>" in card
    assert 'class="readiness-predicate" role="region" tabindex="0"' in card
    assert 'aria-label="Readiness predicate for Receipt ledger"' in card


def test_untrusted_predicates_reasons_and_pointers_are_escaped_in_rendered_html():
    hostile = '<img src=x onerror="alert(1)"> & <script>alert(2)</script>'
    tile = _tile(_contract(
        state="NOT_READY", ready=False, predicate=hostile, reasons=[hostile],
    ))
    tile["name"] = hostile
    tile["provenance"] = {"inspect": "/api/inspect?q=" + hostile, "digest": hostile}
    card = _node("tileCard(payload)", tile)
    assert "<img" not in card
    assert "<script>" not in card
    assert "&lt;img" in card
    assert "&lt;script&gt;" in card
    assert "onerror=&quot;" in card
    assert "&amp;" in card
    assert "<dt>Operational readiness</dt><dd>NOT_READY</dd>" in card


class _ParsedProvenance(HTMLParser):
    def __init__(self, markup):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.links = []
        self.text = []
        self.feed(markup)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        if tag == "a":
            self.links.append(dict(attrs))

    def handle_data(self, data):
        self.text.append(data)


def test_descriptive_and_templated_provenance_references_remain_text():
    references = [
        "/api/a11oy/v1/immune/verdict (REAL fail-closed gate) + the MEASURED energy joule-truth path",
        "/api/a11oy/v1/materials/certify (PAC-Bayes/Lean evidence must retain the status reported by that dependency)",
        "/api/a11oy/v1/provenance/receipts/{receipt_id}",
        "/api/a11oy/v1/provenance/receipts/receipt_id}",
        "/api/a11oy/v1/provenance/receipts?filter={pending}&scope=all",
    ]
    rendered = _node("payload.map(value => provHtml({inspect: value}))", references)
    for reference, markup in zip(references, rendered):
        parsed = _ParsedProvenance(markup)
        assert parsed.links == [], repr(reference)
        assert parsed.tags == ["div", "span"]
        assert "".join(parsed.text) == "inspect: " + reference


def test_raw_whitespace_and_ascii_controls_never_become_provenance_links():
    separators = [chr(value) for value in range(32)] + [
        "\x7f", " ", "\u00a0", "\u2028", "\u2029",
    ]
    references = [
        "/api/a11oy/v1/provenance/" + separator + "receipt"
        for separator in separators
    ] + [
        " /api/a11oy/v1/provenance/chain",
        "/api/a11oy/v1/provenance/chain ",
    ]
    rendered = _node("payload.map(value => provHtml({inspect: value}))", references)
    for reference, markup in zip(references, rendered):
        parsed = _ParsedProvenance(markup)
        assert parsed.links == [], repr(reference)
        assert "".join(parsed.text) == "inspect: " + reference


def test_concrete_api_and_orbital_references_preserve_usable_links():
    references = [
        "/api/a11oy/v1/provenance/chain",
        "/api/a11oy/v1/provenance/chain?limit=5&order=desc",
        "/api/a11oy/v1/provenance/receipts/receipt%20name",
        "/api/a11oy/v1/provenance/receipts?q=receipt%20name&scope=all",
        "/orbital",
    ]
    rendered = _node("payload.map(value => provHtml({inspect: value}))", references)
    for reference, markup in zip(references, rendered):
        parsed = _ParsedProvenance(markup)
        assert parsed.links == [{"href": reference}], repr(reference)
        assert parsed.tags == ["div", "span", "a"]
        assert "".join(parsed.text) == "inspect: " + reference


def test_hostile_provenance_stays_escaped_in_labels_text_and_link_attributes():
    label = '<img src=x onerror="alert(1)">'
    references = [
        '/api/inspect?q="><img/src=x/onerror=alert(1)>&owner=\'reviewer\'',
        '/api/inspect explanatory <script>alert("x")</script> & \'note\'',
    ]
    rendered = _node("payload.map(provHtml)", [{label: value} for value in references])
    for index, (reference, markup) in enumerate(zip(references, rendered)):
        parsed = _ParsedProvenance(markup)
        assert "<img" not in markup
        assert "<script" not in markup
        assert "&lt;" in markup and "&quot;" in markup and "&amp;" in markup
        assert parsed.tags == ["div", "span"] + (["a"] if index == 0 else [])
        assert parsed.links == ([{"href": reference}] if index == 0 else [])
        assert "".join(parsed.text) == label + ": " + reference


def test_manifest_timestamps_are_labeled_without_implying_source_freshness():
    composed = "2026-11-16T23:40:01+00:00"
    cached = "2026-11-16T23:40:02Z"
    rendered = _node("payload.map(manifestTimeText)", [
        {"timestamp_utc": composed, "cached_at": cached},
        {},
        {"timestamp_utc": {"unexpected": True}, "cached_at": "not-a-date"},
    ])
    assert "manifest composition time: " + composed in rendered[0]
    assert "manifest cache time: " + cached in rendered[0]
    for text in rendered:
        assert "(not source freshness)" in text
    for text in rendered[1:]:
        assert "manifest composition time: UNAVAILABLE" in text
        assert "manifest cache time: UNAVAILABLE" in text


def test_readiness_layout_wraps_and_bounds_height_without_dropping_evidence():
    html = frontier._page_html("a11oy")
    assert ".readiness-predicate" in html
    assert "max-height:8rem; overflow:auto" in html
    assert "white-space:pre-wrap; overflow-wrap:anywhere" in html
    assert ".readiness-predicate:focus-visible" in html
    assert ".readiness-reasons code" in html
    assert "Source availability is backend-reported, not an independent network probe." in html
    assert "link to the proof" not in html
    assert "straight to the proof" not in html


def test_complete_served_module_is_valid_javascript():
    node = shutil.which("node")
    assert node, "Node is required to validate the served Frontier module"
    result = subprocess.run(
        [node, "--input-type=module", "--check"], input=_module_script(),
        text=True, encoding="utf-8", capture_output=True, timeout=15, check=False,
    )
    assert result.returncode == 0, result.stderr
