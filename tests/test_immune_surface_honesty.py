# SPDX-License-Identifier: Apache-2.0
"""Static contracts for the Immune operational surface.

These checks lock the fail-closed browser behavior without pretending that a
source inspection is a live backend or device test.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMMUNE = (ROOT / "web" / "immune.html").read_text(encoding="utf-8")
SERVE = (ROOT / "serve.py").read_text(encoding="utf-8")


def test_initial_and_missing_status_never_claim_live_or_real() -> None:
    assert 'id="liveTag" aria-live="polite">IMMUNE · CONNECTING<' in IMMUNE
    assert 'id="organBadge">deny-by-default · connecting<' in IMMUNE
    assert 's.status||"REAL"' not in IMMUNE
    assert 'IMMUNE · LIVE</span>' not in IMMUNE
    assert "connectionState(null,false)" in IMMUNE
    assert 'row("status","UNAVAILABLE")' in IMMUNE
    assert 'const normalized=present(state)?String(state).trim().toUpperCase():"UNKNOWN"' in IMMUNE
    assert "first paint is <b>CONNECTING</b>" in IMMUNE
    assert 'id="kReach">CONNECTING<' in IMMUNE


def test_http_and_parse_failures_retain_evidence() -> None:
    assert "async function requestJSON" in IMMUNE
    assert 'return {ok:false,status:r.status,error:"invalid JSON response",data:null}' in IMMUNE
    assert 'return {ok:false,status:r.status,error:detail||("HTTP "+r.status),data:data}' in IMMUNE
    assert 'return {ok:false,status:null,error:(e&&e.message)||String(e),data:null}' in IMMUNE
    assert 'const status=result.status==null?"network error":"HTTP "+result.status' in IMMUNE
    assert 'required evidence unavailable' in IMMUNE
    assert "async function getJSON" not in IMMUNE


def test_receipt_trace_and_observation_fields_are_conditional() -> None:
    assert 'function present(v)' in IMMUNE
    assert 'if(!present(value))return ""' in IMMUNE
    for field in (
        'row("receipt digest",rec.digest,"digest")',
        'row("receipt sequence",rec.seq)',
        'row("signature",rec.signature,"digest")',
        'row("chain verified",typeof rec.chain_verified==="boolean"?String(rec.chain_verified):null)',
        'row("traceparent",v.traceparent,"digest")',
        'row("observed at",observed)',
    ):
        assert field in IMMUNE
    assert 'rec.digest||""' not in IMMUNE
    assert 'rec.receipt_type||"SZL.Immune.Verdict.v1"' not in IMMUNE
    assert "No receipt or signature state is inferred by this page" in IMMUNE


def test_unknown_decision_does_not_render_as_allow() -> None:
    assert 'const decision=String(v.decision||"UNKNOWN").toLowerCase()' in IMMUNE
    assert 'decision==="allow"?"allow":""' in IMMUNE
    assert '<span class="pill yellow">UNKNOWN</span>' in IMMUNE


def test_mobile_layout_and_tables_are_contained() -> None:
    assert "repeat(auto-fit,minmax(min(100%,220px),1fr))" in IMMUNE
    assert ".grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))" in IMMUNE
    assert "@media(max-width:760px)" in IMMUNE
    assert ".grid2{grid-template-columns:minmax(0,1fr);}" in IMMUNE
    assert ".switcher{order:3;width:100%;margin-left:0;flex-wrap:nowrap;overflow-x:auto" in IMMUNE
    assert IMMUNE.count('class="table-scroll" role="region"') == 2
    assert ".table-scroll{max-width:100%;overflow-x:auto" in IMMUNE
    assert ".table-scroll table{min-width:680px;}" in IMMUNE
    assert "button.run{min-height:44px;width:100%;}" in IMMUNE


def test_page_loader_uses_local_web_directory_outside_the_container() -> None:
    assert '_PTG_IMAGE_WEB = Path("/app/web")' in SERVE
    assert '_PTG_LOCAL_WEB = Path(__file__).resolve().parent / "web"' in SERVE
    assert "_PTG_IMAGE_WEB if _PTG_IMAGE_WEB.is_dir() else _PTG_LOCAL_WEB" in SERVE


def test_immune_route_accepts_head() -> None:
    assert 'app.add_api_route("/immune", _ptg_serve("immune.html"), methods=["GET", "HEAD"]' in SERVE
    assert 'app.add_api_route("/a11oy/immune", _ptg_serve("immune.html"), methods=["GET", "HEAD"]' in SERVE


def test_kernel_panel_is_same_origin_and_never_auto_embeds() -> None:
    assert "GET /api/a11oy/v1/immune/kernel" in IMMUNE
    assert "async function loadKernel()" in IMMUNE
    assert 'requestJSON(BASE + "/kernel")' in IMMUNE
    assert 's.reachability==="REACHABLE"' in IMMUNE
    assert 'iframe src="https://szlholdings-immune.hf.space"' not in IMMUNE
    assert 'f.src="https://szlholdings-immune.hf.space"' in IMMUNE
    assert "Neither Space is deleted" in IMMUNE
    assert "szlholdings-immune-lattice.hf.space" in IMMUNE
    assert "never fabricates <b>LIVE</b> or <b>PASS</b>" in IMMUNE
    assert 'id="fReach">CONNECTING<' in IMMUNE
    assert "async function loadField()" in IMMUNE
    assert 'requestJSON(BASE + "/field")' in IMMUNE
    assert 'requestJSON(BASE + "/nexus")' in IMMUNE
    assert "GET /api/a11oy/v1/immune/nexus" in IMMUNE
    assert "hunt / isolate / deceive" in IMMUNE
    assert "never strike people" in IMMUNE
    assert "not a second COP" in IMMUNE
    assert 'f.src="https://szlholdings-immune-lattice.hf.space"' in IMMUNE
    assert "RANGE.CLOUD.EXILE" in IMMUNE
