"""Investor-facing category, solution, evidence, and mobile contracts.

These checks keep the public story on one governed substrate, require every named
solution to open a real console view and probe a real read-only source, and prevent
dated estate counts or unproved commercial claims from returning to the front door.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_front_door_presents_one_platform_and_six_working_solution_views() -> None:
    landing = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")

    assert "Evidence and control for consequential AI" in landing
    assert "Observe → Gate → Act → Prove" in landing
    assert "One substrate, not six separate products." in landing
    assert '/console?investor=1' in landing
    assert '/company#contact' in landing

    solutions = {
        "vcyber": "/api/a11oy/v1/vert/cyber/feed?limit=1",
        "vfinance": "/api/a11oy/v1/vert/finance/feed",
        "lineage": "/api/a11oy/provenance",
        "entCockpit": "/api/a11oy/v1/observability/summary",
        "vrealestate": "/api/a11oy/v1/deva/re/pulse",
        "vlegal": "/api/a11oy/v1/devb/legal/matter?limit=1",
    }
    for view, endpoint in solutions.items():
        assert f'href="/console#{view}"' in landing
        assert f'data-solution-probe="{endpoint}"' in landing

    assert "A reachable source proves the route answered" in landing
    assert "not that its data is" in landing
    assert landing.count("data-solution-contract=") == 6
    assert "function solutionProbeState(contract,d)" in landing
    assert 'sourceMap(d.equities,["SPY","AAPL","MSFT","NVDA","^VIX"]' in landing
    assert 'sourceMap(d.crypto,["BTC-USD","ETH-USD","SOL-USD"]' in landing
    assert '["kev","nvd","gh_events","hf"].forEach' in landing
    assert '["hpd","dob","rates"].forEach' in landing
    assert 'source(d.opinions,"legal.opinions")' in landing
    assert "states.every(s=>good.has(s))" in landing
    assert "source clock invalid" in landing
    assert "Object.keys(v).forEach(k => walk" not in landing
    assert "schema and evidence-state validation" in landing

    # Receipt state follows returned signer/ledger evidence; digest-only fallbacks
    # must not be advertised as unconditionally signed.
    assert "Emit a signed, hash-chained receipt" not in landing
    assert "UNSIGNED · DIGEST ONLY" in landing
    assert 'id="chain-receipts-label"' in landing


def test_front_door_inventory_is_runtime_sourced_not_frozen_marketing_copy() -> None:
    landing = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")

    assert "/api/a11oy/v1/ecosystem/atlas" in landing
    for inventory_id in (
        "estate-models",
        "estate-kernels",
        "estate-datasets",
        "estate-spaces",
        "estate-collections",
        "estate-buckets",
    ):
        assert f'id="{inventory_id}">—<' in landing

    assert "snapshot observed 2026-07-16" not in landing
    assert '<div class="estate-cell"><b>15</b>' not in landing
    assert "no stale count is promoted to current" in landing


def test_console_investor_view_is_live_evidence_bound_and_mobile_reachable() -> None:
    console = (ROOT / "pages" / "console.html").read_text(encoding="utf-8")

    assert "The evidence and control plane" in console
    assert "Observe → Gate → Act → Prove" in console
    assert 'id="inv-runtime"' in console
    assert 'id="inv-contract"' in console
    assert 'id="inv-build"' in console
    assert "'/healthz'" in console
    assert "'/api/a11oy/v1/readiness/tab-matrix?view=summary'" in console
    assert "'/api/build-info'" in console
    assert "d.matrix_summary" in console
    assert "PROBED CLEAN" in console
    assert "UNREACHABLE" in console
    assert "THROTTLED" in console

    for view in ("vcyber", "vfinance", "lineage", "entCockpit", "vrealestate", "vlegal"):
        assert f"a11oyInvestor.openView('{view}')" in console

    assert "Commercial evidence." in console
    assert "does not claim named customers, paid pilots, revenue, retention" in console
    assert "Compliance support." in console
    assert "they do not confer certification, accreditation, or legal compliance" in console
    assert "@media(max-width:390px){.topbar .live{display:none}" in console
    assert ".inv-loop{grid-template-columns:1fr}" in console
    assert "aria-hidden=\"true\"" in console
    assert "function isolateBackground(open,o)" in console
    assert "n.inert=true" in console
    assert "backgroundState.forEach" in console
    assert "removeAttribute('aria-hidden')" in console
    assert "savedBodyOverflow=document.body.style.overflow" in console
    assert "document.body.style.overflow=savedBodyOverflow" in console
    assert "if(String(u.hash||'').toLowerCase()==='#investor')u.hash=''" in console
    assert 'id="ar-gov-history-badge">INVENTORY' in console
    assert "histBadge.textContent=storageError?'STORAGE ERROR'" in console
    assert "freshLabel==='LIVE'?'b-live'" in console
    assert "build.revision" in console
    assert "build.state" in console


def test_console_observability_names_and_posture_fail_closed() -> None:
    console = (ROOT / "pages" / "console.html").read_text(encoding="utf-8")
    service = (ROOT / "serve.py").read_text(encoding="utf-8")

    # Both deployed payload shapes (id-keyed object and array) use one normalizer;
    # array indexes must never leak into the investor-visible service-name column.
    assert "window._meshRows=function(raw)" in console
    assert "window._meshDisplayName=function(p,i)" in console
    assert "window._meshIsUp=function(p)" in console
    assert "Object.keys(mr)" not in console
    assert "out.observed=out.observed===true" in console
    assert "p&&p.observed===true" in console

    # Missing evidence is unavailable/inventory, not an implicit healthy service.
    assert "Missing status is deliberately UNAVAILABLE" in console
    assert "inventory, not health evidence" in console
    assert "health not observed" in console
    assert "attestation/signature not inferred" in console
    assert "getJSON('/api/a11oy/provenance')" in console
    assert "?\u0027L2\u0027:\u0027UNAVAILABLE\u0027" not in console
    assert ".att + .sig" not in console
    assert "(p.status||'ok')==='ok'" not in console
    assert "6/6 healthy" not in console

    # Every investor-visible org posture reads the same bounded live source.
    assert "async function observedOrgLambda()" in console
    assert "getPublic('/api/a11oy/v1/lambda/org',8000)" in console
    assert "orgLambdaText(orgLambda)" in console
    assert "trust score: 0.919" not in console
    assert '"observation_state": "inventory"' in service
    assert '"observed": False, "latency_ms": None' in service
    assert '"signed_spans": None' in service
    assert "not runtime health or provenance observations" in service
    assert "Nervous · Observability posture" in console
    assert "INVENTORY · PROVENANCE BOUNDARY" in console
    assert "every span is a DSSE-signable receipt" not in console
    assert "L1 honest; L2 .att emitted" not in console
    assert "_A11OY_SLSA_LEVEL = getattr" in service
    assert '"slsa": _A11OY_SLSA_TEXT' in service
    assert '"level": "L2"' not in service
    assert "L2 .att emitted" not in service
    assert "signed SLSA build-provenance attestation" not in service
    assert "hash records; not span signatures" in console

    # Search/social metadata must preserve the same evidence boundary as the UI.
    assert "Every view reads a live endpoint" not in console
    assert "signed receipts, the formula knowledge base" not in console
    assert "observed, cached, modeled, demo, unsigned, or unavailable" in console


def test_sample_chain_and_receipt_export_are_not_operational_evidence() -> None:
    landing = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")
    service = (ROOT / "serve.py").read_text(encoding="utf-8")

    assert '"data_kind": "sample"' in service
    assert '"operational": False' in service
    assert '"structure_verified": True' in service
    assert '"chain_verified": False' in service
    assert '"signature_state": "UNSIGNED"' in service
    assert '("operator.approve", "human approval recorded for high-consequence action")' not in service
    assert "_A11OY_SAMPLE_EXPORT = _a11oy_build_sample_export()" in service
    assert "GET serves the same envelope and never invokes the signer" in service
    assert "SAMPLE hash-link records · not operational receipts" in landing
    assert 'getJSON("/api/lake/v1/health")' not in landing
    assert "excluded from operational receipt and ROI counts" in landing
