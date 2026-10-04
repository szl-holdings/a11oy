#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Qualify the shared shell in its real HTML, JavaScript, CSS and font contexts.

All requests are intercepted. Provider responses are UNAVAILABLE, except for
explicitly synthetic inventory cards that exercise the existing card renderer.
This checks source rendering; it does not establish runtime or provider health.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import mimetypes
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "https://szl-shell-fixture.invalid"
CSS_PATH = "static/shared/szl_command_bar.css"
VIEWPORTS = ((320, 568), (375, 812), (768, 1024), (1440, 900))
PAGES = (
    ("console", "pages/console.html", "/console?view=investor"),
    ("legacy-console", "console/index.html", "/legacy-console"),
    ("estate", "pages/estate.html", "/estate"),
    ("atelier", "pages/atelier.html", "/atelier"),
)
SHARED_ASSETS = {
    "szl_label_engine.js", "szl_receipt_cosign.js", "szl_codename_sanitizer.js",
    "szl_holo3d.js", "szl_command_bar.js", "szl_command_bar.css", "puriq_receipt_v1.js",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inventory_fixture():
    cards = []
    for lane, evidence in (("model", "REPORTED"), ("kernel", "SOFTWARE")):
        cards.append({
            "id": "fixture-" + lane, "lane": lane, "owner": "Synthetic browser fixture",
            "title": "Fixture " + lane, "one_line": "Layout observation only; no provider result.",
            "hub_id": "SZLHOLDINGS/fixture-" + lane + "-" + "a" * 72,
            "hub_href": "https://huggingface.co/SZLHOLDINGS/fixture-" + lane,
            "github": "https://github.com/szl-holdings/a11oy",
            "evidence_class": evidence,
            "listing": {"label": "REPORTED", "note": "Synthetic listing fixture"},
            "artifacts": {"label": evidence, "note": "No execution was performed."},
            "evals": {"label": "UNAVAILABLE", "note": "No model evaluation."},
            "revision_pin": {"label": "UNAVAILABLE", "sha": None},
            "not": "Not an operational model or kernel.", "lambda": {"label": "Conjecture 1"},
        })
    return {"scope": "SYNTHETIC_BROWSER_FIXTURE", "cards": cards, "roadmap_kernels": []}


LAYOUT = """() => {
  const bar = document.querySelector('[data-szl-command-bar]');
  const roots = [bar, ...document.querySelectorAll('.szl-estate-grid')].filter(Boolean);
  const overflows = [];
  const scrollRegions = [];
  for (const root of roots) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const parent = node.parentElement;
      if (!parent || !node.textContent.trim() || parent.closest('[hidden],[aria-hidden="true"],script,style')) continue;
      if (!parent.getClientRects().length || getComputedStyle(parent).visibility === 'hidden') continue;
      const range = document.createRange(); range.selectNodeContents(node);
      const box = range.getBoundingClientRect();
      if (!box.width || (box.left >= -1 && box.right <= innerWidth + 1)) continue;
      let scroller = parent;
      while (scroller && scroller !== document.body) {
        const style = getComputedStyle(scroller);
        if (['auto', 'scroll'].includes(style.overflowX) && scroller.scrollWidth > scroller.clientWidth) break;
        scroller = scroller.parentElement;
      }
      const entry = {text: node.textContent.trim().slice(0, 100), left: box.left, right: box.right};
      if (scroller && scroller !== document.body) scrollRegions.push(entry);
      else overflows.push(entry);
    }
  }
  const controls = [...document.querySelectorAll(
    '.szl-hbar a,.szl-hbar button,.szl-estate-grid .szl-holo-act a,.szl-estate-grid .szl-empty__retry'
  )].filter(el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden')
    .map(el => {
      const box = el.getBoundingClientRect();
      return {label: el.textContent.trim(), width: box.width, height: box.height, left: box.left, right: box.right};
    });
  return {
    viewport: innerWidth, scrollWidth: document.documentElement.scrollWidth,
    shell: bar ? bar.getBoundingClientRect().toJSON() : null, overflows, scrollRegions, controls,
    textLength: document.body.innerText.trim().length,
    runtime: document.querySelector('#runtime-status-text')?.textContent,
    liveChips: document.querySelectorAll('.szl-hbar .szl-chip--live').length,
    fonts: [...document.fonts].map(font => ({family: font.family, status: font.status})),
    fontFamilies: [...new Set(roots.flatMap(root => [root, ...root.querySelectorAll('*')])
      .filter(element => element.getClientRects().length).map(element => getComputedStyle(element).fontFamily))],
  };
}"""


ATELIER_EVIDENCE = """async () => {
  const saved = NANO;
  const root = document.querySelector('#play');
  const original = DATA.models[idx];
  const observations = [];
  const cases = [
    {play:'moons', key:'moons', metric:'holdoutAcc', bounded:true, expected:'holdout 0.8875 MEASURED'},
    {play:'tell', key:'willay', metric:'holdoutAcc', bounded:true, expected:'holdout 1.0000 SYNTHETIC'},
    {play:'courier', slug:'chaski', key:'chaski', metric:'holdoutAcc', bounded:true, expected:'holdout 0.9808 SYNTHETIC'},
    {play:'courier', slug:'chaski-5050', key:'chaski5050', metric:'holdoutAcc', bounded:true, expected:'holdout 0.9808 SYNTHETIC'},
    {play:'courier', slug:'chaski-r2', key:'chaskiR2', metric:'holdoutAcc', bounded:true, expected:'holdout 1.0000 SYNTHETIC'},
    {play:'lambda', key:'lambdaGate', metric:'lambdaStar', bounded:true, expected:'λ* 0.6279'},
    {play:'embed', key:'miniEmbed', metric:'retrievalHitAt2', bounded:true, expected:'bundled hit@2 0.40'},
    {play:'ouroboros', key:'kernelMeasures', metric:'ouroborosModelMs', expected:'modelMs=1120 REPORTED sample'},
    {play:'ouroboros', key:'kernelMeasures', metric:'ouroborosOverheadMs', expected:'overhead=180 DERIVED'},
    {play:'attn', key:'kernelMeasures', metric:'receiptAttnResidual', expected:'residual=2.220e-16'},
  ];
  async function observe(test, control, unavailable) {
    await mountPlay(root, test);
    if (test.play === 'moons') document.querySelector('#cv').click();
    const detail = document.querySelector('#g').innerText;
    const label = document.querySelector('#g .lbl')?.textContent || detail;
    if (unavailable) {
      if (!label.startsWith('UNAVAILABLE') || /\\bMEASURED\\b/.test(detail))
        throw new Error(test.key + '/' + control + ' fabricated an available observation: ' + detail);
    } else if (!detail.includes(test.expected) || !detail.includes('bundled NumPy snapshot')) {
      throw new Error(test.key + '/' + control + ' lost its bundled observation scope: ' + detail);
    }
    observations.push({play:test.play, key:test.key, metric:test.metric, control, state:unavailable?'UNAVAILABLE':'BUNDLED'});
  }
  try {
    for (const test of cases) {
      NANO = structuredClone(saved);
      await observe(test, 'bundled', false);
      NANO = null;
      await observe(test, 'missing bundle', true);
      const invalid = [['missing', undefined], ['null', null], ['string', '0.8875'],
        ['NaN', NaN], ['infinity', Infinity], ['negative infinity', -Infinity], ['negative', -1]];
      if (test.bounded) invalid.push(['above one', 1.1]);
      for (const [control, value] of invalid) {
        NANO = structuredClone(saved);
        NANO[test.key][test.metric] = value;
        await observe(test, control, true);
      }
      if (['tell','courier'].includes(test.play)) {
        for (const value of [null, [[1]], Array.from({length:5}, () => Array(8).fill(NaN))]) {
          NANO = structuredClone(saved);
          NANO[test.key].w1 = value;
          await observe(test, 'invalid weights', true);
        }
      }
      if (test.play === 'embed') {
        for (const value of [null, [[1]], Array.from({length:64}, () => Array(12).fill(NaN)), Array.from({length:64}, () => Array(12).fill(0))]) {
          NANO = structuredClone(saved);
          NANO.miniEmbed.table = value;
          await observe(test, 'invalid embedding table or vector', true);
        }
      }
      if (test.play === 'moons') {
        for (const value of [null, [], [{x:NaN, y:0, yTrue:1}]]) {
          NANO = structuredClone(saved);
          NANO.moons.cloud = value;
          await observe(test, 'invalid cloud', true);
        }
        for (const [key, value] of [['trainedAt', undefined], ['trainedAt', 'invalid'], ['trainedAt', 0], ['label', undefined], ['label', 'UNAVAILABLE']]) {
          NANO = structuredClone(saved);
          NANO[key] = value;
          await observe(test, 'missing or invalid measurement provenance', true);
        }
      }
    }
  } finally {
    NANO = saved;
    await mountPlay(root, original);
  }
  return {scope:'Actual source callbacks; mutated in-memory bundle only', observations};
}"""


def run_case(browser, output, name, source_path, route_path, width, height, css, variant, fonts):
    context = browser.new_context(
        viewport={"width": width, "height": height}, reduced_motion="reduce",
        color_scheme="dark", service_workers="block",
    )
    page = context.new_page()
    page.set_default_timeout(10000)
    errors, missing_assets, served = [], [], {}
    result = {"page": name, "source": source_path, "variant": variant,
              "width": width, "height": height, "state": "FAIL", "failures": []}
    source = (ROOT / source_path).read_bytes()
    result["html_sha256"] = digest(source)
    page.on("pageerror", lambda error: errors.append(str(error)))

    def intercept(route):
        request = route.request
        url = urlsplit(request.url)
        if url.scheme + "://" + url.netloc != ORIGIN:
            route.fulfill(status=503, json={"state": "UNAVAILABLE", "scope": "SYNTHETIC_BROWSER_FIXTURE"},
                          headers={"Access-Control-Allow-Origin": "*"})
            return
        path = unquote(url.path)
        body, content_type = None, None
        if request.is_navigation_request() and path == urlsplit(route_path).path:
            body, content_type = source, "text/html; charset=utf-8"
        elif path == "/static/shared/szl_command_bar.css":
            body, content_type = css, "text/css"
        elif path.startswith("/vendor/fonts/") or path == "/vendor/earth-night.jpg":
            body = fonts.get(path.removeprefix("/vendor/"))
            content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
        else:
            directory, relative = None, None
            if path.startswith("/assets/"):
                directory, relative = ROOT / "console/assets", path.removeprefix("/assets/")
            elif path.startswith("/vendor/"):
                directory, relative = ROOT / "static-vendor", path.removeprefix("/vendor/")
            elif path.startswith("/static/shared/") and path.rsplit("/", 1)[-1] in SHARED_ASSETS:
                directory, relative = ROOT / "static/shared", path.removeprefix("/static/shared/")
            if directory is not None:
                file = (directory / relative).resolve()
                if file.is_relative_to(directory.resolve()) and file.is_file():
                    body = file.read_bytes()
                    content_type = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        if body is not None:
            served[path] = digest(body)
            route.fulfill(status=200, body=body, content_type=content_type)
        elif path == "/api/a11oy/v1/models/series-a":
            route.fulfill(status=200, json=inventory_fixture())
        else:
            if request.resource_type in ("stylesheet", "script", "font"):
                missing_assets.append(path)
            route.fulfill(status=503, json={"state": "UNAVAILABLE", "scope": "SYNTHETIC_BROWSER_FIXTURE"})

    context.route("**/*", intercept)
    slug = f"{variant}-{name}-{width}"
    try:
        page.goto(ORIGIN + route_path, wait_until="load")
        page.wait_for_function("document.querySelector('[data-szl-command-bar]')?.getAttribute('data-szl-mounted') === '1'")
        page.wait_for_function("document.querySelector('#runtime-status-text')?.textContent === 'UNAVAILABLE'")
        page.evaluate("() => document.fonts.ready")
        page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
        if name == "estate":
            page.wait_for_function("document.querySelector('.szl-estate-grid')?.getAttribute('aria-busy') === 'false'")
        if name == "atelier":
            page.wait_for_function("document.querySelector('#app h1')?.textContent.trim().length > 0")
        layout = page.evaluate(LAYOUT)
        result["layout"] = layout
        failures = result["failures"]
        if not layout["shell"] or layout["textLength"] < 100:
            failures.append("source page or shared shell did not render")
        if layout["scrollWidth"] > width + 1:
            failures.append("document horizontal overflow")
        if layout["overflows"]:
            failures.append("shared shell or card text escapes viewport")
        if layout["liveChips"]:
            failures.append("unavailable fixture produced a live shell chip")
        if name == "atelier" and width >= 1024:
            sidebar = page.locator(".walk > .side").bounding_box()
            article = page.locator(".walk > article").bounding_box()
            result["atelier_walk"] = {"sidebar": sidebar, "article": article}
            if not sidebar or not article or article["x"] < sidebar["x"] + sidebar["width"] or article["width"] < sidebar["width"] * 2:
                failures.append("Atelier desktop article occupies the sidebar column")
        if any(control["width"] < 44 or control["height"] < 44 for control in layout["controls"]):
            failures.append("shared shell action target is below 44px")
        if any(control["left"] < -1 or control["right"] > width + 1 for control in layout["controls"]):
            failures.append("shared shell action is outside viewport")
        for family in ("Space Grotesk", "JetBrains Mono"):
            declared = [font for font in layout["fonts"] if font["family"].strip("'\"") == family]
            used = any(family in families for families in layout["fontFamilies"])
            if used and declared and not any(font["status"] == "loaded" for font in declared):
                failures.append(f"used declared {family} font did not load")
        page.screenshot(path=str(output / (slug + ".png")), full_page=False)

        more = page.locator(".szl-more").first
        more.focus()
        page.keyboard.press("ArrowDown")
        if more.get_attribute("aria-expanded") != "true":
            failures.append("More menu keyboard opening failed")
        menu = page.locator(".szl-overflow.open .szl-overflow-menu")
        menu_box = menu.bounding_box()
        result["more_menu"] = menu_box
        if not menu_box or menu_box["x"] < -1 or menu_box["x"] + menu_box["width"] > width + 1 or menu_box["y"] < -1 or menu_box["y"] + menu_box["height"] > height + 1:
            failures.append("More menu escapes viewport")
        visible_menu_item = """element => {
          const box = element.getBoundingClientRect();
          const menu = element.closest('.szl-overflow-menu').getBoundingClientRect();
          const uncovered = [box.top + 1, box.y + box.height / 2, box.bottom - 1].every(y => {
            const hit = document.elementFromPoint(box.x + box.width / 2, y);
            return hit === element || element.contains(hit);
          });
          return box.top >= menu.top && box.bottom <= Math.min(menu.bottom, innerHeight) + 1 &&
            uncovered;
        }"""
        first_visible = menu.locator("a").first.evaluate(visible_menu_item)
        if not first_visible:
            failures.append("More menu first keyboard destination is clipped or covered")
        if width == 320:
            page.screenshot(path=str(output / (slug + "-more.png")), full_page=False)
        page.keyboard.press("End")
        last_visible = menu.locator("a").last.evaluate(visible_menu_item)
        result["more_menu_keyboard"] = {"first_visible": first_visible, "last_visible": last_visible}
        if not last_visible:
            failures.append("More menu last keyboard destination is clipped or covered")
        if width == 320:
            page.screenshot(path=str(output / (slug + "-more-last.png")), full_page=False)
        page.keyboard.press("Escape")
        if more.get_attribute("aria-expanded") != "false":
            failures.append("More menu Escape closing failed")

        for theme in (("dark", "light") if name == "console" else ("dark",)):
            if theme == "light":
                page.locator(".szl-theme-toggle").click()
                if page.locator("html").get_attribute("data-surface") != "light":
                    failures.append("console light theme did not activate")
            trigger = page.locator(".szl-cmdk").first
            trigger.click()
            palette = page.locator("#szl-command-palette")
            box = page.locator(".szl-pal").bounding_box()
            if not box or box["x"] < 0 or box["x"] + box["width"] > width:
                failures.append("command palette escapes viewport")
            layers = palette.evaluate("""element => ({
              palette: Number(getComputedStyle(element).zIndex),
              navigation: [...document.querySelectorAll('.szl-flow-rail,.szl-flow-progress,.szl-flow-announcement,.szl-holo-rail,.szl-holo-progress')]
                .map(node => Number(getComputedStyle(node).zIndex) || 0),
            })""")
            result.setdefault("palette_layers", {})[theme] = layers
            if layers["palette"] <= max(layers["navigation"], default=0):
                failures.append("page navigation paints above command palette backdrop")
            items = page.locator(".szl-pal-list a").all()
            first, second = items[0].bounding_box(), items[1].bounding_box()
            if not first or not second or second["y"] < first["y"] + first["height"] - 1:
                failures.append("page navigation styles turned palette destinations into columns")
            focus = page.evaluate("() => ({inside:!!document.activeElement.closest('.szl-pal'), outline:getComputedStyle(document.activeElement).outlineStyle})")
            if not focus["inside"] or focus["outline"] == "none":
                failures.append("palette initial keyboard focus is not visible")
            if width in (320, 1440):
                page.screenshot(path=str(output / (slug + "-palette-" + theme + ".png")), full_page=False)
            page.keyboard.press("Escape")
            if palette.get_attribute("aria-hidden") != "true":
                failures.append("palette Escape closing failed")
            if not trigger.evaluate("element => document.activeElement === element"):
                failures.append("palette did not restore trigger focus")
        page.emulate_media(forced_colors="active")
        if not page.evaluate("matchMedia('(forced-colors: active)').matches"):
            failures.append("forced-colors emulation failed")
        if page.locator(".szl-hbar").evaluate("element => getComputedStyle(element, '::before').display") != "none":
            failures.append("shell decoration survives forced-colors")
        if name == "atelier":
            if variant == "candidate" and width == 320:
                result["atelier_evidence_controls"] = page.evaluate(ATELIER_EVIDENCE)
            with page.expect_request(lambda request: request.is_navigation_request() and request.url == ORIGIN + "/console?view=investor"):
                page.locator("#inv-toggle").click()
            result["investor_destination"] = "/console?view=investor"
        if errors:
            failures.append("page JavaScript errors")
        if missing_assets:
            failures.append("referenced local script, stylesheet or font is unavailable")
        result["state"] = "FAIL" if failures else "PASS"
    except Exception as error:
        result["failures"].append(type(error).__name__ + ": " + str(error))
    finally:
        result["page_errors"] = errors
        result["missing_assets"] = sorted(set(missing_assets))
        result["served_asset_sha256"] = served
        context.close()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--chromium")
    parser.add_argument("--base", help="Optional exact commit for a baseline CSS comparison on the same page source")
    args = parser.parse_args()
    if args.base and not re.fullmatch(r"[0-9a-f]{40}", args.base):
        parser.error("--base must be a full immutable commit SHA")
    args.output.mkdir(parents=True, exist_ok=False)
    candidate = (ROOT / CSS_PATH).read_bytes()
    variants = [("candidate", candidate)]
    if args.base:
        baseline = subprocess.run(["git", "show", f"{args.base}:{CSS_PATH}"], cwd=ROOT, check=True,
                                  capture_output=True).stdout
        variants.insert(0, ("baseline", baseline))
    report = {
        "schema": "szl.shell-source-check/v1", "state": "FAIL",
        "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "scope": "ACTUAL_SOURCE_AND_LOCAL_ASSETS_WITH_SYNTHETIC_PROVIDER_FIXTURES",
        "comparison": "BASE_STYLESHEET_ON_CANDIDATE_PAGE_SOURCE" if args.base else "NOT_REQUESTED",
        "base_sha": args.base, "css_sha256": digest(candidate), "checks": [],
        "not_verified": ["live APIs", "HF deployment", "model quality", "server authorization", "WCAG conformance"],
    }
    try:
        spec = importlib.util.spec_from_file_location("source_vendor_blobs", ROOT / "_vendor_blobs.py")
        fonts = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fonts)
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, **({"executable_path": args.chromium} if args.chromium else {}))
            report["browser_version"] = browser.version
            try:
                for variant, css in variants:
                    for name, source, route in PAGES:
                        for width, height in VIEWPORTS:
                            result = run_case(browser, args.output, name, source, route, width, height, css, variant, fonts)
                            report["checks"].append(result)
                            print(json.dumps({key: result[key] for key in ("page", "variant", "width", "state", "failures")}), flush=True)
                candidate_checks = [check for check in report["checks"] if check["variant"] == "candidate"]
                if len(candidate_checks) == len(PAGES) * len(VIEWPORTS) and all(check["state"] == "PASS" for check in candidate_checks):
                    report["state"] = "PASS"
            finally:
                browser.close()
    except Exception as error:
        report["error"] = type(error).__name__ + ": " + str(error)
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"state": report["state"], "completed_cases": len(report["checks"])}))
    return 0 if report["state"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
