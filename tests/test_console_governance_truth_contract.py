"""Console mutation-authentication and investor truth-boundary contracts.

These checks intentionally inspect the shipped, self-contained console source.  The
console builds several panels at runtime, so a conventional HTML parser would miss
the credential inputs and request call-sites embedded in those panel templates.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _console() -> str:
    return (ROOT / "pages" / "console.html").read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    start_at = source.index(start)
    end_at = source.index(end, start_at)
    return source[start_at:end_at]


def _input_template(source: str, marker: str) -> str:
    """Return enough of a runtime HTML template to inspect one credential field."""

    start_at = source.index(marker)
    return source[start_at : start_at + 500]


def test_governance_helper_uses_one_shot_in_memory_bearer_without_retry_or_leak() -> None:
    console = _console()
    helper = _between(console, "window._a11oyGovernPost=async function", "function esc(s)")
    compact = re.sub(r"\s+", "", helper)

    assert "document.getElementById(inputId)" in helper
    assert "String(input&&input.value||'').trim()" in compact
    assert "if(input)input.value=''" in compact
    assert "'Authorization':'Bearer'+token" in compact
    assert "fetch(p," in compact
    assert "_szlFetch" not in helper
    assert "cache:'no-store'" in compact
    assert "credentials:'same-origin'" in compact
    assert "No mutation was attempted" in helper
    assert "credential required" in helper.lower()
    assert "mutation unavailable" in helper.lower()

    # The DOM field and local variable are blank before network I/O.  The bearer is
    # sent only as a header; it is not copied into the URL or JSON body.
    assert compact.index("if(input)input.value=''") < compact.index("fetch(p,")
    assert compact.index("token=''") < compact.index("fetch(p,")
    fetch_call = compact[compact.index("fetch(p,") :]
    assert "body:JSON.stringify(b||{})" in fetch_call
    assert "JSON.stringify(token" not in fetch_call
    assert "p+token" not in fetch_call and "token+p" not in fetch_call

    # Credential material must never cross into persistence, navigation, or logs.
    forbidden_sinks = (
        "localStorage",
        "sessionStorage",
        "URLSearchParams",
        "location.search",
        "location.hash",
        "location.href",
        "history.pushState",
        "history.replaceState",
        "console.log",
        "console.info",
        "console.warn",
        "console.error",
    )
    for sink in forbidden_sinks:
        assert sink not in helper

    # Also reject a future per-panel shortcut that sends a bearer/token/credential
    # directly to one of those sinks outside the shared helper.
    sensitive = re.compile(r"(?:bearer|credential|\btoken\b)", re.IGNORECASE)
    for line in console.splitlines():
        if not sensitive.search(line):
            continue
        for sink in forbidden_sinks:
            assert sink not in line


def test_every_vertical_govern_mutation_uses_the_credential_bound_direct_helper() -> None:
    console = _console()
    compact = re.sub(r"\s+", "", console)

    # The shared vertical pack, real-estate/finance pack, legal/enterprise pack,
    # and the enterprise incident shortcut must all use the same no-retry helper.
    expected_calls = (
        "window._a11oyGovernPost(VBASE+'/'+vk+'/govern'",
        "window._a11oyGovernPost(DBASE+'/'+tab+'/govern'",
        "window._a11oyGovernPost(DB+'/'+label+'/govern'",
        "window._a11oyGovernPost(DB+'/ent-incident/govern'",
    )
    for call in expected_calls:
        assert call in compact

    expected_input_ids = (
        "'vd-'+vk+'-token'",
        "'deva-'+tab+'-token'",
        "'dg-'+label+'-token'",
        "'ein-token'",
    )
    for input_id in expected_input_ids:
        assert input_id in compact

    # These were the unauthenticated/retrying call paths.  They must not regress.
    forbidden_calls = (
        "window.postJSON(VBASE+'/'+vk+'/govern'",
        "fetch(DBASE+'/'+tab+'/govern'",
        "pj(DB+'/'+label+'/govern'",
        "pj(DB+'/ent-incident/govern'",
    )
    for call in forbidden_calls:
        assert call not in compact

    # Each panel presents a password field whose value is neither pre-filled nor
    # browser-persisted.  The field copy tells the operator it is one-shot.
    for marker in (
        "vd-'+vk+'-token",
        "deva-'+tab+'-token",
        "dg-'+label+'-token",
        "ein-token",
    ):
        fragment = _input_template(console, marker)
        assert 'type="password"' in fragment
        assert 'autocomplete="off"' in fragment
        assert "value=" not in fragment.split(">", 1)[0]

    assert "one-shot" in console.lower()
    assert "never stored" in console.lower()


def test_governed_write_receipt_copy_is_strictly_signature_conditional() -> None:
    console = _console()
    blocks = {
        "vertical": _between(
            console,
            "window._vertGovern = async function",
            "window._vertVerify = async function",
        ),
        "deva": _between(console, "function governPanel(host, tab, presets)", "async function loadLedger"),
        "devb": _between(
            console,
            "window._devbGovern=async function",
            "window._devbVerify=async function",
        ),
        "enterprise incident": _between(console, "window._einGovern=async function", "poll(async function()"),
    }

    for name, block in blocks.items():
        assert re.search(r"\.signed\s*===\s*true", block), name
        assert "unsigned" in block.lower(), name
        assert "digest" in block.lower(), name
        assert "digest only" in block.lower(), name
        assert "signed!==false" not in re.sub(r"\s+", "", block), name
        assert "e.message" in block, name

    # A signature can authenticate returned bytes; digest-only evidence must never
    # inherit a green/signed label merely because a DSSE object is present.
    assert "UNSIGNED" in console
    assert "DIGEST ONLY" in console


def test_anonymous_mesh_arrays_are_unidentified_and_never_observed_by_position() -> None:
    console = _console()
    normalizer = _between(console, "window._meshRows=function(raw)", "window._meshIsUp=function")

    assert "Unidentified capability" in normalizer
    assert "identity_state='unidentified'" in normalizer
    assert "out.observed=false" in normalizer
    assert "observed:false" in normalizer
    assert "row(v,null,i)" in re.sub(r"\s+", "", normalizer)
    assert "CAPS[" not in normalizer
    assert "observed=out.observed===true" in normalizer


def test_investor_surfaces_claim_only_established_slsa_l1() -> None:
    console = _console()
    landing = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")

    assert "SLSA L1" in console
    assert "SLSA L1" in landing

    # These are the historic visible L2 overclaims.  L2 may be described only as
    # unavailable/unestablished, never as emitted, attested, or carried today.
    forbidden_claims = (
        "SLSA L1+L2",
        "SLSA Level 1+2",
        "SLSA L1/L2",
        "L2 .att emitted",
        "L2 build-attested",
        "L2 attested",
        "signed SLSA build-provenance attestation",
    )
    for claim in forbidden_claims:
        assert claim not in console
        assert claim not in landing


def test_chain_and_export_views_label_sample_structure_not_operational_evidence() -> None:
    console = _console()
    landing = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")

    assert "Sample Hash-Link Chain" in console
    assert "SAMPLE · STRUCTURE DEMO" in console
    assert "not an operational command log" in console
    assert "prebuilt SAMPLE envelope" in console
    assert "does not prove an operational decision occurred" in console
    assert "GET is read-only and never mints a new signature" in console
    assert "Prebuilt SAMPLE envelope signature verified; no operational action inferred" in console
    assert "receipt export did not declare SAMPLE evidence" in console
    assert "SAMPLE hash-link records · not operational receipts" in landing
    assert "Source-labelled chain records · state pending" in landing
    assert "Ledger receipts · signer state pending" not in landing

    # Later additive scripts also assign V.chain/V.receipts. They must preserve
    # the same SAMPLE boundary instead of replacing the first truth-safe view with
    # a newer "real/live/always recording" marketing definition.
    forbidden_chain_upgrades = (
        "The real SHA-256 receipt hash-chain",
        "Each node is a real receipt from the live ledger",
        "real hash chain",
        "Every governed action across every vertical appends one tamper-evident receipt",
        "The chain is always recording",
        "auto-polled live",
        "T('ch-ver','VERIFIED')",
        "Verify a signed receipt — in your browser",
    )
    for claim in forbidden_chain_upgrades:
        assert claim not in console

    assert "/v1/wow/ledger?limit=18&advance=0" in console
    assert "SIMULATED SAMPLE · STRUCTURE ONLY" in console
