#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Bounded shell/System Health fixture QA; no external or production requests."""
import argparse
import hashlib
import json
import subprocess
import threading
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright
from test_console_mobile_integrity import StaticHandler, ROOT

WIDTHS = (375, 390, 768, 1280, 1920)
MEASURE = r"""() => {
  const scope='.szl-hbar,.side,.szl-pal,.content';
  function visible(e) {
    if (!e.getClientRects().length || e.closest('[inert]')) return false;
    let r=e.getBoundingClientRect();
    if (r.width===0 || r.height===0 || r.bottom<=0 || r.top>=innerHeight || r.right<=0 || r.left>=innerWidth) return false;
    for(let p=e;p;p=p.parentElement) {
      let c=getComputedStyle(p);
      if(c.visibility==='hidden'||c.display==='none'||Number(c.opacity)===0) return false;
      if(p!==e && /hidden|clip|auto|scroll/.test(c.overflow+c.overflowX+c.overflowY)) {
        let q=p.getBoundingClientRect();
        if(r.right<=q.left||r.left>=q.right||r.bottom<=q.top||r.top>=q.bottom) return false;
      }
    }
    return true;
  }
  const canvas=document.createElement('canvas'),ctx=canvas.getContext('2d');
  function color(s) { ctx.clearRect(0,0,1,1);ctx.fillStyle=s;ctx.fillRect(0,0,1,1);return [...ctx.getImageData(0,0,1,1).data].map((v,i)=>i===3?v/255:v); }
  function over(a,b) {let t=a[3]+b[3]*(1-a[3]);return [0,1,2].map(i=>(a[i]*a[3]+b[i]*b[3]*(1-a[3]))/t).concat(t);}
  function bg(e) {let chain=[];for(let p=e;p;p=p.parentElement)chain.unshift(p);return chain.reduce((b,p)=>over(color(getComputedStyle(p).backgroundColor),b),[255,255,255,1]);}
  function lum(c) {return c.slice(0,3).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);}
  let texts=[],targets=[],gradients=[];
  document.querySelectorAll(scope).forEach(root=>[root,...root.querySelectorAll('*')].forEach(e=>{
    if(!visible(e))return;
    let c=getComputedStyle(e);
    if(c.backgroundImage!=='none')gradients.push({element:e.className,image:c.backgroundImage});
    if([...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())) {
      let b=bg(e),f=over(color(c.color),b),l1=lum(f),l2=lum(b);
      texts.push({text:e.textContent.trim().slice(0,90),ratio:(Math.max(l1,l2)+.05)/(Math.min(l1,l2)+.05),foreground:c.color,background:b});
    }
    if(e.matches('a[href],button,input,select,[role="button"]')&&!e.disabled) {
      let r=e.getBoundingClientRect();targets.push({text:(e.getAttribute('aria-label')||e.textContent).trim().slice(0,80),width:r.width,height:r.height});
    }
  }));
  for(const e of document.querySelectorAll('html,body,.app,.content')) {
    for(const pseudo of [null,'::before','::after']) {
      const c=getComputedStyle(e,pseudo);
      if(c.display!=='none'&&c.backgroundImage!=='none')gradients.push({element:e.tagName+(pseudo||''),image:c.backgroundImage});
    }
  }
  const active=document.activeElement,style=getComputedStyle(active),background=bg(active.parentElement||active);
  const ring=lum(over(color(style.outlineColor),background)),ground=lum(background);
  const focus={width:parseFloat(style.outlineWidth),ratio:(Math.max(ring,ground)+.05)/(Math.min(ring,ground)+.05)};
  return {texts,targets,gradients,focus};
}"""

def run(output):
    output.mkdir(parents=True, exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),StaticHandler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    origin='http://127.0.0.1:'+str(server.server_port)
    checks=[]; requests=[]; errors=[]; measurements=[]; state={'mode':'rows'}
    def check(name, passed, detail=None):
        checks.append({'name':name,'passed':bool(passed),'detail':detail})
    def intercept(route):
        req=route.request; url=urlsplit(req.url); local=req.url.startswith(origin+'/')
        if local and req.method=='GET' and (url.path in ('/console','/console/') or url.path.startswith(('/assets/','/vendor/','/static/shared/'))):
            route.continue_(); return
        requests.append({'path':url.path,'query':url.query,'method':req.method,'local':local})
        data=None
        if local and req.method=='GET':
            if url.path=='/healthz': data={'status':'ok'}
            elif url.path=='/api/a11oy/v1/honest': data={'locked_formula_count':8}
            elif url.path=='/api/a11oy/v1/lambda': data={'lambda':.9191}
            elif url.path=='/api/a11oy/v1/wow/ledger' and parse_qs(url.query).get('advance')==['0']: data={'receipts':[],'chain_depth':0}
            elif url.path=='/api/a11oy/v1/observability/summary':
                data={'source':'LOCAL TEST FIXTURE','capabilities':[
                    {'name':'TEST FIXTURE · Registry','status':'ok','latency_ms':0},
                    {'name':'TEST FIXTURE · History','status':'unavailable'},
                    {'name':'TEST FIXTURE · Queue','status':'degraded','latency_ms':12},
                    {'name':'TEST FIXTURE · Archive','status':'down'},
                ]}
                if state['mode']=='empty': data['capabilities']=[]
                elif state['mode']=='malformed': data={}
                elif state['mode']=='error': data=None
        route.fulfill(status=200 if data is not None else 503,content_type='application/json',body=json.dumps(data if data is not None else {'state':'UNAVAILABLE','source':'TEST: blocked request'}))
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',headless=True,args=['--disable-gpu'])
            context=browser.new_context(viewport={'width':390,'height':1000},reduced_motion='reduce',color_scheme='dark',service_workers='block')
            context.route('**/*',intercept)
            page=context.new_page(); page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(origin+'/console?view=fleet',wait_until='load',timeout=60000)
            page.wait_for_selector('.health-list'); page.wait_for_timeout(600)
            check('System Health URL retained',page.url.endswith('/console?view=fleet'))
            initial_links=page.locator('.szl-hbar a').evaluate_all('(es)=>es.map(e=>e.getAttribute("href"))')
            for theme in ('dark','light'):
                if page.locator('html').get_attribute('data-surface')!=theme: page.locator('.szl-theme-toggle').click()
                for width in WIDTHS:
                    page.set_viewport_size({'width':width,'height':1000}); page.wait_for_timeout(150)
                    name=f'{theme}/{width}'
                    check(name+' theme applied',page.locator('html').get_attribute('data-surface')==theme)
                    size=page.evaluate('({width:innerWidth,document:document.documentElement.scrollWidth,content:document.querySelector(".content").scrollWidth,client:document.querySelector(".content").clientWidth})')
                    check(name+' containment',size['document']<=width+1 and size['content']<=size['client']+1,size)
                    m=page.evaluate(MEASURE)
                    measurements.append({'case':name,**m})
                    bad=[t for t in m['texts'] if t['ratio']<4.5]
                    check(name+' visible text contrast >=4.5',bool(m['texts']) and not bad,bad)
                    bad=[t for t in m['targets'] if t['width']<43.99 or t['height']<43.99]
                    check(name+' visible targets >=44px',bool(m['targets']) and not bad,bad)
                    check(name+' no decorative gradients',not m['gradients'],m['gradients'])
                    check(name+' truthful observation labels','latency unavailable' in page.locator('#fl-grid').inner_text() and '0 ms' in page.locator('#fl-grid').inner_text() and 'Delivery classification: UNKNOWN' in page.locator('.health-evidence').inner_text())
                    page.locator('.health-note').scroll_into_view_if_needed()
                    bottom=page.evaluate(MEASURE); measurements.append({'case':name+'/below-fold',**bottom})
                    check(name+' below-fold text contrast >=4.5',all(t['ratio']>=4.5 for t in bottom['texts']),[t for t in bottom['texts'] if t['ratio']<4.5])
                    page.locator('.view-title').evaluate('(e)=>{for(let p=e;p;p=p.parentElement)p.scrollTop=0;window.scrollTo(0,0)}')
                    page.screenshot(path=str(output/f'health-{theme}-{width}.png'),full_page=False)
                page.set_viewport_size({'width':390,'height':1000})
                trigger=page.locator('.menu-btn'); trigger.focus(); page.keyboard.press('Enter')
                check(theme+' drawer opens by keyboard',trigger.get_attribute('aria-expanded')=='true')
                check(theme+' drawer focus contained',page.evaluate('document.activeElement.closest(".side")!==null'))
                dm=page.evaluate(MEASURE); measurements.append({'case':theme+'/drawer',**dm})
                check(theme+' drawer text contrast',all(t['ratio']>=4.5 for t in dm['texts']),[t for t in dm['texts'] if t['ratio']<4.5])
                check(theme+' drawer targets',all(t['width']>=43.99 and t['height']>=43.99 for t in dm['targets']),[t for t in dm['targets'] if t['width']<43.99 or t['height']<43.99])
                page.keyboard.press('Escape'); check(theme+' drawer restores focus',trigger.evaluate('(e)=>e===document.activeElement'))
                page.keyboard.press('Control+k'); page.wait_for_selector('.szl-pal-ov.open')
                page.locator('.szl-pal input').fill('receipt')
                results=page.evaluate(MEASURE); measurements.append({'case':theme+'/palette-results',**results})
                check(theme+' palette result contrast',all(t['ratio']>=4.5 for t in results['texts']),[t for t in results['texts'] if t['ratio']<4.5])
                check(theme+' palette result targets',all(t['width']>=43.99 and t['height']>=43.99 for t in results['targets']),[t for t in results['targets'] if t['width']<43.99 or t['height']<43.99])
                page.locator('.szl-pal input').fill('no_such_fixture_command')
                page.keyboard.press('Shift+Tab')
                check(theme+' palette reverse tab trapped',page.evaluate('document.activeElement.matches(".szl-pal-close")'))
                pm=page.evaluate(MEASURE); measurements.append({'case':theme+'/palette',**pm})
                check(theme+' palette contrast',all(t['ratio']>=4.5 for t in pm['texts']),[t for t in pm['texts'] if t['ratio']<4.5])
                check(theme+' keyboard focus visible >=3:1',pm['focus']['width']>=2 and pm['focus']['ratio']>=3,pm['focus'])
                page.keyboard.press('Escape'); check(theme+' palette restores focus',trigger.evaluate('(e)=>e===document.activeElement'))
                more=page.locator('.szl-more');more.focus();page.keyboard.press('ArrowDown')
                check(theme+' More keyboard menu',more.get_attribute('aria-expanded')=='true' and page.evaluate('document.activeElement.closest(".szl-overflow-menu")!==null'))
                page.keyboard.press('Escape');check(theme+' More restores focus',more.evaluate('(e)=>e===document.activeElement'))
                check(theme+' reduced motion',page.evaluate('!document.getAnimations().some(a=>a.playState==="running"&&a.effect&&a.effect.target.closest(".szl-hbar,.side,.content"))'))
                theme_btn=page.locator('.szl-theme-toggle'); theme_btn.focus(); page.keyboard.press('Enter'); page.keyboard.press('Enter')
                check(theme+' theme keyboard toggle',page.locator('html').get_attribute('data-surface')==theme)
            page.reload(wait_until='load'); page.wait_for_selector('.health-list')
            check('explicit light preference survives reload',page.locator('html').get_attribute('data-surface')=='light')
            page.evaluate('localStorage.removeItem("szl.console.theme")');page.emulate_media(color_scheme='dark')
            page.reload(wait_until='load');page.wait_for_selector('.health-list')
            check('system dark theme without saved preference',page.locator('html').get_attribute('data-surface')=='dark')
            page.emulate_media(color_scheme='light');page.wait_for_timeout(100)
            check('system light theme change followed',page.locator('html').get_attribute('data-surface')=='light')
            for mode in ('empty','malformed','error'):
                state['mode']=mode; page.evaluate('go("fleet")'); page.wait_for_timeout(300)
                check(mode+' observation state',('EMPTY' if mode=='empty' else 'unavailable') in page.locator('#fl-grid').inner_text())
            check('navigation URLs unchanged by theme',initial_links==page.locator('.szl-hbar a').evaluate_all('(es)=>es.map(e=>e.getAttribute("href"))'))
            led=[r for r in requests if r['path'].endswith('/wow/ledger')]
            check('ledger reads passive',bool(led) and all(parse_qs(r['query']).get('advance')==['0'] for r in led))
            check('no mutation requests',all(r['method']=='GET' for r in requests))
            browser.close()
    except Exception as exc:
        errors.append(str(exc))
        print(json.dumps({'error':str(exc),'page_errors':errors,'requests':requests[-10:]}))
        raise
    finally:
        server.shutdown()
        files=('pages/console.html','static/shared/szl_command_bar.js','console/assets/szl-console-focus.css','scripts/test_console_focused_theme.py')
        git=['git','-c','safe.directory='+ROOT.as_posix()]
        report={'commit':subprocess.check_output(git+['rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                'working_tree_dirty':bool(subprocess.check_output(git+['status','--porcelain'],cwd=ROOT,text=True).strip()),
                'source':'LOCAL LABELLED FIXTURES; not production readiness or WCAG certification',
                'scope':['shared console shell','System Health (fleet)'],'widths':WIDTHS,'themes':['dark','light'],
                'checks':checks,'browser_errors':errors,'measurements':measurements,'requests':requests,
                'file_sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files},
                'lighthouse':{'status':'NOT_RUN','reason':'No installed Lighthouse tool identified; no downloads authorized.'}}
        (output/'focused-browser-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    failures=[c for c in checks if not c['passed']]
    print(json.dumps({'checks':len(checks),'failures':failures,'browser_errors':errors}))
    return bool(failures or errors)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    raise SystemExit(run(parser.parse_args().output))
