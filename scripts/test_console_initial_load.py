#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Direct benign URL regression. Local fixtures only; never force navigation."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import threading
from urllib.parse import urlsplit, parse_qs

from playwright.sync_api import sync_playwright
from console_lighthouse_fixture import ROOT, CONSOLE_SHA256, SOURCE_REVISION, resolve_request, response_headers
from measure_console_lighthouse import capacity, FixtureServer, BoundedFixtureHandler
from test_console_focused_theme import MEASURE

VIEWS = ('fleet', 'readiness', 'estate')
WIDTHS = (375, 390, 768, 1280, 1920)
SELECTORS = {'fleet': '.health-list', 'readiness': '#rd-sec-fixture', 'estate': '#szl-estate-full'}
PRIMARY = {'fleet': '/api/a11oy/v1/observability/summary', 'readiness': '/api/a11oy/v1/readiness',
           'estate': '/api/a11oy/v1/models/series-a'}
COMMAND_PROBES = ('/api/build-info', '/api/a11oy/v1/series-a/status', '/api/a11oy/v1/steward/status')
OBSERVE_VIEWS = """(() => {
  window.__qaObservedViews=[];
  new MutationObserver(rows=>rows.forEach(row=>{
    if(row.target!==document.documentElement)return;
    if(row.oldValue)window.__qaObservedViews.push(row.oldValue);
    const current=row.target.getAttribute('data-view');
    if(current)window.__qaObservedViews.push(current);
  })).observe(document,{subtree:true,attributes:true,attributeFilter:['data-view'],attributeOldValue:true});
})()"""


def run(output):
    admission = capacity()
    if min(admission.values()) < 2 * 1024**3:
        raise RuntimeError(f'Resource admission failed: {admission}')
    assert hashlib.sha256((ROOT / 'pages/console.html').read_bytes()).hexdigest() == CONSOLE_SHA256
    output.mkdir(parents=True, exist_ok=False)
    server = FixtureServer(('127.0.0.1', 0), BoundedFixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    checks, requests, errors, measurements = [], [], [], []
    current = {'id': '', 'expected': 'fleet', 'denied': None, 'malformed': False}
    browser = None

    def check(name, passed, detail=None):
        checks.append({'case': current['id'], 'name': name, 'passed': bool(passed), 'detail': detail})

    def intercept(route):
        request = route.request
        parsed = urlsplit(request.url)
        local = f'{parsed.scheme}://{parsed.netloc}' == origin
        row = {'case': current['id'], 'url': request.url, 'method': request.method, 'local': local}
        if not local or request.method != 'GET':
            route.abort('blockedbyclient')
            requests.append({**row, 'action': 'ABORT', 'acknowledged': True})
            return
        if parsed.path in ('/console', '/console/'):
            # The same pinned shell supplies explicitly listed hash/invalid selector cases.
            # Its URL is untouched; the browser's actual bootstrap chooses the view.
            source_view = current['expected'] if current['expected'] in VIEWS else 'fleet'
            response = resolve_request(f'/console?view={source_view}', 'GET', f'127.0.0.1:{server.server_port}', server.server_port)
            route.fulfill(status=response.status, headers=response_headers(response), body=response.body)
            requests.append({**row, 'action': 'PINNED_DOCUMENT', 'status': response.status, 'acknowledged': True})
            return
        if parsed.path.startswith('/api/') or parsed.path == '/healthz':
            status = current['denied'] if parsed.path == PRIMARY.get(current['expected']) else None
            if current['malformed']:
                status = 503
            if status:
                body = json.dumps({'state': 'UNAVAILABLE', 'source': 'LOCAL TEST FIXTURE', 'reason': 'Denied fixture source'})
                route.fulfill(status=status, content_type='application/json', body=body)
            else:
                response = resolve_request(parsed.path + ('?' + parsed.query if parsed.query else ''), 'GET',
                                           f'127.0.0.1:{server.server_port}', server.server_port)
                status = response.status
                route.fulfill(status=status, headers=response_headers(response), body=response.body)
            requests.append({**row, 'action': 'FIXTURE', 'status': status, 'acknowledged': True,
                             'authorization_sent': bool(request.headers.get('authorization'))})
            return
        route.continue_()
        requests.append({**row, 'action': 'FORWARD_LOOPBACK', 'acknowledged': True})

    def load(context, target, expected, case, denied=None, malformed=False):
        current.update(id=case, expected=expected, denied=denied, malformed=malformed)
        resource = capacity()
        if resource['free_ram_bytes'] < 750 * 1024**2 or resource['free_disk_bytes'] < 1024**3:
            raise RuntimeError(f'Resource stop: {resource}')
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append({'case': case, 'error': str(error)}))
        before = len(requests)
        page.goto(origin + target, wait_until='load', timeout=60000)
        page.wait_for_function('view=>document.documentElement.dataset.view===view', arg=expected, timeout=15000)
        if expected in VIEWS:
            if denied:
                page.wait_for_function("()=>document.querySelector('#vbody').textContent.includes('UNAVAILABLE')", timeout=15000)
            else:
                page.wait_for_selector(SELECTORS[expected], timeout=15000)
        page.wait_for_timeout(500)
        parsed = urlsplit(page.url)
        check('requested canonical URL retained', f'{parsed.scheme}://{parsed.netloc}' == origin and
              parse_qs(parsed.query).get('view') == [expected], page.url)
        observed = page.evaluate('window.__qaObservedViews')
        if expected in VIEWS:
            check('no incidental Command Center render', 'command' not in observed, observed)
            check('no Command Center source probes', not any(urlsplit(r['url']).path in COMMAND_PROBES for r in requests[before:]))
        if denied:
            own = [r for r in requests[before:] if urlsplit(r['url']).path == PRIMARY[expected]]
            check('denied source stays denied', bool(own) and all(r.get('status') == denied for r in own), own)
            check('no implicit credential escalation', all(not r.get('authorization_sent') for r in requests[before:]))
            check('denied data remains visibly unavailable', 'UNAVAILABLE' in page.locator('#vbody').inner_text())
        if malformed:
            check('malformed selector never leaves origin', page.url.startswith(origin + '/console'))
            check('malformed selector rejects inherited registry entries', not any(v in ('__proto__', 'constructor') for v in observed), observed)
        return page

    try:
        with sync_playwright() as p:
            binary = Path.home() / 'AppData/Local/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-win64/chrome-headless-shell.exe'
            browser = p.chromium.launch(executable_path=str(binary), headless=True,
                args=['--disable-gpu', '--disable-background-networking', '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1'])
            for kind in ('query', 'hash'):
                for view in VIEWS:
                    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark',
                                                  reduced_motion='reduce', service_workers='block')
                    context.route('**/*', intercept)
                    context.route_web_socket('**/*', lambda route: route.close(code=1008))
                    context.add_init_script(OBSERVE_VIEWS)
                    try:
                        target = '/console?view=' + view if kind == 'query' else '/console#' + view
                        page = load(context, target, view, f'{kind}/{view}')
                        if kind == 'query':
                            for theme in ('dark', 'light'):
                                if page.locator('html').get_attribute('data-surface') != theme:
                                    page.locator('.szl-theme-toggle').click()
                                for width in WIDTHS:
                                    page.set_viewport_size({'width': width, 'height': 844})
                                    page.wait_for_timeout(150)
                                    sizes = page.evaluate('({width:innerWidth,doc:document.documentElement.scrollWidth,content:document.querySelector(".content").scrollWidth,client:document.querySelector(".content").clientWidth})')
                                    check(f'{theme}/{width} containment', sizes['doc'] <= width + 1 and sizes['content'] <= sizes['client'] + 1, sizes)
                                    measure = page.evaluate(MEASURE)
                                    measurements.append({'case': current['id'], 'theme': theme, 'width': width, **measure})
                                    small = [t for t in measure['targets'] if t['width'] < 43.99 or t['height'] < 43.99]
                                    check(f'{theme}/{width} visible tap targets >=44px', bool(measure['targets']) and not small, small)
                                    if width in (390, 1280):
                                        page.screenshot(path=str(output / f'{view}-{theme}-{width}.png'))
                                page.set_viewport_size({'width': 390, 'height': 844})
                                trigger = page.locator('.menu-btn')
                                trigger.focus(); page.keyboard.press('Enter')
                                check(f'{theme} drawer keyboard open', trigger.get_attribute('aria-expanded') == 'true')
                                check(f'{theme} drawer contains focus', page.evaluate('document.activeElement.closest(".side")!==null'))
                                page.keyboard.press('Escape')
                                check(f'{theme} drawer restores focus', trigger.evaluate('(e)=>e===document.activeElement'))
                                page.keyboard.press('Control+k')
                                page.wait_for_selector('.szl-pal-ov.open')
                                page.locator('.szl-pal input').fill('no_fixture_command')
                                page.keyboard.press('Shift+Tab')
                                check(f'{theme} palette focus trapped', page.evaluate('document.activeElement.matches(".szl-pal-close")'))
                                page.keyboard.press('Escape')
                                check(f'{theme} palette restores focus', trigger.evaluate('(e)=>e===document.activeElement'))
                                check(f'{theme} reduced motion respected', page.evaluate('!document.getAnimations().some(a=>a.playState==="running"&&a.effect&&a.effect.target.closest(".content,.side,.szl-hbar"))'))
                    finally:
                        context.close()
            for view in VIEWS:
                for status in (401, 403):
                    context = browser.new_context(viewport={'width': 390, 'height': 844}, reduced_motion='reduce', service_workers='block')
                    context.route('**/*', intercept)
                    context.route_web_socket('**/*', lambda route: route.close(code=1008))
                    context.add_init_script(OBSERVE_VIEWS)
                    try:
                        page = load(context, '/console?view=' + view, view, f'denied/{view}/{status}', denied=status)
                    finally:
                        context.close()
            for target in ('?view=invalid-fixture-view', '?view=__proto__', '?view=constructor',
                           '?view=https%3A%2F%2Fexample.invalid%2F', '#invalid-fixture-view', '?view='):
                context = browser.new_context(viewport={'width': 390, 'height': 844}, reduced_motion='reduce', service_workers='block')
                context.route('**/*', intercept)
                context.route_web_socket('**/*', lambda route: route.close(code=1008))
                context.add_init_script(OBSERVE_VIEWS)
                try:
                    page = load(context, '/console' + target, 'command', 'invalid/' + target, malformed=True)
                finally:
                    context.close()
            current['id'] = 'overall'
            check('no JavaScript startup errors', not errors, errors)
            check('read-only requests', all(r['method'] == 'GET' for r in requests))
            check('no external requests forwarded', all(r['local'] or r['action'] == 'ABORT' for r in requests))
            ledger = [r for r in requests if urlsplit(r['url']).path.endswith('/wow/ledger')]
            check('ledger remains passive', bool(ledger) and all(parse_qs(urlsplit(r['url']).query).get('advance') == ['0'] for r in ledger))
            browser.close()
            browser = None
    except Exception as error:
        errors.append({'case': current['id'], 'error': str(error)})
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        server.shutdown(); server.server_close(); thread.join(timeout=5)
        report = {'source': 'LOCAL LABELLED FIXTURES; not deployed authentication or WCAG certification',
                  'qa_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  'product_revision': SOURCE_REVISION, 'console_sha256': CONSOLE_SHA256,
                  'checks': checks, 'errors': errors, 'requests': requests, 'measurements': measurements,
                  'completed_capacity': capacity(), 'forced_go_calls': False}
        (output / 'initial-load-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    failed = [c for c in checks if not c['passed']]
    print(json.dumps({'checks': len(checks), 'failed': failed, 'errors': errors}))
    return int(bool(failed or errors))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    raise SystemExit(run(parser.parse_args().output))
