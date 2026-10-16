# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Current public and investor surfaces preserve source and evidence boundaries.

Protect the shipped homepage research paths and first-class console investor view;
retired overlay markup and a former marketing copy layout are not runtime contracts.
"""

from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_front_door_keeps_current_research_paths_and_claim_boundaries() -> None:
    landing = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")
    assert 'id="use-cases"' in landing
    assert "Make AI decisions" in landing
    assert "conceptual, not a live transaction" in landing
    assert "opening one does not establish model readiness or operational status" in landing
    for path in ("/command/brain", "/living-anatomy", "/holographic", "/killinchu"):
        assert f'href="{path}"' in landing
    for label in ("RESEARCH SURFACE", "ENGINEERING VIEW", "VISUAL INTERFACE", "SIMULATED EFFECTS"):
        assert label in landing
    assert 'href="/verify"' in landing and 'href="/trust"' in landing
    assert "SAMPLE · committed offline fixture" in landing
    assert "Motion and depth do not prove agent activity" in landing
    assert "Every vertical emits into a single" not in landing
    assert "fsync-durable" not in landing
    assert "UNSIGNED · DIGEST ONLY" in landing
    assert 'id="chain-receipts-label"' in landing


def test_front_door_catalog_links_do_not_invent_runtime_inventory_counts() -> None:
    landing = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")
    import re
    ecosystem = re.search(r'<section[^>]*id="ecosystem"[^>]*>(.*?)</section>', landing, re.S).group(1)
    assert "A reachable URL is reachability only" in ecosystem
    assert "not source/runtime alignment" in ecosystem
    assert "ROADMAP cards are empty on purpose" in ecosystem
    for slug in ("szl-flagship-models", "szl-kernels-software", "szl-roadmap-no-admitted-data", "szl-flagship-spaces"):
        assert f'https://huggingface.co/collections/SZLHOLDINGS/{slug}-' in ecosystem
    assert "Canonical public catalog sources" in ecosystem
    assert ecosystem.count('<b>OPEN</b>') == 4
    assert not re.search(r'<b>\d+</b>', ecosystem)
    assert "snapshot observed 2026-07-16" not in landing


def test_console_investor_view_is_live_evidence_bound_and_mobile_reachable():
    console = (ROOT / "pages/console.html").read_text(encoding="utf-8")
    investor = _between(console, "/* Investor View", "<!-- DEV1 WAVE K")
    controller = _between(console, '<script id="inv-mode-js">', "</script>")
    # The current public destination is a first-class console view; the retired
    # overlay's probes, CSS layout and modal isolation are not its runtime contract.
    assert "V.investor={" in investor
    assert "window.go('investor')" in controller
    assert "viewQ==='investor'" in controller
    assert "set(true)" not in controller
    assert "/api/a11oy/v1/honest" in investor
    assert "/api/a11oy/v1/wow/ledger?limit=1&advance=0" in investor
    assert "canonicalLockedIds" in investor
    assert "lockedCount===8" in investor
    assert "(new Set(lockedIds)).size===8" in investor
    assert "SIMULATED" in investor and "UNAVAILABLE" in investor
    assert "REPORTED" not in investor
    assert 'href="/verify"' in investor
    assert 'href="https://a11oy.net"' in investor
    assert "Signing is claimed only when persistent signer evidence is active and verification passes" in investor
    assert "Read paths never mint receipts" in investor
    assert "does not claim named customers, paid pilots, revenue, retention" in investor
    assert "they do not confer certification, accreditation, or legal compliance" in investor
    assert "postJSON" not in investor


def test_console_observability_names_and_posture_fail_closed():
    console = (ROOT / "pages/console.html").read_text(encoding="utf-8")
    normalizer = _between(console, "window._meshRows=function(raw)", "function _meshSortRows")
    nervous = _between(console, "V.organnervous={", "V.organskeleton={")
    assert "row(v,null,i)" in normalizer
    assert "Object.entries(raw)" in normalizer
    assert "identity_state='unidentified'" in normalizer
    assert "out.observed=false" in normalizer
    assert "row.identity_state==='identified'" in normalizer
    assert "window._meshRows(d.mesh_reach)" in nervous
    assert "window._meshIsUp" in nervous
    assert "gj('/api/a11oy/provenance')" in nervous
    assert "Nervous · Observability posture" in nervous
    assert "INVENTORY · PROVENANCE BOUNDARY" in nervous
    assert "hash records; not span signatures" in nervous
    assert "every span is a DSSE-signable receipt" not in nervous
    assert "0.919" not in console
    for name in ('description', 'og:description', 'twitter:description'):
        line = next(line for line in console.splitlines() if f'="{name}"' in line)
        assert "observed, cached, modeled, demo, unsigned, or unavailable" in line
        assert "signed receipts" not in line
    assert "getPublic('/api/a11oy/v1/lambda/org',8000)" in console
    assert "orgLambdaText(orgLambda)" in console
    service = (ROOT / "serve.py").read_text(encoding="utf-8")
    for retained_server_boundary in (
        '"observation_state": "inventory"',
        '"observed": False, "latency_ms": None',
        '"signed_spans": None',
        "not runtime health or provenance observations",
        "_A11OY_SLSA_LEVEL = getattr",
        '"slsa": _A11OY_SLSA_TEXT',
    ):
        assert retained_server_boundary in service
    for unsupported_claim in ('"level": "L2"', "L2 .att emitted", "signed SLSA build-provenance attestation"):
        assert unsupported_claim not in service


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
    assert 'd.operational === true && d.data_kind === "live"' in landing
    assert 'd.operational === false && d.data_kind === "sample"' in landing
    assert "function setChain(" not in landing
    assert "ts.signed_receipts" not in landing


def _render_ledger(data):
    """Execute the shipped parser and painter, without a server or network."""
    import json
    import shutil
    import subprocess
    landing = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")
    code = landing.split("  function ledgerReading(d){", 1)[1].split("  // ---- (A) try the ONE consolidated read", 1)[0]
    code = "function ledgerReading(d){" + code
    node = shutil.which("node")
    assert node, "Node is required to test the actual landing renderer"
    harness = r'''
const vm=require('node:vm');
const input=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const nodes={};
const scope={$:id=>nodes[id] ||= {textContent:'OLD',innerHTML:'OLD'},
  grayChip:label=>'GRAY:'+label,downChip:label=>'DOWN:'+label};
vm.createContext(scope); vm.runInContext(input.code,scope);
const value=scope.setHeroReceiptsFromLedger(input.data);
process.stdout.write(JSON.stringify({nodes,value}));
'''
    result = subprocess.run([node, "-e", harness], input=json.dumps({"code": code, "data": data}),
        text=True, encoding="utf-8", capture_output=True, check=True, timeout=10)
    return json.loads(result.stdout)


def _ledger_fixture(count=0, *, sample=False, signed=False):
    return {"count": count, "receipts": [{"digest": "a" * 64} for _ in range(count)],
            "state": "SAMPLE" if sample else "live", "data_kind": "sample" if sample else "live",
            "operational": not sample, "hash_algorithm": "sha256-hex",
            "signature_state": "SIGNED" if signed else "UNSIGNED"}


def test_empty_operational_ledger_is_zero_and_never_a_sample_or_estate_total():
    result = _render_ledger(_ledger_fixture())
    assert result["value"]["state"] == "OPERATIONAL"
    for name in ("hs-receipts", "chain-receipts", "chain-depth"):
        assert result["nodes"][name]["textContent"] == "0"
    assert "Operational" in result["nodes"]["hs-receipts-label"]["textContent"]
    assert result["nodes"]["chain-head"]["textContent"] == "UNAVAILABLE"
    assert result["nodes"]["chain-alg"]["textContent"] == "sha256-hex"
    assert "UNSIGNED" in result["nodes"]["chain-split"]["textContent"]


def test_sample_and_reported_signatures_remain_separate_from_operational_proof():
    result = _render_ledger(_ledger_fixture(2, sample=True, signed=True))
    assert result["value"]["state"] == "SAMPLE"
    for name in ("hs-receipts-label", "chain-receipts-label"):
        assert "not operational" in result["nodes"][name]["textContent"]
    assert "not verified here" in result["nodes"]["chain-split"]["textContent"]
    assert result["nodes"]["chain-head"]["textContent"] == "aaaaaaaaaa…aaaa"


def test_invalid_or_conflicting_ledger_evidence_clears_every_count():
    fixtures = [None, [], {}, {"count": 7, "receipts": []},
                {**_ledger_fixture(), "count": True},
                {**_ledger_fixture(), "count": "0"},
                {**_ledger_fixture(), "count": -1},
                {**_ledger_fixture(), "count": 0.5},
                {**_ledger_fixture(), "count": 9007199254740992},
                {**_ledger_fixture(), "receipts": None},
                {**_ledger_fixture(1), "receipts": [None]},
                {**_ledger_fixture(), "data_kind": "sample"},
                {**_ledger_fixture(), "operational": "true"},
                {**_ledger_fixture(), "state": "cached"}]
    for data in fixtures:
        result = _render_ledger(data)
        assert result["value"] is None, data
        for name in ("hs-receipts", "chain-receipts", "chain-depth", "chain-alg", "chain-head"):
            assert result["nodes"][name]["textContent"] == "UNAVAILABLE", data
        assert result["nodes"]["chain-src"]["innerHTML"] == "DOWN:UNAVAILABLE"


def test_unrecognized_metadata_cannot_become_signature_or_hash_claim():
    data = _ledger_fixture(1)
    data.update(signature_state="VERIFIED", hash_algorithm="<script>fake</script>")
    data["receipts"][0]["digest"] = "not-a-digest"
    result = _render_ledger(data)
    assert result["nodes"]["chain-alg"]["textContent"] == "UNAVAILABLE"
    assert result["nodes"]["chain-head"]["textContent"] == "UNAVAILABLE"
    assert result["nodes"]["chain-split"]["textContent"] == "Signer state unavailable"


def _between(source, start, end):
    begin = source.index(start)
    return source[begin:source.index(end, begin)]


def _node(source):
    node = shutil.which("node")
    assert node, "Node.js is required for the shipped console behavior contract"
    result = subprocess.run([node, "-e", source], input=(ROOT / "pages/console.html").read_text(encoding="utf-8"), text=True, encoding="utf-8", capture_output=True, timeout=25)
    assert result.returncode == 0, result.stdout + result.stderr


def test_console_mesh_normalization_and_org_posture_runtime():
    _node(r"""
const assert = require('node:assert/strict'), fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(0,'utf8');
function between(a,b){const i=source.indexOf(a);assert(i>=0,a);const j=source.indexOf(b,i);assert(j>i,b);return source.slice(i,j);}
let payload, fail=false, calls=[];
const c=vm.createContext({window:{},getPublic:async(url,ms)=>{calls.push([url,ms]);if(fail)throw Error('offline');return payload;}});
vm.runInContext(between('window._meshRows=function(raw)','function _meshSortRows'),c);
vm.runInContext(between('async function observedOrgLambda()','async function ledger3d_load()'),c);
const norm=c.window._meshRows, up=c.window._meshIsUp;
for(const input of [null,[],{},'bad',false]) assert.equal(norm(input).length,0);
for(const input of [[{status:'ok',latency_ms:0}],{core:{status:'ok',observed:false,latency_ms:0}},{core:{observed:true,latency_ms:1}},{core:{status:'invented',observed:true,latency_ms:1}}]){
 const row=norm(input)[0];assert.equal(up(row),false);assert.equal(row.status,'unavailable');assert.equal(row.latency_ms,null);assert.equal(c._meshHealthScore([row]),null);
}
assert.equal(norm([{status:'ok'}])[0].name,'Unidentified capability');
assert.equal(norm({core:{status:'ok',latency_ms:0}})[0].name,'core');
assert.equal(norm({core:{status:'ok',latency_ms:0}})[0].latency_ms,0);
assert.equal(up(norm([{id:'core',status:'healthy',latency_ms:0}])[0]),true);
assert.equal(norm({core:{status:'ok',latency_ms:'0',http_code:'200'}})[0].http_code,null);
assert.equal(norm({core:{status:'ok',latency_ms:Infinity}})[0].latency_ms,null);
(async()=>{
 for(const value of [null,{}, {lambda_org:0.9}, {lambda_org:'0.9',inputs:{class:'SUPPLIED'}}, {lambda_org:NaN,inputs:{class:'SUPPLIED'}}, {lambda_org:Infinity,inputs:{class:'SUPPLIED'}}, {lambda_org:-1,inputs:{class:'SUPPLIED'}}, {lambda_org:2,inputs:{class:'SUPPLIED'}}, {lambda_org:0.9,inputs:{class:'MEASURED'}}]){payload=value;assert.equal(await c.observedOrgLambda(),null);}
 payload={lambda_org:0,lambda_floor:0,inputs:{class:'SAMPLE'}};let reading=await c.observedOrgLambda();assert.equal(reading.value,0);assert.equal(reading.floor,0);assert.match(c.orgLambdaText(reading),/SAMPLE 0\.000.*not measured/);
 payload={lambda_org:0.8,lambda_floor:'0.9',inputs:{class:'SUPPLIED'}};reading=await c.observedOrgLambda();assert.equal(reading.floor,null);assert.match(c.orgLambdaText(reading),/SUPPLIED 0\.800.*not measured/);
 fail=true;assert.equal(await c.observedOrgLambda(),null);assert.match(c.orgLambdaText(null),/^UNAVAILABLE/);
 for(const [url,ms] of calls){assert.equal(url,'/api/a11oy/v1/lambda/org');assert.equal(ms,8000);}
})().catch(e=>{console.error(e);process.exitCode=1;});
""")


def test_active_observation_renderers_do_not_invent_health_coverage_or_signatures():
    _node(r"""
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(0,'utf8');
function between(a,b){const i=source.indexOf(a);assert(i>=0,a);const j=source.indexOf(b,i);assert(j>i,b);return source.slice(i,j);}
let data={}, charts=[], reads=[], pending=[], fail=false; const elements=new Map();
function node(id){if(!elements.has(id))elements.set(id,{textContent:'',innerHTML:'',style:{}});return elements.get(id);}
const echarts={init:()=>({setOption:option=>charts.push(option),resize:()=>{}})};
const esc=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const read=async path=>{reads.push(path);if(fail)throw Error('offline');return data[path]||{};};
const c=vm.createContext({window:{echarts,addEventListener:()=>{},a11oyPoll:fn=>pending.push(fn())},V:{},echarts,
 E:node,T:(id,value)=>node(id).textContent=String(value),H:(id,value)=>node(id).innerHTML=String(value),
 gj:read,getPublic:read,esc,API:'/api/a11oy',HON:'',honest:()=>'',kpi:()=>'',card:()=>'',
 chip:()=>'',srcline:()=>'',TEAL:'success',GOLD:'warning',RED:'error',GRAY:'neutral'});
vm.runInContext(between('window._meshRows=function(raw)','function _meshSortRows'),c);
vm.runInContext(between('async function observedOrgLambda()','async function ledger3d_load()'),c);
vm.runInContext(between('    V.fleet={','    /* =============== mesh'),c);
vm.runInContext(between('    V.mission={','    /* =============== melt'),c);
vm.runInContext(between('    V.melt={','    /* =============== deploy'),c);
vm.runInContext(between('    V.organnervous={','    /* ============================================================================'),c);
const container={innerHTML:'',isConnected:true,querySelector:()=>true};
function reset(){elements.clear();charts=[];reads=[];pending=[];fail=false;}
(async()=>{
 reset();data={'/api/a11oy/v1/observability/summary':{capabilities:[{id:'core',name:'<script>bad</script>',status:'ok',observed:false,latency_ms:0}],mesh_reach:{core:{status:'inventory',observed:false,latency_ms:null}},observed:false,spans_available:true,melt:{metrics:{organs_total:1,organs_reachable:1,dag_depth:99},events:{signed_spans:7},traces:{chain_verified:true}}}};
 await c.V.fleet.render(container);assert.equal(node('fl-up').textContent,'UNAVAILABLE');assert.match(node('fl-grid').innerHTML,/unavailable/);assert.doesNotMatch(node('fl-grid').innerHTML,/<script>/);assert.doesNotMatch(node('fl-grid').innerHTML,/data-status="ok"/);
 await c.V.mission.render(container);assert.equal(node('ms-floor').textContent,'UNAVAILABLE · Conjecture 1 (advisory)');assert.equal(node('ms-cov').textContent,'UNAVAILABLE');assert.equal(node('ms-h').textContent,'UNAVAILABLE');
 for(const series of charts[0].series){assert.equal(series.progress.show,false);assert.equal(series.data[0].value,'-');assert.equal(series.detail.formatter(0),'UNAVAILABLE');}
 await c.V.melt.render(container);assert.equal(node('mt-cv').textContent,'UNAVAILABLE');assert.equal(node('mt-sp').textContent,'UNAVAILABLE');assert.equal(charts[1].series[0].data.length,0);
 await c.V.organnervous.render(container);await Promise.all(pending);assert.equal(node('on-reach').textContent,'UNAVAILABLE');assert.equal(node('on-spans').textContent,'UNAVAILABLE');assert.equal(node('on-depth').textContent,'UNAVAILABLE');assert.equal(node('on-slsa').textContent,'UNAVAILABLE');assert.match(node('on-reachlist').innerHTML,/health not observed/);assert.doesNotMatch(node('on-reachlist').innerHTML,/>DOWN</);
 reset();data={'/api/a11oy/v1/observability/summary':{capabilities:[{id:'core',name:'Core',status:'ok',observed:true,latency_ms:0}],mesh_reach:[{id:'core',name:'Core',status:'up',observed:true,latency_ms:0}],observed:true,spans_available:false,melt:{metrics:{organs_total:1,organs_reachable:1,dag_depth:0},events:{signed_spans:0},traces:{chain_verified:false}}},'/api/a11oy/v1/lambda/org':{lambda_org:0.8,inputs:{class:'SAMPLE'}},'/api/a11oy/v1/formulas/selftest':{reasoning:{conformal_interval:{coverage:0.9}}},'/api/a11oy/provenance':{slsa:'L1'}};
 await c.V.mission.render(container);assert.equal(node('ms-h').textContent,'100% observed');assert.equal(node('ms-cov').textContent,'SELFTEST 90%');assert.match(node('ms-floor').textContent,/SAMPLE.*not measured/);
 assert.equal(charts[0].series[0].data[0].value,100);assert.equal(charts[0].series[1].progress.itemStyle.color,'neutral');assert.equal(charts[0].series[2].data[0].value,'-');assert.equal(charts[0].series[5].data[0].value,'-');
 await c.V.melt.render(container);assert.equal(node('mt-cv').textContent,'REPORTED false');assert.equal(node('mt-sp').textContent,'REPORTED 0');assert.equal(charts[1].series[0].data.length,3);assert.equal(charts[1].series[0].data[0][2],0);
 await c.V.organnervous.render(container);await Promise.all(pending);assert.equal(node('on-reach').textContent,'1 / 1 observed');assert.equal(node('on-spans').textContent,'REPORTED NO');assert.equal(node('on-depth').textContent,'0');assert.match(node('on-slsa').textContent,/L1 source-declared/);assert.match(node('on-reachlist').innerHTML,/0ms/);
 fail=true;await c.V.organnervous.render(container);await Promise.all(pending);for(const id of ['on-reach','on-depth','on-spans','on-slsa'])assert.equal(node(id).textContent,'UNAVAILABLE');assert.doesNotMatch(node('on-reachlist').innerHTML,/>OK</);
 await c.V.mission.render(container);for(const id of ['ms-floor','ms-cov','ms-h'])assert.equal(node(id).textContent,'UNAVAILABLE');
 for(const path of reads)assert.match(path,/^\/api\//);
})().catch(e=>{console.error(e);process.exitCode=1;});
""")


def test_investor_aliases_open_current_view_without_retired_overlay():
    _node(r"""
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(0,'utf8'),start=source.indexOf('<script id="inv-mode-js">');
const logic=source.slice(source.indexOf('>',start)+1,source.indexOf('</script>',start));
for(const [search,hash] of [['?investor=1',''],['?view=investor',''],['','#investor']]){
 let calls=[],domTouches=0;
 const c=vm.createContext({window:{location:{search,hash},go:view=>calls.push(view)},URLSearchParams,
 document:{addEventListener:()=>{},getElementById:()=>{domTouches++;throw Error('retired overlay touched');}}});
 vm.runInContext(logic,c);assert.deepEqual(calls,['investor']);assert.equal(domTouches,0);
 c.window.a11oyInvestor.open();assert.deepEqual(calls,['investor','investor']);
}
""")
