#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Qualify the shipped console registry using blocked provider traffic.

All external/API responses are labelled local fixtures. This checks presentation,
navigation, passive request behavior and unavailable states, not production data,
scientific results, model quality, signatures, or scenario execution.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import threading
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import sync_playwright
from test_console_mobile_integrity import ROOT, StaticHandler
from test_console_focused_theme import MEASURE

THEMED = {'command', 'fleet', 'readiness', 'estate', 'ask', 'decision'}
SCREENSHOTS = {'lambda', 'govern', 'replay', 'energy', 'atlas', 'putnamsampler'}
QUICK = SCREENSHOTS | THEMED | {
    'arena', 'llm', 'wowdrop', 'wowtoggle', 'whHero', 'whTamper', 'whCannonico',
    'cuas_pq', 'cuas_swarm', 'cuas_fusion',
    'oversight', 'warboard', 'reciprocity', 'wowroi', 'receiptfp',
    'conjecturefactory', 'ouro_spiral', 'allodialai', 'neuro',
}
TEXT_MEASURE = MEASURE.replace(
    "const scope='.szl-hbar,.side,.szl-pal,.content';", "const scope='#vbody';"
).replace(
    'texts.push({text:',
    'texts.push({tag:e.tagName,fontSize:parseFloat(c.fontSize),fontWeight:parseFloat(c.fontWeight),text:'
)
SURFACES = """() => {
  const host=document.querySelector('#vbody');
  const cards=[...host.querySelectorAll('.card,.kpi')].filter(e=>e.getClientRects().length);
  return {workspace:host.dataset.consoleWorkspace||null,polarity:host.dataset.surface||null,
    cards:cards.map(e=>{const c=getComputedStyle(e);return {
      label:(e.querySelector('.card-t,.k')?.textContent||e.className).slice(0,100),
      image:c.backgroundImage,background:c.backgroundColor,filter:c.backdropFilter,opacity:c.opacity
    }})};
}"""


def run(output, quick=False):
    output.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), StaticHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = 'http://127.0.0.1:' + str(server.server_port)
    current = {'view': 'bootstrap', 'theme': 'dark', 'width': 1280}
    report = {
        'scope': 'LOCAL PRESENTATION AND PASSIVE-NAVIGATION QUALIFICATION; provider traffic blocked',
        'at': datetime.now(timezone.utc).isoformat(), 'quick': quick,
        'base_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'source_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                          for path in ('pages/console.html', 'console/assets/szl-console-focus.css',
                                       'scripts/test_console_view_workspaces.py')},
        'inventory': [], 'cases': [], 'checks': [], 'errors': [], 'requests': [],
        'contrast_scope': 'Visible top and bottom text; background images listed separately. Canvas data is not a measured text claim.',
    }

    def check(name, passed, detail=None):
        report['checks'].append({'name': name, 'passed': bool(passed), 'detail': detail})

    def intercept(route):
        req = route.request
        url = urlsplit(req.url)
        local = req.url.startswith(origin + '/')
        if local and req.method == 'GET' and (
            url.path in ('/console', '/console/') or
            url.path.startswith(('/assets/', '/vendor/', '/static/shared/'))
        ):
            route.continue_()
            return
        report['requests'].append({**current, 'path': url.path, 'query': url.query,
                                   'method': req.method, 'local': local})
        data = None
        if local and req.method == 'GET':
            if url.path == '/healthz':
                data = {'status': 'ok', 'source': 'LOCAL TEST FIXTURE'}
            elif url.path == '/api/a11oy/v1/honest':
                data = {'source': 'LOCAL TEST FIXTURE', 'locked_formula_count': 8}
            elif url.path == '/api/a11oy/v1/lambda':
                data = {'source': 'LOCAL TEST FIXTURE', 'lambda': .9191, 'lambda_floor': .9, 'pass': True}
            elif url.path.endswith('/wow/ledger') and parse_qs(url.query).get('advance') == ['0']:
                data = {'source': 'LOCAL TEST FIXTURE', 'receipts': [], 'chain_depth': 0}
            elif url.path.endswith('/observability/summary'):
                data = {'source': 'LOCAL TEST FIXTURE', 'capabilities': [], 'mesh_reach': {}}
        route.fulfill(status=200 if data is not None else 503, content_type='application/json',
                      body=json.dumps(data if data is not None else {
                          'state': 'UNAVAILABLE', 'available': False,
                          'source': 'LOCAL TEST FIXTURE: provider traffic blocked',
                      }))

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=os.environ.get('CONSOLE_QA_BROWSER') or os.environ.get('CHROME_PATH'),
                headless=True, args=['--disable-dev-shm-usage', '--use-gl=angle',
                                     '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
            context = browser.new_context(viewport={'width': 1280, 'height': 1000},
                                          reduced_motion='reduce', color_scheme='dark',
                                          service_workers='block')
            context.route('**/*', intercept)
            page = context.new_page()
            page.set_default_timeout(10000)
            page.on('pageerror', lambda error: report['errors'].append({**current, 'error': str(error)}))
            page.goto(origin + '/console?view=command', wait_until='load', timeout=60000)
            page.wait_for_function('window.VIEWS && window.VIEWS.estate')
            page.wait_for_timeout(1000)
            inventory = page.evaluate('Object.entries(window.VIEWS).map(([key,v])=>({key,title:v.title,badge:v.badge}))')
            report['inventory'] = inventory
            views = [v for v in inventory if v['key'] in QUICK] if quick else inventory
            check('registry captured', len(inventory) >= 100, len(inventory))
            for theme, width in [('dark', 1280), ('light', 1280), ('dark', 390), ('light', 390)]:
                page.set_viewport_size({'width': width, 'height': 1000})
                page.evaluate('theme=>{localStorage.setItem("szl.console.theme",theme);document.documentElement.dataset.surface=theme}', theme)
                for index, view in enumerate(views):
                    current.update(view=view['key'], theme=theme, width=width)
                    case = {**current}
                    label = f"{view['key']}/{theme}/{width}"
                    try:
                        page.evaluate('key=>go(key)', view['key'])
                        page.wait_for_timeout(400)
                        page.locator('.content').evaluate('e=>e.scrollTop=0')
                        size = page.evaluate('({document:document.documentElement.scrollWidth,content:document.querySelector(".content").scrollWidth,client:document.querySelector(".content").clientWidth})')
                        case['size'] = size
                        check(label + ' selected', page.locator('html').get_attribute('data-view') == view['key'])
                        check(label + ' contained', size['document'] <= width + 1 and size['content'] <= size['client'] + 1, size)
                        surfaces = page.evaluate(SURFACES)
                        case['surfaces'] = surfaces
                        if view['key'] not in THEMED:
                            check(label + ' explicit analytical polarity', surfaces['polarity'] == 'dark' and surfaces['workspace'] == 'analytical')
                            bad = [c for c in surfaces['cards'] if c['image'] != 'none' or c['opacity'] != '1' or c['filter'] != 'none' or c['background'].startswith('rgba(')]
                            check(label + ' opaque chart-compatible cards', not bad, bad)
                        case['measurements'] = [page.evaluate(TEXT_MEASURE)]
                        page.locator('.content').evaluate('e=>e.scrollTop=e.scrollHeight')
                        case['measurements'].append(page.evaluate(TEXT_MEASURE))
                        failures = []
                        for measurement in case['measurements']:
                            for text in measurement['texts']:
                                large = text['fontSize'] >= 24 or (text['fontSize'] >= 18.66 and text['fontWeight'] >= 700)
                                if text['ratio'] + .005 < (3 if large else 4.5):
                                    failures.append(text)
                        check(label + ' sampled text contrast', not failures, failures)
                        if view['key'] in ('cuas_swarm', 'cuas_fusion'):
                            stamp = '#cux-ts-' + ('csw-gate' if view['key'] == 'cuas_swarm' else 'cfu-gate')
                            page.wait_for_function('selector=>document.querySelector(selector)?.textContent==="UNAVAILABLE"', arg=stamp)
                            check(label + ' failed read visible', page.locator(stamp).inner_text() == 'UNAVAILABLE')
                        if view['key'] == 'putnamsampler':
                            region = page.locator('.console-table-region')
                            region.focus()
                            page.keyboard.press('ArrowRight')
                            if region.evaluate('e=>e.scrollWidth>e.clientWidth'):
                                page.wait_for_function('document.querySelector(".console-table-region").scrollLeft>0')
                            check(label + ' table reachable by keyboard', region.evaluate('e=>e===document.activeElement') and bool(region.get_attribute('aria-label')))
                            check(label + ' table column semantics', region.locator('th:not([scope=col])').count() == 0)
                        if view['key'] == 'decision':
                            note = page.locator('.gnd[data-grounding="decision"] .gnd-say').text_content()
                            check(label + ' research note respects local draft scope',
                                  'local draft' in note and 'do not execute an inference' in note
                                  and 'mint a receipt' in note and 'ROADMAP' in note)
                        if view['key'] == 'energy':
                            note = page.locator('.gnd[data-grounding="energy"] .gnd-say').text_content()
                            check(label + ' research note respects meter evidence scope',
                                  'J/token' in note and 'matched operator aggregate' in note and 'UNAVAILABLE' in note
                                  and 'do not establish rack energy' in note and 'SAMPLE' in note)
                        if view['key'] in SCREENSHOTS:
                            page.locator('.content').evaluate('e=>e.scrollTop=0')
                            page.screenshot(path=str(output / f"{view['key']}-{theme}-{width}.png"), timeout=60000)
                    except Exception as error:
                        case['error'] = str(error)
                        check(label + ' render completes', False, str(error))
                    report['cases'].append(case)
                    if index % 25 == 0:
                        print(json.dumps({'theme': theme, 'width': width, 'completed': index + 1, 'total': len(views)}), flush=True)
                (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
            # Passive navigation includes legacy GETs that append a record through a
            # cmd parameter. Checking HTTP method alone would miss that side effect.
            writes = [r for r in report['requests'] if r['method'] not in ('GET', 'HEAD') or
                      (r['path'].endswith('/cuas/pqbus') and 'cmd' in parse_qs(r['query'])) or
                      (r['path'].endswith('/wow/ledger') and parse_qs(r['query']).get('advance') != ['0'])]
            check('navigation produces no write-like requests', not writes, writes)
            check('unavailable fixtures produce no unhandled page errors', not report['errors'], report['errors'])
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    failures = [c for c in report['checks'] if not c['passed']]
    print(json.dumps({'views': len(report['inventory']), 'cases': len(report['cases']),
                      'checks': len(report['checks']), 'failures': [c['name'] for c in failures],
                      'page_errors': len(report['errors']), 'report': str(output / 'report.json')}))
    return bool(failures or report['errors'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--quick', action='store_true', help='Target the identified regressions; default covers every registered view.')
    args = parser.parse_args()
    raise SystemExit(run(args.output, args.quick))
