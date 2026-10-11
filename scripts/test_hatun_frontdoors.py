#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Exercise Hatun's actual HTML and CSS with labelled, read-only local fixtures.

Set CHROME_PATH to an installed Chromium and pass --output DIR. This records
presentation and keyboard behavior; it makes no production readiness claim.
"""
import argparse
import hashlib
import json
import mimetypes
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
WIDTHS = (320, 390, 768, 1280, 1920)
PAGES = {'/hatun-mcp': 'pages/hatun-mcp.html', '/wires': 'pages/wires.html'}
FIXTURES = {
    '/mcp/': {'source': 'LOCAL TEST FIXTURE', 'protocolVersion': 'TEST-FIXTURE',
              'tools': [{'name': 'fixture_read_only', 'description': 'LOCAL TEST FIXTURE; no execution.'}]},
    '/api/hatun/evidence': {'source': 'LOCAL TEST FIXTURE', 'signer': {'status': 'UNKNOWN'},
                            'receipt_chain': {'status': 'UNKNOWN'}},
    '/api/hatun/mesh': {'source': 'LOCAL TEST FIXTURE', 'organs': [
        {'id': 'fixture_context', 'job': 'LOCAL TEST FIXTURE', 'href': '/fixture/' + 'long-path-' * 10,
         'label': 'DECLARED'}]},
    '/api/hatun/invocations': {'source': 'LOCAL TEST FIXTURE', 'items': []},
    '/api/a11oy/v1/mesh/state': {'source': 'LOCAL TEST FIXTURE', 'state': 'DECLARED', 'wires': [
        {'id': 'LOCAL-FIXTURE-' + 'long-identifier-' * 7, 'title': 'LOCAL TEST FIXTURE ' + 'long-title-' * 9,
         'state': 'DECLARED', 'detail': 'LOCAL TEST FIXTURE; no execution or health evidence.',
         'source': 'LOCAL-TEST-FIXTURE/' + 'long-provenance-path/' * 14},
        {'id': 'unknown-fixture', 'title': 'LOCAL TEST FIXTURE unknown state', 'state': 'UNRECOGNIZED',
         'source': 'LOCAL TEST FIXTURE'}]},
}


class StaticHandler(BaseHTTPRequestHandler):
    brand_dir = ROOT / 'console/assets/szl'

    def log_message(self, *_args):
        pass

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in PAGES:
            file = ROOT / PAGES[path]
        elif path.startswith('/assets/szl/'):
            file = self.brand_dir / path.removeprefix('/assets/szl/')
        elif path.startswith('/assets/'):
            file = ROOT / 'console/assets' / path.removeprefix('/assets/')
        elif path.startswith('/vendor/'):
            file = ROOT / 'static-vendor' / path.removeprefix('/vendor/')
        else:
            file = ROOT / '__missing__'
        if not any(file.resolve().is_relative_to(parent.resolve()) for parent in (ROOT, self.brand_dir)) or not file.is_file():
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', mimetypes.guess_type(file)[0] or 'application/octet-stream')
        self.end_headers()
        self.wfile.write(file.read_bytes())


def run(output, brand_dir=None):
    output.mkdir(parents=True, exist_ok=True)
    StaticHandler.brand_dir = brand_dir or ROOT / 'console/assets/szl'
    server = ThreadingHTTPServer(('127.0.0.1', 0), StaticHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = 'http://127.0.0.1:' + str(server.server_port)
    checks, errors, requests, layouts, stalled_routes = [], [], [], [], []
    mode = {'value': 'success'}

    def check(name, passed, detail=None):
        checks.append({'name': name, 'passed': bool(passed), 'detail': detail})

    def intercept(route):
        request = route.request
        path = urlsplit(request.url).path
        local = request.url.startswith(origin + '/')
        if local and request.method == 'GET' and (path in PAGES or path.startswith(('/assets/', '/vendor/'))):
            route.continue_()
            return
        requests.append({'path': path, 'method': request.method, 'local': local, 'mode': mode['value']})
        if local and path in FIXTURES and mode['value'] == 'stall':
            stalled_routes.append(route)
            return  # Leave the request pending so the page's own timeout must finish the state.
        data = FIXTURES.get(path) if local and request.method == 'GET' and mode['value'] == 'success' else None
        route.fulfill(status=200 if data else 503, content_type='application/json',
                      body=json.dumps(data or {'state': 'UNAVAILABLE', 'source': 'LOCAL TEST FIXTURE'}))

    try:
        with sync_playwright() as controller:
            browser = controller.chromium.launch(executable_path=os.environ.get('CHROME_PATH'), headless=True,
                args=['--disable-dev-shm-usage', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
            context = browser.new_context(viewport={'width': 1280, 'height': 1100}, reduced_motion='reduce',
                                          color_scheme='dark', service_workers='block')
            context.route('**/*', intercept)
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.set_default_timeout(10000)
            for path in PAGES:
                mode['value'] = 'success'
                page.goto(origin + path, wait_until='load')
                page.wait_for_function("document.querySelector('#runtime-status')?.getAttribute('aria-busy')==='false'||document.querySelectorAll('.wire').length===2")
                page.keyboard.press('Tab')
                check(path + ' first keyboard target is skip link', page.locator('.skip-link').evaluate('e=>e===document.activeElement'))
                page.keyboard.press('Enter')
                check(path + ' skip moves focus to main', page.locator('main').evaluate('e=>e===document.activeElement'))
                for surface in ('dark', 'light'):
                    page.locator('html').evaluate('(e,s)=>e.dataset.surface=s', surface)
                    for width in WIDTHS:
                        page.set_viewport_size({'width': width, 'height': 1100})
                        page.evaluate('scrollTo(0,0)')
                        page.evaluate('document.activeElement?.blur()')
                        page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
                        name = f'{path}/{surface}/{width}'
                        layout = page.evaluate("""() => ({viewport:innerWidth,document:document.documentElement.scrollWidth,
                          h1:document.querySelectorAll('h1').length,main:document.querySelectorAll('main').length,
                          navHeight:document.querySelector('.hatun-nav,.local-nav').getBoundingClientRect().height,
                          controls:[...document.querySelectorAll('.hatun-nav a,.local-nav a,.action,.footer a')].map(e=>{
                            const r=e.getBoundingClientRect();return {text:e.textContent.trim(),width:r.width,height:r.height};}),
                          wires:[...document.querySelectorAll('.wire')].map(e=>({display:getComputedStyle(e).display,
                            width:e.clientWidth,scroll:e.scrollWidth,radius:getComputedStyle(e).borderRadius})),
                          instrument:document.querySelector('.instrument')?getComputedStyle(document.querySelector('.instrument')).display:null,
                          scrollBehavior:getComputedStyle(document.documentElement).scrollBehavior,
                          atmosphere:(()=>{const card=document.querySelector('.hatun-runtime');
                            const style=getComputedStyle(card||document.body),probe=document.createElement('span');
                            probe.hidden=true;probe.style.backgroundColor=card?'var(--surface)':'var(--page)';
                            document.body.append(probe);const expectedFill=getComputedStyle(probe).backgroundColor;probe.remove();
                            return {image:style.backgroundImage,fill:style.backgroundColor,expectedFill};})()})""")
                        layouts.append({'case': name, **layout})
                        check(name + ' document fits viewport', layout['document'] <= width + 1, layout)
                        check(name + ' one main and heading', layout['h1'] == 1 and layout['main'] == 1)
                        check(name + ' page navigation stays compact', layout['navHeight'] < 160, layout['navHeight'])
                        check(name + ' links have44px targets', all(row['width'] >= 43.99 and row['height'] >= 43.99 for row in layout['controls']), layout['controls'])
                        check(name + ' reduced motion scrolls without animation', layout['scrollBehavior'] == 'auto', layout['scrollBehavior'])
                        paint = layout['atmosphere']
                        check(name + ' atmosphere renders over its opaque surface role', 'radial-gradient(' in paint['image'] and
                              paint['fill'] == paint['expectedFill'] and paint['fill'] != 'rgba(0, 0, 0, 0)', paint)
                        if path == '/wires':
                            check(name + ' state containers stay readable blocks', layout['instrument'] == 'block' and
                                  all(row['display'] == 'block' and row['scroll'] <= row['width'] + 1 and row['radius'] != '999px' for row in layout['wires']), layout['wires'])
                        if width in (320, 1280) and surface == 'dark':
                            page.screenshot(path=str(output / f'{path.strip("/")}-{surface}-{width}.png'), full_page=True, timeout=60000)
                page.emulate_media(forced_colors='active')
                forced_paint = page.evaluate("""() => {const paint=getComputedStyle(document.querySelector('.hatun-runtime')||document.body);
                  return {image:paint.backgroundImage,fill:paint.backgroundColor};}""")
                check(path + ' forced colors remove atmosphere for a solid reading ground',
                      forced_paint['image'] == 'none' and forced_paint['fill'] != 'rgba(0, 0, 0, 0)', forced_paint)
                page.emulate_media(forced_colors='none')
                if path == '/hatun-mcp':
                    check('reachable runtime remains a declaration', page.locator('#health').inner_text() == 'REACHABLE' and page.locator('#toolsource').inner_text() == 'RUNTIME DECLARED')
                    check('no receipt fixture stays UNKNOWN', page.locator('#signer').inner_text() == 'UNKNOWN' and page.locator('#chain').inner_text() == 'UNKNOWN' and 'UNKNOWN' in page.locator('#inv').inner_text())
                    check('all table headers have column scope', page.locator('th:not([scope="col"])').count() == 0)
                    page.set_viewport_size({'width': 320, 'height': 1100})
                    for index, table in enumerate(page.locator('.table-wrap').all()):
                        table.focus()
                        page.keyboard.press('ArrowRight')
                        page.wait_for_function('(i)=>document.querySelectorAll(".table-wrap")[i].scrollLeft>0', arg=index)
                        check(f'table{index} keyboard scrolls', table.get_attribute('role') == 'region' and bool(table.get_attribute('aria-labelledby')))
                    config = json.loads(page.locator('pre').inner_text())
                    check('sample client uses an absolute HTTPS target', config['mcpServers']['szl-a11oy']['args'][-1].startswith('https://'))
                else:
                    check('unknown wire state is not promoted', page.locator('.wire').nth(1).get_attribute('data-state') == 'UNAVAILABLE')
                    check('Verify opens the human verifier', page.locator('.pathway').nth(2).get_attribute('href') == '/verify')
                for value in ('error', 'stall'):
                    mode['value'] = value
                    page.goto(origin + path, wait_until='load')
                    if path == '/hatun-mcp':
                        page.wait_for_function("document.querySelector('#runtime-status').getAttribute('aria-busy')==='false'")
                        page.wait_for_function("document.querySelector('#inv').textContent.includes('UNAVAILABLE')")
                        check(path + '/' + value + ' terminates without inventing evidence', page.locator('#signer').inner_text() == 'UNAVAILABLE' and page.locator('#chain').inner_text() == 'UNAVAILABLE' and page.locator('#toolsource').inner_text() == 'STATIC FALLBACK')
                        check(path + '/' + value + ' mesh terminates', 'UNAVAILABLE' in page.locator('#mesh').inner_text())
                    else:
                        page.wait_for_function("document.querySelector('#instrument-state').textContent.includes('not read')")
                        check(path + '/' + value + ' remains unavailable', page.locator('#gateway-instrument').get_attribute('data-state') == 'UNAVAILABLE' and page.locator('.wire').count() == 0)
                    for route in stalled_routes:
                        route.abort('aborted')
                    stalled_routes.clear()
            context.close()
            static_context = browser.new_context(java_script_enabled=False, viewport={'width': 320, 'height': 1100})
            static_context.route('**/*', intercept)
            static_page = static_context.new_page()
            for path in PAGES:
                static_page.goto(origin + path, wait_until='load')
                static_page.keyboard.press('Tab')
                check(path + ' works without JS: skip remains first', static_page.locator('.skip-link').evaluate('e=>e===document.activeElement'))
                check(path + ' works without JS: source navigation remains', static_page.locator('a[href]').count() > 5)
            browser.close()
    except Exception as error:
        errors.append(str(error))
    finally:
        server.shutdown()
        files = (*PAGES.values(), 'scripts/test_hatun_frontdoors.py')
        check('requests use read-only local fixtures', bool(requests) and all(row['method'] == 'GET' for row in requests))
        report = {'source': 'LOCAL LABELLED FIXTURES; not production or certification',
                  'base_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  'file_sha256': {file: hashlib.sha256((ROOT / file).read_bytes()).hexdigest() for file in files},
                  'brand_directory': str(StaticHandler.brand_dir),
                  'design_css_sha256': hashlib.sha256((StaticHandler.brand_dir / 'szl-design-system.css').read_bytes()).hexdigest(),
                  'checks': checks, 'errors': errors, 'layouts': layouts, 'requests': requests}
        (output / 'hatun-browser-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    failures = [row for row in checks if not row['passed']]
    print(json.dumps({'checks': len(checks), 'failures': failures, 'errors': errors}))
    return bool(failures or errors)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--brand-dir', type=Path, help='Optional candidate canonical bundle; its hash is recorded separately.')
    args = parser.parse_args()
    raise SystemExit(run(args.output, args.brand_dir))
