#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fail-closed public-product topology and exact-source witness.

This witness distinguishes public products from independently testable internal
capability planes. It performs fixed-origin GET requests only, stores no remote
response bodies in its receipt, and grants no deployment or execution authority.

Approved public topology (five products):

* Killinchu — defense, cyber-resilience, and maritime command;
* Terra — real-estate intelligence;
* PRISM Counsel — legal matter intelligence;
* PURIQ Finance — financial intelligence;
* Lyte — business observability.

Sentra and Vessels are capability planes inside Killinchu, not additional public
products. Aegis is a portfolio label. IMMUNE remains migration-gated until its
unique admission, signed-authority, and tripwire contracts pass parity.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

SCHEMA = "szl.estate-product-topology-witness/v1"
USER_AGENT = "SZLHOLDINGS-EstateTopologyWitness/1.0"
MAX_BODY_BYTES = 1_048_576
DEFAULT_TIMEOUT_SECONDS = 18.0

PUBLIC_PRODUCTS: tuple[dict[str, Any], ...] = (
    {
        "slug": "killinchu",
        "title": "Killinchu",
        "space": "SZLHOLDINGS/killinchu",
        "host": "https://szlholdings-killinchu.hf.space",
        "source_repository": "szl-holdings/killinchu",
        "routes": (
            "/api/build-info",
            "/api/defend/status",
            "/api/defend/readyz",
            "/api/defend/source",
            "/defend",
            "/resilience",
        ),
    },
    {
        "slug": "terra",
        "title": "Terra",
        "space": "SZLHOLDINGS/terra",
        "host": "https://szlholdings-terra.hf.space",
        "source_repository": "szl-holdings/a11oy",
        "routes": ("/healthz", "/api/source", "/api/build-info"),
    },
    {
        "slug": "counsel",
        "title": "PRISM Counsel",
        "space": "SZLHOLDINGS/counsel",
        "host": "https://szlholdings-counsel.hf.space",
        "source_repository": "szl-holdings/a11oy",
        "routes": ("/healthz", "/api/source", "/api/build-info"),
    },
    {
        "slug": "finance",
        "title": "PURIQ Finance",
        "space": "SZLHOLDINGS/finance",
        "host": "https://szlholdings-finance.hf.space",
        "source_repository": "szl-holdings/a11oy",
        "routes": ("/healthz", "/api/source", "/api/build-info"),
    },
    {
        "slug": "lyte",
        "title": "Lyte",
        "space": "SZLHOLDINGS/lyte",
        "host": "https://szlholdings-lyte.hf.space",
        "source_repository": "szl-holdings/a11oy",
        "routes": ("/healthz", "/api/source", "/api/build-info"),
    },
)

INTERNAL_SERVICES: tuple[dict[str, str], ...] = (
    {
        "slug": "vertical-services",
        "space": "SZLHOLDINGS/vertical-services",
        "host": "https://szlholdings-vertical-services.hf.space",
        "source_repository": "szl-holdings/vertical-services",
    },
)

FOLDED_CAPABILITY_PLANES: tuple[dict[str, str], ...] = (
    {
        "slug": "sentra",
        "canonical_product": "killinchu",
        "canonical_route": "https://szlholdings-killinchu.hf.space/defend",
    },
    {
        "slug": "vessels",
        "canonical_product": "killinchu",
        "canonical_route": "https://szlholdings-killinchu.hf.space/resilience",
    },
)

PORTFOLIO_LABELS = ("aegis",)
MIGRATION_GATED = ("immune",)

GITHUB_BRANCH_URLS = {
    repository: f"https://api.github.com/repos/{repository}/branches/main"
    for repository in {
        item["source_repository"] for item in PUBLIC_PRODUCTS
    }
    | {item["source_repository"] for item in INTERNAL_SERVICES}
}


@dataclass(frozen=True)
class HttpResult:
    url: str
    status: int
    content_type: str
    body: bytes
    elapsed_ms: float
    error: str | None = None

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300 and self.error is None


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def default_fetch(url: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> HttpResult:
    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Accept": "application/json,text/html;q=0.9,text/plain;q=0.8",
            "User-Agent": USER_AGENT,
        },
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(MAX_BODY_BYTES + 1)
            if len(body) > MAX_BODY_BYTES:
                raise RuntimeError("bounded response limit exceeded")
            return HttpResult(
                url=url,
                status=int(response.status),
                content_type=str(response.headers.get("content-type", "")),
                body=body,
                elapsed_ms=round((time.monotonic() - started) * 1000, 2),
            )
    except urllib.error.HTTPError as exc:
        body = exc.read(MAX_BODY_BYTES + 1)
        return HttpResult(
            url=url,
            status=int(exc.code),
            content_type=str(exc.headers.get("content-type", "")),
            body=body[:MAX_BODY_BYTES],
            elapsed_ms=round((time.monotonic() - started) * 1000, 2),
            error=f"HTTPError:{exc.code}",
        )
    except Exception as exc:  # bounded network witness; error type is sufficient
        return HttpResult(
            url=url,
            status=0,
            content_type="",
            body=b"",
            elapsed_ms=round((time.monotonic() - started) * 1000, 2),
            error=type(exc).__name__,
        )


def parse_json(result: HttpResult) -> dict[str, Any] | list[Any] | None:
    if not result.body:
        return None
    try:
        value = json.loads(result.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, (dict, list)) else None


def recursive_values(value: Any, keys: Iterable[str]) -> list[str]:
    wanted = set(keys)
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in wanted and isinstance(item, str):
                found.append(item)
            found.extend(recursive_values(item, wanted))
    elif isinstance(value, list):
        for item in value:
            found.extend(recursive_values(item, wanted))
    return found


def exact_sha(value: Any) -> str | None:
    for candidate in recursive_values(
        value,
        ("source_revision", "source_sha", "git_sha", "github_sha"),
    ):
        normalized = candidate.strip().lower()
        if len(normalized) == 40 and all(ch in "0123456789abcdef" for ch in normalized):
            return normalized
    return None


def github_main_shas(
    fetch: Callable[[str, float], HttpResult],
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    shas: dict[str, str] = {}
    observations: list[dict[str, Any]] = []
    for repository, url in sorted(GITHUB_BRANCH_URLS.items()):
        result = fetch(url, DEFAULT_TIMEOUT_SECONDS)
        payload = parse_json(result)
        sha = None
        if isinstance(payload, dict):
            commit = payload.get("commit")
            if isinstance(commit, dict) and isinstance(commit.get("sha"), str):
                candidate = commit["sha"].strip().lower()
                if len(candidate) == 40:
                    sha = candidate
        if sha:
            shas[repository] = sha
        observations.append(
            {
                "kind": "github-default-branch",
                "repository": repository,
                "url": url,
                "http_status": result.status,
                "elapsed_ms": result.elapsed_ms,
                "response_sha256": sha256_bytes(result.body) if result.body else None,
                "main_sha": sha,
                "pass": bool(result.ok and sha),
                "error": result.error,
            }
        )
    return shas, observations


def hf_space_metadata(
    space: str,
    fetch: Callable[[str, float], HttpResult],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    url = f"https://huggingface.co/api/spaces/{space}"
    result = fetch(url, DEFAULT_TIMEOUT_SECONDS)
    payload = parse_json(result)
    body = payload if isinstance(payload, dict) else None
    runtime = body.get("runtime") if body else None
    stage = runtime.get("stage") if isinstance(runtime, dict) else None
    sha = body.get("sha") if body and isinstance(body.get("sha"), str) else None
    return body, {
        "kind": "hf-space-metadata",
        "space": space,
        "url": url,
        "http_status": result.status,
        "stage": stage,
        "hf_revision": sha,
        "elapsed_ms": result.elapsed_ms,
        "response_sha256": sha256_bytes(result.body) if result.body else None,
        "pass": bool(result.ok and stage == "RUNNING"),
        "error": result.error,
    }


def route_observation(
    *,
    product: str,
    url: str,
    fetch: Callable[[str, float], HttpResult],
) -> tuple[Any, dict[str, Any]]:
    result = fetch(url, DEFAULT_TIMEOUT_SECONDS)
    payload = parse_json(result)
    marker = None
    if payload is None and result.body:
        text = result.body.decode("utf-8", errors="replace").lower()
        marker = product.lower() in text or "szl" in text
    return payload, {
        "kind": "public-route",
        "product": product,
        "url": url,
        "http_status": result.status,
        "content_type": result.content_type.split(";", 1)[0],
        "elapsed_ms": result.elapsed_ms,
        "response_sha256": sha256_bytes(result.body) if result.body else None,
        "json_object": isinstance(payload, dict),
        "html_identity_marker": marker,
        "pass": bool(result.ok and (payload is not None or marker is True)),
        "error": result.error,
    }


def folded_space_observation(
    item: dict[str, str],
    fetch: Callable[[str, float], HttpResult],
) -> dict[str, Any]:
    slug = item["slug"]
    space = f"SZLHOLDINGS/{slug}"
    metadata_url = f"https://huggingface.co/api/spaces/{space}"
    result = fetch(metadata_url, DEFAULT_TIMEOUT_SECONDS)
    if result.status == 404:
        return {
            "kind": "folded-space-retirement",
            "space": space,
            "canonical_product": item["canonical_product"],
            "canonical_route": item["canonical_route"],
            "state": "ABSENT",
            "http_status": 404,
            "pass": True,
        }

    readme_url = f"https://huggingface.co/spaces/{space}/raw/main/README.md"
    readme = fetch(readme_url, DEFAULT_TIMEOUT_SECONDS)
    text = readme.body.decode("utf-8", errors="replace").lower()
    tombstoned = (
        readme.ok
        and "retired" in text
        and "killinchu" in text
        and ("canonical" in text or "consolidated" in text)
    )
    return {
        "kind": "folded-space-retirement",
        "space": space,
        "canonical_product": item["canonical_product"],
        "canonical_route": item["canonical_route"],
        "state": "TOMBSTONED" if tombstoned else "RETIREMENT_REQUIRED",
        "http_status": result.status,
        "readme_http_status": readme.status,
        "readme_sha256": sha256_bytes(readme.body) if readme.body else None,
        "pass": tombstoned,
    }


def assess_once(
    fetch: Callable[[str, float], HttpResult] = default_fetch,
) -> dict[str, Any]:
    started_at = utc_now()
    observations: list[dict[str, Any]] = []
    main_shas, github_observations = github_main_shas(fetch)
    observations.extend(github_observations)

    product_results: list[dict[str, Any]] = []
    for product in PUBLIC_PRODUCTS:
        _, metadata = hf_space_metadata(product["space"], fetch)
        observations.append(metadata)
        route_payloads: dict[str, Any] = {}
        route_results: list[dict[str, Any]] = []
        for route in product["routes"]:
            url = f"{product['host']}{route}"
            payload, observation = route_observation(
                product=product["slug"],
                url=url,
                fetch=fetch,
            )
            route_payloads[route] = payload
            route_results.append(observation)
            observations.append(observation)

        build_payload = route_payloads.get("/api/build-info")
        observed_revision = exact_sha(build_payload)
        expected_revision = main_shas.get(product["source_repository"])
        revision_match = bool(
            observed_revision
            and expected_revision
            and observed_revision == expected_revision
        )
        source_observation = {
            "kind": "exact-source-binding",
            "product": product["slug"],
            "space": product["space"],
            "source_repository": product["source_repository"],
            "expected_revision": expected_revision,
            "observed_revision": observed_revision,
            "pass": revision_match,
        }
        observations.append(source_observation)

        additional_pass = True
        additional: dict[str, Any] = {}
        if product["slug"] == "killinchu":
            status = route_payloads.get("/api/defend/status")
            ready = route_payloads.get("/api/defend/readyz")
            status_object = status if isinstance(status, dict) else {}
            ready_object = ready if isinstance(ready, dict) else {}
            defend_ready = bool(
                status_object
                and ready_object
                and status_object.get("status") not in {"UNAVAILABLE", "ERROR"}
                and ready_object.get("ready") is not False
            )
            additional = {
                "defend_status_present": bool(status_object),
                "defend_ready_present": bool(ready_object),
                "defend_ready": defend_ready,
            }
            additional_pass = defend_ready

        product_results.append(
            {
                "slug": product["slug"],
                "title": product["title"],
                "space": product["space"],
                "source_repository": product["source_repository"],
                "metadata_running": metadata["pass"],
                "all_routes_live": all(item["pass"] for item in route_results),
                "exact_source_revision": revision_match,
                **additional,
                "pass": bool(
                    metadata["pass"]
                    and all(item["pass"] for item in route_results)
                    and revision_match
                    and additional_pass
                ),
            }
        )

    service_results: list[dict[str, Any]] = []
    for service in INTERNAL_SERVICES:
        _, metadata = hf_space_metadata(service["space"], fetch)
        observations.append(metadata)
        route_payloads: dict[str, Any] = {}
        route_results: list[dict[str, Any]] = []
        for route in ("/healthz", "/api/build-info", "/api/catalog"):
            payload, observation = route_observation(
                product=service["slug"],
                url=f"{service['host']}{route}",
                fetch=fetch,
            )
            route_payloads[route] = payload
            route_results.append(observation)
            observations.append(observation)

        build_payload = route_payloads.get("/api/build-info")
        catalog = route_payloads.get("/api/catalog")
        observed_revision = exact_sha(build_payload)
        expected_revision = main_shas.get(service["source_repository"])
        exact_source = bool(
            observed_revision and expected_revision and observed_revision == expected_revision
        )
        topology_contract = bool(
            isinstance(catalog, dict)
            and catalog.get("sentra_independent_public_vertical") is False
            and catalog.get("aegis_canonical_runtime") == "killinchu:defend"
            and catalog.get("immune_canonical_runtime") == "MIGRATION_REQUIRED"
            and isinstance(catalog.get("sentra_public_route"), str)
            and catalog["sentra_public_route"].endswith("/defend")
        )
        observations.append(
            {
                "kind": "internal-service-topology",
                "service": service["slug"],
                "expected_revision": expected_revision,
                "observed_revision": observed_revision,
                "exact_source": exact_source,
                "topology_contract": topology_contract,
                "pass": bool(exact_source and topology_contract),
            }
        )
        service_results.append(
            {
                "slug": service["slug"],
                "space": service["space"],
                "metadata_running": metadata["pass"],
                "all_routes_live": all(item["pass"] for item in route_results),
                "exact_source_revision": exact_source,
                "topology_contract": topology_contract,
                "pass": bool(
                    metadata["pass"]
                    and all(item["pass"] for item in route_results)
                    and exact_source
                    and topology_contract
                ),
            }
        )

    folded_results = [
        folded_space_observation(item, fetch) for item in FOLDED_CAPABILITY_PLANES
    ]
    observations.extend(folded_results)

    slugs = tuple(product["slug"] for product in PUBLIC_PRODUCTS)
    static_contract = {
        "public_product_count": len(slugs),
        "public_product_slugs": list(slugs),
        "unique_public_product_slugs": len(set(slugs)) == len(slugs),
        "folded_capability_planes": [item["slug"] for item in FOLDED_CAPABILITY_PLANES],
        "portfolio_labels": list(PORTFOLIO_LABELS),
        "migration_gated": list(MIGRATION_GATED),
        "pass": bool(
            len(slugs) == 5
            and len(set(slugs)) == 5
            and not (set(slugs) & {item["slug"] for item in FOLDED_CAPABILITY_PLANES})
            and not (set(slugs) & set(MIGRATION_GATED))
        ),
    }
    complete = bool(
        static_contract["pass"]
        and all(item["pass"] for item in product_results)
        and all(item["pass"] for item in service_results)
        and all(item["pass"] for item in folded_results)
        and all(item["pass"] for item in github_observations)
    )
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "started_at": started_at,
        "complete": complete,
        "truth_label": "MEASURED" if complete else "BLOCKED",
        "authority": {
            "method": "FIXED_ORIGIN_GET_ONLY",
            "third_party_writes": False,
            "deployment_authority": False,
            "effectors_enabled": False,
            "remote_response_bodies_recorded": False,
        },
        "static_contract": static_contract,
        "products": product_results,
        "internal_services": service_results,
        "folded_spaces": folded_results,
        "observations": observations,
    }


def run_until_complete(
    *,
    retry_seconds: int,
    interval_seconds: int,
    fetch: Callable[[str, float], HttpResult] = default_fetch,
) -> dict[str, Any]:
    deadline = time.monotonic() + max(0, retry_seconds)
    attempts = 0
    while True:
        attempts += 1
        receipt = assess_once(fetch)
        receipt["attempts"] = attempts
        if receipt["complete"] or time.monotonic() >= deadline:
            return receipt
        time.sleep(max(1, interval_seconds))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("estate-product-topology.json"))
    parser.add_argument("--retry-seconds", type=int, default=0)
    parser.add_argument("--interval-seconds", type=int, default=30)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    receipt = run_until_complete(
        retry_seconds=args.retry_seconds,
        interval_seconds=args.interval_seconds,
    )
    args.output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
