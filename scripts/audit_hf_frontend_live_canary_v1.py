#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import urllib.request
from pathlib import Path
from typing import Any

VIEWPORTS = (
    (360, 800),
    (390, 844),
    (768, 1024),
    (1024, 900),
    (1440, 1000),
)
TARGETS = {
    "organization-card": "https://szlholdings-readme.static.hf.space/",
    "a11oy-space": "https://szlholdings-a11oy.hf.space/",
    "a11oy-domain": "https://a-11-oy.com/",
}
IDENTITY_URLS = {
    "organization_deployment": "https://szlholdings-readme.static.hf.space/deployment.json",
    "a11oy_space_build": "https://szlholdings-a11oy.hf.space/api/build-info",
    "a11oy_domain_build": "https://a-11-oy.com/api/build-info",
    "a11oy_space_metadata": "https://huggingface.co/api/spaces/SZLHOLDINGS/a11oy",
    "organization_space_metadata": "https://huggingface.co/api/spaces/SZLHOLDINGS/README",
}
SHA40 = re.compile(r"^[0-9a-f]{40}$")


def _read_json(url: str, timeout: int = 30) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "SZL-HF-frontend-live-canary/1.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root from {url} is not an object")
    return payload


def _valid_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA40.fullmatch(value.strip().lower()))


def _device_width_viewport_meta(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    directives: dict[str, str] = {}
    for item in value.split(","):
        key, separator, raw_value = item.strip().partition("=")
        if separator:
            directives[key.strip().casefold()] = raw_value.strip().casefold()
    return directives.get("width") == "device-width"


def _organization_deployment_revision(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    source = payload.get("source")
    target = payload.get("target")
    if not isinstance(source, dict) or not isinstance(target, dict):
        return None
    revision = source.get("revision")
    if not (
        payload.get("schema") == "szl.hf-static-deployment/v1"
        and source.get("repository") == "szl-holdings/.github"
        and source.get("manifest") == "huggingface/org-card.manifest.json"
        and target.get("repo_id") == "SZLHOLDINGS/README"
        and target.get("repo_type") == "space"
        and target.get("live_base_url")
        == "https://szlholdings-readme.static.hf.space"
        and _valid_sha(revision)
    ):
        return None
    return str(revision).strip().lower()


def _build_identity(payload: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    build = payload.get("build") or {}
    if not isinstance(build, dict):
        return None, None, None
    revision = build.get("revision")
    source = build.get("revision_source")
    status = payload.get("status")
    return (
        str(revision).lower() if _valid_sha(revision) else None,
        str(source) if isinstance(source, str) else None,
        str(status) if isinstance(status, str) else None,
    )


def evaluate_page_result(result: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    metrics = result.get("metrics") or {}
    status = result.get("http_status")
    if not isinstance(status, int) or status >= 400:
        failures.append({"code": "HTTP_FAILURE", "detail": f"status={status}"})
    if result.get("load_error"):
        failures.append({"code": "LOAD_FAILURE", "detail": str(result["load_error"])})
    viewport_meta = metrics.get("viewport_meta")
    if not viewport_meta:
        failures.append({"code": "VIEWPORT_META_MISSING", "detail": "viewport metadata is absent"})
    elif not _device_width_viewport_meta(viewport_meta):
        failures.append(
            {
                "code": "VIEWPORT_META_UNSAFE",
                "detail": f"viewport metadata is not device-width bound: {viewport_meta!r}",
            }
        )
    if metrics.get("horizontal_overflow") is True:
        failures.append(
            {
                "code": "HORIZONTAL_OVERFLOW",
                "detail": f"scroll_width={metrics.get('scroll_width')} inner_width={metrics.get('inner_width')}",
            }
        )
    undersized = metrics.get("undersized_primary_targets") or []
    exhausted = [
        item
        for item in undersized
        if isinstance(item, dict) and item.get("hit_area_scan_exhausted") is True
    ]
    measured_undersized = [item for item in undersized if item not in exhausted]
    if measured_undersized:
        failures.append(
            {
                "code": "PRIMARY_TARGET_UNDERSIZED",
                "detail": f"{len(measured_undersized)} primary controls are below 44px",
                "examples": measured_undersized[:10],
            }
        )
    if exhausted:
        failures.append(
            {
                "code": "PRIMARY_TARGET_HIT_SCAN_EXHAUSTED",
                "detail": f"{len(exhausted)} primary controls exceeded the bounded hit-area scan",
                "examples": exhausted[:10],
            }
        )
    primary_targets = metrics.get("primary_targets")
    if (
        not isinstance(primary_targets, int)
        or isinstance(primary_targets, bool)
        or primary_targets <= 0
    ):
        failures.append(
            {
                "code": "PRIMARY_TARGETS_MISSING",
                "detail": "no visible primary interaction target was rendered",
            }
        )
    page_errors = result.get("page_errors") or []
    if page_errors:
        failures.append(
            {
                "code": "PAGE_SCRIPT_ERROR",
                "detail": f"{len(page_errors)} uncaught page errors",
                "examples": page_errors[:10],
            }
        )
    return failures


def evaluate_identity(
    identity: dict[str, Any], expected_source_sha: str
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    expected_source = (
        expected_source_sha.strip().lower()
        if _valid_sha(expected_source_sha)
        else None
    )
    if not expected_source:
        failures.append(
            {
                "code": "EXPECTED_PROTECTED_SOURCE_INVALID",
                "detail": f"expected protected source is not an immutable SHA: {expected_source_sha!r}",
            }
        )
    org_deployment = identity.get("organization_deployment") or {}
    if not _organization_deployment_revision(org_deployment):
        failures.append(
            {
                "code": "ORG_DEPLOYMENT_IDENTITY_FAILED",
                "detail": "organization deployment metadata is not bound to the canonical source manifest and target",
            }
        )

    space_build = identity.get("a11oy_space_build") or {}
    domain_build = identity.get("a11oy_domain_build") or {}
    space_revision, space_source, space_status = _build_identity(space_build)
    domain_revision, domain_source, domain_status = _build_identity(domain_build)
    if not (
        space_revision
        and space_revision == expected_source
        and space_source == "env:SZL_GIT_SHA"
        and space_status == "OBSERVED"
    ):
        failures.append(
            {
                "code": "SPACE_SOURCE_BINDING_FAILED",
                "detail": {
                    "revision": space_revision,
                    "expected_revision": expected_source,
                    "revision_source": space_source,
                    "status": space_status,
                },
            }
        )
    if not (
        domain_revision
        and domain_revision == expected_source
        and domain_source == "env:SZL_GIT_SHA"
        and domain_status == "OBSERVED"
    ):
        failures.append(
            {
                "code": "DOMAIN_SOURCE_BINDING_FAILED",
                "detail": {
                    "revision": domain_revision,
                    "expected_revision": expected_source,
                    "revision_source": domain_source,
                    "status": domain_status,
                },
            }
        )
    if space_revision and domain_revision and space_revision != domain_revision:
        failures.append(
            {
                "code": "DOMAIN_SPACE_SOURCE_DIVERGENCE",
                "detail": {"space": space_revision, "domain": domain_revision},
            }
        )

    metadata = identity.get("a11oy_space_metadata") or {}
    hf_sha = metadata.get("sha")
    runtime = metadata.get("runtime") or {}
    runtime_raw = runtime.get("raw") or {} if isinstance(runtime, dict) else {}
    runtime_sha = runtime.get("sha") or runtime_raw.get("sha") if isinstance(runtime, dict) else None
    runtime_stage = runtime.get("stage") if isinstance(runtime, dict) else None
    if not (_valid_sha(hf_sha) and runtime_sha == hf_sha and runtime_stage == "RUNNING"):
        failures.append(
            {
                "code": "HF_RUNTIME_IDENTITY_FAILED",
                "detail": {
                    "repository_sha": hf_sha,
                    "runtime_sha": runtime_sha,
                    "runtime_stage": runtime_stage,
                },
            }
        )

    organization_metadata = identity.get("organization_space_metadata") or {}
    organization_hf_sha = organization_metadata.get("sha")
    organization_runtime = organization_metadata.get("runtime") or {}
    organization_runtime_raw = (
        organization_runtime.get("raw") or {}
        if isinstance(organization_runtime, dict)
        else {}
    )
    organization_runtime_sha = (
        organization_runtime.get("sha") or organization_runtime_raw.get("sha")
        if isinstance(organization_runtime, dict)
        else None
    )
    organization_runtime_stage = (
        organization_runtime.get("stage")
        if isinstance(organization_runtime, dict)
        else None
    )
    organization_runtime_sha_matches = (
        organization_runtime_sha is None
        or (
            _valid_sha(organization_runtime_sha)
            and str(organization_runtime_sha).strip().lower()
            == str(organization_hf_sha).strip().lower()
        )
    )
    if not (
        organization_metadata.get("id") == "SZLHOLDINGS/README"
        and _valid_sha(organization_hf_sha)
        and organization_metadata.get("sdk") == "static"
        and organization_runtime_stage == "RUNNING"
        and organization_runtime_sha_matches
    ):
        failures.append(
            {
                "code": "ORG_HF_RUNTIME_IDENTITY_FAILED",
                "detail": {
                    "repository_sha": organization_hf_sha,
                    "runtime_sha": organization_runtime_sha,
                    "runtime_sha_exposed": organization_runtime_sha is not None,
                    "runtime_stage": organization_runtime_stage,
                    "space_id": organization_metadata.get("id"),
                    "sdk": organization_metadata.get("sdk"),
                },
            }
        )
    return failures


def build_summary(results: list[dict[str, Any]], identity_failures: list[dict[str, Any]]) -> dict[str, Any]:
    page_failures = sum(len(result.get("failures") or []) for result in results)
    return {
        "surfaces": len({result["surface"] for result in results}),
        "viewports": len({(result["viewport"]["width"], result["viewport"]["height"]) for result in results}),
        "render_checks": len(results),
        "page_failures": page_failures,
        "identity_failures": len(identity_failures),
        "console_errors_observed": sum(len(result.get("console_errors") or []) for result in results),
        "status": "PASS" if page_failures == 0 and not identity_failures else "BLOCKED",
    }


def audit(
    output_dir: Path,
    expected_source_sha: str,
    chrome: str | None = None,
) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    executable = chrome or shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")

    with sync_playwright() as playwright:
        launch_options: dict[str, Any] = {"headless": True}
        if executable:
            launch_options["executable_path"] = executable
        browser = playwright.chromium.launch(**launch_options)
        for surface, url in TARGETS.items():
            for width, height in VIEWPORTS:
                page = browser.new_page(viewport={"width": width, "height": height})
                console_errors: list[dict[str, str]] = []
                page_errors: list[str] = []
                page.on(
                    "console",
                    lambda message, bucket=console_errors: bucket.append(
                        {"type": message.type, "text": message.text}
                    )
                    if message.type == "error"
                    else None,
                )
                page.on("pageerror", lambda error, bucket=page_errors: bucket.append(str(error)))
                response = None
                load_error = None
                try:
                    response = page.goto(url, wait_until="domcontentloaded", timeout=45_000)
                    page.wait_for_timeout(1_500)
                except Exception as error:  # pragma: no cover - browser/network boundary
                    load_error = str(error)
                metrics = page.evaluate(
                    """() => {
                      const root = document.documentElement;
                      const meta = document.querySelector('meta[name="viewport"]');
                      const filterMakesTransparent = (filter) => {
                        for (const match of filter.matchAll(/opacity[(]([^)]*)[)]/gi)) {
                          const value = Number.parseFloat(match[1]);
                          if (Number.isFinite(value) && value <= 0) return true;
                        }
                        return false;
                      };
                      const visible = (el) => {
                        const rect = el.getBoundingClientRect();
                        if (!(rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.right > 0 && rect.top < window.innerHeight && rect.left < window.innerWidth)) return false;
                        for (let node = el; node instanceof Element; node = node.parentElement) {
                          const style = getComputedStyle(node);
                          if (style.display === 'none' || style.visibility === 'hidden' || style.visibility === 'collapse' || Number(style.opacity) <= 0 || filterMakesTransparent(style.filter) || style.pointerEvents === 'none') return false;
                          if (node.hasAttribute('hidden') || node.hasAttribute('inert') || node.getAttribute('aria-hidden') === 'true' || node.getAttribute('aria-disabled') === 'true') return false;
                        }
                        return true;
                      };
                      const effectiveBounds = (el) => {
                        const rect = el.getBoundingClientRect();
                        let left = Math.max(0, rect.left);
                        let right = Math.min(window.innerWidth, rect.right);
                        let top = Math.max(0, rect.top);
                        let bottom = Math.min(window.innerHeight, rect.bottom);
                        for (let node = el.parentElement; node instanceof Element; node = node.parentElement) {
                          const style = getComputedStyle(node);
                          const contain = style.contain.split(/\\s+/);
                          const clipsPaint = style.clipPath !== 'none' || contain.some(value => value === 'paint' || value === 'strict' || value === 'content');
                          const clipsX = clipsPaint || style.overflowX !== 'visible';
                          const clipsY = clipsPaint || style.overflowY !== 'visible';
                          if (clipsX || clipsY) {
                            const clip = node.getBoundingClientRect();
                            if (clipsX) { left = Math.max(left, clip.left); right = Math.min(right, clip.right); }
                            if (clipsY) { top = Math.max(top, clip.top); bottom = Math.min(bottom, clip.bottom); }
                          }
                        }
                        return {left, right, top, bottom, width: Math.max(0, right - left), height: Math.max(0, bottom - top)};
                      };
                      const hitAt = (el, x, y) => {
                        const hit = document.elementFromPoint(x, y);
                        return hit instanceof Element && (hit === el || el.contains(hit));
                      };
                      const hitTestable = (el) => {
                        const {left, right, top, bottom} = effectiveBounds(el);
                        if (!(right > left && bottom > top)) return false;
                        const insetX = Math.min(1, (right - left) / 2);
                        const insetY = Math.min(1, (bottom - top) / 2);
                        const points = [
                          [(left + right) / 2, (top + bottom) / 2],
                          [left + insetX, top + insetY],
                          [right - insetX, top + insetY],
                          [left + insetX, bottom - insetY],
                          [right - insetX, bottom - insetY],
                        ];
                        return points.some(([x, y]) => hitAt(el, x, y));
                      };
                      const maxHitCoverageCells = 1000000;
                      let remainingHitCoverageCells = maxHitCoverageCells;
                      const hasMinimumHitArea = (el, bounds) => {
                        if (bounds.width < 44 || bounds.height < 44) return false;
                        const sampleStep = 1 / Math.max(1, Math.min(4, window.devicePixelRatio || 1));
                        const originCountX = Math.floor((bounds.width - 44) / sampleStep) + 1;
                        const originCountY = Math.floor((bounds.height - 44) / sampleStep) + 1;
                        const windowCells = Math.ceil(44 / sampleStep - 0.5 - 1e-9);
                        const columns = originCountX + windowCells - 1;
                        const rows = originCountY + windowCells - 1;
                        const coverageCells = columns * rows;
                        if (!Number.isSafeInteger(coverageCells) || coverageCells > remainingHitCoverageCells) return null;
                        remainingHitCoverageCells -= coverageCells;
                        const stride = columns + 1;
                        const blockedPrefix = new Uint32Array((rows + 1) * stride);
                        for (let row = 0; row < rows; row += 1) {
                          let blockedInRow = 0;
                          const y = bounds.top + (row + 0.5) * sampleStep;
                          for (let column = 0; column < columns; column += 1) {
                            const x = bounds.left + (column + 0.5) * sampleStep;
                            if (!hitAt(el, x, y)) blockedInRow += 1;
                            blockedPrefix[(row + 1) * stride + column + 1] =
                              blockedPrefix[row * stride + column + 1] + blockedInRow;
                          }
                        }
                        for (let originY = 0; originY < originCountY; originY += 1) {
                          for (let originX = 0; originX < originCountX; originX += 1) {
                            const right = originX + windowCells;
                            const bottom = originY + windowCells;
                            const blocked =
                              blockedPrefix[bottom * stride + right]
                              - blockedPrefix[originY * stride + right]
                              - blockedPrefix[bottom * stride + originX]
                              + blockedPrefix[originY * stride + originX];
                            if (blocked === 0) return true;
                          }
                        }
                        return false;
                      };
                      const actionable = (el) => {
                        if (!visible(el) || !hitTestable(el) || el.matches(':disabled') || el.hasAttribute('disabled') || el.getAttribute('aria-disabled') === 'true') return false;
                        if (el.tagName === 'A') return Boolean((el.getAttribute('href') || '').trim());
                        if (el.tagName === 'BUTTON' || el.tagName === 'INPUT' || el.tagName === 'SELECT' || el.tagName === 'TEXTAREA') return true;
                        return el.getAttribute('role') === 'button' && el.tabIndex >= 0;
                      };
                      const selectors = ['button', '[role="button"]', '.btn', '.button', 'a[class*="btn"]', 'a[class*="button"]', 'header nav a', 'nav .cta'];
                      const nodes = [...new Set(selectors.flatMap(selector => [...document.querySelectorAll(selector)]))].filter(actionable);
                      const undersized = nodes.map((el) => {
                        const bounds = effectiveBounds(el);
                        const hitArea = hasMinimumHitArea(el, bounds);
                        return {
                          tag: el.tagName,
                          text: (el.innerText || el.getAttribute('aria-label') || '').trim().slice(0, 80),
                          href: el.getAttribute('href'),
                          width: Math.round(bounds.width * 100) / 100,
                          height: Math.round(bounds.height * 100) / 100,
                          hit_testable_44: hitArea,
                          hit_area_scan_exhausted: hitArea === null,
                        };
                      }).filter(item => item.width < 44 || item.height < 44 || item.hit_testable_44 !== true);
                      return {
                        title: document.title,
                        viewport_meta: meta ? meta.getAttribute('content') : null,
                        inner_width: window.innerWidth,
                        scroll_width: root.scrollWidth,
                        horizontal_overflow: root.scrollWidth > window.innerWidth + 2,
                        primary_targets: nodes.length,
                        undersized_primary_targets: undersized,
                        hit_area_sample_budget: maxHitCoverageCells,
                        hit_area_samples_reserved: maxHitCoverageCells - remainingHitCoverageCells,
                        release_marker: document.documentElement.getAttribute('data-szl-release') || document.body?.getAttribute('data-szl-release') || document.querySelector('[data-szl-release]')?.getAttribute('data-szl-release') || null,
                      };
                    }"""
                )
                screenshot = output_dir / f"{surface}-{width}x{height}.png"
                page.screenshot(path=str(screenshot), full_page=True)
                result = {
                    "surface": surface,
                    "url": url,
                    "viewport": {"width": width, "height": height},
                    "http_status": response.status if response else None,
                    "load_error": load_error,
                    "console_errors": console_errors,
                    "page_errors": page_errors,
                    "metrics": metrics,
                    "screenshot": screenshot.name,
                }
                result["failures"] = evaluate_page_result(result)
                results.append(result)
                page.close()
        browser.close()

    identity: dict[str, Any] = {}
    for name, url in IDENTITY_URLS.items():
        try:
            identity[name] = _read_json(url)
        except Exception as error:  # pragma: no cover - network boundary
            identity[name] = {"error": str(error)}
    identity_failures = evaluate_identity(identity, expected_source_sha)
    summary = build_summary(results, identity_failures)
    return {
        "schema": "szl.hf-frontend-live-canary/v1",
        "remote_mutation": False,
        "expected_source_sha": expected_source_sha.strip().lower(),
        "summary": summary,
        "identity": identity,
        "identity_failures": identity_failures,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("evidence/hf-frontend-live-canary"))
    parser.add_argument("--expected-source-sha", required=True)
    parser.add_argument("--chrome")
    args = parser.parse_args()
    report = audit(args.output_dir, args.expected_source_sha, args.chrome)
    report_path = args.output_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"]["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
