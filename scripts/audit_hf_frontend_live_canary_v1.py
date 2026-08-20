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


def _find_sha(node: Any) -> str | None:
    if _valid_sha(node):
        return str(node).strip().lower()
    if isinstance(node, dict):
        preferred = (
            "source_sha",
            "source_revision",
            "github_sha",
            "commit_sha",
            "revision",
            "sha",
        )
        for key in preferred:
            if key in node:
                found = _find_sha(node[key])
                if found:
                    return found
        for value in node.values():
            found = _find_sha(value)
            if found:
                return found
    if isinstance(node, list):
        for value in node:
            found = _find_sha(value)
            if found:
                return found
    return None


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
    if not metrics.get("viewport_meta"):
        failures.append({"code": "VIEWPORT_META_MISSING", "detail": "viewport metadata is absent"})
    if metrics.get("horizontal_overflow") is True:
        failures.append(
            {
                "code": "HORIZONTAL_OVERFLOW",
                "detail": f"scroll_width={metrics.get('scroll_width')} inner_width={metrics.get('inner_width')}",
            }
        )
    undersized = metrics.get("undersized_primary_targets") or []
    if undersized:
        failures.append(
            {
                "code": "PRIMARY_TARGET_UNDERSIZED",
                "detail": f"{len(undersized)} primary controls are below 44px",
                "examples": undersized[:10],
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


def evaluate_identity(identity: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    org_deployment = identity.get("organization_deployment") or {}
    if not _find_sha(org_deployment):
        failures.append(
            {
                "code": "ORG_SOURCE_REVISION_UNAVAILABLE",
                "detail": "organization deployment metadata exposes no immutable revision",
            }
        )

    space_build = identity.get("a11oy_space_build") or {}
    domain_build = identity.get("a11oy_domain_build") or {}
    space_revision, space_source, space_status = _build_identity(space_build)
    domain_revision, domain_source, domain_status = _build_identity(domain_build)
    if not (
        space_revision
        and space_source == "env:SZL_GIT_SHA"
        and space_status == "OBSERVED"
    ):
        failures.append(
            {
                "code": "SPACE_SOURCE_BINDING_FAILED",
                "detail": {
                    "revision": space_revision,
                    "revision_source": space_source,
                    "status": space_status,
                },
            }
        )
    if not (
        domain_revision
        and domain_source == "env:SZL_GIT_SHA"
        and domain_status == "OBSERVED"
    ):
        failures.append(
            {
                "code": "DOMAIN_SOURCE_BINDING_FAILED",
                "detail": {
                    "revision": domain_revision,
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


def audit(output_dir: Path, chrome: str | None = None) -> dict[str, Any]:
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
                      const visible = (el) => {
                        const style = getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
                      };
                      const selectors = ['button', '[role="button"]', '.btn', '.button', 'a[class*="btn"]', 'a[class*="button"]', 'header nav a', 'nav .cta'];
                      const nodes = [...new Set(selectors.flatMap(selector => [...document.querySelectorAll(selector)]))].filter(visible);
                      const undersized = nodes.map((el) => {
                        const rect = el.getBoundingClientRect();
                        return {
                          tag: el.tagName,
                          text: (el.innerText || el.getAttribute('aria-label') || '').trim().slice(0, 80),
                          href: el.getAttribute('href'),
                          width: Math.round(rect.width * 100) / 100,
                          height: Math.round(rect.height * 100) / 100,
                        };
                      }).filter(item => item.width < 44 || item.height < 44);
                      return {
                        title: document.title,
                        viewport_meta: meta ? meta.getAttribute('content') : null,
                        inner_width: window.innerWidth,
                        scroll_width: root.scrollWidth,
                        horizontal_overflow: root.scrollWidth > window.innerWidth + 2,
                        primary_targets: nodes.length,
                        undersized_primary_targets: undersized,
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
    identity_failures = evaluate_identity(identity)
    summary = build_summary(results, identity_failures)
    return {
        "schema": "szl.hf-frontend-live-canary/v1",
        "remote_mutation": False,
        "summary": summary,
        "identity": identity,
        "identity_failures": identity_failures,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("evidence/hf-frontend-live-canary"))
    parser.add_argument("--chrome")
    args = parser.parse_args()
    report = audit(args.output_dir, args.chrome)
    report_path = args.output_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"]["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
