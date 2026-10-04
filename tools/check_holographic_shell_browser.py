#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Offline component browser checks. Not full-site, HF, font or WCAG qualification.

Requires the existing Playwright Python package and a locally installed Chromium.
Run: python tools/check_holographic_shell_browser.py --output /new/report/directory
No network, app backend, credentials, or provider calls are used.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>SZL shell test fixture</title>
<style>body{margin:0;background:#080c14;color:#f5f1e9;font-family:system-ui,sans-serif}
main{max-width:1040px;margin:auto;padding:24px 16px}h1{font-size:clamp(28px,5vw,48px);letter-spacing:-.04em}
.fixture-note{color:#c3cedd;line-height:1.6;max-width:680px;margin-bottom:28px}
.fixture-palette{max-width:520px;margin-top:24px}.fixture-palette .szl-pal{margin:0;width:100%}
</style><style>__CSS__</style>
<header class="topbar szl-hbar" aria-label="Test command bar">
<div class="szl-hbar-zone szl-hbar-scope"><span class="szl-hbar-crumb"><b>SZL</b><span class="sep">/</span><span class="now">Evidence workspace</span></span></div>
<div class="szl-hbar-zone szl-hbar-live">
<span class="szl-chip" id="unknown"><i class="szl-dot" aria-hidden="true"></i>UNKNOWN</span>
<span class="szl-chip szl-chip--live" id="measured"><i class="szl-dot" aria-hidden="true"></i>MEASURED · fixture</span>
<span class="szl-chip szl-chip--live szl-chip--lambda" id="advisory"><i class="szl-dot" aria-hidden="true"></i>ADVISORY</span>
<span class="szl-chip szl-chip--live szl-chip--off" id="off"><i class="szl-dot" aria-hidden="true"></i>UNAVAILABLE</span>
</div><nav class="szl-hbar-zone szl-hbar-switch szl-origins" aria-label="Fixture navigation">
<a class="szl-origin is-on" href="#fixture" id="first-link">Inspect</a><button class="szl-origin" type="button">Evidence</button></nav></header>
<main id="fixture"><p class="szl-estate-h">Offline component fixture</p><h1>Inspect before you act.</h1>
<p class="fixture-note">Synthetic interface states for layout and accessibility tests. These are not live services, model results, or verified release evidence.</p>
<section class="szl-estate-page" aria-label="Example artifact cards"><div class="szl-estate-tiles">
<article class="szl-holo-card" data-lane="kernel"><span class="szl-holo-k">Source / artifact / revision</span><h2 class="szl-holo-title">Readable evidence.</h2>
<p class="szl-holo-one">Separate a listed software artifact from an executed measurement. Follow the source before making a claim.</p>
<dl class="szl-holo-facts"><div><dt>State</dt><dd><span class="szl-holo-chip szl-holo-chip--software" id="software">SOFTWARE</span></dd></div>
<div><dt>Identity</dt><dd class="szl-holo-id">SZLHOLDINGS/fixture-only-__LONG_ID__</dd></div></dl>
<p class="szl-holo-lambda">Advisory only. No authorization is implied.</p><div class="szl-holo-act"><a href="#fixture">Inspect source</a><a href="#fixture">View evidence</a></div></article>
<article class="szl-holo-card szl-holo-card--roadmap"><span class="szl-holo-k">Deliberate boundaries</span><h2 class="szl-holo-title">Unknown stays unknown.</h2>
<p class="szl-holo-one">Missing evidence should remain visible without low-contrast text, decorative success badges, or invented readings.</p>
<div class="szl-empty" data-kind="permission"><span class="szl-empty__k">UNAVAILABLE</span><p class="szl-empty__d">This fixture has no provider connection.</p><button class="szl-empty__retry" type="button">Review requirements</button></div></article>
</div></section><section class="fixture-palette" aria-label="Command palette fixture"><div class="szl-pal"><div class="szl-pal-head">
<input aria-label="Find evidence" placeholder="Find evidence or an action"><button class="szl-pal-close" aria-label="Close fixture palette" type="button">×</button></div>
<div class="szl-pal-list"><button class="szl-pal-item sel">Inspect source revision</button><button class="szl-pal-item">Review unresolved evidence</button></div></div></section></main></html>'''


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--chromium", default=shutil.which("chromium") or shutil.which("chromium-browser"))
    args = parser.parse_args()
    if not args.chromium or not Path(args.chromium).is_file():
        parser.error("A locally installed Chromium executable is required; nothing is downloaded.")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        parser.error("The existing Playwright Python environment is required; no check was executed.")
    args.output.mkdir(parents=True, exist_ok=False)
    css = (ROOT / "static/shared/szl_command_bar.css").read_bytes()
    html = FIXTURE.replace("__LONG_ID__", "a" * 96).replace("__CSS__", css.decode("utf-8"))
    report = {"schema": "szl.shell-component-check/v1", "state": "FAIL", "checks": [],
              "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
              "css_sha256": hashlib.sha256(css).hexdigest(),
              "fixture_sha256": hashlib.sha256(html.encode()).hexdigest(),
              "scope": "OFFLINE_SYNTHETIC_COMPONENT_ONLY_SYSTEM_FONTS",
              "not_verified": ["full site", "live APIs", "HF projection", "vendored fonts", "WCAG conformance"]}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=args.chromium, headless=True,
                                        args=["--no-sandbox", "--disable-dev-shm-usage"])
            try:
                for width, height in ((320, 568), (375, 812), (768, 1024), (1440, 900)):
                    page = browser.new_page(viewport={"width": width, "height": height}, color_scheme="dark")
                    page.route("**/*", lambda route: route.abort())
                    errors = []
                    page.on("pageerror", lambda error: errors.append(type(error).__name__))
                    page.set_content(html, wait_until="domcontentloaded")
                    dimensions = page.evaluate("({content:document.documentElement.scrollWidth, viewport:document.documentElement.clientWidth})")
                    require(dimensions["content"] <= dimensions["viewport"], "horizontal overflow")
                    colors = {name: page.locator("#" + name + " .szl-dot").evaluate("e=>getComputedStyle(e).backgroundColor")
                              for name in ("unknown", "measured", "advisory", "off")}
                    require(colors["unknown"] == colors["advisory"] == colors["off"], "neutral state changed")
                    require(colors["measured"] != colors["unknown"], "measured state is indistinguishable")
                    require(page.locator("#software").evaluate("e=>getComputedStyle(e).color") != colors["measured"], "software implies measurement")
                    for target in page.locator(".szl-origins a,.szl-origins button,.szl-holo-act a,.szl-empty__retry,.szl-pal button").all():
                        rect = target.bounding_box()
                        require(rect is not None and rect["width"] >= 44 and rect["height"] >= 44, "small action target")
                    page.locator("body").click(position={"x": 1, "y": 1})
                    page.keyboard.press("Tab")
                    focus = page.evaluate("({id:document.activeElement.id, outline:getComputedStyle(document.activeElement).outlineStyle, width:parseFloat(getComputedStyle(document.activeElement).outlineWidth)})")
                    require(focus["id"] == "first-link" and focus["outline"] != "none" and focus["width"] >= 2, "keyboard focus not visible")
                    # A page-level monochrome/low-contrast override must not leak into components.
                    page.add_style_tag(content=":root{--proof:#00ff00;--muted:#000;--panel:#fff;--gray:#00ff00}")
                    require(page.locator("#advisory .szl-dot").evaluate("e=>getComputedStyle(e).backgroundColor") == colors["unknown"], "legacy token contamination")
                    page.emulate_media(reduced_motion="reduce")
                    page.locator("#measured").evaluate("e=>e.classList.add('szl-pulse')")
                    require(page.locator("#measured").evaluate("e=>getComputedStyle(e).animationName") == "none", "reduced motion ignored")
                    page.screenshot(path=str(args.output / (str(width) + ".png")), full_page=True)
                    page.emulate_media(forced_colors="active")
                    require(page.evaluate("matchMedia('(forced-colors: active)').matches"), "forced colors not active")
                    require(page.locator(".szl-holo-card").first.evaluate("e=>getComputedStyle(e,'::before').display") == "none", "decoration in forced colors")
                    require(not errors, "browser page error")
                    report["checks"].append({"width": width, "height": height, "state": "PASS", "colors": colors,
                                             "checks": ["overflow", "state separation", "targets", "focus", "token isolation", "reduced motion", "forced colors", "page errors"]})
                    page.close()
                report["state"] = "PASS"
            finally:
                browser.close()
    except Exception as error:
        report["error_type"] = type(error).__name__
        report["error"] = str(error)
    (args.output / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"state": report["state"], "scope": report["scope"], "completed_viewports": len(report["checks"])}))
    return 0 if report["state"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
