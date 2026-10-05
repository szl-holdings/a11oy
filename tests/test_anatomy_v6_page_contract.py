#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Static contracts for the additive, summary-only Anatomy v6 evidence page.

These assertions inspect source, not browser execution or hosted runtime. They
do not establish deployment, model evaluation, or independent evidence replay.
"""

import re
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "anatomy-v6.html"


class _PageStructure(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.elements: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.elements.append((tag, dict(attrs)))


def _read() -> str:
    return PAGE.read_text(encoding="utf-8")


def _script() -> str:
    return _read().split("<script>", 1)[1].split("</script>", 1)[0]


def _structure() -> _PageStructure:
    structure = _PageStructure()
    structure.feed(_read())
    return structure


def test_v6_is_an_additive_evidence_page_with_its_own_canonical_path() -> None:
    html = _read()
    assert "<title>Anatomy v6 evidence view | a11oy</title>" in html
    assert '<link rel="canonical" href="https://a-11-oy.com/anatomy-v6">' in html
    assert "additive A11oy evidence view" in html
    assert "canonical Anatomy companion" in html
    assert "is already v7" in html
    assert "Canonical Anatomy · v7" in html
    assert "does not replace, rename, or downgrade" in html
    assert "not a runtime probe" in html


def test_page_uses_existing_self_hosted_kanchay_tokens_without_raw_palette() -> None:
    html = _read()
    structure = _structure()
    stylesheets = [
        attrs.get("href")
        for tag, attrs in structure.elements
        if tag == "link" and attrs.get("rel") == "stylesheet"
    ]
    assert stylesheets == ["/assets/szl/szl-design-system.css"]
    assert html.index("/assets/szl/szl-design-system.css") < html.index("<style>")
    css = html.split("<style>", 1)[1].split("</style>", 1)[0]
    assert "gradient(" not in css
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\s*\(", css)
    for font in re.findall(r"font-family:\s*([^;]+)", css):
        assert font.strip().startswith("var(")
    for token in (
        "--font-body",
        "--font-mono",
        "--surface",
        "--border",
        "--text",
        "--accent",
    ):
        assert f"var({token})" in css
    assert css.count("var(--accent)") == 1
    assert "@font-face" not in html
    assert not any(
        tag == "script" and attrs.get("src") for tag, attrs in structure.elements
    )


def test_source_runtime_evaluation_and_authority_are_separate_semantic_lanes() -> None:
    html = _read()
    for name in ("source", "runtime", "eval", "authority"):
        assert f'aria-labelledby="{name}-title"' in html
        assert f'id="{name}-title"' in html
    for boundary in (
        "does not establish deployment or provider publication",
        "Endpoint reachability is not model quality",
        "No held-out evaluation is supplied",
        "Receipt and graph counts are not model scores",
        "An internally consistent chain is not an independent signature check",
        "Source ≠ runtime ≠ evaluation ≠ authorization",
    ):
        assert boundary in html


def test_all_count_fields_start_unavailable_not_at_sample_values() -> None:
    html = _read()
    expected_ids = {
        "receipts-checked",
        "proposed-demotions",
        "broken-receipts",
        "overlay-nodes",
        "reinforced-edges",
    }
    fields = {
        attrs["id"]
        for tag, attrs in _structure().elements
        if tag == "dd" and "data-evidence-count" in attrs
    }
    assert fields == expected_ids
    for field_id in expected_ids:
        assert f'id="{field_id}" data-evidence-count>UNAVAILABLE</dd>' in html
    assert 'id="chain-state">UNAVAILABLE' in html
    assert 'id="evidence-scope">UNAVAILABLE' in html
    assert 'id="computed-at">UNAVAILABLE' in html
    assert "no sample values are substituted" in html


def test_only_one_same_origin_get_is_used_without_credentials_or_writes() -> None:
    script = _script()
    assert 'const ENDPOINT = "/api/a11oy/v1/anatomy/evidence";' in script
    assert script.count("fetch(") == 1
    for option in (
        'method: "GET"',
        'mode: "same-origin"',
        'credentials: "omit"',
        'cache: "no-store"',
        'redirect: "error"',
    ):
        assert option in script
    assert "https://" not in script and "http://" not in script
    for mechanism in (
        "localStorage",
        "sessionStorage",
        "indexedDB",
        "document.cookie",
        "sendBeacon",
        "WebSocket",
        "EventSource",
        "setInterval",
        'method: "POST"',
    ):
        assert mechanism not in script
    assert not any(tag == "form" for tag, _ in _structure().elements)


def test_exact_schema_and_read_only_authority_are_checked_before_rendering() -> None:
    script = _script()
    assert 'const EXPECTED_SCHEMA = "szl.anatomy.evidence/v6";' in script
    assert "Object.keys(value).length === keys.length" in script
    assert "Object.prototype.hasOwnProperty.call(value, key)" in script
    assert "!Array.isArray(value)" in script
    for check in (
        "data.schema !== EXPECTED_SCHEMA",
        'data.evidence_class !== "MODELED"',
        'data.mode !== "READ_ONLY"',
        'data.content_access !== "SUMMARY_ONLY"',
        "data.storage_writes !== 0",
        "data.receipt_minted_on_get !== false",
        "data.model_invoked !== false",
        "data.gradient_training !== false",
        'hasExactKeys(data.authority, ["training", "promotion", "execution", "provider_write"])',
        'Object.values(data.authority).every((value) => value === "NONE")',
    ):
        assert check in script
    assert script.index("if (!validateEvidence(data))") < script.index(
        "renderEvidence(data);", script.index("const data = JSON.parse(raw)")
    )


def test_counts_booleans_text_and_response_shape_are_strictly_validated() -> None:
    script = _script()
    assert "Number.isSafeInteger(value) && value >= 0" in script
    assert 'typeof data.audit.chain_ok !== "boolean"' in script
    for path in (
        "data.audit.receipts_checked",
        "data.audit.proposed_demotions",
        "data.audit.broken_receipts",
        "data.overlay.nodes",
        "data.overlay.reinforced_edges",
    ):
        assert f"isCount({path})" in script
    assert 'hasExactKeys(data.overlay, ["nodes", "reinforced_edges"])' in script
    assert "isBoundedText(data.scope, 512)" in script
    assert "isBoundedText(data.computed_at, 80)" in script
    assert "Number.isFinite(Date.parse(data.computed_at))" in script
    assert 'contentType !== "application/json"' in script
    assert "raw.length > MAX_RESPONSE_CHARS" in script


def test_rendering_uses_only_text_content_and_fixed_summary_fields() -> None:
    script = _script()
    assert "document.getElementById(id).textContent = String(value);" in script
    for sink in (
        "innerHTML",
        "outerHTML",
        "insertAdjacentHTML",
        "document.write",
        "eval(",
        "new Function",
    ):
        assert sink not in script
    render = script.split("function renderEvidence(data) {", 1)[1].split(
        "async function refreshEvidence()", 1
    )[0]
    displayed_paths = set(re.findall(r"data\.([a-z_]+(?:\.[a-z_]+)?)", render))
    assert displayed_paths == {
        "audit.receipts_checked",
        "audit.proposed_demotions",
        "audit.broken_receipts",
        "audit.chain_ok",
        "overlay.nodes",
        "overlay.reinforced_edges",
        "scope",
        "computed_at",
    }
    assert "JSON.stringify" not in script
    assert (
        "No node identifiers, private queries, receipt bodies, or source text"
        in _read()
    )


def test_refresh_and_failure_clear_counts_instead_of_substituting_evidence() -> None:
    script = _script()
    refresh = script.split("async function refreshEvidence() {", 1)[1]
    assert refresh.index("clearEvidence();") < refresh.index("await fetch(ENDPOINT")
    failure = refresh.split("} catch (error) {", 1)[1].split("} finally {", 1)[0]
    assert "clearEvidence();" in failure
    assert 'setText("request-state", "UNAVAILABLE")' in failure
    assert "No counts or stronger evidence state were substituted" in failure
    assert "controller.abort(), 8000" in script
    assert 'summary.setAttribute("aria-busy", "true")' in script
    assert 'summary.setAttribute("aria-busy", "false")' in script
    assert "refreshButton.disabled = true" in script
    assert "refreshButton.disabled = false" in script
    assert 'refreshButton.addEventListener("click", refreshEvidence)' in script
    assert 'countIds.forEach((id) => setText(id, "UNAVAILABLE"))' in script


def test_navigation_accessibility_and_small_screen_contracts_are_present() -> None:
    html = _read()
    structure = _structure()
    assert '<html lang="en">' in html
    assert '<main id="main"' in html
    assert 'href="#main">Skip to evidence' in html
    assert 'role="status" aria-live="polite" aria-atomic="true"' in html
    assert 'aria-describedby="refresh-note"' in html
    assert "<noscript>" in html
    assert "@media (max-width: 960px)" in html
    assert "@media (max-width: 640px)" in html
    assert "@media (prefers-reduced-motion: reduce)" in html
    hrefs = {attrs.get("href") for tag, attrs in structure.elements if tag == "a"}
    assert {
        "/anatomy-v5",
        "/brain",
        "/api/a11oy/v1/second-brain",
        "/ecosystem",
        "https://betterwithage-anatomy.hf.space",
        "https://a11oy.net",
    } <= hrefs
    for tag, attrs in structure.elements:
        if tag == "a" and attrs.get("target") == "_blank":
            assert set((attrs.get("rel") or "").split()) >= {"noopener", "noreferrer"}
    ids = [attrs["id"] for _, attrs in structure.elements if "id" in attrs]
    assert len(ids) == len(set(ids))
