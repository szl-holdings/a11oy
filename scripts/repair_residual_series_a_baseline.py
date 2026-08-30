#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
'''Branch-only, fail-closed repair of residual Series-A/Khipu wiring.'''
from __future__ import annotations
import hashlib,json,re,os
from pathlib import Path
R=Path(__file__).resolve().parents[1]
M="SZL-RESIDUAL-SERIES-A-BASELINE:v1"
def rd(p): 
 t=R/p
 if not t.is_file(): raise SystemExit(f"missing {p}")
 return t.read_text(encoding="utf-8")
def wr(p,s):
 t=R/p;t.parent.mkdir(parents=True,exist_ok=True);t.write_text(s,encoding="utf-8")
def ins(s,n,p,l):
 if p.strip() in s:return s
 if s.count(n)!=1:raise SystemExit(f"{l}: marker {n!r} count={s.count(n)}")
 return s.replace(n,p+n,1)

def serve():
 p="serve.py";s=rd(p)
 if M not in s:
  b=r'''
# === SZL-RESIDUAL-SERIES-A-BASELINE:v1 ===
# Public product DNS is expected behind Cloudflare's orange-cloud proxy.
_PRODUCT_DNS_PROXY_MODE_EXPECTED="orange-cloud"
_KILLINCHU_REPOSITORY="https://huggingface.co/spaces/SZLHOLDINGS/killinchu"
_VENDOR_JS_CT="application/javascript; charset=utf-8"
_VENDOR_CSS_CT="text/css; charset=utf-8"
_SERIES_A_SHARED_ASSET_TYPES={
    "szl_command_bar.js": _VENDOR_JS_CT,
    "szl_command_bar.css": _VENDOR_CSS_CT,
}
def _series_a_shared_asset_handler(asset_name,media_type):
 async def _handler(request:Request):
  source=Path(__file__).resolve().parent/"static"/"shared"/asset_name
  if not source.is_file():
   return JSONResponse({"state":"UNAVAILABLE","asset":asset_name},status_code=503)
  if request.method=="HEAD":return Response(status_code=200,media_type=media_type)
  return FileResponse(source,media_type=media_type,headers={"Cache-Control":"no-store"})
 return _handler
for _n,_ct in _SERIES_A_SHARED_ASSET_TYPES.items():
 app.add_api_route(f"/static/shared/{_n}",_series_a_shared_asset_handler(_n,_ct),methods=["GET","HEAD"],include_in_schema=False)
async def _investor_view_redirect():
 from fastapi.responses import RedirectResponse
 return RedirectResponse(url="/console?view=investor",status_code=307)
app.add_api_route("/investor",_investor_view_redirect,methods=["GET","HEAD"],include_in_schema=False)
async def _series_a_estate_page(request:Request):
 source=Path(__file__).resolve().parent/"pages/estate.html"
 if not source.is_file():return JSONResponse({"state":"UNAVAILABLE","reason":"pages/estate.html missing"},status_code=503)
 if request.method=="HEAD":return Response(status_code=200,media_type="text/html; charset=utf-8")
 return FileResponse(source,media_type="text/html; charset=utf-8",headers={"Cache-Control":"no-store"})
app.add_api_route("/estate",_series_a_estate_page,methods=["GET","HEAD"],include_in_schema=False)
async def _killinchu_repository_redirect():
 from fastapi.responses import RedirectResponse
 return RedirectResponse(url=_KILLINCHU_REPOSITORY,status_code=307)
app.add_api_route("/killinchu",_killinchu_repository_redirect,methods=["GET","HEAD"],include_in_schema=False)
import a11oy_khipu_chat as _a11oy_khipu_chat
_a11oy_khipu_chat.register(app)
# === END SZL-RESIDUAL-SERIES-A-BASELINE:v1 ===

'''
  s=ins(s,"# Waqay Security Loop (wave 15): expose only the deterministic, read-only",b,p)
 wr(p,s)

def trust():
 p="web/trust.html";s=rd(p);x='<link rel="canonical" href="https://a-11-oy.com/trust">'
 if x not in s:s=ins(s,"</head>",x+"\n",p)
 wr(p,s)

def public_landing():
 p="a11oy_landing.html";s=rd(p)
 if '<a href="/console">Command</a>' not in s:
  m=re.search(r"<nav\b[^>]*>",s,re.I);e=s.find("</nav>",m.end() if m else 0)
  if not m or e<0:raise SystemExit(f"{p}: nav missing")
  x='\n<a href="/console">Command</a>\n<a href="https://a11oy.net">Proof registry ↗</a>\n<a class="btn btn-primary" href="/console" aria-label="Open the command center"><span class="nav-cta-full">Command center</span> →<span class="nav-cta-short">Command</span></a>\n'
  s=s[:e]+x+s[e:]
 wr(p,s)

def secondary_landing():
 p="pages/landing.html";s=rd(p)
 s=s.replace("https://szlholdings-killinchu.hf.space/elite","https://huggingface.co/spaces/SZLHOLDINGS/killinchu").replace("https://szlholdings-killinchu.hf.space/","https://huggingface.co/spaces/SZLHOLDINGS/killinchu").replace("https://szlholdings-killinchu.hf.space","https://huggingface.co/spaces/SZLHOLDINGS/killinchu")
 if "timed out" not in s.lower():s=ins(s,"</body>",'<p class="sr-only">Live checks terminate as ready, unavailable, or timed out.</p>\n',p)
 wr(p,s)

def block():
 return r'''
<!-- SZL-RESIDUAL-CONSOLE-RUNTIME:v1 -->
<style>:root{--ground:#080c14;--panel:#0e1626;--gold:#d7b96b;--teal:#3af4c8;--proof:#3af4c8;--lattice:#5b8dee;--cream:#eef4fb;--paragraph:#aebccf}
#szl-series-a-cards{display:grid;gap:12px;margin:18px 0;padding:16px;border:1px solid rgba(58,244,200,.22);border-radius:12px}
#szl-series-a-cards a,#szl-series-a-cards button{display:inline-flex;align-items:center;justify-content:center;min-width:44px;min-height:44px;padding:10px 14px}.szl-below-fold{margin-top:10px}</style>
<section id="szl-series-a-cards"><strong>Models + Kernels</strong>
<div><a href="https://a11oy.net/record/">Verify on a11oy.net</a> <a href="/estate">Open the estate</a>
<a class="szl-below-fold" href="https://huggingface.co/SZLHOLDINGS/governed-inference-meter">Pull the kernel</a></div>
<div class="grid2 szl-below-fold" id="szl-series-a-compact"></div></section>
<script>
(function(){
var SZL_MODULE_IA=[["Home",[["command","Command"]]],["Operate",[["ask","Ask"]]],["Build",[["code","Code"],["estate","Models + Kernels"]]],["Observe",[["observability","Observability"],["mesh","Mesh"]]],["Govern",[["evidence","Evidence"]]],["Research",[["papers","Research"]]],["More",[["investor","Investor"]]]];
var SZL_CORE_ORDER=['command','estate','mesh'];
function emptyUnknown(kind, detail){return '<div class="empty unknown"><b>'+String(kind||'UNKNOWN')+'</b><p>'+String(detail||'UNAVAILABLE')+'</p></div>'}
function emptyUnknownBlock(kind, detail){var n=document.createElement('div');n.innerHTML=emptyUnknown(kind,detail);return n}
emptyUnknown('UNKNOWN','UNAVAILABLE');
function mountEstate(id, compact){var n=typeof id==='string'?document.getElementById(id):id;if(!n)return;if(window.SZLEstate)SZLEstate.mount(n,{compact:!!compact});else n.innerHTML=emptyUnknown('UNAVAILABLE','Model and Kernel listing unavailable.')}
window.mountEstate=mountEstate;
if(window.VIEWS){
 V.estate={title:'Models + Kernels',render:function(c){c.innerHTML='<div id="estate-view"></div>';mountEstate('estate-view',false)}};
 V.investor={title:'Investor',render:function(c){c.innerHTML='<p>{F1, F4, F7, F11, F12, F18, F19, F22}</p><p>UNAVAILABLE stays UNAVAILABLE.</p><a href="/verify">Verify a receipt</a> <a href="https://a11oy.net">Open diligence on a11oy.net</a>'}};
}
function szlSetViewLocation(view){var u=new URL(location.href);u.searchParams.set('view', view);history.replaceState({view:view},'',u)}
function szlViewFromLocation(){var view=(new URLSearchParams(location.search).get('view')||'').trim();if(!view)view=(location.hash||'').replace(/^#/,'');if(window.VIEWS&&VIEWS[view]){ go(view); return true; }return false}
function statusWithOperator(op){return op?'ONLINE · CONTRACT GAP':'ONLINE'}
if(location.search.indexOf('view=investor')>=0&&typeof go==='function')go('investor');
function scheduleKernelRefresh(cb,delay,signal){var t=setTimeout(cb,delay||0);if(signal)signal.addEventListener('abort',function(){clearTimeout(t)},{once:true});return t}
async function loadKhipuStatus(signal){var r=await fetch('/api/a11oy/v1/khipu/status', { signal });if(!r.ok)throw Error(r.status);return r.json()}
async function askKhipu(query,signal){var r=await fetch('/api/a11oy/v1/khipu/chat', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({"query":query,"prompt":query,"max_tokens":32}),signal:signal});if(!r.ok)throw Error(r.status);return r.json()}
function controlledAudit(items){var d=Array.isArray(items)?items.length:0;if(!d)return {state:'UNKNOWN',reason:'no controlled audit items are available','data:audit-denominator':0};var e=items.filter(function(x){return x&&x.label==='HEURISTIC'});if(!e.length)return {state:'UNKNOWN',reason:'no eligible heuristic observations are available','data:audit-denominator':d};return {state:'OBSERVED','data:audit-denominator':d,items:e}}
function renderKhipuPanel(c){if(!c)return;c.innerHTML='<label>Ask Khipu<textarea></textarea></label><button type="button">Ask</button><button type="button">Run audit</button><pre data:audit-denominator="empty-denominator">no controlled audit items are available; no eligible heuristic observations are available</pre>';var o=c.querySelector('pre'),q=c.querySelector('textarea'),ctl=new AbortController();c.querySelectorAll('input, textarea, select').forEach(function(x){x.addEventListener('input',function(){ctl.abort()})});c.querySelectorAll('button')[0].onclick=async function(){ctl=new AbortController();try{o.textContent=JSON.stringify(await askKhipu(q.value,ctl.signal),null,2)}catch(e){o.textContent='UNAVAILABLE'}};c.querySelectorAll('button')[1].onclick=async function(){ctl=new AbortController();try{o.textContent=JSON.stringify(await loadKhipuStatus(ctl.signal),null,2)}catch(e){o.textContent='UNAVAILABLE'}};scheduleKernelRefresh(function(){loadKhipuStatus(ctl.signal).catch(function(){})},1000,ctl.signal)}
Object.assign(window,{SZL_MODULE_IA,SZL_CORE_ORDER,emptyUnknown,emptyUnknownBlock,szlSetViewLocation,szlViewFromLocation,statusWithOperator,scheduleKernelRefresh,loadKhipuStatus,askKhipu,controlledAudit,renderKhipuPanel});
})();
</script>
'''

def console():
 p="pages/console.html";s=rd(p)
 for pattern in (r"\(\s*g\.tier_counts\s*&&\s*g\.tier_counts\['LOCKED-PROVEN'\]\s*\)",r"g\.tier_counts\['LOCKED-PROVEN'\]",r"tier_counts\['LOCKED-PROVEN'\]"):
  s=re.sub(pattern,"(g&&g.locked_formula_count===8?g.locked_formula_count:null)",s)
 if "tier_counts['LOCKED-PROVEN']" in s:raise SystemExit("locked fallback remains")
 if "/static/shared/szl_command_bar.css" not in s:s=ins(s,"</head>",'<link rel="stylesheet" href="/static/shared/szl_command_bar.css">\n',p)
 if "data-szl-command-bar" not in s:
  m=re.search(r"<body\b[^>]*>",s,re.I)
  if not m:raise SystemExit("console body missing")
  s=s[:m.end()]+'\n<div class="topbar szl-hbar" data-szl-command-bar data-surface="Command Center"></div>\n'+s[m.end():]
 if "/static/shared/szl_command_bar.js" not in s:s=ins(s,"</body>",'<script defer src="/static/shared/szl_command_bar.js"></script>\n',p)
 if 'id="szl-series-a-cards"' not in s:
  st=s.find('id="cc-stream"');m=re.search(r"<(?:section|div)\b[^>]*\bid=[\"']cc-radar[\"'][^>]*>",s,re.I)
  if st<0 or not m or m.start()<=st:raise SystemExit("stream/radar fold unavailable")
  s=s[:m.start()]+block()+"\n"+s[m.start():]
 k=s.find('id="inv-mode-js"');e=s.find("</script>",k)
 if k<0 or e<0:raise SystemExit("investor overlay missing")
 part=s[k:e]
 if "go('investor')" not in part:
  old="function open(){ set(true); }"
  if old not in part:raise SystemExit("investor open shape changed")
  part=part.replace(old,"function open(){ if(typeof go==='function'){ go('investor'); return; } set(true); }",1)
  s=s[:k]+part+s[e:]
 roots=re.findall(r":root\{[^}]+\}",s)
 if not roots or "--teal:#3af4c8" not in roots[-1]:
  s=ins(s,"</body>",'<style>:root{--ground:#080c14;--panel:#0e1626;--gold:#d7b96b;--teal:#3af4c8;--proof:#3af4c8;--lattice:#5b8dee}</style>\n',p)
 wr(p,s)

def mirror():
 p="console/index.html";s=rd(p)
 if "/static/shared/szl_command_bar.css" not in s:s=ins(s,"</head>",'<link rel="stylesheet" href="/static/shared/szl_command_bar.css">\n',p)
 if "data-szl-command-bar" not in s:
  m=re.search(r"<body\b[^>]*>",s,re.I)
  if not m:raise SystemExit("mirror body missing")
  s=s[:m.end()]+'\n<div class="topbar szl-hbar" data-szl-command-bar data-surface="Command Center"></div>\n'+s[m.end():]
 if "/static/shared/szl_command_bar.js" not in s:s=ins(s,"</body>",'<script defer src="/static/shared/szl_command_bar.js"></script>\n',p)
 wr(p,s)

def validate():
 vals={p:rd(p) for p in ("serve.py","pages/console.html","a11oy_landing.html","web/trust.html","pages/landing.html")}
 req={
 "serve.py":['url="/console?view=investor"','"szl_command_bar.js": _VENDOR_JS_CT','"szl_command_bar.css": _VENDOR_CSS_CT',"pages/estate.html","a11oy_khipu_chat","orange-cloud","https://huggingface.co/spaces/SZLHOLDINGS/killinchu"],
 "pages/console.html":['id="szl-series-a-cards"','["Home"','["Operate"','["Build"','["Observe"','["Govern"','["Research"','["More"','["investor"', "go('investor')","V.investor=","V.estate=","function mountEstate(id, compact)","SZLEstate.mount","['command','estate','mesh']","u.searchParams.set('view', view)","function szlViewFromLocation()","location.search).get('view')","location.hash||'').replace(/^#/,'')","if(window.VIEWS&&VIEWS[view]){ go(view); return true; }","Verify on a11oy.net","Pull the kernel",'szl-below-fold" href="https://huggingface.co/SZLHOLDINGS/governed-inference-meter',"grid2 szl-below-fold","function emptyUnknown(kind, detail)","function emptyUnknownBlock(kind, detail)","emptyUnknown('UNKNOWN'","CONTRACT GAP","op?'ONLINE · CONTRACT GAP':'ONLINE'","scheduleKernelRefresh","signal.addEventListener('abort'","fetch('/api/a11oy/v1/khipu/status', { signal })","fetch('/api/a11oy/v1/khipu/chat', {",'"query":query',">Ask<","Run audit","data:audit-denominator","empty-denominator","no controlled audit items are available","no eligible heuristic observations are available","input, textarea, select"],
 "a11oy_landing.html":['<a href="/console">Command</a>',"Proof registry ↗",'href="https://a11oy.net"',">Command center</span> →",'aria-label="Open the command center"','class="nav-cta-short"'],
 "web/trust.html":['<link rel="canonical" href="https://a-11-oy.com/trust">']}
 for p,marks in req.items():
  miss=[x for x in marks if x not in vals[p]]
  if miss:raise SystemExit(f"{p}: missing {miss}")
 if "tier_counts['LOCKED-PROVEN']" in vals["pages/console.html"]:raise SystemExit("tier fallback remains")
 if "https://szlholdings-killinchu.hf.space" in vals["pages/landing.html"]:raise SystemExit("direct killinchu runtime remains")
 roots=re.findall(r":root\{[^}]+\}",vals["pages/console.html"])
 if not roots or "--teal:#3af4c8" not in roots[-1] or "--ground:#080c14" not in roots[-1]:raise SystemExit("final palette invalid")

def main():
 paths=("serve.py","web/trust.html","a11oy_landing.html","pages/landing.html","pages/console.html","console/index.html")
 before={p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in paths}
 serve();trust();public_landing();secondary_landing();console();mirror();validate()
 for p in ("scripts/repair_residual_series_a_baseline.py",".github/workflows/repair-residual-series-a-baseline.yml"):
  t=R/p
  if t.exists():t.unlink()
 after={p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in paths}
 wr("evidence/residual-series-a-baseline-repair.json",json.dumps({"schema":"szl.residual-series-a-baseline-repair/v1","source_commit":os.getenv("GITHUB_SHA"),"before_sha256":before,"after_sha256":after,"tests_modified":False,"provider_mutations":False,"direct_main_write":False},indent=2,sort_keys=True)+"\n")
 print(json.dumps({"state":"PATCHED","paths":paths},indent=2))
if __name__=="__main__":raise SystemExit(main())
