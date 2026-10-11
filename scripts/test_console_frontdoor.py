#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Render the shipped front door against labelled, read-only local fixtures.

Run with --output DIR and optionally CHROME_PATH for an installed Chromium.
This measures presentation and interaction, not live provider readiness.
"""
import argparse
import hashlib
import json
import os
import subprocess
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import sync_playwright
from test_console_mobile_integrity import ROOT, StaticHandler

WIDTHS = (320, 390, 768, 1280, 1920, 2560)


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), StaticHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = 'http://127.0.0.1:' + str(server.server_port)
    checks, errors, requests, measurements = [], [], [], []

    def check(name, passed, detail=None):
        checks.append({'name': name, 'passed': bool(passed), 'detail': detail})

    def intercept(route):
        request = route.request
        url = urlsplit(request.url)
        local = request.url.startswith(origin + '/')
        if local and request.method == 'GET' and (
            url.path in ('/console', '/console/')
            or url.path.startswith(('/assets/', '/vendor/', '/static/shared/'))
        ):
            route.continue_()
            return
        requests.append({'path': url.path, 'query': url.query, 'method': request.method, 'local': local})
        fixtures = {
            '/healthz': {'status': 'ok', 'source': 'LOCAL TEST FIXTURE'},
            '/api/a11oy/v1/honest': {'locked_formula_count': 8, 'source': 'LOCAL TEST FIXTURE'},
            '/api/a11oy/v1/lambda': {'lambda': .9191, 'axes': [], 'source': 'LOCAL TEST FIXTURE'},
            '/api/a11oy/v1/wow/ledger': {'receipts': [], 'chain_depth': 0, 'source': 'LOCAL TEST FIXTURE'},
            '/api/a11oy/v1/observability/summary': {'mesh_reach': {}, 'capabilities': [], 'source': 'LOCAL TEST FIXTURE'},
            '/api/a11oy/v1/energy/operator/status': {'stub_mode': True, 'source': 'LOCAL TEST FIXTURE'},
            '/api/a11oy/v1/policy/decisions/feed': {'verdicts': [], 'total_buffered': 0, 'source': 'LOCAL TEST FIXTURE'},
            '/api/a11oy/v1/gdw/healthz': {'service': 'gdw-frontier', 'write_ready': False,
                'governance_ready': False, 'write_blockers': ['LOCAL FIXTURE'], 'source': 'LOCAL TEST FIXTURE'},
        }
        data = fixtures.get(url.path) if local and request.method == 'GET' else None
        route.fulfill(status=200 if data is not None else 503, content_type='application/json', body=json.dumps(
            data if data is not None else {'state': 'UNAVAILABLE', 'source': 'LOCAL TEST FIXTURE'}))

    try:
        with sync_playwright() as controller:
            browser = controller.chromium.launch(
                executable_path=os.environ.get('CHROME_PATH'), headless=True,
                args=['--disable-dev-shm-usage', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
            context = browser.new_context(viewport={'width': 1280, 'height': 1100}, reduced_motion='reduce',
                                          color_scheme='dark', service_workers='block')
            context.route('**/*', intercept)
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(origin + '/console?view=command', wait_until='load', timeout=60000)
            page.locator('.hero-h1').wait_for()
            page.wait_for_function("document.querySelector('#hero-gate-tag').textContent !== 'PENDING'")
            for theme in ('dark', 'light'):
                if page.locator('html').get_attribute('data-surface') != theme:
                    if not page.locator('.szl-theme-toggle').is_visible():
                        page.locator('.szl-more').click()
                    page.locator('.szl-theme-toggle').click()
                for width in WIDTHS:
                    page.set_viewport_size({'width': width, 'height': 1100})
                    page.locator('.view-title').evaluate('(e)=>{for(let p=e;p;p=p.parentElement)p.scrollTop=0;}')
                    page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
                    name = f'{theme}/{width}'
                    layout = page.evaluate("""() => {
                      const content=document.querySelector('.content'), hero=document.querySelector('.hero');
                      const controls=[...hero.querySelectorAll('a[href],button')].filter(e=>e.getClientRects().length).map(e=>{
                        const r=e.getBoundingClientRect(); return {text:e.textContent.trim(),x:r.x,y:r.y,width:r.width,height:r.height};
                      });
                      const clipped=[];
                      const walker=document.createTreeWalker(hero,NodeFilter.SHOW_TEXT);
                      let n;
                      while((n=walker.nextNode())) {
                        const e=n.parentElement;
                        if(!n.textContent.trim()||e.closest('script,style,svg,[hidden]')||!e.getClientRects().length)continue;
                        const range=document.createRange();range.selectNodeContents(n);
                        for(const r of range.getClientRects()) if(r.left<0||r.right>innerWidth+1) clipped.push(n.textContent.trim());
                      }
                      return {viewport:innerWidth,document:document.documentElement.scrollWidth,
                        content:content.scrollWidth,client:content.clientWidth,controls,clipped,
                        h1:document.querySelectorAll('h1').length,
                        heroSurface:hero.getAttribute('data-surface'),
                        headerHeight:document.querySelector('.szl-hbar').getBoundingClientRect().height,
                        motion:getComputedStyle(hero).animationName,
                        cta:[...document.querySelectorAll('.hero-cta a')].map(e=>({margin:getComputedStyle(e).marginTop,text:e.textContent.trim()}))};
                    }""")
                    measurements.append({'case': name, **layout})
                    check(name + ' contains the document and content', layout['document'] <= width + 1 and layout['content'] <= layout['client'] + 1, layout)
                    check(name + ' keeps all hero text readable', not layout['clipped'], layout['clipped'])
                    check(name + ' touch controls at least44px', all(row['width'] >= 43.99 and row['height'] >= 43.99 for row in layout['controls']), layout['controls'])
                    check(name + ' one page heading and explicit dark hero', layout['h1'] == 1 and layout['heroSurface'] == 'dark')
                    check(name + ' aligned CTA margins', all(row['margin'] == '0px' for row in layout['cta']), layout['cta'])
                    check(name + ' reduced motion', layout['motion'] == 'none')
                    if width <= 820:
                        check(name + ' compact header under200px', layout['headerHeight'] < 200, layout['headerHeight'])
                    if width in (320, 1280, 1920):
                        page.screenshot(path=str(output / f'command-{theme}-{width}.png'))
                page.set_viewport_size({'width': 1280, 'height': 1100})
                material = page.locator('.hero').evaluate("""hero => {
                  const c=getComputedStyle(hero),canvas=document.createElement('canvas'),x=canvas.getContext('2d');
                  function rgba(value){x.clearRect(0,0,1,1);x.fillStyle=value;x.fillRect(0,0,1,1);return [...x.getImageData(0,0,1,1).data];}
                  function l(rgb){return rgb.slice(0,3).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);}
                  const base=rgba(c.backgroundColor),atmosphere=rgba(c.getPropertyValue('--hero-atmosphere'));
                  const peak=base.slice(0,3).map((v,i)=>atmosphere[i]*atmosphere[3]/255+v*(1-atmosphere[3]/255));
                  return {base,peak,labels:['.hero-eyebrow','.hero-h1','.hero-sub'].map(selector=>{
                    const ink=rgba(getComputedStyle(hero.querySelector(selector)).color),a=l(ink);
                    const ratios=[base,peak].map(fill=>{const b=l(fill);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05)});
                    return {selector,ink,minimum:Math.min(...ratios)};})};
                }""")
                check(theme + ' hero has an opaque ground', material['base'][3] == 255, material)
                check(theme + ' hero text contrast >=4.5 across atmosphere bounds', all(row['minimum'] >= 4.5 for row in material['labels']), material)
                button = page.locator('.hero-cta .btn-primary')
                for state in ('rest', 'hover', 'pressed'):
                    if state != 'rest':
                        button.hover()
                    if state == 'pressed':
                        page.mouse.down()
                    colors = button.evaluate("""e => {
                      const c=getComputedStyle(e),canvas=document.createElement('canvas'),x=canvas.getContext('2d');
                      function rgb(value){x.fillStyle=value;x.fillRect(0,0,1,1);return [...x.getImageData(0,0,1,1).data].slice(0,3);}
                      function l(color){return rgb(color).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);}
                      const a=l(c.color),b=l(c.backgroundColor);
                      return {ink:c.color,fill:c.backgroundColor,ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05)};
                    }""")
                    check(theme + '/' + state + ' primary label contrast >=4.5', colors['ratio'] >= 4.5, colors)
                    if state == 'pressed':
                        page.mouse.move(0, 0)
                        page.mouse.up()
                button.focus()
                check(theme + ' keyboard focus visible', button.evaluate('e=>parseFloat(getComputedStyle(e).outlineWidth)>=2'))
                page.set_viewport_size({'width': 320, 'height': 1100})
                more = page.locator('.szl-more')
                more.focus()
                page.keyboard.press('ArrowDown')
                check(theme + ' More opens by keyboard', more.get_attribute('aria-expanded') == 'true')
                check(theme + ' mobile controls remain available', all(page.locator(selector).is_visible() for selector in ('.szl-theme-toggle', '.szl-op-toggle', '#inv-toggle')))
                page.keyboard.press('End')
                check(theme + ' menu keyboard reaches final action', page.locator('.szl-theme-toggle').evaluate('e=>e===document.activeElement'))
                page.keyboard.press('Escape')
                check(theme + ' More restores keyboard focus', more.evaluate('e=>e===document.activeElement') and more.get_attribute('aria-expanded') == 'false')
            check('energy with no reading stays unavailable', page.locator('#hero-joules-tag').inner_text() == 'UNAVAILABLE')
            check('empty gate feed is an observation', page.locator('#hero-gate-tag').inner_text() == 'OBSERVED')
            for view in ('ask', 'decision'):
                page.goto(origin + '/console?view=' + view, wait_until='load')
                page.locator('#gdw-intent').wait_for()
                check(view + ' fresh deep link survives all module registration',
                      parse_qs(urlsplit(page.url).query).get('view') == [view]
                      and page.locator('html').get_attribute('data-view') == view)
                page.locator('#gdw-intent').fill('Review this local fixture; do not run an action.')
                page.locator('#gdw-constraints').fill('Evidence required: a source-bound record. <untrusted text>')
                page.locator('#gdw-review').click()
                check(view + ' creates a readable local draft', 'LOCAL_DRAFT' in page.locator('#gdw-preview').inner_text())
                page.locator('#gdw-approve').click()
                check(view + ' approval remains local', 'It has not run' in page.locator('#gdw-draft-state').inner_text()
                      and '"executed": false' in page.locator('#gdw-preview').inner_text())
                for draft_theme in ('light', 'dark'):
                    if page.locator('html').get_attribute('data-surface') != draft_theme:
                        if not page.locator('.szl-theme-toggle').is_visible():
                            page.locator('.szl-more').click()
                        page.locator('.szl-theme-toggle').click()
                    for width in (320, 1280):
                        page.set_viewport_size({'width': width, 'height': 1100})
                        case = f'{view}/{draft_theme}/{width}'
                        check(case + ' draft fits the viewport', page.evaluate(
                            "document.documentElement.scrollWidth<=innerWidth+1 && document.querySelector('#content').scrollWidth<=document.querySelector('#content').clientWidth+1"))
                        check(case + ' one heading', page.locator('h1').count() == 1)
                        colors = page.locator('.gdw-draft-panel').evaluate("""panel => {
                          const canvas=document.createElement('canvas'),x=canvas.getContext('2d');
                          function rgba(value){x.clearRect(0,0,1,1);x.fillStyle=value;x.fillRect(0,0,1,1);return [...x.getImageData(0,0,1,1).data];}
                          function background(node){if(!node)return [255,255,255];const value=rgba(getComputedStyle(node).backgroundColor),a=value[3]/255;
                            return a>=1?value:background(node.parentElement).map((v,i)=>value[i]*a+v*(1-a));}
                          function l(rgb){return rgb.slice(0,3).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);}
                          return [...panel.querySelectorAll('h2,p,.field__label,.input,.btn:enabled,summary')].map(e=>{
                            const ink=rgba(getComputedStyle(e).color),fill=background(e),a=l(ink),b=l(fill);
                            return {label:e.id||e.textContent.trim().slice(0,40),ink,fill,ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05)};});
                        }""")
                        check(case + ' editor text contrast >=4.5', all(row['ratio'] >= 4.5 for row in colors), colors)
                        page.screenshot(path=str(output / f'draft-{view}-{draft_theme}-{width}.png'))
                page.locator('#gdw-intent').fill('Changed local draft')
                check(view + ' editing invalidates the prior approval', page.locator('#gdw-approve').is_disabled()
                      and 'prior review is no longer current' in page.locator('#gdw-preview').inner_text())
            check('drafts never call legacy execution routes', not any(row['path'].endswith(('/governed-decision', '/operator/act')) for row in requests))
            ledger = [request for request in requests if request['path'].endswith('/wow/ledger')]
            check('ledger observations remain passive', bool(ledger) and all(parse_qs(row['query']).get('advance') == ['0'] for row in ledger))
            check('no state-changing requests', all(row['method'] == 'GET' for row in requests))
            browser.close()
    except Exception as error:
        errors.append(str(error))
    finally:
        server.shutdown()
        files = ('pages/console.html', 'console/assets/szl-console-focus.css',
                 'console/assets/szl/szl-design-system.css', 'console/assets/szl/SOURCE.json',
                 'static/shared/szl_command_bar.js', 'scripts/test_console_frontdoor.py')
        report = {'source': 'LOCAL LABELLED FIXTURES; not production or certification',
                  'base_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  'file_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in files},
                  'checks': checks, 'errors': errors, 'measurements': measurements, 'requests': requests}
        (output / 'frontdoor-browser-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    failures = [row for row in checks if not row['passed']]
    print(json.dumps({'checks': len(checks), 'failures': failures, 'errors': errors}))
    return bool(failures or errors)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    raise SystemExit(run(parser.parse_args().output))
