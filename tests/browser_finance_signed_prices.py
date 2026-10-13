# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Exercise the emitted page with explicitly synthetic signed responses."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright, expect
from tests.test_finance_signed_verifier import signed, _resign
from tests.test_finance_signed_prices import sample, prices, ENV


def envelope(age=1, tampered=False):
    key, data, ring, _ = signed.__wrapped__()
    now = time.time()
    data['at'] = datetime.fromtimestamp(now-age, timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
    _resign(key, data)
    if tampered:
        data['sources'] = 999
    client, _ = sample((key, data, ring, now))
    return prices.envelope(ENV, client.observe('BTC'))


def run(url, output):
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width':1280,'height':900})
        errors=[]
        page.on('pageerror', lambda err: errors.append(str(err)))
        state={'age':1, 'tampered':False, 'status':200}
        def respond(route):
            body = envelope(state['age'], state['tampered']) if state['status']==200 else {'error':'SOURCE_UNAVAILABLE'}
            route.fulfill(status=state['status'], content_type='application/json', body=json.dumps(body))
        page.route('**/api/finance/signed-prices/BTC', respond)
        page.route('**/api/finance/signed-prices/model', lambda route: route.fulfill(content_type='application/json', body=json.dumps(prices.envelope(ENV,prices.reference.synthetic_demo(),modeled=True))))
        page.goto(url+'/signed-prices#fin-signed')
        button=page.get_by_role('button', name='Verify latest print')
        button.click(); expect(page.locator('#fin-signed-state')).to_contain_text('REVIEW')
        expect(page.locator('#fin-signed-price')).to_contain_text('81234.56')
        expect(page.locator('#fin-signed-export')).to_be_enabled()
        page.screenshot(path=str(output/'signed-desktop.png'),full_page=True)
        state['tampered']=True
        button.click(); expect(page.locator('#fin-signed-state')).to_have_text('ABSTAIN')
        expect(page.locator('#fin-signed-price')).to_have_text('No accepted price')
        expect(page.locator('#fin-signed-export')).to_be_disabled()
        state.update(tampered=False,age=28)
        button.click(); expect(page.locator('#fin-signed-state')).to_contain_text('REVIEW')
        expect(page.locator('#fin-signed-state')).to_contain_text('EXPIRED',timeout=5000)
        expect(page.locator('#fin-signed-price')).to_have_text('No accepted price')
        state.update(status=503)
        button.click(); expect(page.locator('#fin-signed-state')).to_have_text('UNAVAILABLE')
        page.get_by_role('button',name='Run synthetic comparison').click()
        expect(page.locator('#fin-signed-model-state')).to_have_text('MODELED / SYNTHETIC')
        expect(page.locator('#fin-signed-model-rows')).to_contain_text('100.5')
        page.set_viewport_size({'width':390,'height':844})
        page.screenshot(path=str(output/'signed-mobile.png'),full_page=True)
        assert page.evaluate('() => document.documentElement.scrollWidth <= window.innerWidth')
        assert not errors, errors
        (output/'signed-browser.json').write_text(json.dumps({'passed':True,'fixture':'SYNTHETIC_EPHEMERAL_KEY', 'checks':['review','tamper-abstain','local-expiry','source-unavailable','modeled-comparison','mobile-overflow'], 'console_errors':errors},indent=2))
        browser.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--url',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); run(args.url.rstrip('/'),args.output)
