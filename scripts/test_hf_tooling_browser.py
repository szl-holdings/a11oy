# SPDX-License-Identifier: Apache-2.0
"""Exercise the real Python API and responsive page together, not an API mock."""
from __future__ import annotations
import hashlib
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from routers.hf_tooling_evidence import BUNDLE_SHA256, FORGE_SOURCE, register


def main() -> None:
    app = FastAPI()
    register(app)
    # Match production /assets/* using the actual existing source assets.
    # No new production writer or second copy of the shared flow shell.
    app.mount("/assets", StaticFiles(directory=ROOT / "console" / "assets"), name="assets")
    # Reserve the listening socket before starting the server to avoid port races.
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(128)
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level='error', lifespan='off'))
    worker = threading.Thread(target=server.run, kwargs={'sockets': [listener]}, daemon=True)
    worker.start()
    output = ROOT / 'artifacts' / 'hf-tooling-product'
    output.mkdir(parents=True, exist_ok=True)
    errors, observations = [], []
    try:
        deadline = time.monotonic() + 10
        while not server.started:
            if time.monotonic() >= deadline:
                raise RuntimeError('Local API server did not start')
            time.sleep(.05)
        with sync_playwright() as pw:
            # System Chromium is useful in offline review containers; CI uses
            # the Chromium revision installed by its pinned Playwright package.
            executable = os.environ.get('SZL_TEST_CHROMIUM')
            launch = {'headless': True, 'args': ['--no-sandbox']}
            if executable:
                launch['executable_path'] = executable
            browser = pw.chromium.launch(**launch)
            for width, height in ((320, 568), (375, 812), (768, 1024), (1440, 900)):
                context = browser.new_context(viewport={'width': width, 'height': height}, reduced_motion='reduce')
                page = context.new_page()
                page.on('pageerror', lambda error: errors.append(str(error)))
                assets = {}
                page.on('response', lambda response: assets.update({response.url.split('/')[-1]: response.status})
                        if '/assets/szl-' in response.url else None)
                page.goto(f'http://127.0.0.1:{port}/frontier-tooling', wait_until='networkidle')
                page.locator('#content').wait_for(state='visible')
                page.locator('.szl-flow-rail').wait_for(state='visible')
                assert all(assets.get(name) == 200 for name in ('szl-flow.js', 'szl-flow.css', 'szl-spectral-v2.css')), assets
                assert page.locator('.szl-flow-link').count() == 5
                if width <= 820:
                    toggle = page.get_by_role('button', name='Open journey navigation')
                    toggle.focus()
                    page.keyboard.press('Enter')
                    assert toggle.get_attribute('aria-expanded') == 'true'
                    assert page.get_by_role('link', name='Products & Demos', exact=True).is_visible()
                    page.keyboard.press('Escape')
                    assert toggle.get_attribute('aria-expanded') == 'false'
                assert page.locator('.lane').count() == 4
                assert page.locator('.package').count() == 5
                assert page.locator('#status').inner_text() == 'Archive verified · process metadata observed'
                page.screenshot(path=str(output / f'loaded-{width}.png'), full_page=True)
                overflow = page.evaluate("""[...document.body.querySelectorAll('*')].map(el => ({tag:el.tagName,
                    className:el.className, right:el.getBoundingClientRect().right})).filter(row => row.right > innerWidth)""")
                (output / f'layout-{width}.json').write_text(json.dumps(overflow, indent=2))
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Horizontal overflow: {overflow}'
                assert page.locator('.orbit div').first.evaluate('(el) => getComputedStyle(el).animationName') == 'none'
                page.get_by_role('button', name='Memory', exact=True).click()
                assert page.locator('.lane').count() == 1
                assert page.locator('.lane').get_attribute('data-lane') == 'tau'
                page.locator('summary').first.focus()
                page.keyboard.press('Enter')
                assert page.locator('.lane details').first.get_attribute('open') is not None
                assert page.locator('.lane pre').is_visible()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Open details overflow'
                page.get_by_role('button', name='All evaluations', exact=True).focus()
                page.keyboard.press('Enter')
                assert page.locator('.lane').count() == 4
                assert page.locator('#lane-filters button[aria-pressed=true]').inner_text() == 'All evaluations'
                page.screenshot(path=str(output / f'view-{width}.png'), full_page=True)
                # Fail a real refresh and ensure previous pass cards disappear.
                page.route('**/api/a11oy/v1/frontier-tooling', lambda route: route.fulfill(status=503, content_type='application/json', body='{"available":false}'))
                page.get_by_role('button', name='Refresh observation').click()
                page.locator('#error').wait_for(state='visible')
                assert not page.locator('#content').is_visible()
                assert page.locator('.lane').count() == 0
                page.unroute('**/api/a11oy/v1/frontier-tooling')
                page.get_by_role('button', name='Refresh observation').click()
                page.locator('#content').wait_for(state='visible')
                assert page.locator('.lane').count() == 4
                observations.append({'width': width, 'height': height, 'horizontalOverflow': False,
                    'livePythonApi': True, 'keyboardControls': 'PASS', 'filter': 'PASS',
                    'reducedMotion': 'PASS', 'failedRefreshClearsSuccess': 'PASS',
                    'sharedFlowShell': 'PASS', 'sharedAssetStatus': assets})
                context.close()
            browser.close()
        assert not errors, errors
        try:
            revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            revision = None
        report = {'schema': 'szl.hf-tooling-browser-test.v1', 'target': 'LOCAL_PYTHON_API',
            'productionDeploymentVerified': False, 'sourceRevision': revision,
            'forgeEvaluationSource': FORGE_SOURCE, 'archiveSha256': BUNDLE_SHA256,
            'observations': observations, 'pageErrors': errors,
            'fileSha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in
               ('routers/hf_tooling_evidence.py', 'pages/hf-tooling.html', 'pages/hf-tooling.js', 'pages/hf-tooling.css',
                'console/assets/szl-flow.js', 'console/assets/szl-flow.css', 'console/assets/szl-spectral-v2.css')}}
        (output / 'browser-report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
    finally:
        server.should_exit = True
        worker.join(timeout=10)
        listener.close()


if __name__ == '__main__':
    main()
