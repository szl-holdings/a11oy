# SPDX-License-Identifier: Apache-2.0
"""Read-only, exact-source model-preparation delivery checks after canonical publish.

This validates selected HTTP contracts and served asset bytes, not weights,
complete estate inventory, signatures, training approval, or a browser rendering.
No provider credentials, cookie jar, redirects, or model calls are used.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import time
from typing import Any
from urllib import error, request
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ORIGINS = {'canonical': 'https://szlholdings-a11oy.hf.space', 'product': 'https://a-11-oy.com'}
API = '/api/a11oy/v1/models/pretraining'
ASSETS = {
    '/frontier-tooling/models': ('pages/model-pretraining.html', {'text/html'}),
    '/frontier-tooling/models/': ('pages/model-pretraining.html', {'text/html'}),
    '/frontier-tooling/models/assets/view.js': ('pages/model-pretraining.js', {'text/javascript', 'application/javascript'}),
    '/frontier-tooling/models/assets/view.css': ('pages/model-pretraining.css', {'text/css'}),
    '/assets/szl-flow.js': ('console/assets/szl-flow.js', {'text/javascript', 'application/javascript'}),
    '/assets/szl-flow.css': ('console/assets/szl-flow.css', {'text/css'}),
    '/assets/szl-spectral-v2.css': ('console/assets/szl-spectral-v2.css', {'text/css'}),
}
AUTHORITY = dict.fromkeys(('training', 'inference', 'publication', 'promotion', 'deletion', 'toolExecution'), False)
LIMIT = 8 * 1024 * 1024
SHA = re.compile(r'[a-f0-9]{40}\Z')
CATEGORIES = {'ADAPTER_HINT', 'CHECKPOINT_HINT', 'GGUF_HINT', 'CLASSICAL_MODEL_HINT',
              'KERNEL_OR_SOFTWARE_HINT', 'RECIPE_OR_PLACEHOLDER_HINT', 'UNCLASSIFIED'}


class VerificationError(ValueError):
    """A necessary observation is missing, incompatible, or unsuccessful."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def strict_json(raw: bytes) -> Any:
    require(type(raw) is bytes and 0 < len(raw) <= LIMIT, 'JSON size/type')
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, 'duplicate JSON key')
            value[key] = item
        return value
    def finite(value):
        number = float(value)
        require(math.isfinite(number), 'nonfinite JSON')
        return number
    def reject(_):
        raise VerificationError('nonfinite JSON')
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=unique,
                          parse_float=finite, parse_constant=reject)
    except (UnicodeError, ValueError, RecursionError, OverflowError) as exc:
        raise VerificationError('invalid strict JSON') from exc


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def source_revision(payload: Any, expected: str) -> None:
    require(type(payload) is dict and payload.get('status') == 'OBSERVED', 'build-info unavailable')
    require(payload.get('receipt_minted') is False, 'build-info authority')
    build = payload.get('build')
    require(type(build) is dict and build.get('state') == 'OBSERVED'
            and build.get('revision') == expected
            and build.get('revision_source') == 'env:SZL_GIT_SHA', 'source witness differs')


def validate_catalog(value: Any, manifest_raw: bytes, projection_raw: bytes, expected: str,
                     now: datetime) -> None:
    manifest, projection = strict_json(manifest_raw), strict_json(projection_raw)
    require(type(manifest) is dict and manifest.get('schemaVersion') == 2
            and manifest.get('org') == 'SZLHOLDINGS', 'source manifest schema')
    require(type(projection) is dict and projection.get('schema') == 'szl.model-pretraining-input/v1'
            and projection.get('sourceManifestSha256') == sha256(manifest_raw), 'source/projection mismatch')
    require(type(value) is dict and value.get('schema') == 'szl.model-pretraining-view/v1'
            and value.get('available') is True
            and value.get('state') == 'PRETRAINING_REVIEW_NOT_ALIGNMENT', 'model API unavailable/schema')
    for name in ('trainingAllowed', 'sourceAlignmentVerified', 'wholeOrganizationInventoryVerified',
                 'productSourceIndependentlyAttested'):
        require(value.get(name) is False, 'authority/qualification amplification: ' + name)
    authority = value.get('authority')
    require(type(authority) is dict and set(authority) == set(AUTHORITY)
            and all(authority[key] is False for key in AUTHORITY), 'authority differs')
    require(value.get('productSourceRevisionReported') == expected, 'API source differs')
    require(value.get('manifestSha256') == sha256(manifest_raw)
            and value.get('projectionSha256') == sha256(projection_raw), 'inventory digest differs')
    require(value.get('manifestDigestState') == 'BUILD_DERIVED_SOURCE_DIGEST_NOT_REHASHED_AT_RUNTIME',
            'digest meaning differs')
    scope = value.get('inventoryScope')
    require(type(scope) is dict and scope.get('visibility') == 'public-only'
            and scope.get('authenticated') is False and scope.get('privateAssetsIncluded') is False,
            'inventory scope differs')
    require(value.get('observedAt') == manifest.get('observedAt'), 'observation time differs')
    try:
        stamp = datetime.fromisoformat(value['observedAt'].replace('Z', '+00:00'))
        require(stamp.tzinfo is not None and now.tzinfo is not None, 'naive observation time')
        age = (now - stamp).total_seconds()
    except (AttributeError, TypeError, ValueError) as exc:
        raise VerificationError('observation time invalid') from exc
    # Clock skew and stale metadata must be visible. Delivery can pass while
    # a correctly labelled historical inventory still requires refresh.
    freshness = value.get('snapshotFreshness')
    require(freshness in {'CLOCK_SKEW', 'STALE_SNAPSHOT', 'SNAPSHOT_NOT_LIVE'}, 'freshness label invalid')
    if age < -120:
        require(freshness == 'CLOCK_SKEW', 'future snapshot hidden')
    elif age > 86520:
        require(freshness == 'STALE_SNAPSHOT', 'stale snapshot hidden')
    elif 120 < age < 86280:
        require(freshness == 'SNAPSHOT_NOT_LIVE', 'snapshot freshness differs')
    source_rows = manifest.get('inventory', {}).get('models')
    require(type(source_rows) is list and len(source_rows) <= 2000, 'source model scope invalid')
    recorded = {}
    for row in source_rows:
        require(type(row) is dict and type(row.get('id')) is str
                and row['id'].startswith('SZLHOLDINGS/') and row['id'] not in recorded
                and row.get('repoType') == 'model' and row.get('private') is False
                and type(row.get('sha')) is str and SHA.fullmatch(row['sha']) is not None,
                'source inventory identity invalid')
        recorded[row['id']] = row
    require(type(manifest.get('counts',{}).get('models')) is int
            and manifest['counts']['models'] == len(recorded), 'source count differs')
    rows = value.get('models')
    require(type(rows) is list and type(value.get('returned')) is int
            and len(rows) == value['returned'] == len(recorded), 'model row count differs')
    seen, linked, counts = set(), 0, Counter()
    for row in rows:
        require(type(row) is dict and type(row.get('id')) is str
                and row['id'] in recorded and row['id'] not in seen, 'model identity differs/duplicate')
        seen.add(row['id']); item = recorded[row['id']]
        require(row.get('hubRevision') == item['sha']
                and row.get('hubUrl') == f"https://huggingface.co/{row['id']}/tree/{item['sha']}"
                and row.get('hubRevisionState') == 'RECORDED_SNAPSHOT_NOT_LIVE', 'model revision differs')
        for field in ('weightsVerified', 'sourceBytesVerified', 'evaluationVerified', 'publicationVerified',
                      'runtimeVerified', 'trainingAllowed', 'categoryIsVerified'):
            require(row.get(field) is False, 'model qualification amplification')
        require(type(row.get('gated')) is type(item.get('gated')) and row['gated'] == item['gated']
                and type(row.get('disabled')) is bool and row['disabled'] == item['disabled'], 'access state differs')
        require(row.get('categoryHint') in CATEGORIES, 'category unknown')
        counts[row['categoryHint']] += 1
        state, url = row.get('sourceState'), row.get('sourceUrl')
        require(state in {'DECLARED_POINTER_ONLY', 'AMBIGUOUS', 'NOT_RESOLVED_BY_THIS_CATALOG'}, 'source state invalid')
        if state == 'DECLARED_POINTER_ONLY':
            require(type(url) is str and re.fullmatch(r'https://github\.com/szl-holdings/[A-Za-z0-9._/-]+', url)
                    is not None and not any(p in ('.', '..', '') for p in url.split('/')[3:]), 'unsafe source URL')
            linked += 1
        else:
            require(url is None, 'unresolved source has a URL')
    require(type(value.get('sourcePointersDeclared')) is int and value['sourcePointersDeclared'] == linked,
            'declared pointer count differs')
    require(type(value.get('categoryCounts')) is dict and value['categoryCounts'] == dict(counts)
            and all(type(n) is int for n in value['categoryCounts'].values()), 'category counts differ')


def safe_source_pointer(value: Any) -> str | None:
    """Match the existing product URL boundary without importing its network code."""
    if not isinstance(value, str) or len(value) > 1024 or any(ord(c) <= 32 or ord(c) == 127 for c in value):
        return None
    try:
        parsed = urlsplit(value)
        parts = parsed.path.split('/')
        if (parsed.scheme != 'https' or parsed.netloc != 'github.com'
                or parsed.query or parsed.fragment or len(parts) < 3
                or parts[1] != 'szl-holdings'
                or any(not re.fullmatch(r'[A-Za-z0-9._-]+', part) or part in ('.', '..')
                       for part in parts[2:])):
            return None
        return value
    except ValueError:
        return None


def declared_source_pointers(raw: bytes) -> dict[str, tuple[str, str | None]]:
    """Read only literal SERIES_A_CARDS declarations from the selected checkout.

    No import, eval, exec, attribute lookup or function call is evaluated. The
    only supported interpolation is the existing literal _FORGE prefix. A source
    refactor outside this grammar requires review, not a network/import fallback.
    Duplicate cards retain the product's AMBIGUOUS state, even with equal URLs.
    """
    require(type(raw) is bytes and 0 < len(raw) <= LIMIT, 'catalog source size/type')
    try:
        tree = ast.parse(raw.decode('utf-8'))
        require(sum(1 for _ in ast.walk(tree)) <= 100000, 'catalog AST size')
        assigned = {}
        for node in tree.body:
            targets = node.targets if isinstance(node, ast.Assign) else (
                [node.target] if isinstance(node, (ast.AnnAssign, ast.AugAssign)) else [])
            for target in targets:
                if isinstance(target, ast.Name) and target.id in {'_FORGE', 'SERIES_A_CARDS'}:
                    require(not isinstance(node, ast.AugAssign) and target.id not in assigned,
                            'ambiguous catalog declaration')
                    assigned[target.id] = node.value
        require(set(assigned) == {'_FORGE', 'SERIES_A_CARDS'}, 'catalog declarations unavailable')
        forge = ast.literal_eval(assigned['_FORGE'])
        require(safe_source_pointer(forge) is not None, 'invalid Forge source prefix')
        def literal(node):
            if isinstance(node, ast.JoinedStr):
                result = []
                for part in node.values:
                    if isinstance(part, ast.Constant) and type(part.value) is str:
                        result.append(part.value)
                    else:
                        require(isinstance(part, ast.FormattedValue) and isinstance(part.value, ast.Name)
                                and part.value.id == '_FORGE' and part.conversion == -1
                                and part.format_spec is None, 'unsupported catalog interpolation')
                        result.append(forge)
                return ''.join(result)
            if isinstance(node, ast.Dict):
                keys = [literal(key) for key in node.keys]
                require(all(type(key) is str for key in keys) and len(set(keys)) == len(keys),
                        'duplicate or invalid catalog field')
                return dict(zip(keys, (literal(value) for value in node.values)))
            if isinstance(node, (ast.List, ast.Tuple)):
                return [literal(item) for item in node.elts]
            return ast.literal_eval(node)
        require(isinstance(assigned['SERIES_A_CARDS'], ast.Tuple), 'catalog must be a tuple')
        cards = literal(assigned['SERIES_A_CARDS'])
        require(len(cards) <= 2000 and all(type(card) is dict for card in cards), 'invalid source cards')
        grouped = {}
        for card in cards:
            if card.get('hub_kind') == 'model' and isinstance(card.get('hub_id'), str):
                grouped.setdefault(card['hub_id'], []).append(safe_source_pointer(card.get('github')))
        return {identity: ('AMBIGUOUS', None) if len(urls) > 1 else (
                    ('DECLARED_POINTER_ONLY', urls[0]) if urls[0] is not None else
                    ('NOT_RESOLVED_BY_THIS_CATALOG', None))
                for identity, urls in grouped.items()}
    except (SyntaxError, ValueError, TypeError, UnicodeError, RecursionError, OverflowError) as exc:
        raise VerificationError('unsupported or invalid source catalog') from exc


def validate_source_pointers(value: Any, pointers: dict[str, tuple[str, str | None]]) -> None:
    """Bind each returned declaration to its actual source, not merely a safe URL.

    This verifies catalog correspondence only, never source ownership, executable
    training code, weight lineage, license rights or model qualification.
    """
    require(type(value) is dict and type(value.get('models')) is list,
            'model source rows unavailable')
    require(value.get('sourcePointerCatalogState') == 'EXISTING_SERIES_A_CATALOG_SUBSET',
            'runtime source catalog unavailable')
    seen, linked = set(), 0
    for row in value['models']:
        require(type(row) is dict and type(row.get('id')) is str and row['id'] not in seen,
                'invalid/duplicate source row')
        seen.add(row['id'])
        expected = pointers.get(row['id'], ('NOT_RESOLVED_BY_THIS_CATALOG', None))
        require((row.get('sourceState'), row.get('sourceUrl')) == expected,
                'source pointer differs from selected catalog: ' + row['id'])
        linked += int(expected[0] == 'DECLARED_POINTER_ONLY')
    require(type(value.get('sourcePointersDeclared')) is int and value['sourcePointersDeclared'] == linked,
            'source-bound pointer count differs')


def validate_asset(path: str, status: int, media: str, body: bytes, expected: bytes) -> None:
    require(path in ASSETS and type(status) is int and status == 200, 'asset status/path')
    require(media.split(';', 1)[0].strip().lower() in ASSETS[path][1], 'asset media type')
    require(type(body) is bytes and 0 < len(body) <= LIMIT and body == expected, 'served asset bytes differ')


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise VerificationError('redirect refused')


def probe(root: Path, origin: str, expected: str, *, fetch=None) -> dict[str, Any]:
    require(origin in ORIGINS.values(), 'origin not admitted for this read-only check')
    require(type(expected) is str and SHA.fullmatch(expected) is not None, 'exact source required')
    manifest = (root / 'docs/huggingface-ecosystem-manifest.json').read_bytes()
    projection = (root / 'routers/data/model-pretraining-snapshot.json').read_bytes()
    catalog_raw = (root / 'a11oy_model_intel.py').read_bytes()
    pointers = declared_source_pointers(catalog_raw)
    deadline = time.monotonic() + 180
    opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
    def get(path, method='GET'):
        require(time.monotonic() < deadline, 'observation deadline exceeded')
        req = request.Request(origin + path, method=method,
            headers={'User-Agent': 'SZL-Model-Delivery-Readback/1', 'Accept-Encoding': 'identity', 'Cache-Control': 'no-cache'})
        with opener.open(req, timeout=min(10, max(.1, deadline-time.monotonic()))) as response:
            status, media = response.status, response.headers.get('Content-Type', '')
            require(response.geturl() == origin + path, 'unexpected final URL')
            chunks, size = [], 0
            while method != 'HEAD':
                chunk = response.read(65536)
                if not chunk: break
                chunks.append(chunk); size += len(chunk)
                require(size <= LIMIT and time.monotonic() < deadline, 'response bound exceeded')
            return status, media, b''.join(chunks)
    getter = fetch or get
    def api(path):
        status, media, body = getter(path)
        require(type(status) is int and status == 200 and media.split(';',1)[0].strip().lower() == 'application/json',
                'API transport/content type differs')
        return strict_json(body)
    source_revision(api('/api/build-info'), expected)
    api_head, api_media, api_body = getter(API, 'HEAD')
    require(api_head == 200 and api_body == b''
            and api_media.split(';',1)[0].strip().lower() == 'application/json', 'model API HEAD differs')
    data = api(API)
    validate_catalog(data, manifest, projection, expected, datetime.now(timezone.utc))
    validate_source_pointers(data, pointers)
    observations = {}
    for path, (filename, _) in ASSETS.items():
        head, head_media, head_body = getter(path, 'HEAD')
        require(head == 200 and head_body == b'' and head_media.split(';',1)[0].strip().lower() in ASSETS[path][1],
                'asset HEAD differs')
        status, media, body = getter(path)
        validate_asset(path, status, media, body, (root / filename).read_bytes())
        observations[path] = {'head': head, 'get': status, 'sha256': sha256(body), 'bytes': len(body)}
    source_revision(api('/api/build-info'), expected)
    return {'state':'PASS_SELECTED_SOURCE_AND_DELIVERY', 'origin':origin, 'sourceRevision':expected,
        'inventoryObservedAt':data['observedAt'], 'inventoryFreshness':data['snapshotFreshness'],
        'recordedModelCount':data['returned'], 'declaredSourcePointers':data['sourcePointersDeclared'],
        'projectionSha256':sha256(projection), 'sourcePointerCatalogSha256':sha256(catalog_raw),
        'sourcePointerCorrespondence':'DECLARATIONS_MATCH_NOT_LINEAGE_VERIFIED', 'assets':observations,
        'modelLineageVerified':False, 'wholeEstateAligned':False, 'trainingAllowed':False,
        'browserRenderingVerified':False, 'runtimeIdentity':'REPORTED_SOURCE_MATCH_AND_SERVED_ASSET_BYTES'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--surface', choices=tuple(ORIGINS), required=True)
    parser.add_argument('--expected-source', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = {'schema':'szl.model-pretraining-live/v1', 'observedAt':datetime.now(timezone.utc).isoformat(),
              'surface':args.surface, 'state':'UNAVAILABLE', 'trainingAllowed':False, 'wholeEstateAligned':False}
    code = 1
    try:
        actual = subprocess.run(['git','rev-parse','HEAD'], cwd=ROOT, check=True, capture_output=True,
                                text=True, timeout=10).stdout.strip()
        require(actual == args.expected_source, 'checkout/source mismatch')
        report.update(probe(ROOT, ORIGINS[args.surface], actual)); code = 0
    except (VerificationError, OSError, error.URLError, subprocess.SubprocessError, TypeError, KeyError) as exc:
        report['errorType'] = type(exc).__name__
        report['reason'] = str(exc)[:300]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps(report, sort_keys=True, allow_nan=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
