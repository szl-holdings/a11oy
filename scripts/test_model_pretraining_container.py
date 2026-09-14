# SPDX-License-Identifier: Apache-2.0
"""Probe the existing PR image's full HTTP stack on fixed loopback routes.

Reuses the selected-source observer's validators; it neither starts a server nor
publishes an image. The workflow owns image identity, startup and cleanup. Every
result is explicitly local-container scope, never public release qualification.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import time
from typing import Any, Callable
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'http://127.0.0.1:7860'
SPEC = importlib.util.spec_from_file_location(
    'container_model_delivery_contract', ROOT / 'scripts/verify_model_pretraining_live.py')
if SPEC is None or SPEC.loader is None:
    raise RuntimeError('source delivery contract unavailable')
V = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(V)
PATHS = frozenset(('/api/build-info', V.API, *V.ASSETS))
Headers = dict[str, str]
Fetch = Callable[[str, str], tuple[int, Headers, bytes]]


def source_bytes(root: Path, relative: str) -> bytes:
    path = root / relative
    V.require(path.resolve().is_relative_to(root.resolve()), 'source path escaped checkout')
    V.require(path.is_file() and path.stat().st_size <= V.LIMIT, 'source file unavailable or oversized')
    with path.open('rb') as stream:
        raw = stream.read(V.LIMIT + 1)
    V.require(len(raw) <= V.LIMIT, 'source file grew beyond limit')
    return raw


def feature_headers(headers: Headers, *, page: bool = False) -> None:
    """The model route's security headers must survive the assembled stack."""
    V.require(headers.get('x-content-type-options', '').lower() == 'nosniff', 'nosniff header lost')
    directives = {part.strip().lower() for part in headers.get('cache-control', '').split(',')}
    V.require('no-store' in directives, 'no-store header lost')
    if page:
        policy = {}
        for directive in headers.get('content-security-policy', '').split(';'):
            words = directive.strip().split()
            if words:
                name = words[0].lower()
                V.require(name not in policy, 'duplicate CSP directive')
                policy[name] = words[1:]
        required = {'default-src': ["'none'"], 'script-src': ["'self'"],
                    'style-src': ["'self'"], 'connect-src': ["'self'"],
                    'base-uri': ["'none'"], 'form-action': ["'none'"], 'object-src': ["'none'"]}
        V.require(all(policy.get(key) == value for key, value in required.items()),
                  'model page CSP weakened or unavailable')


def make_fetch(*, seconds: float = 120) -> Fetch:
    """Only bounded GET/HEAD to a fixed loopback host; no proxy or redirects."""
    deadline = time.monotonic() + seconds
    opener = request.build_opener(request.ProxyHandler({}), V.NoRedirect())

    def fetch(path: str, method: str = 'GET') -> tuple[int, Headers, bytes]:
        V.require(path in PATHS and method in {'GET', 'HEAD'}, 'probe path/method not admitted')
        remaining = deadline - time.monotonic()
        V.require(remaining > 0, 'container probe deadline exhausted')
        req = request.Request(ORIGIN + path, method=method, headers={
            'User-Agent': 'SZL-Model-Container-Contract/1',
            'Accept-Encoding': 'identity', 'Cache-Control': 'no-cache'})
        try:
            response = opener.open(req, timeout=min(5.0, remaining))
        except error.HTTPError as exc:
            response = exc  # Preserve an actual negative status, not empty success.
        with response:
            V.require(response.geturl() == ORIGIN + path, 'response origin changed')
            body, size = [], 0
            while method != 'HEAD':
                part = response.read(65536)
                if not part:
                    break
                size += len(part)
                V.require(size <= V.LIMIT and time.monotonic() < deadline, 'response limit')
                body.append(part)
            headers = {key.lower(): value for key, value in response.headers.items()
                       if key.lower() in {'content-type', 'cache-control',
                           'content-security-policy', 'x-content-type-options'}}
            return response.status, headers, b''.join(body)
    return fetch


def container_source_revision(payload: Any, expected: str) -> None:
    """Verify the local image's build-argument identity, not the HF env profile.

    Dockerfile binds REVISION to A11OY_GIT_SHA and the smoke workflow checks the
    OCI revision label before starting this exact image. The runtime prioritizes
    A11OY_GIT_SHA over SZL_GIT_SHA. Keep this fixed local profile separate from
    the public-HF verifier; never rewrite a response to impersonate its origin.
    """
    V.require(type(expected) is str and V.SHA.fullmatch(expected) is not None,
              'container source identity invalid')
    V.require(type(payload) is dict and payload.get('status') == 'OBSERVED',
              'container build-info unavailable')
    V.require(payload.get('receipt_minted') is False, 'container build-info authority')
    build = payload.get('build')
    V.require(type(build) is dict and build.get('state') == 'OBSERVED'
              and build.get('revision') == expected
              and build.get('revision_source') == 'env:A11OY_GIT_SHA',
              'container image source witness differs')


def collect(root: Path, expected: str, image_id: str, *, fetch: Fetch | None = None) -> dict[str, Any]:
    """Run every selected contract and retain failures without storing bodies.

    A failed asset cannot erase earlier witnesses, and the final source check
    still runs after a feature failure. No failure is converted to a pass.
    """
    V.require(type(expected) is str and V.SHA.fullmatch(expected) is not None, 'source identity invalid')
    V.require(type(image_id) is str and re.fullmatch(r'sha256:[a-f0-9]{64}', image_id), 'image identity invalid')
    report: dict[str, Any] = {
        'schema': 'szl.model-pretraining-container/v1',
        'observedAt': datetime.now(timezone.utc).isoformat(),
        'scope': 'LOCAL_FULL_CONTAINER_INTEGRATION', 'origin': ORIGIN,
        'sourceRevision': expected, 'workflowObservedImageId': image_id,
        'sourceIdentityProfile': 'DOCKER_REVISION_ENV_A11OY_GIT_SHA',
        'state': 'FAIL_CONTAINER_FEATURE_CONTRACT', 'checks': [], 'observations': [],
        'productionDeploymentVerified': False, 'wholeEstateAligned': False,
        'browserRenderingVerified': False, 'probeModelInferenceRequested': False,
        'trainingStarted': False, 'probeProviderMutationRequested': False,
        'backgroundActivityVerification': 'NOT_PERFORMED',
    }
    getter = fetch or make_fetch()

    def check(name: str, operation: Callable[[], Any]) -> None:
        try:
            operation()
            report['checks'].append({'name': name, 'state': 'PASS'})
        except Exception as exc:
            # Do not persist raw exception/response text, headers, queries or secrets.
            report['checks'].append({'name': name, 'state': 'FAIL', 'errorType': type(exc).__name__})

    def read(path: str, method: str, phase: str) -> tuple[int, Headers, bytes]:
        record: dict[str, Any] = {'path': path, 'method': method, 'phase': phase, 'state': 'UNAVAILABLE'}
        report['observations'].append(record)
        status, headers, body = getter(path, method)
        V.require(type(status) is int and type(headers) is dict and type(body) is bytes
                  and len(body) <= V.LIMIT, 'invalid transport response')
        record.update(state='OBSERVED', status=status, bytes=len(body), sha256=V.sha256(body))
        # Bounded media type is the only retained header value.
        media = headers.get('content-type', '')
        record['contentType'] = media[:128] if isinstance(media, str) else 'INVALID'
        return status, headers, body

    def json_response(path: str, phase: str) -> Any:
        status, headers, body = read(path, 'GET', phase)
        V.require(status == 200 and headers.get('content-type', '').split(';', 1)[0].strip().lower()
                  == 'application/json', 'JSON transport differs')
        if path == V.API:
            feature_headers(headers)
        return V.strict_json(body)

    def source(phase: str) -> None:
        container_source_revision(json_response('/api/build-info', phase), expected)

    def api() -> None:
        value = json_response(V.API, 'catalog')
        manifest = source_bytes(root, 'docs/huggingface-ecosystem-manifest.json')
        projection = source_bytes(root, 'routers/data/model-pretraining-snapshot.json')
        declarations = source_bytes(root, 'a11oy_model_intel.py')
        V.validate_catalog(value, manifest, projection, expected, datetime.now(timezone.utc))
        V.validate_source_pointers(value, V.declared_source_pointers(declarations))
        report['catalog'] = {
            'count': value['returned'], 'freshness': value['snapshotFreshness'],
            'observedAt': value['observedAt'], 'declaredPointers': value['sourcePointersDeclared'],
            'manifestSha256': V.sha256(manifest), 'projectionSha256': V.sha256(projection),
            'sourcePointerCatalogSha256': V.sha256(declarations), 'modelLineageVerified': False,
        }

    def head(path: str, allowed: set[str]) -> None:
        status, headers, body = read(path, 'HEAD', 'head')
        V.require(status == 200 and body == b'' and headers.get('content-type', '')
                  .split(';', 1)[0].strip().lower() in allowed, 'HEAD transport differs')
        if path == V.API or path.startswith('/frontier-tooling/models'):
            feature_headers(headers, page=path in {'/frontier-tooling/models', '/frontier-tooling/models/'})

    def asset(path: str, filename: str) -> None:
        status, headers, body = read(path, 'GET', 'asset')
        expected_bytes = source_bytes(root, filename)
        report['observations'][-1]['expectedSha256'] = V.sha256(expected_bytes)
        if path in {'/frontier-tooling/models', '/frontier-tooling/models/'} and body != expected_bytes:
            # Failure diagnostics preserve byte equality as the actual gate.
            # Only source locations and hashes are recorded, never response text.
            diagnostic_spec = importlib.util.spec_from_file_location(
                'model_html_source_delta', ROOT / 'scripts/model_pretraining_html_diagnostics.py')
            if diagnostic_spec is None or diagnostic_spec.loader is None:
                raise RuntimeError('HTML source diagnostics unavailable')
            diagnostic = importlib.util.module_from_spec(diagnostic_spec)
            diagnostic_spec.loader.exec_module(diagnostic)
            report['observations'][-1]['sourceDelta'] = diagnostic.describe_delta(root, expected_bytes, body)
        V.validate_asset(path, status, headers.get('content-type', ''), body, expected_bytes)
        if path.startswith('/frontier-tooling/models'):
            feature_headers(headers, page=path in {'/frontier-tooling/models', '/frontier-tooling/models/'})

    check('source before', lambda: source('before'))
    check('model API HEAD', lambda: head(V.API, {'application/json'}))
    check('model API and source declarations', api)
    for path, (filename, allowed) in V.ASSETS.items():
        check('HEAD ' + path, lambda path=path, allowed=allowed: head(path, allowed))
        check('GET exact source ' + path, lambda path=path, filename=filename: asset(path, filename))
    check('source after', lambda: source('after'))
    report['failedChecks'] = [row['name'] for row in report['checks'] if row['state'] != 'PASS']
    report['expectedChecks'] = 4 + 2 * len(V.ASSETS)
    if len(report['checks']) == report['expectedChecks'] and not report['failedChecks']:
        report['state'] = 'PASS_LOCAL_CONTAINER_FEATURE_CONTRACT'
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-source', required=True)
    parser.add_argument('--image-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report: dict[str, Any] = {
        'schema': 'szl.model-pretraining-container/v1',
        'scope': 'LOCAL_FULL_CONTAINER_INTEGRATION', 'state': 'UNAVAILABLE',
        'productionDeploymentVerified': False, 'trainingStarted': False,
    }
    try:
        actual = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True,
                                text=True, check=True, timeout=10).stdout.strip()
        V.require(actual == args.expected_source, 'checkout/source mismatch')
        report = collect(ROOT, actual, args.image_id)
    except Exception as exc:
        report['errorType'] = type(exc).__name__
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps(report, sort_keys=True, allow_nan=False))
    return 0 if report['state'] == 'PASS_LOCAL_CONTAINER_FEATURE_CONTRACT' else 1


if __name__ == '__main__':
    raise SystemExit(main())
