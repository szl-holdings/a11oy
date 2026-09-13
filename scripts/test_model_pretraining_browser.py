# SPDX-License-Identifier: Apache-2.0
"""Run the real parent router, Python model projection and browser together.

No model calls, training, credentials, provider writes or public deployment.
The full production app is not launched; this tests its existing route seam.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from routers import hf_tooling_evidence as tooling
from routers import model_pretraining as view


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    output = ROOT / 'artifacts' / 'model-pretraining'
    output.mkdir(parents=True, exist_ok=True)
    raw = view.MANIFEST.read_bytes()
    snapshot, source_digest = view.decode_projection(raw)
    expected = len(view.parse_manifest(snapshot)['inventory']['models'])
    app = FastAPI()
    tooling.register(app)
    # Match the existing image/serve asset mount; do not copy or mock the shell.
    app.mount("/assets", StaticFiles(directory=ROOT / "console" / "assets"), name="assets")
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0)); listener.listen(128)
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level='error', lifespan='off'))
    worker = threading.Thread(target=server.run, kwargs={'sockets': [listener]}, daemon=True)
    worker.start()
    observations, errors = [], []
    try:
        deadline = time.monotonic() + 10
        while not server.started:
            check(time.monotonic() < deadline, 'Loopback server startup timed out')
            time.sleep(.05)
        with sync_playwright() as p:
            executable = os.getenv('SZL_TEST_CHROMIUM')
            launch = {'headless': True, 'args': ['--no-sandbox']}
            if executable:
                launch['executable_path'] = executable
            browser = p.chromium.launch(**launch)
            try:
                for width, height in ((320,568),(375,812),(390,844),(414,896),
                                      (768,1024),(810,1180),(1024,768),(1440,900)):
                    context = browser.new_context(viewport={'width': width, 'height': height},
                                                  reduced_motion='reduce')
                    page = context.new_page()
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    assets = {}
                    page.on('response', lambda response, assets=assets: assets.update(
                        {response.url.split('/')[-1]: response.status})
                        if '/assets/szl-' in response.url else None)
                    page.goto(f'http://127.0.0.1:{port}/frontier-tooling/models')
                    expect(page.locator('.szl-flow-rail')).to_be_visible()
                    check(all(assets.get(name) == 200 for name in
                        ('szl-flow.js', 'szl-flow.css', 'szl-spectral-v2.css')),
                        'Existing flow-shell assets did not load')
                    check(page.locator('.szl-flow-link').count() == 5, 'Journey links missing')
                    if width <= 820:
                        toggle = page.get_by_role('button', name='Open journey navigation')
                        toggle.focus(); page.keyboard.press('Enter')
                        expect(toggle).to_have_attribute('aria-expanded', 'true')
                        page.keyboard.press('Escape')
                        expect(toggle).to_have_attribute('aria-expanded', 'false')
                    expect(page.locator('#total')).to_have_text(str(expected))
                    expect(page.locator('#models .card')).to_have_count(expected)
                    expect(page.locator('#status')).to_contain_text('alignment is not certified')
                    expect(page.locator('#manifest-hash')).to_have_text(source_digest)
                    page.locator('#search').fill('szl-receiptagent')
                    count = page.locator('#models .card').count()
                    check(0 < count < expected, 'Search did not narrow rows')
                    page.locator('#search').fill('no-such-model-unique-test')
                    expect(page.locator('#models .card')).to_have_count(0)
                    page.locator('#search').fill('')
                    page.locator('#category').select_option('GGUF_HINT')
                    check(0 < page.locator('#models .card').count() < expected, 'Category filter failed')
                    page.locator('#category').select_option('ALL')
                    page.locator('summary').focus(); page.keyboard.press('Enter')
                    check(page.locator('#evidence').get_attribute('open') is not None, 'Keyboard details failed')
                    check(page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Page overflow')
                    page.screenshot(path=str(output / f'models-{width}.png'), full_page=True)
                    page.emulate_media(forced_colors='active')
                    check(page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Forced-color overflow')
                    page.emulate_media(forced_colors='none')
                    # Negative transport injection only; initial and recovered data are actual Python responses.
                    page.route('**/api/a11oy/v1/models/pretraining', lambda route: route.fulfill(
                        status=503, content_type='application/json', body='{"available":false}'))
                    page.locator('#reload').click()
                    expect(page.locator('#status')).to_contain_text('HTTP 503')
                    expect(page.locator('#total')).to_have_text('—')
                    expect(page.locator('#models .card')).to_have_count(0)
                    expect(page.locator('#search')).to_be_disabled()
                    page.unroute('**/api/a11oy/v1/models/pretraining')
                    page.locator('#reload').click()
                    expect(page.locator('#models .card')).to_have_count(expected)
                    expect(page.locator('#search')).to_be_enabled()
                    observations.append({'width':width,'height':height,'recordedEntries':expected,
                        'realPythonProjection':True,'keyboardDetails':True,'searchAndCategory':True,
                        'failedRefreshClearsRows':True,'horizontalOverflow':False,
                        'reducedMotionMode':True,'forcedColorsLayout':True,
                        'sharedFlowShell':True,'sharedAssetStatus':assets})
                    context.close()
                browser_version = browser.version
            finally:
                browser.close()
        check(not errors, 'Browser script errors: '+str(errors))
        report = {'schema':'szl.model-pretraining-browser/v1','scope':'LOCAL_ROUTE_GROUP_INTEGRATION',
                  'productionDeploymentVerified':False,'wholeEstateAligned':False,
                  'trainingStarted':False,'modelInferencePerformed':False,
                  'projectionSha256':hashlib.sha256(raw).hexdigest(),'sourceManifestSha256':source_digest,'browser':browser_version,
                  'observations':observations,'pageErrors':errors,
                  'fileSha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in (
                      'routers/hf_tooling_evidence.py','routers/model_pretraining.py',
                      'pages/model-pretraining.html','pages/model-pretraining.css','pages/model-pretraining.js',
                      'console/assets/szl-flow.js','console/assets/szl-flow.css',
                      'console/assets/szl-spectral-v2.css')}}
        (output/'browser-report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,sort_keys=True))
    finally:
        server.should_exit = True; worker.join(timeout=10); listener.close()
        check(not worker.is_alive(), 'Loopback server did not terminate')


if __name__ == '__main__':
    main()
