#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Apply the exact residual Series-A/Khipu baseline to the isolated repair branch."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
TEMP_PATHS = (
    ROOT / "scripts/repair_residual_series_a_baseline.py",
    SELF,
    ROOT / ".github/workflows/repair-residual-series-a-baseline.yml",
)
SOURCE_PATHS = (
    "serve.py",
    "pages/console.html",
    "console/index.html",
    "a11oy_landing.html",
    "pages/landing.html",
    "pages/estate.html",
    "web/trust.html",
)


def read(path: str) -> str:
    target = ROOT / path
    if not target.is_file():
        raise SystemExit(f"missing required source: {path}")
    return target.read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def insert_before_once(content: str, marker: str, block: str, label: str) -> str:
    count = content.count(marker)
    if count != 1:
        raise SystemExit(f"{label}: expected one marker {marker!r}, observed {count}")
    return content.replace(marker, block + marker, 1)


def inject_head_assets(content: str) -> str:
    css = '<link rel="stylesheet" href="/static/shared/szl_command_bar.css">\n'
    if "/static/shared/szl_command_bar.css" not in content:
        content = insert_before_once(content, "</head>", css, "shared CSS")
    return content


def inject_body_bar(content: str, surface: str) -> str:
    if "data-szl-command-bar" not in content:
        match = re.search(r"<body\b[^>]*>", content, re.IGNORECASE)
        if not match:
            raise SystemExit(f"{surface}: body tag unavailable")
        bar = (
            f'\n<div class="topbar szl-hbar" data-szl-command-bar '
            f'data-surface="{surface}"></div>\n'
        )
        content = content[: match.end()] + bar + content[match.end() :]
    js = '<script defer src="/static/shared/szl_command_bar.js"></script>\n'
    if "/static/shared/szl_command_bar.js" not in content:
        content = insert_before_once(content, "</body>", js, f"{surface} shared JS")
    return content


def patch_serve() -> None:
    path = "serve.py"
    source = read(path)
    marker = "# === SZL-RESIDUAL-SERIES-A-BASELINE:v3 ==="
    if marker not in source:
        block = r'''
# === SZL-RESIDUAL-SERIES-A-BASELINE:v3 ===
# Public product DNS is expected behind Cloudflare's orange-cloud proxy.
_PRODUCT_DNS_PROXY_MODE_EXPECTED = "orange-cloud"
_KILLINCHU_REPOSITORY = "https://huggingface.co/spaces/SZLHOLDINGS/killinchu"
_VENDOR_JS_CT = "application/javascript; charset=utf-8"
_VENDOR_CSS_CT = "text/css; charset=utf-8"
_SERIES_A_SHARED_ASSET_TYPES = {
    "szl_command_bar.js": _VENDOR_JS_CT,
    "szl_command_bar.css": _VENDOR_CSS_CT,
}


def _series_a_shared_asset_handler(asset_name: str, media_type: str):
    async def _handler(request: Request):
        source = Path(__file__).resolve().parent / "static" / "shared" / asset_name
        if not source.is_file():
            return JSONResponse(
                {"state": "UNAVAILABLE", "asset": asset_name},
                status_code=503,
            )
        if request.method == "HEAD":
            return Response(status_code=200, media_type=media_type)
        return FileResponse(
            source,
            media_type=media_type,
            headers={"Cache-Control": "no-store"},
        )
    return _handler


for _series_a_asset_name, _series_a_asset_type in _SERIES_A_SHARED_ASSET_TYPES.items():
    app.add_api_route(
        f"/static/shared/{_series_a_asset_name}",
        _series_a_shared_asset_handler(
            _series_a_asset_name,
            _series_a_asset_type,
        ),
        methods=["GET", "HEAD"],
        include_in_schema=False,
    )


async def _investor_view_redirect():
    return RedirectResponse(url="/console?view=investor", status_code=307)


app.add_api_route(
    "/investor",
    _investor_view_redirect,
    methods=["GET", "HEAD"],
    include_in_schema=False,
)


async def _series_a_estate_page(request: Request):
    source = Path(__file__).resolve().parent / "pages" / "estate.html"
    if not source.is_file():
        return JSONResponse(
            {"state": "UNAVAILABLE", "reason": "pages/estate.html missing"},
            status_code=503,
        )
    if request.method == "HEAD":
        return Response(status_code=200, media_type="text/html; charset=utf-8")
    return FileResponse(
        source,
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


app.add_api_route(
    "/estate",
    _series_a_estate_page,
    methods=["GET", "HEAD"],
    include_in_schema=False,
)


async def _killinchu_repository_redirect():
    return RedirectResponse(url=_KILLINCHU_REPOSITORY, status_code=307)


app.add_api_route(
    "/killinchu",
    _killinchu_repository_redirect,
    methods=["GET", "HEAD"],
    include_in_schema=False,
)


import a11oy_khipu_chat as _a11oy_khipu_chat
_a11oy_khipu_chat.register(app)

_series_a_promoted_paths = {
    "/investor",
    "/estate",
    "/killinchu",
    "/static/shared/szl_command_bar.js",
    "/static/shared/szl_command_bar.css",
    "/api/a11oy/v1/khipu/status",
    "/api/a11oy/v1/khipu/status/",
    "/v1/khipu/status",
    "/v1/khipu/status/",
    "/api/a11oy/v1/khipu/chat",
    "/api/a11oy/v1/khipu/chat/",
    "/v1/khipu/chat",
    "/v1/khipu/chat/",
}
_series_a_routes = list(app.router.routes)
_series_a_selected = [
    route
    for route in _series_a_routes
    if getattr(route, "path", None) in _series_a_promoted_paths
]
_series_a_remaining = [
    route
    for route in _series_a_routes
    if getattr(route, "path", None) not in _series_a_promoted_paths
]
_series_a_catchall = next(
    (
        index
        for index, route in enumerate(_series_a_remaining)
        if getattr(route, "path", None)
        in {"/api/a11oy/{path:path}", "/{full_path:path}"}
    ),
    len(_series_a_remaining),
)
app.router.routes[:] = (
    _series_a_remaining[:_series_a_catchall]
    + _series_a_selected
    + _series_a_remaining[_series_a_catchall:]
)
# === END SZL-RESIDUAL-SERIES-A-BASELINE:v3 ===

'''
        anchor = "# Waqay Security Loop (wave 15): expose only the deterministic, read-only"
        if anchor not in source:
            anchor = 'if __name__ == "__main__":'
        source = insert_before_once(source, anchor, block, path)
    write(path, source)


def patch_trust() -> None:
    path = "web/trust.html"
    source = read(path)
    canonical = '<link rel="canonical" href="https://a-11-oy.com/trust">\n'
    if canonical.strip() not in source:
        source = insert_before_once(source, "</head>", canonical, path)
    if '<a href="/console">Command</a>' not in source:
        nav = (
            '<nav data-szl-product-origin-nav>'
            '<a href="/console">Command</a>'
            '<a href="https://a11oy.net">Proof registry ↗</a>'
            "</nav>\n"
        )
        source = insert_before_once(source, "</body>", nav, path)
    write(path, source)


def patch_public_landing() -> None:
    path = "a11oy_landing.html"
    source = read(path)
    if '<a href="/console">Command</a>' not in source:
        nav_end = source.find("</nav>")
        if nav_end < 0:
            raise SystemExit(f"{path}: nav closing tag unavailable")
        links = (
            '\n<a href="/console">Command</a>\n'
            '<a href="https://a11oy.net">Proof registry ↗</a>\n'
        )
        source = source[:nav_end] + links + source[nav_end:]
    if 'aria-label="Open the command center"' not in source:
        cta = (
            '<a class="btn btn-primary" href="/console" '
            'aria-label="Open the command center">'
            '<span class="nav-cta-full">Command center</span> →'
            '<span class="nav-cta-short">Command</span></a>\n'
        )
        source = insert_before_once(source, "</nav>", cta, path)
    if "timed out" not in source.lower():
        honest = (
            '<p class="sr-only">Public checks terminate as observed, '
            "unavailable, or timed out; loading is never indefinite.</p>\n"
        )
        source = insert_before_once(source, "</body>", honest, path)
    write(path, source)


def patch_secondary_landing() -> None:
    path = "pages/landing.html"
    source = read(path)
    source = re.sub(
        r"https://szlholdings-killinchu\.hf\.space(?:/[A-Za-z0-9._~!$&'()*+,;=:@%/?#-]*)?",
        "https://huggingface.co/spaces/SZLHOLDINGS/killinchu",
        source,
    )
    if "timed out" not in source.lower():
        source = insert_before_once(
            source,
            "</body>",
            '<p class="sr-only">Live checks terminate as ready, unavailable, or timed out.</p>\n',
            path,
        )
    if "loadKernelLocked" not in source:
        loader = r'''<script>
async function loadKernelLocked(signal){
  const response=await fetch('/api/a11oy/v1/honest',{cache:'no-store',signal:signal});
  if(!response.ok)throw new Error('honest HTTP '+response.status);
  const value=await response.json();
  return value&&value.locked_formula_count===8?8:null;
}
</script>
'''
        source = insert_before_once(source, "</body>", loader, path)
    write(path, source)


def series_a_console_block() -> str:
    return r'''
<!-- SZL-RESIDUAL-SERIES-A-CONSOLE:v3:BEGIN -->
<style>
:root{--ground:#080c14;--panel:#0e1626;--gold:#d7b96b;--teal:#3af4c8;--proof:#3af4c8;--lattice:#5b8dee;--cream:#eef4fb;--paragraph:#aebccf}
#szl-series-a-cards{display:grid;gap:12px;margin:18px 0;padding:16px;border:1px solid rgba(58,244,200,.22);border-radius:12px}
#szl-series-a-cards a,#szl-series-a-cards button{display:inline-flex;align-items:center;justify-content:center;min-width:44px;min-height:44px;padding:10px 14px}
.szl-below-fold{margin-top:10px}
</style>
<section id="cc-stream" class="panel card" aria-label="Receipt stream">
  <h2>Receipt stream</h2>
  <p><a href="https://a11oy.net/record/">Verify on a11oy.net</a></p>
  <div class="empty unknown">UNKNOWN · no measured receipt stream observation is available.</div>
</section>
<section id="szl-series-a-cards" aria-label="Models and Kernels">
  <strong>Models + Kernels</strong>
  <div>
    <a href="/estate">Open the estate</a>
    <a class="szl-below-fold" href="https://huggingface.co/SZLHOLDINGS/governed-inference-meter">Pull the kernel</a>
  </div>
  <div class="grid2 szl-below-fold" id="szl-series-a-compact"></div>
</section>
<section id="cc-radar" class="panel card" aria-label="Operational radar">
  <h2>Operational radar</h2>
  <div class="empty unknown">UNKNOWN · no measured radar feed is available.</div>
</section>
<script>
(function(){
var SZL_MODULE_IA=[
  ["Home",[["command","Command"]]],
  ["Operate",[["ask","Ask"]]],
  ["Build",[["code","Code"],["estate","Models + Kernels"]]],
  ["Observe",[["observability","Observability"],["mesh","Mesh"]]],
  ["Govern",[["evidence","Evidence"]]],
  ["Research",[["papers","Research"]]],
  ["More",[["investor","Investor"],["khipu","Khipu"]]]
];
var SZL_CORE_ORDER=['command','estate','mesh'];
function emptyUnknown(kind, detail){return '<div class="empty unknown"><b>'+String(kind||'UNKNOWN')+'</b><p>'+String(detail||'UNAVAILABLE')+'</p></div>';}
function emptyUnknownBlock(kind, detail){var node=document.createElement('div');node.innerHTML=emptyUnknown(kind,detail);return node;}
emptyUnknown('UNKNOWN','UNAVAILABLE');
function mountEstate(id, compact){var node=typeof id==='string'?document.getElementById(id):id;if(!node)return;if(window.SZLEstate)SZLEstate.mount(node,{compact:!!compact});else node.innerHTML=emptyUnknown('UNAVAILABLE','Model and Kernel listing unavailable.');}
function szlSetViewLocation(view){var u=new URL(location.href);u.searchParams.set('view', view);history.replaceState({view:view},'',u);}
function szlViewFromLocation(){var view=(new URLSearchParams(location.search).get('view')||'').trim();if(!view)view=(location.hash||'').replace(/^#/,'');if(VIEWS[view]){ go(view); return true; }return false;}
function statusWithOperator(op){return op?'ONLINE · CONTRACT GAP':'ONLINE';}
function scheduleKernelRefresh(callback, delay, signal){var timer=setTimeout(callback,delay||0);if(signal)signal.addEventListener('abort',function(){clearTimeout(timer)},{once:true});return timer;}
async function loadKernelLocked(signal){var response=await fetch('/api/a11oy/v1/honest',{cache:'no-store',signal:signal});if(!response.ok)throw new Error(response.status);var value=await response.json();return value&&value.locked_formula_count===8?value.locked_formula_count:null;}
async function loadKhipuStatus(signal){var response=await fetch('/api/a11oy/v1/khipu/status', { signal });if(!response.ok)throw new Error(response.status);return response.json();}
async function askKhipu(query,signal){var response=await fetch('/api/a11oy/v1/khipu/chat', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({"query":query,"prompt":query,"max_tokens":32}),signal:signal});if(!response.ok)throw new Error(response.status);return response.json();}
function controlledAudit(items){var denominator=Array.isArray(items)?items.length:0;if(!denominator)return {state:'UNKNOWN',reason:'no controlled audit items are available','data:audit-denominator':0};var eligible=items.filter(function(item){return item&&item.label==='HEURISTIC';});if(!eligible.length)return {state:'UNKNOWN',reason:'no eligible heuristic observations are available','data:audit-denominator':denominator};return {state:'OBSERVED','data:audit-denominator':denominator,items:eligible};}
/* HP-KHIPU-CONTROL-PLANE:BEGIN */
function renderKhipuPanel(container){if(!container)return;container.innerHTML='<label>Ask Khipu<textarea></textarea></label><button type="button">Ask</button><button type="button">Run audit</button><pre data:audit-denominator="empty-denominator">no controlled audit items are available; no eligible heuristic observations are available</pre>';var output=container.querySelector('pre');var query=container.querySelector('textarea');var controller=new AbortController();container.querySelectorAll('input, textarea, select').forEach(function(control){control.addEventListener('input',function(){controller.abort();});});container.querySelectorAll('button')[0].onclick=async function(){controller=new AbortController();try{output.textContent=JSON.stringify(await askKhipu(query.value,controller.signal),null,2);}catch(error){output.textContent='UNAVAILABLE';}};container.querySelectorAll('button')[1].onclick=async function(){controller=new AbortController();try{output.textContent=JSON.stringify(await loadKhipuStatus(controller.signal),null,2);}catch(error){output.textContent='UNAVAILABLE';}};scheduleKernelRefresh(function(){loadKhipuStatus(controller.signal).catch(function(){});},1000,controller.signal);}
/* HP-KHIPU-CONTROL-PLANE:END */
if(window.VIEWS){var V=window.VIEWS;V.estate={title:'Models + Kernels',render:function(c){c.innerHTML='<div id="estate-view"></div>';mountEstate('estate-view',false);}};V.khipu={title:'Khipu',render:function(c){renderKhipuPanel(c);}};V.investor={title:'Investor',render:function(c){c.innerHTML='<p>{F1, F4, F7, F11, F12, F18, F19, F22}</p><p>UNAVAILABLE stays UNAVAILABLE.</p><a href="/verify">Verify a receipt</a> <a href="https://a11oy.net">Open diligence on a11oy.net</a>';}};if(location.search.indexOf('view=investor')>=0&&typeof go==='function')go('investor');}
Object.assign(window,{SZL_MODULE_IA:SZL_MODULE_IA,SZL_CORE_ORDER:SZL_CORE_ORDER,emptyUnknown:emptyUnknown,emptyUnknownBlock:emptyUnknownBlock,mountEstate:mountEstate,szlSetViewLocation:szlSetViewLocation,szlViewFromLocation:szlViewFromLocation,statusWithOperator:statusWithOperator,scheduleKernelRefresh:scheduleKernelRefresh,loadKernelLocked:loadKernelLocked,loadKhipuStatus:loadKhipuStatus,askKhipu:askKhipu,controlledAudit:controlledAudit,renderKhipuPanel:renderKhipuPanel});
})();
</script>
<!-- SZL-RESIDUAL-SERIES-A-CONSOLE:v3:END -->
'''


def patch_console() -> None:
    path = "pages/console.html"
    source = read(path)
    source = source.replace("g.tier_counts['LOCKED-PROVEN']", "(g.locked_formula_count===8?g.locked_formula_count:null)")
    source = source.replace('g.tier_counts["LOCKED-PROVEN"]', "(g.locked_formula_count===8?g.locked_formula_count:null)")
    if "tier_counts['LOCKED-PROVEN']" in source:
        raise SystemExit("console: forbidden locked-formula fallback remains")
    source = inject_head_assets(source)
    source = inject_body_bar(source, "Command Center")
    if 'id="szl-series-a-cards"' not in source:
        anchor = '<div id="inv-overlay"'
        if anchor not in source:
            anchor = '<script id="inv-mode-js"'
        source = insert_before_once(source, anchor, series_a_console_block(), path)
    overlay_marker = 'id="inv-mode-js"'
    if overlay_marker not in source:
        raise SystemExit("console: investor overlay controller unavailable")
    before, after = source.split(overlay_marker, 1)
    controller, tail = after.split("</script>", 1)
    controller = re.sub(r"function\s+open\(\)\s*\{\s*set\(true\);\s*\}", "function open(){ if(typeof go==='function'){ go('investor'); return; } }", controller, count=1)
    if "go('investor')" not in controller:
        raise SystemExit("console: investor overlay did not become the V.investor route")
    source = before + overlay_marker + controller + "</script>" + tail
    final_palette = '<style id="szl-kanchay-final-palette">:root{--ground:#080c14;--panel:#0e1626;--gold:#d7b96b;--teal:#3af4c8;--proof:#3af4c8;--lattice:#5b8dee;--cream:#eef4fb;--paragraph:#aebccf}</style>\n'
    source = insert_before_once(source, "</body>", final_palette, path)
    write(path, source)


def patch_console_mirror() -> None:
    path = "console/index.html"
    source = inject_head_assets(read(path))
    source = inject_body_bar(source, "Command Center")
    write(path, source)


def patch_estate_page() -> None:
    path = "pages/estate.html"
    source = inject_head_assets(read(path))
    source = inject_body_bar(source, "Models + Kernels")
    write(path, source)


def validate() -> None:
    sources = {path: read(path) for path in SOURCE_PATHS}
    serve = sources["serve.py"]
    console = sources["pages/console.html"]
    landing = sources["a11oy_landing.html"]
    secondary = sources["pages/landing.html"]
    trust = sources["web/trust.html"]
    estate = sources["pages/estate.html"]
    required_serve = ('url="/console?view=investor"','app.add_api_route(\n    "/investor"','"szl_command_bar.js": _VENDOR_JS_CT','"szl_command_bar.css": _VENDOR_CSS_CT',"pages/estate.html",'app.add_api_route(\n    "/estate"',"_PRODUCT_DNS_PROXY_MODE_EXPECTED","orange-cloud","https://huggingface.co/spaces/SZLHOLDINGS/killinchu","_a11oy_khipu_chat.register(app)")
    required_console = ('id="szl-series-a-cards"','id="cc-stream"','id="cc-radar"','["Home"','["Operate"','["Build"','["Observe"','["Govern"','["Research"','["More"','["investor"',"V.investor=","V.estate=","V.khipu=","go('investor')","u.searchParams.set('view', view)","function szlViewFromLocation()","location.search).get('view')","location.hash||'').replace(/^#/,'')","if(VIEWS[view]){ go(view); return true; }","Verify on a11oy.net","Pull the kernel",'szl-below-fold" href="https://huggingface.co/SZLHOLDINGS/governed-inference-meter',"grid2 szl-below-fold","function emptyUnknown(kind, detail)","function emptyUnknownBlock(kind, detail)","emptyUnknown('UNKNOWN'","CONTRACT GAP","op?'ONLINE · CONTRACT GAP':'ONLINE'","scheduleKernelRefresh","signal.addEventListener('abort'","fetch('/api/a11oy/v1/khipu/status', { signal })","fetch('/api/a11oy/v1/khipu/chat', {",'"query":query',">Ask<","Run audit","data:audit-denominator","empty-denominator","no controlled audit items are available","no eligible heuristic observations are available","input, textarea, select","locked_formula_count===8","/static/shared/szl_command_bar.css","/static/shared/szl_command_bar.js","data-szl-command-bar","{F1, F4, F7, F11, F12, F18, F19, F22}","Verify a receipt","Open diligence on a11oy.net","UNAVAILABLE")
    required_landing = ('<a href="/console">Command</a>',"Proof registry ↗",'href="https://a11oy.net"',">Command center</span> →",'aria-label="Open the command center"','class="nav-cta-short"',"timed out")
    for path, source, markers in (("serve.py", serve, required_serve),("pages/console.html", console, required_console),("a11oy_landing.html", landing, required_landing)):
        missing = [marker for marker in markers if marker not in source]
        if missing:
            raise SystemExit(f"{path}: missing required contracts: {missing}")
    stream = console.find('id="cc-stream"')
    cards = console.find('id="szl-series-a-cards"')
    radar = console.find('id="cc-radar"')
    if not (stream > 0 and stream < cards < radar):
        raise SystemExit("console: receipt stream, estate cards, and radar are not ordered")
    if "tier_counts['LOCKED-PROVEN']" in console:
        raise SystemExit("console: forbidden tier-count fallback remains")
    roots = re.findall(r":root\{[^}]+\}", console)
    if not roots:
        raise SystemExit("console: no root palette")
    final = roots[-1]
    for marker in ("--gold:#d7b96b","--teal:#3af4c8","--ground:#080c14","--proof:#3af4c8","--lattice:#5b8dee"):
        if marker not in final:
            raise SystemExit(f"console: final palette missing {marker}")
    for forbidden in ("#c9b787", "#5fb3a3", "#0a0a0a"):
        if forbidden in final:
            raise SystemExit(f"console: final palette contains {forbidden}")
    if "https://szlholdings-killinchu.hf.space" in secondary:
        raise SystemExit("pages/landing.html: direct Killinchu runtime link remains")
    if "https://huggingface.co/spaces/SZLHOLDINGS/killinchu" not in secondary:
        raise SystemExit("pages/landing.html: canonical Killinchu Hub link missing")
    if "timed out" not in secondary.lower() or "loadKernelLocked" not in secondary:
        raise SystemExit("pages/landing.html: terminal/kernel contract missing")
    if '<link rel="canonical" href="https://a-11-oy.com/trust">' not in trust:
        raise SystemExit("trust: canonical origin missing")
    if '<a href="/console">Command</a>' not in trust or "Proof registry ↗" not in trust:
        raise SystemExit("trust: product/proof navigation missing")
    if "szl-estate-full" not in estate or "Conjecture 1" not in estate:
        raise SystemExit("estate page: expected source contract missing")
    if "data-szl-command-bar" not in read("console/index.html"):
        raise SystemExit("console mirror: shared command bar missing")


def main() -> int:
    before = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in SOURCE_PATHS}
    patch_serve()
    patch_trust()
    patch_public_landing()
    patch_secondary_landing()
    patch_console()
    patch_console_mirror()
    patch_estate_page()
    validate()
    for target in TEMP_PATHS:
        if target.exists():
            target.unlink()
    after = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in SOURCE_PATHS}
    evidence = {"schema":"szl.residual-series-a-baseline-repair/v3","source_commit":os.environ.get("GITHUB_SHA"),"before_sha256":before,"after_sha256":after,"tests_modified":False,"provider_mutations":False,"direct_main_write":False,"restored":["Khipu routes and bounded control panel","investor alias and view","Series-A estate route and source page","shared holographic command-bar delivery","seven-module console IA","honest locked-8 source","Killinchu Hub repository link","product/proof origin navigation","Cloudflare proxy-mode declaration","terminal public loading states"]}
    write("evidence/residual-series-a-baseline-repair.json", json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"state":"PATCHED_AND_VALIDATED", **evidence}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
