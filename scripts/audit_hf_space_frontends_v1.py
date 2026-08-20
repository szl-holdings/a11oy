#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

HF_SPACES_API = "https://huggingface.co/api/spaces"
HF_ORG = "SZLHOLDINGS"
VIEWPORTS = (
    (360, 800),
    (390, 844),
    (768, 1024),
    (1024, 900),
    (1440, 1000),
)
SHA40 = re.compile(r"^[0-9a-f]{40}$")
NON_RUNNING_STAGES = {
    "BUILD_ERROR",
    "CONFIG_ERROR",
    "DELETED",
    "ERROR",
    "NO_APP_FILE",
    "PAUSED",
    "RUNTIME_ERROR",
    "STOPPED",
    "UNAVAILABLE",
}
PRIMARY_SELECTORS = (
    "button[type='submit']",
    "button.primary",
    "button[class*='primary']",
    "a[role='button']",
    "a.btn",
    "a[class*='button']",
    ".btn",
    ".button",
    ".gr-button-primary",
    "[data-testid*='submit']",
    "header nav a",
)


def _request_json(url: str, timeout: int = 45) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "SZL-HF-Space-frontend-census/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def fetch_spaces(author: str = HF_ORG) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(
        {
            "author": author,
            "limit": 100,
            "full": "true",
        }
    )
    payload = _request_json(f"{HF_SPACES_API}?{query}")
    if not isinstance(payload, list):
        raise ValueError("Hugging Face Spaces API did not return a list")
    records = [item for item in payload if isinstance(item, dict)]
    prefix = author.lower() + "/"
    records = [
        item
        for item in records
        if isinstance(item.get("id"), str)
        and item["id"].lower().startswith(prefix)
    ]
    records.sort(key=lambda item: item["id"].lower())
    if not records:
        raise ValueError(f"no public Spaces were returned for {author}")
    return records


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


def _runtime(record: dict[str, Any]) -> dict[str, Any]:
    runtime = record.get("runtime")
    return runtime if isinstance(runtime, dict) else {}


def _card_data(record: dict[str, Any]) -> dict[str, Any]:
    for key in ("cardData", "card_data"):
        value = record.get(key)
        if isinstance(value, dict):
            return value
    return {}


def runtime_stage(record: dict[str, Any]) -> str:
    runtime = _runtime(record)
    value = runtime.get("stage") or record.get("runtimeStage") or record.get("stage")
    if isinstance(value, str) and value.strip():
        return value.strip().upper()
    return "UNAVAILABLE"


def runtime_sha(record: dict[str, Any]) -> str | None:
    runtime = _runtime(record)
    raw = runtime.get("raw") if isinstance(runtime.get("raw"), dict) else {}
    for value in (runtime.get("sha"), raw.get("sha")):
        if _valid_sha(value):
            return str(value).strip().lower()
    return None


def repository_sha(record: dict[str, Any]) -> str | None:
    value = record.get("sha")
    return str(value).strip().lower() if _valid_sha(value) else None


def _host_from_record(record: dict[str, Any]) -> str | None:
    runtime = _runtime(record)
    raw = runtime.get("raw") if isinstance(runtime.get("raw"), dict) else {}
    candidates = (
        record.get("host"),
        runtime.get("host"),
        raw.get("host"),
        record.get("subdomain"),
        runtime.get("subdomain"),
        raw.get("subdomain"),
    )
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        text = candidate.strip()
        if not text:
            continue
        parsed = urllib.parse.urlparse(text if "://" in text else "//" + text)
        host = parsed.netloc or parsed.path
        host = host.strip("/").lower()
        if host.endswith(".hf.space"):
            return host
    return None


def _fallback_host(repo_id: str) -> str:
    owner, name = repo_id.split("/", 1)
    slug = f"{owner}-{name}".lower()
    slug = re.sub(r"[^a-z0-9-]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug + ".hf.space"


def space_url(record: dict[str, Any]) -> str:
    repo_id = str(record["id"])
    return "https://" + (_host_from_record(record) or _fallback_host(repo_id)) + "/"


def sdk(record: dict[str, Any]) -> str | None:
    card = _card_data(record)
    value = record.get("sdk") or card.get("sdk")
    return str(value).strip().lower() if isinstance(value, str) and value.strip() else None


def app_file(record: dict[str, Any]) -> str | None:
    card = _card_data(record)
    for key in ("app_file", "appFile"):
        value = card.get(key) or record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def short_description(record: dict[str, Any]) -> str | None:
    card = _card_data(record)
    for key in ("short_description", "shortDescription"):
        value = card.get(key) or record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def metadata_failures(record: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    repo_id = str(record["id"])
    repo_revision = repository_sha(record)
    run_revision = runtime_sha(record)
    stage = runtime_stage(record)
    space_sdk = sdk(record)
    description = short_description(record)

    if not repo_revision:
        failures.append(
            {
                "code": "HF_REPOSITORY_SHA_UNAVAILABLE",
                "priority": "P0",
                "detail": "The public Space record exposes no immutable repository SHA.",
            }
        )
    if run_revision and repo_revision and run_revision != repo_revision:
        failures.append(
            {
                "code": "HF_RUNTIME_SHA_DIVERGENT",
                "priority": "P0",
                "detail": {
                    "repository_sha": repo_revision,
                    "runtime_sha": run_revision,
                },
            }
        )
    if stage != "RUNNING":
        failures.append(
            {
                "code": "SPACE_RUNTIME_NOT_RUNNING",
                "priority": "P1",
                "detail": f"Observed runtime stage is {stage}.",
            }
        )
    if not space_sdk:
        failures.append(
            {
                "code": "SPACE_SDK_UNAVAILABLE",
                "priority": "P1",
                "detail": "The public Space record exposes no SDK.",
            }
        )
    if not description:
        failures.append(
            {
                "code": "SHORT_DESCRIPTION_UNAVAILABLE",
                "priority": "P1",
                "detail": "The public Space card exposes no short_description.",
            }
        )
    elif len(description) > 60:
        failures.append(
            {
                "code": "SHORT_DESCRIPTION_TOO_LONG",
                "priority": "P1",
                "detail": {
                    "length": len(description),
                    "maximum": 60,
                },
            }
        )
    if space_sdk in {"static", "gradio", "streamlit"} and not app_file(record):
        failures.append(
            {
                "code": "APP_FILE_UNAVAILABLE",
                "priority": "P2",
                "detail": f"The {space_sdk} Space card exposes no app_file.",
            }
        )
    if repo_id.lower() == f"{HF_ORG.lower()}/readme" and space_sdk != "static":
        failures.append(
            {
                "code": "ORG_CARD_SDK_DIVERGENT",
                "priority": "P0",
                "detail": f"The organization card must be a static Space; observed SDK is {space_sdk!r}.",
            }
        )
    return failures


def evaluate_page(result: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = result.get("metrics") or {}
    failures: list[dict[str, Any]] = []
    status = result.get("http_status")
    if not isinstance(status, int) or status >= 400:
        failures.append(
            {
                "code": "HTTP_FAILURE",
                "priority": "P0",
                "detail": f"HTTP status is {status!r}.",
            }
        )
    if result.get("load_error"):
        failures.append(
            {
                "code": "PAGE_LOAD_FAILURE",
                "priority": "P0",
                "detail": str(result["load_error"]),
            }
        )
    viewport_meta = metrics.get("viewport_meta")
    if not viewport_meta:
        failures.append(
            {
                "code": "VIEWPORT_META_MISSING",
                "priority": "P1",
                "detail": "No viewport metadata was rendered.",
            }
        )
    elif not _device_width_viewport_meta(viewport_meta):
        failures.append(
            {
                "code": "VIEWPORT_META_UNSAFE",
                "priority": "P1",
                "detail": f"Viewport metadata is not device-width bound: {viewport_meta!r}.",
            }
        )
    if metrics.get("horizontal_overflow") is True:
        failures.append(
            {
                "code": "HORIZONTAL_OVERFLOW",
                "priority": "P1",
                "detail": {
                    "inner_width": metrics.get("inner_width"),
                    "scroll_width": metrics.get("scroll_width"),
                },
            }
        )
    undersized = metrics.get("undersized_primary_targets") or []
    if undersized:
        failures.append(
            {
                "code": "PRIMARY_TARGET_UNDERSIZED",
                "priority": "P1",
                "detail": f"{len(undersized)} primary controls are smaller than 44px.",
                "examples": undersized[:10],
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
                "priority": "P1",
                "detail": "No visible primary interaction target was rendered.",
            }
        )
    page_errors = result.get("page_errors") or []
    if page_errors:
        failures.append(
            {
                "code": "UNCAUGHT_PAGE_ERROR",
                "priority": "P1",
                "detail": f"{len(page_errors)} uncaught page errors were observed.",
                "examples": page_errors[:10],
            }
        )
    return failures


def _page_metrics(page) -> dict[str, Any]:
    selectors = json.dumps(list(PRIMARY_SELECTORS))
    return page.evaluate(
        f"""() => {{
          const root = document.documentElement;
          const meta = document.querySelector('meta[name="viewport"]');
          const visible = (el) => {{
            const style = getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
          }};
          const selectors = {selectors};
          const nodes = [...new Set(selectors.flatMap(selector => [...document.querySelectorAll(selector)]))].filter(visible);
          const undersized = nodes.map((el) => {{
            const rect = el.getBoundingClientRect();
            return {{
              tag: el.tagName,
              text: (el.innerText || el.getAttribute('aria-label') || '').trim().slice(0, 80),
              href: el.getAttribute('href'),
              width: Math.round(rect.width * 100) / 100,
              height: Math.round(rect.height * 100) / 100,
            }};
          }}).filter(item => item.width < 44 || item.height < 44);
          return {{
            title: document.title,
            viewport_meta: meta ? meta.getAttribute('content') : null,
            inner_width: window.innerWidth,
            scroll_width: root.scrollWidth,
            horizontal_overflow: root.scrollWidth > window.innerWidth + 2,
            primary_targets: nodes.length,
            undersized_primary_targets: undersized,
            release_marker: document.documentElement.getAttribute('data-szl-release') || document.body?.getAttribute('data-szl-release') || document.querySelector('[data-szl-release]')?.getAttribute('data-szl-release') || null,
          }};
        }}"""
    )


def audit_spaces(
    records: list[dict[str, Any]],
    output_dir: Path,
    chrome: str | None = None,
) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    output_dir.mkdir(parents=True, exist_ok=True)
    screenshots = output_dir / "screenshots"
    screenshots.mkdir(parents=True, exist_ok=True)
    executable = (
        chrome
        or shutil.which("google-chrome")
        or shutil.which("chromium")
        or shutil.which("chromium-browser")
    )
    results: list[dict[str, Any]] = []

    with sync_playwright() as playwright:
        launch: dict[str, Any] = {"headless": True}
        if executable:
            launch["executable_path"] = executable
        browser = playwright.chromium.launch(**launch)
        for record in records:
            repo_id = str(record["id"])
            stage = runtime_stage(record)
            asset = {
                "space_id": repo_id,
                "url": space_url(record),
                "sdk": sdk(record),
                "app_file": app_file(record),
                "short_description": short_description(record),
                "repository_sha": repository_sha(record),
                "runtime_sha": runtime_sha(record),
                "runtime_stage": stage,
                "metadata_failures": metadata_failures(record),
                "viewport_results": [],
            }
            if stage in NON_RUNNING_STAGES or stage != "RUNNING":
                results.append(asset)
                continue

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
                    response = page.goto(
                        asset["url"],
                        wait_until="domcontentloaded",
                        timeout=35_000,
                    )
                    page.wait_for_timeout(1_000)
                except Exception as error:  # pragma: no cover - public network boundary
                    load_error = str(error)
                try:
                    metrics = _page_metrics(page)
                except Exception as error:  # pragma: no cover - broken page boundary
                    metrics = {
                        "viewport_meta": None,
                        "inner_width": width,
                        "scroll_width": None,
                        "horizontal_overflow": None,
                        "primary_targets": 0,
                        "undersized_primary_targets": [],
                        "metrics_error": str(error),
                    }
                viewport_result = {
                    "viewport": {"width": width, "height": height},
                    "http_status": response.status if response else None,
                    "load_error": load_error,
                    "console_errors": console_errors,
                    "page_errors": page_errors,
                    "metrics": metrics,
                }
                viewport_result["failures"] = evaluate_page(viewport_result)
                if viewport_result["failures"] and width in {390, 1440}:
                    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", repo_id).strip("-")
                    path = screenshots / f"{safe}-{width}x{height}.png"
                    try:
                        page.screenshot(path=str(path), full_page=True)
                        viewport_result["screenshot"] = str(path.relative_to(output_dir))
                    except Exception as error:  # pragma: no cover
                        viewport_result["screenshot_error"] = str(error)
                asset["viewport_results"].append(viewport_result)
                page.close()
            results.append(asset)
        browser.close()

    priority_counts: Counter[str] = Counter()
    code_counts: Counter[str] = Counter()
    blocked_assets = 0
    running_assets = 0
    viewport_checks = 0
    for asset in results:
        if asset["runtime_stage"] == "RUNNING":
            running_assets += 1
        failures = list(asset["metadata_failures"])
        for viewport in asset["viewport_results"]:
            viewport_checks += 1
            failures.extend(viewport["failures"])
        asset["failures"] = failures
        asset["status"] = "PASS" if not failures else "BLOCKED"
        if failures:
            blocked_assets += 1
        for failure in failures:
            priority_counts[failure["priority"]] += 1
            code_counts[failure["code"]] += 1

    summary = {
        "spaces_observed": len(results),
        "spaces_running": running_assets,
        "spaces_blocked": blocked_assets,
        "spaces_passing": len(results) - blocked_assets,
        "viewport_classes": len(VIEWPORTS),
        "viewport_checks": viewport_checks,
        "failures_total": sum(priority_counts.values()),
        "failures_by_priority": dict(sorted(priority_counts.items())),
        "failures_by_code": dict(sorted(code_counts.items())),
        "status": "PASS" if blocked_assets == 0 else "BLOCKED",
    }
    return {
        "schema": "szl.hf-space-frontend-census/v1",
        "organization": HF_ORG,
        "remote_mutation": False,
        "viewports": [
            {"width": width, "height": height} for width, height in VIEWPORTS
        ],
        "summary": summary,
        "spaces": results,
    }


def write_csv(report: dict[str, Any], path: Path) -> None:
    rows: list[dict[str, Any]] = []
    for asset in report["spaces"]:
        codes = sorted({failure["code"] for failure in asset["failures"]})
        priorities = sorted({failure["priority"] for failure in asset["failures"]})
        rows.append(
            {
                "space_id": asset["space_id"],
                "status": asset["status"],
                "runtime_stage": asset["runtime_stage"],
                "sdk": asset["sdk"],
                "repository_sha": asset["repository_sha"],
                "runtime_sha": asset["runtime_sha"],
                "failure_priorities": ",".join(priorities),
                "failure_codes": ",".join(codes),
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["space_id"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("evidence/hf-space-frontend-census"))
    parser.add_argument("--chrome")
    parser.add_argument("--author", default=HF_ORG)
    args = parser.parse_args()

    records = fetch_spaces(args.author)
    report = audit_spaces(records, args.output_dir, args.chrome)
    report_path = args.output_dir / "report.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_csv(report, args.output_dir / "summary.csv")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"]["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
