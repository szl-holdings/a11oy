# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from scripts import witness_platform_candidate_preview as witness


REVISION = "a" * 40
MANIFEST_SHA256 = "b" * 64
INDEX = b"<!doctype html><html><body><div id='root'></div></body></html>"
MAIN_JS = b"globalThis.candidate = true;"
STYLE = b"body { color: white; }"
LAZY_JS = b"globalThis.securityAgents = true;"


def _binding(path: str, body: bytes, media_type: str) -> witness.FileBinding:
    return witness.FileBinding(
        path=path,
        body=body,
        sha256=hashlib.sha256(body).hexdigest(),
        size=len(body),
        media_type=media_type,
    )


@pytest.fixture
def contract() -> witness.CandidateContract:
    return witness.CandidateContract(
        source_revision=REVISION,
        manifest_sha256=MANIFEST_SHA256,
        index=_binding("index.html", INDEX, "text/html"),
        assets={
            "assets/app-ABCdef12.js": _binding(
                "assets/app-ABCdef12.js", MAIN_JS, "text/javascript"
            ),
            "assets/app-ABCdef12.css": _binding(
                "assets/app-ABCdef12.css", STYLE, "text/css"
            ),
            "assets/route-XYZuvw98.js": _binding(
                "assets/route-XYZuvw98.js", LAZY_JS, "text/javascript"
            ),
        },
    )


def _headers(
    binding: witness.FileBinding,
    *,
    origin: str,
    updates: dict[str, str] | None = None,
    omit: set[str] | None = None,
    duplicate: tuple[str, str] | None = None,
) -> tuple[tuple[str, str], ...]:
    values = {
        **witness.STATIC_HEADERS,
        "content-security-policy": witness.CANONICAL_CSP,
        "content-type": binding.media_type + "; charset=utf-8",
        "content-length": str(binding.size),
        "x-szl-platform-source-revision": REVISION,
        "x-szl-candidate-manifest-sha256": MANIFEST_SHA256,
    }
    if origin == witness.PRODUCT_ORIGIN:
        values["speculation-rules"] = witness.EDGE_SPECULATION_HEADER
    values.update(updates or {})
    headers = [(key, value) for key, value in values.items() if key not in (omit or set())]
    if duplicate is not None:
        headers.append(duplicate)
    return tuple(headers)


def _candidate_exchange(
    binding: witness.FileBinding,
    *,
    origin: str,
    route: str,
    request_url: str | None = None,
    resource_type: str | None = None,
    response: witness.ResponseObservation | None = None,
) -> witness.Exchange:
    is_index = binding.path == "index.html"
    url = request_url or (
        witness._route_url(origin, route)
        if is_index
        else origin + witness.PREFIX + "/" + binding.path
    )
    return witness.Exchange(
        request=witness.RequestObservation(
            method="GET",
            url=url,
            resource_type=resource_type
            or ("document" if is_index else "stylesheet" if binding.media_type == "text/css" else "script"),
        ),
        response=response
        or witness.ResponseObservation(
            status=200,
            headers=_headers(binding, origin=origin),
            body=binding.body,
        ),
    )


def _edge_exchange(
    *,
    url: str = witness.EDGE_SPECULATION_URL,
    method: str = "GET",
    resource_type: str = "other",
    response: witness.ResponseObservation | None = None,
) -> witness.Exchange:
    return witness.Exchange(
        request=witness.RequestObservation(method, url, resource_type),
        response=response
        or witness.ResponseObservation(
            status=200,
            headers=(
                ("content-type", witness.EDGE_SPECULATION_MEDIA_TYPE),
                ("content-length", str(witness.EDGE_SPECULATION_SIZE)),
                ("speculation-rules", witness.EDGE_SPECULATION_HEADER),
            ),
            body=witness.EDGE_SPECULATION_BODY,
        ),
    )


def _trace(
    contract: witness.CandidateContract,
    *,
    origin: str,
    route: str,
) -> list[witness.Exchange]:
    names = ["assets/app-ABCdef12.js", "assets/app-ABCdef12.css"]
    if route == "/security-agents":
        names.append("assets/route-XYZuvw98.js")
    exchanges = [_candidate_exchange(contract.index, origin=origin, route=route)]
    exchanges.extend(
        _candidate_exchange(contract.assets[name], origin=origin, route=route)
        for name in names
    )
    if origin == witness.PRODUCT_ORIGIN:
        exchanges.append(_edge_exchange())
    return exchanges


def test_provider_body_pin_and_schema_are_exact():
    assert len(witness.EDGE_SPECULATION_BODY) == 151
    assert hashlib.sha256(witness.EDGE_SPECULATION_BODY).hexdigest() == (
        "4d958f26d792adc0b7c79e26bb5264ff3ae27f6f32c1f67cbdcbe8b765b7f9fb"
    )
    assert json.loads(witness.EDGE_SPECULATION_BODY) == witness.EDGE_SPECULATION_SCHEMA


def test_contract_loader_binds_manifest_and_every_local_file(tmp_path: Path):
    bundle = tmp_path / "bundle"
    (bundle / "assets").mkdir(parents=True)
    files = {
        "index.html": INDEX,
        "assets/app-ABCdef12.js": MAIN_JS,
        "assets/app-ABCdef12.css": STYLE,
    }
    for relative, body in files.items():
        path = bundle / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    manifest = {
        "schema": witness.SCHEMA,
        "state": witness.STATE,
        "source_repository": witness.SOURCE_REPOSITORY,
        "source_revision": REVISION,
        "base_path": witness.BASE_PATH,
        "production_ready": False,
        "runtime_api_binding": "UNAVAILABLE",
        "effectors": 0,
        "unknown_route_policy": "not_found",
        "reviewed_routes": list(witness.REVIEWED_ROUTES),
        "files": [
            {
                "path": relative,
                "sha256": hashlib.sha256(body).hexdigest(),
                "size": len(body),
            }
            for relative, body in sorted(files.items())
        ],
    }
    raw = json.dumps(manifest, separators=(",", ":")).encode()
    (bundle / "source.json").write_bytes(raw)

    loaded = witness.load_contract(
        bundle,
        expected_source_revision=REVISION,
        expected_manifest_sha256=hashlib.sha256(raw).hexdigest(),
    )

    assert loaded.index.body == INDEX
    assert set(loaded.assets) == set(files) - {"index.html"}
    assert loaded.manifest_sha256 == hashlib.sha256(raw).hexdigest()


def test_contract_loader_rejects_bridge_reference_even_when_manifest_matches(tmp_path: Path):
    bundle = tmp_path / "bundle"
    (bundle / "assets").mkdir(parents=True)
    files = {
        "index.html": INDEX,
        "assets/app-ABCdef12.js": b"fetch('/.webmcp/bridge.js')",
    }
    for relative, body in files.items():
        (bundle / relative).write_bytes(body)
    manifest = {
        "schema": witness.SCHEMA,
        "state": witness.STATE,
        "source_repository": witness.SOURCE_REPOSITORY,
        "source_revision": REVISION,
        "base_path": witness.BASE_PATH,
        "production_ready": False,
        "runtime_api_binding": "UNAVAILABLE",
        "effectors": 0,
        "unknown_route_policy": "not_found",
        "reviewed_routes": list(witness.REVIEWED_ROUTES),
        "files": [
            {
                "path": relative,
                "sha256": hashlib.sha256(body).hexdigest(),
                "size": len(body),
            }
            for relative, body in sorted(files.items())
        ],
    }
    raw = json.dumps(manifest, separators=(",", ":")).encode()
    (bundle / "source.json").write_bytes(raw)

    with pytest.raises(witness.WitnessError, match="edge bridge"):
        witness.load_contract(
            bundle,
            expected_source_revision=REVISION,
            expected_manifest_sha256=hashlib.sha256(raw).hexdigest(),
        )


def test_read_expected_contract_is_literal_and_exact(tmp_path: Path):
    contract_file = tmp_path / "contract.py"
    contract_file.write_text(
        f'_PLATFORM_CANDIDATE_SOURCE_REVISION = "{REVISION}"\n'
        f'_PLATFORM_CANDIDATE_MANIFEST_SHA256 = "{MANIFEST_SHA256}"\n',
        encoding="utf-8",
    )
    assert witness.read_expected_contract(contract_file) == (REVISION, MANIFEST_SHA256)
    contract_file.write_text(
        '_PLATFORM_CANDIDATE_SOURCE_REVISION = "a" * 40\n'
        f'_PLATFORM_CANDIDATE_MANIFEST_SHA256 = "{MANIFEST_SHA256}"\n',
        encoding="utf-8",
    )
    with pytest.raises(witness.WitnessError, match="dynamic"):
        witness.read_expected_contract(contract_file)


@pytest.mark.parametrize(
    ("method", "url", "resource_type"),
    [
        ("POST", witness.PRODUCT_ORIGIN + witness.BASE_PATH, "document"),
        ("GET", "http://a-11-oy.com" + witness.BASE_PATH, "document"),
        ("GET", "https://a-11-oy.com.evil.invalid" + witness.BASE_PATH, "document"),
        ("GET", "https://user@a-11-oy.com" + witness.BASE_PATH, "document"),
        ("GET", witness.PRODUCT_ORIGIN + witness.BASE_PATH + "?x=1", "document"),
        ("GET", witness.PRODUCT_ORIGIN + "/api/build-info", "fetch"),
        ("GET", witness.PRODUCT_EDGE_SCRIPT_SOURCE, "script"),
        ("GET", witness.PRODUCT_ORIGIN + witness.EDGE_SPECULATION_PATH + "?x=1", "other"),
        ("GET", witness.SPACE_ORIGIN + witness.EDGE_SPECULATION_PATH, "other"),
        ("GET", witness.PRODUCT_ORIGIN + witness.BASE_PATH, "script"),
    ],
)
def test_request_policy_rejects_method_host_api_bridge_and_variants(
    contract: witness.CandidateContract,
    method: str,
    url: str,
    resource_type: str,
):
    with pytest.raises(witness.WitnessError):
        witness.classify_request(
            contract,
            origin=witness.PRODUCT_ORIGIN,
            route="/",
            request=witness.RequestObservation(method, url, resource_type),
        )


def test_product_trace_accepts_only_exact_provider_exchange(contract: witness.CandidateContract):
    report = witness.validate_route_trace(
        contract,
        origin=witness.PRODUCT_ORIGIN,
        route="/",
        exchanges=_trace(contract, origin=witness.PRODUCT_ORIGIN, route="/"),
    )
    assert report["provider_edge_requests"] == 1
    assert report["provider_edge_ownership"] == "PROVIDER_OWNED"
    assert report["document_sha256"] == contract.index.sha256


def test_space_trace_has_no_provider_header_or_request(contract: witness.CandidateContract):
    report = witness.validate_route_trace(
        contract,
        origin=witness.SPACE_ORIGIN,
        route="/",
        exchanges=_trace(contract, origin=witness.SPACE_ORIGIN, route="/"),
    )
    assert report["provider_edge_requests"] == 0
    assert report["provider_edge_ownership"] == "NOT_PRESENT"

    with pytest.raises(witness.WitnessError):
        witness.validate_route_trace(
            contract,
            origin=witness.SPACE_ORIGIN,
            route="/",
            exchanges=[
                *_trace(contract, origin=witness.SPACE_ORIGIN, route="/"),
                _edge_exchange(),
            ],
        )


def test_product_trace_requires_one_provider_request_without_duplicates(
    contract: witness.CandidateContract,
):
    trace = _trace(contract, origin=witness.PRODUCT_ORIGIN, route="/")
    with pytest.raises(witness.WitnessError, match="request count"):
        witness.validate_route_trace(
            contract,
            origin=witness.PRODUCT_ORIGIN,
            route="/",
            exchanges=trace[:-1],
        )
    with pytest.raises(witness.WitnessError, match="repeated"):
        witness.validate_route_trace(
            contract,
            origin=witness.PRODUCT_ORIGIN,
            route="/",
            exchanges=[*trace, trace[-1]],
        )


@pytest.mark.parametrize(
    "response",
    [
        replace(_edge_exchange().response, status=204),
        replace(
            _edge_exchange().response,
            headers=(("content-type", "application/json"), ("content-length", "151"),
                     ("speculation-rules", witness.EDGE_SPECULATION_HEADER)),
        ),
        replace(_edge_exchange().response, body=witness.EDGE_SPECULATION_BODY[:-1] + b" "),
        replace(
            _edge_exchange().response,
            headers=(*_edge_exchange().response.headers,
                     ("speculation-rules", witness.EDGE_SPECULATION_HEADER)),
        ),
    ],
)
def test_provider_response_rejects_status_media_bytes_and_duplicate_header(
    contract: witness.CandidateContract,
    response: witness.ResponseObservation,
):
    trace = _trace(contract, origin=witness.PRODUCT_ORIGIN, route="/")
    trace[-1] = _edge_exchange(response=response)
    with pytest.raises(witness.WitnessError):
        witness.validate_route_trace(
            contract,
            origin=witness.PRODUCT_ORIGIN,
            route="/",
            exchanges=trace,
        )


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ("body", "bytes"),
        ("source", "source provenance"),
        ("manifest", "manifest provenance"),
        ("csp", "content-security-policy"),
        ("content_type", "content-type"),
        ("speculation", "speculation-rules"),
        ("duplicate_speculation", "speculation-rules"),
        ("encoding", "content-encoded"),
    ],
)
def test_candidate_response_rejects_byte_header_and_provenance_drift(
    contract: witness.CandidateContract,
    mutation: str,
    match: str,
):
    binding = contract.index
    updates: dict[str, str] = {}
    omit: set[str] = set()
    duplicate = None
    body = binding.body
    if mutation == "body":
        body += b" "
    elif mutation == "source":
        updates["x-szl-platform-source-revision"] = "c" * 40
    elif mutation == "manifest":
        updates["x-szl-candidate-manifest-sha256"] = "d" * 64
    elif mutation == "csp":
        updates["content-security-policy"] = witness.CANONICAL_CSP + "; connect-src 'self'"
    elif mutation == "content_type":
        updates["content-type"] = binding.media_type + "; totally-unreviewed=value"
    elif mutation == "speculation":
        omit.add("speculation-rules")
    elif mutation == "duplicate_speculation":
        duplicate = ("speculation-rules", witness.EDGE_SPECULATION_HEADER)
    elif mutation == "encoding":
        updates["content-encoding"] = "br"
    response = witness.ResponseObservation(
        status=200,
        headers=_headers(
            binding,
            origin=witness.PRODUCT_ORIGIN,
            updates=updates,
            omit=omit,
            duplicate=duplicate,
        ),
        body=body,
    )
    with pytest.raises(witness.WitnessError, match=match):
        witness.validate_exchange(
            contract,
            origin=witness.PRODUCT_ORIGIN,
            route="/",
            exchange=_candidate_exchange(
                binding,
                origin=witness.PRODUCT_ORIGIN,
                route="/",
                response=response,
            ),
        )


@pytest.mark.parametrize("origin", witness.ALLOWED_ORIGINS)
def test_both_origins_reject_bridge_csp(contract: witness.CandidateContract, origin: str):
    binding = contract.index
    response = witness.ResponseObservation(
        status=200,
        headers=_headers(
            binding,
            origin=origin,
            updates={
                "content-security-policy": witness.CANONICAL_CSP.replace(
                    "; script-src-attr", " " + witness.PRODUCT_EDGE_SCRIPT_SOURCE + "; script-src-attr"
                ),
            },
        ),
        body=binding.body,
    )
    with pytest.raises(witness.WitnessError):
        witness.validate_exchange(
            contract,
            origin=origin,
            route="/",
            exchange=_candidate_exchange(
                binding,
                origin=origin,
                route="/",
                response=response,
            ),
        )


@pytest.mark.parametrize("origin", witness.ALLOWED_ORIGINS)
def test_both_reviewed_routes_close_the_manifest_asset_set(
    contract: witness.CandidateContract,
    origin: str,
):
    report = witness.validate_origin_traces(
        contract,
        origin=origin,
        traces={
            route: _trace(contract, origin=origin, route=route)
            for route in witness.REVIEWED_ROUTES
        },
    )
    assert report["verified_assets"] == sorted(contract.assets)
    assert report["provider_edge_csp"] == "NOT_PRESENT"


def test_origin_trace_fails_when_lazy_manifest_asset_was_not_exercised(
    contract: witness.CandidateContract,
):
    security_trace = _trace(
        contract, origin=witness.SPACE_ORIGIN, route="/security-agents"
    )
    security_trace = [
        exchange
        for exchange in security_trace
        if not exchange.request.url.endswith("route-XYZuvw98.js")
    ]
    with pytest.raises(witness.WitnessError, match="complete manifest asset set"):
        witness.validate_origin_traces(
            contract,
            origin=witness.SPACE_ORIGIN,
            traces={
                "/": _trace(contract, origin=witness.SPACE_ORIGIN, route="/"),
                "/security-agents": security_trace,
            },
        )


def test_contract_loader_enforces_manifest_count_and_aggregate_limits(tmp_path: Path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()

    oversized_manifest = b" " * (witness.MANIFEST_LIMIT + 1)
    (bundle / "source.json").write_bytes(oversized_manifest)
    with pytest.raises(witness.WitnessError, match="source.json exceeded"):
        witness.load_contract(
            bundle,
            expected_source_revision=REVISION,
            expected_manifest_sha256=hashlib.sha256(oversized_manifest).hexdigest(),
        )

    def raw_manifest(rows: list[dict[str, object]]) -> bytes:
        return json.dumps(
            {
                "schema": witness.SCHEMA,
                "state": witness.STATE,
                "source_repository": witness.SOURCE_REPOSITORY,
                "source_revision": REVISION,
                "base_path": witness.BASE_PATH,
                "production_ready": False,
                "runtime_api_binding": "UNAVAILABLE",
                "effectors": 0,
                "unknown_route_policy": "not_found",
                "reviewed_routes": list(witness.REVIEWED_ROUTES),
                "files": rows,
            },
            separators=(",", ":"),
        ).encode()

    too_many = [
        {
            "path": "index.html" if index == 0 else f"assets/file-{index:08d}.js",
            "sha256": "a" * 64,
            "size": 0,
        }
        for index in range(witness.FILE_COUNT_LIMIT + 1)
    ]
    raw = raw_manifest(too_many)
    assert len(raw) <= witness.MANIFEST_LIMIT
    (bundle / "source.json").write_bytes(raw)
    with pytest.raises(witness.WitnessError, match="closed file inventory"):
        witness.load_contract(
            bundle,
            expected_source_revision=REVISION,
            expected_manifest_sha256=hashlib.sha256(raw).hexdigest(),
        )

    aggregate = [
        {
            "path": "index.html" if index == 0 else f"assets/file-{index:08d}.js",
            "sha256": "b" * 64,
            "size": witness.MAX_RESPONSE_BYTES,
        }
        for index in range(9)
    ]
    raw = raw_manifest(aggregate)
    (bundle / "source.json").write_bytes(raw)
    with pytest.raises(witness.WitnessError, match="aggregate byte limit"):
        witness.load_contract(
            bundle,
            expected_source_revision=REVISION,
            expected_manifest_sha256=hashlib.sha256(raw).hexdigest(),
        )


def test_browser_prechecks_exact_status_and_content_length_before_body(
    contract: witness.CandidateContract,
):
    binding = contract.index
    response = type("Response", (), {"status": 200})()
    headers = (("content-length", str(binding.size)),)
    witness._require_declared_response_size(
        "candidate_document", binding, response, headers
    )

    with pytest.raises(witness.WitnessError, match="pre-body content length"):
        witness._require_declared_response_size(
            "candidate_document",
            binding,
            response,
            (("content-length", str(binding.size + 1)),),
        )
    with pytest.raises(witness.WitnessError, match="status"):
        witness._require_declared_response_size(
            "candidate_document",
            binding,
            type("Response", (), {"status": 302})(),
            headers,
        )
