# SPDX-License-Identifier: Apache-2.0
"""Chromium exercises the actual generated UI using explicitly synthetic APIs.

The optional URL must be loopback and is used by CI to read HTML from the
actual image. API requests are intercepted and never reach external providers.
Without a URL a loopback fixture server serves the same generated HTML bytes.
No trading, credentials, provider publication, or external browser navigation.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys
import threading
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright, expect

REVISION = "1" * 40
NOW = 1789689600


def load(name):
    path = ROOT / "scripts" / (name + ".py")
    spec = importlib.util.spec_from_file_location("browser_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def fixture_body(source, query, mode):
    transport = importlib.import_module("verticals.puriq-markets.runtime.transport")
    def fetch(plan):
        if source == "coinbase-candles":
            p = plan.parameters
            # Smooth deterministic fixture, explicitly not observed prices.
            rows = []
            for i, stamp in enumerate(range(p["start"], p["end"], p["granularity"])):
                close = 100 + i / 10 + math.sin(i / 5)
                rows.append([stamp, close - 2, close + 2, close - .2, close, 0])
            if mode == "gapped":
                rows.pop(len(rows) // 2)
            return json.dumps(rows).encode()
        if source == "polymarket-markets":
            return json.dumps([{"id":"123", "question":"<img src=x onerror=window.fixtureInjected=true>",
                "outcomes":'["Yes","No"]',"outcomePrices":'["0.5","0.5"]',
                "volume24hr":0,"liquidity":None}]).encode()
        if source == "coinbase-ticker":
            return b'{"price":"100","bid":null,"ask":"101","volume":"0"}'
        raise transport.FinanceError("UPSTREAM_HTTP_503")
    client = transport.FinanceClient(fetch=fetch, environ={"SZL_GIT_SHA": REVISION},
                                     clock=lambda: NOW, monotonic=lambda: 100)
    body = client.observe(source, query)
    if mode == "failure":
        return 503, client._unavailable(source, NOW, "UPSTREAM_HTTP_503")
    if mode == "wrong_revision":
        body["source_revision"] = "2" * 40
    return (200 if body.get("ok") else 503), body


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--url", help="Optional actual generated container, http://127.0.0.1:PORT")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    renderer = load("hf_publish_vertical_flagships_v4_impl")
    emitter = load("materialize_finance_runtime")
    html = emitter.payloads(renderer, REVISION, 1)["index.html"]
    server = None
    if args.url:
        parts = urlsplit(args.url)
        check(parts.scheme == "http" and parts.hostname == "127.0.0.1" and parts.port
              and not parts.username and not parts.password and not parts.query
              and not parts.fragment and parts.path in ("", "/"), "non-loopback browser target")
        origin = args.url.rstrip("/")
    else:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path not in ("/", "/research", "/panels"):
                    self.send_error(404); return
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers(); self.wfile.write(html)
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        origin = "http://127.0.0.1:" + str(server.server_port)
    report = {"schema":"szl.finance.workspace-browser/v1", "market_data":"SYNTHETIC_FIXTURES",
              "deployment_verified":False, "live_provider_verified":False,
              "html_sha256":hashlib.sha256(html).hexdigest(),
              "served_by":"GENERATED_CONTAINER" if args.url else "LOOPBACK_FIXTURE_SERVER", "cases":[]}
    try:
        with sync_playwright() as p:
            options = {"headless":True, "args":["--no-sandbox"]}
            if os.environ.get("FINANCE_BROWSER_EXECUTABLE"):
                options["executable_path"] = os.environ["FINANCE_BROWSER_EXECUTABLE"]
            browser = p.chromium.launch(**options)
            report["browser_version"] = browser.version
            for width in (320, 375, 768, 1440):
                context = browser.new_context(viewport={"width":width,"height":900}, accept_downloads=True)
                page = context.new_page()
                mode = {"name":"normal"}
                requests, errors, unexpected = [], [], []
                page.on("pageerror", lambda error: errors.append(str(error)))
                transport = importlib.import_module("verticals.puriq-markets.runtime.transport")
                registry = transport.FinanceClient(environ={"SZL_GIT_SHA":REVISION}).registry()
                def route_handler(route):
                    req = route.request
                    parts = urlsplit(req.url)
                    if req.url.split("?",1)[0] in (origin+"/",origin+"/research",origin+"/panels"):
                        route.continue_(); return
                    if not req.url.startswith(origin + "/"):
                        unexpected.append(req.url); route.abort(); return
                    path = parts.path
                    if path == "/favicon.ico":
                        route.fulfill(status=204,body=""); return
                    if path not in ("/api/source","/api/finance/providers","/api/live") and not path.startswith(("/api/finance/observations/", "/api/finance/v2/")):
                        unexpected.append(path); route.abort(); return
                    requests.append({"path":path,"query":parts.query,"method":req.method})
                    check(req.method == "GET" or req.method == "POST" and path in ("/api/finance/v2/portfolio", "/api/finance/v2/receipts/verify"), "unexpected browser method")
                    check("authorization" not in req.headers and "cookie" not in req.headers, "browser credential forwarded")
                    status = 200
                    if path.startswith("/api/finance/v2/"):
                        analytics = importlib.import_module("verticals.puriq-markets.runtime.analytics")
                        client = transport.FinanceClient(environ={"SZL_GIT_SHA":REVISION})
                        if path.endswith("/portfolio"):
                            body = analytics.portfolio(client, req.post_data_json)
                        elif path.endswith("/receipts/verify"):
                            valid = analytics.verify(req.post_data_json)
                            body = analytics.envelope(client, "receipt-verification", {
                                "verified": valid, "state": "INTEGRITY_VALID" if valid else "INVALID",
                                "authenticity_established": False}, {})
                        else:
                            operation, symbol = path.rsplit("/", 2)[-2:]
                            check(parse_qs(parts.query).get("origin") == ["fixture"], "browser test attempted live analytics")
                            body = analytics.compute(client, operation, symbol, "fixture")
                    elif path == "/api/source":
                        body = {"deployment_source":"szl-holdings/a11oy","source_revision":REVISION}
                    elif path == "/api/finance/providers":
                        body = deepcopy(registry)
                        if mode["name"] == "bad_registry": body["sources"].pop()
                    elif path == "/api/live":
                        status,body=503,{"status":"UNAVAILABLE","http_status":503,"data":{},"execution_enabled":False}
                    else:
                        source=path.rsplit("/",1)[-1]
                        check(source not in ("fred-series","alpaca-quote","alpaca-bars"), "owner-only source request")
                        query={k:v[0] for k,v in parse_qs(parts.query).items()}
                        status,body=fixture_body(source,query,mode["name"])
                        if mode["name"] == "non_json":
                            route.fulfill(status=200,content_type="text/html",body="<h1>Not data</h1>"); return
                    route.fulfill(status=status,content_type="application/json",body=json.dumps(body))
                context.route("**/*", route_handler)
                response=page.goto(origin+"/research",wait_until="networkidle")
                check(response and response.status==200,"research page unavailable")
                check(response.body()==html,"container served different generated page bytes")
                expect(page.locator("#fin-source")).to_be_enabled()
                check(page.locator("#fin-source option").count()==16,"source catalogue incomplete")
                check(page.locator("#fin-source option:disabled").count()==3,"private sources selectable")
                check(not [r for r in requests if "/observations/" in r["path"]],"implicit source fetch on page load")
                report["cases"].append({"width":width,"name":"source-contract-and-private-controls","pass":True})
                # Every public adapter's actual parameters are represented without a network read.
                for spec in registry["sources"]:
                    if spec["private"]: continue
                    page.locator("#fin-source").select_option(spec["id"])
                    fields=page.locator("#fin-fields input").evaluate_all("es=>es.map(e=>e.name)")
                    check(fields==spec["parameters"],"missing adapter parameter")
                page.locator("#fin-source").select_option("coinbase-ticker")
                page.locator("#fin-observe").click()
                expect(page.locator("#fin-export")).to_be_enabled()
                detail=json.loads(page.locator("#fin-detail").text_content())
                check(detail["data"]["bid"] is None and detail["data"]["volume_24h_base_units"]=="0","null/zero semantics changed")
                check("Unavailable" in page.locator("#fin-result-table").text_content(),"missing not rendered unavailable")
                page.locator("#fin-source").select_option("coinbase-candles")
                check(page.locator("#fin-export").is_disabled(),"selection retained stale export")
                page.locator("#fin-observe").click()
                expect(page.locator("#fin-chart svg")).to_have_count(1)
                with page.expect_download() as transfer:
                    page.locator("#fin-export").click()
                exported=Path(transfer.value.path()).read_text()
                check(json.loads(exported)==json.loads(page.locator("#fin-detail").text_content()),"export differs from accepted response")
                # Synthetic label exists only in screenshots, not committed application HTML.
                page.evaluate("""()=>{let e=document.createElement('p');e.id='fixture-label';e.textContent='SYNTHETIC BROWSER FIXTURE — not live market data';e.style.cssText='padding:16px;border:2px solid currentColor;font-weight:800';document.querySelector('#fin-desk').prepend(e)}""")
                page.locator("#fin-desk").screenshot(path=str(args.output/f"finance-workspace-fixture-{width}.png"))
                page.locator("#fixture-label").evaluate("e=>e.remove()")
                overflow=page.evaluate("Math.max(document.documentElement.scrollWidth,document.body.scrollWidth)-innerWidth")
                check(overflow<=1,f"page overflow: {overflow}")
                targets=page.locator("#fin-desk button, #fin-desk select, #fin-desk input").evaluate_all("es=>es.filter(e=>e.getClientRects().length).map(e=>({id:e.id,w:e.getBoundingClientRect().width,h:e.getBoundingClientRect().height}))")
                check(all(t["w"]>=44 and t["h"]>=44 for t in targets),"undersized interactive target")
                report["cases"].append({"width":width,"name":"all-public-forms-chart-export-null-zero-layout","pass":True,"horizontal_overflow_px":overflow,"touch_targets":len(targets)})
                page.locator("#fin-param-count").fill("50")
                check(page.locator("#fin-chart svg").count()==0 and page.locator("#fin-export").is_disabled(),"parameter edit retained stale result")
                for failure in ("failure","wrong_revision","non_json"):
                    mode["name"]=failure
                    page.locator("#fin-observe").click()
                    expect(page.locator("#fin-result-state")).to_contain_text("UNAVAILABLE")
                    check(page.locator("#fin-export").is_disabled() and page.locator("#fin-chart svg").count()==0,"failure retained chart/export")
                    expect(page.locator("#fin-observe")).to_be_enabled()
                mode["name"]="gapped"
                page.locator("#fin-observe").click()
                expect(page.locator("#fin-export")).to_be_enabled()
                check(page.locator("#fin-chart svg").count()==0,"gapped candle chart interpolated")
                expect(page.locator("#fin-chart-note")).to_contain_text("withheld")
                mode["name"]="normal"
                page.locator("#fin-source").select_option("polymarket-markets")
                page.locator("#fin-observe").click()
                expect(page.locator("#fin-export")).to_be_enabled()
                check(page.locator("#fin-result-table img").count()==0 and not page.evaluate("window.fixtureInjected===true"),"untrusted source HTML executed")
                expect(page.locator("#fin-result-table")).to_contain_text("<img")
                report["cases"].append({"width":width,"name":"failure-invalidation-gap-refusal-literal-text","pass":True})
                page.locator("#fin-analysis-origin").select_option("fixture")
                page.locator("#fin-analysis-run").click()
                expect(page.locator("#fin-analysis-export")).to_be_enabled()
                expect(page.locator("#fin-analysis-state")).to_contain_text("FIXTURE")
                evidence = json.loads(page.locator("#fin-analysis-evidence").text_content())
                check(evidence["inputs"]["asset"]["truth_label"] == "SYNTHETIC", "fixture mislabeled")
                check(evidence["receipt"]["signing"] == "UNSIGNED_HONEST", "unsigned boundary lost")
                page.locator("#fin-analysis-verify").click()
                expect(page.locator("#fin-analysis-summary")).to_contain_text("INTEGRITY_VALID")
                page.locator("#fin-analysis-symbol").fill("ETH-USD")
                check(page.locator("#fin-analysis-export").is_disabled(), "changed inputs retained old computation")
                page.locator("#fin-analytics details").first.locator("summary").click()
                page.locator("#fin-portfolio").fill('{"A":[1.25,1.75,1.50]}')
                page.locator("#fin-portfolio-run").click()
                expect(page.locator("#fin-analysis-export")).to_be_enabled()
                evidence = json.loads(page.locator("#fin-analysis-evidence").text_content())
                check(evidence["operation"] == "portfolio" and evidence["inputs"]["truth_label"] == "UNVERIFIED", "caller input mislabeled")
                report["cases"].append({"width":width,"name":"v2-fixture-receipt-fractional-portfolio-invalidation","pass":True})
                # A deliberately delayed browser fixture resolves after a source change.
                page.evaluate("""()=>{const original=window.fetch;window.fetch=(url,options)=>String(url).includes('/observations/')?new Promise(resolve=>{window.releaseFixture=()=>resolve(new Response(JSON.stringify({schema:'szl.finance.observation/v1'}),{status:200,headers:{'Content-Type':'application/json'}}))}):original(url,options)}""")
                page.locator("#fin-observe").click()
                expect(page.locator("#fin-result-state")).to_contain_text("REQUESTING")
                page.locator("#fin-source").select_option("coinbase-ticker")
                page.evaluate("window.releaseFixture()")
                page.wait_for_timeout(50)
                expect(page.locator("#fin-result-state")).to_contain_text("READY TO REQUEST")
                check(page.locator("#fin-export").is_disabled(),"late response resurrected previous result")
                page.locator("#fin-source").focus();page.keyboard.press("Tab")
                check(page.locator("#fin-param-product").evaluate("e=>e===document.activeElement"),"form keyboard order")
                page.emulate_media(reduced_motion="reduce",forced_colors="active")
                page.locator("#fin-param-product").fill("ETH-USD")
                check(page.locator("#fin-observe").is_enabled(),"media preferences broke controls")
                page.locator("#fin-source").evaluate("e=>{e.value='fred-series';e.dispatchEvent(new Event('change',{bubbles:true}))}")
                check(page.locator("#fin-observe").is_disabled(),"tampered source bypassed client private boundary")
                page.locator("#fin-form").evaluate("e=>e.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}))")
                expect(page.locator("#fin-result-state")).to_contain_text("DENIED")
                mode["name"]="bad_registry"
                page.locator("#fin-refresh").click()
                expect(page.locator("#fin-registry-state")).to_contain_text("UNAVAILABLE")
                check(page.locator("#fin-source").is_disabled() and page.locator("#fin-observe").is_disabled(),"incomplete registry accepted")
                check(not errors,"browser errors: "+repr(errors))
                check(not unexpected,"unapproved browser destinations: "+repr(unexpected))
                check(page.evaluate("Object.keys(localStorage).length+Object.keys(sessionStorage).length")==0,"browser stored state")
                report["cases"].append({"width":width,"name":"late-result-keyboard-media-private-registry-refusal","pass":True,"page_errors":0,"unexpected_requests":0})
                context.close()
            browser.close()
        report["status"]="PASS"
    except BaseException as exc:
        report.update(status="FAIL",error_type=type(exc).__name__,error=str(exc))
        raise
    finally:
        if server: server.shutdown();server.server_close()
        (args.output/"browser-report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"status":report["status"],"cases":len(report["cases"]),"data":"SYNTHETIC_FIXTURES"}))


if __name__ == "__main__":
    main()
