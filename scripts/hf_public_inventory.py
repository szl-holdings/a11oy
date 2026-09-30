# SPDX-License-Identifier: Apache-2.0
"""Public Hub membership evidence, never a fleet, rights, or readiness policy.

All three counts use the same explicit anonymous/public predicate. HTTP 200 with
malformed JSON is UNKNOWN, not zero. Pagination is bounded and restricted to the
original Hub endpoint. Same-cardinality substitutions remain visible as ID deltas.
Authenticated official-inventory-v2 totals are a separate observation scope.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Callable, Mapping
from urllib.parse import parse_qs, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

KINDS = ('models', 'datasets', 'spaces')
MAX_BYTES = 2_000_000
MAX_PAGES = 20
MAX_ITEMS = 2_000
PREDICATE = {
    'id': 'hf-public-author-membership/v1',
    'authentication': 'none',
    'visibility': 'public-only',
    'kinds': list(KINDS),
    'include_gated_metadata': True,
    'include_disabled_metadata': True,
    'include_reserved_readme_if_public': True,
    'kernel_policy': 'count-once-as-model-repository-not-a-fourth-kind',
    'collections_and_buckets': 'outside-repository-membership-scope',
    'portfolio_and_operational_policy': False,
}
REPO = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*\Z')
ORG = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]*\Z')


class InventoryError(ValueError):
    """The observed response cannot support a complete membership claim."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InventoryError('DUPLICATE_JSON_KEY')
        result[key] = value
    return result


def _nonfinite(_):
    raise InventoryError('NONFINITE_JSON')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise InventoryError('REDIRECT_REFUSED')


def public_get(url: str) -> Mapping[str, Any]:
    """No environment token, cookie jar, proxy, redirect, or implicit retry."""
    parsed = urlsplit(url)
    org = parse_qs(parsed.query).get('author', [''])[0]
    kind = parsed.path.removeprefix('/api/')
    if kind not in KINDS or not ORG.fullmatch(org):
        raise InventoryError('UNSAFE_PUBLIC_ENDPOINT')
    validate_url(url, org, kind)
    request = Request(url, headers={
        'User-Agent': 'SZL-Public-Membership/1', 'Accept': 'application/json',
        'Cache-Control': 'no-cache, no-store',
    })
    opener = build_opener(ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=20) as response:
        if response.status != 200 or response.geturl() != url:
            raise InventoryError('UNEXPECTED_HTTP_RESPONSE')
        raw = response.read(MAX_BYTES + 1)
        link = response.headers.get('Link')
    if len(raw) > MAX_BYTES:
        raise InventoryError('RESPONSE_BYTE_BUDGET')
    try:
        body = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=_nonfinite)
        canonical(body)  # Reject exponent overflow as well as NaN/Infinity literals.
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise InventoryError('INVALID_JSON_RESPONSE') from exc
    return {'status': 200, 'json': body, 'link': link,
            'response_sha256': hashlib.sha256(raw).hexdigest()}


def validate_url(url: str, org: str, kind: str) -> None:
    p = urlsplit(url)
    query = parse_qs(p.query, keep_blank_values=True)
    if (p.scheme != 'https' or p.netloc != 'huggingface.co'
            or p.path != f'/api/{kind}' or p.fragment
            or set(query) - {'author', 'limit', 'full', 'cursor'}
            or query.get('author') != [org] or query.get('limit') != ['100']
            or query.get('full') != ['true']
            or ('cursor' in query and (len(query['cursor']) != 1 or not query['cursor'][0]))):
        raise InventoryError('UNSAFE_OR_CHANGED_PAGINATION_SCOPE')


def next_url(link: Any, org: str, kind: str) -> str | None:
    if link is None or link == '':
        return None
    if not isinstance(link, str) or len(link) > 16_384:
        raise InventoryError('MALFORMED_LINK_HEADER')
    # Cursor values must encode commas; reject ambiguous/broken fields rather
    # than guessing that an unparseable continuation means enumeration ended.
    found = []
    for field in link.split(','):
        match = re.fullmatch(r'\s*<([^<>]+)>\s*;\s*rel="([a-z ]+)"\s*', field)
        if not match:
            raise InventoryError('MALFORMED_LINK_HEADER')
        target, relations = match.groups()
        if 'next' in relations.split():
            validate_url(target, org, kind)
            found.append(target)
    if len(found) > 1:
        raise InventoryError('MULTIPLE_NEXT_LINKS')
    return found[0] if found else None


def collect(org: str, get: Callable[[str], Mapping[str, Any]] = public_get) -> dict[str, Any]:
    if not isinstance(org, str) or not ORG.fullmatch(org):
        raise InventoryError('INVALID_ORGANIZATION')
    result: dict[str, Any] = {
        'organization': org, 'scope': json.loads(canonical(PREDICATE)),
        'scope_sha256': digest(PREDICATE), 'counts': {}, 'items': {},
        'page_evidence': {}, 'errors': {}, 'observed': False,
    }
    for kind in KINDS:
        url = f'https://huggingface.co/api/{kind}?author={org}&limit=100&full=true'
        seen_urls: set[str] = set()
        members: dict[str, Any] = {}
        pages = []
        try:
            while url is not None:
                validate_url(url, org, kind)
                if url in seen_urls or len(seen_urls) >= MAX_PAGES:
                    raise InventoryError('PAGINATION_CYCLE_OR_PAGE_BUDGET')
                seen_urls.add(url)
                response = get(url)
                if response.get('status') != 200:
                    raise InventoryError('HTTP_UNAVAILABLE')
                rows = response.get('json')
                if not isinstance(rows, list) or len(rows) > 100:
                    raise InventoryError('INVALID_LIST_RESPONSE')
                for row in rows:
                    if not isinstance(row, Mapping):
                        raise InventoryError('MALFORMED_REPOSITORY_ROW')
                    name = row.get('id')
                    if (not isinstance(name, str) or not REPO.fullmatch(name)
                            or name.split('/', 1)[0] != org or name in members):
                        raise InventoryError('FOREIGN_MALFORMED_OR_DUPLICATE_ID')
                    if row.get('private') is not False:
                        raise InventoryError('VISIBILITY_NOT_EXPLICITLY_PUBLIC')
                    members[name] = {'id': name, 'sha': row.get('sha'),
                                     'last_modified': row.get('lastModified'), 'private': False}
                if len(members) > MAX_ITEMS:
                    raise InventoryError('ITEM_BUDGET')
                continuation = next_url(response.get('link'), org, kind)
                if continuation and not rows:
                    raise InventoryError('EMPTY_CONTINUATION_PAGE')
                pages.append({'index': len(pages) + 1, 'count': len(rows),
                              'response_sha256': response.get('response_sha256'),
                              'has_next': continuation is not None})
                url = continuation
            result['items'][kind] = [members[name] for name in sorted(members)]
            result['counts'][kind] = len(members)
        except Exception as exc:
            # Never serialize exception URLs, credentials or private item IDs.
            result['counts'][kind] = None
            result['items'][kind] = []
            result['errors'][kind] = str(exc) if isinstance(exc, InventoryError) else type(exc).__name__
        result['page_evidence'][kind] = pages
    result['observed'] = not result['errors']
    result['membership_sha256'] = digest({k: [r['id'] for r in result['items'][k]] for k in KINDS}) if result['observed'] else None
    return result


def compare_manifest(inventory: Mapping[str, Any], manifest: Any, declared: Any) -> dict[str, Any]:
    """Compare complete anonymous membership against the existing public snapshot.

The old full card-audit manifest is not regenerated or relabeled by this check.
Unknown, private, malformed, and equal-count/different-ID results stay blocked.
"""
    if not isinstance(inventory, Mapping):
        return {'aligned': False, 'blockers': ['HF_PUBLIC_INVENTORY_UNAVAILABLE'], 'delta': {}}
    reasons = []
    delta: dict[str, Any] = {}
    if inventory.get('scope') != PREDICATE or inventory.get('scope_sha256') != digest(PREDICATE):
        reasons.append('HF_INVENTORY_SCOPE_MISMATCH')
    if inventory.get('observed') is not True:
        reasons.append('HF_PUBLIC_INVENTORY_UNAVAILABLE')
    if not isinstance(manifest, Mapping):
        return {'aligned': False, 'blockers': sorted(set(reasons + ['HF_PUBLIC_MANIFEST_UNAVAILABLE'])), 'delta': delta}
    scope = manifest.get('inventoryScope', {})
    if not isinstance(scope, Mapping) or not (
        scope.get('visibility') == 'public-only' and scope.get('authenticated') is False
        and scope.get('privateAssetsIncluded') is False
    ):
        reasons.append('HF_MANIFEST_SCOPE_MISMATCH')
    org = inventory.get('organization')
    if manifest.get('org') != org:
        reasons.append('HF_MANIFEST_ORGANIZATION_MISMATCH')
    observed_counts = inventory.get('counts')
    observed_items = inventory.get('items')
    if not isinstance(observed_counts, Mapping) or not isinstance(observed_items, Mapping):
        return {'aligned': False, 'blockers': sorted(set(reasons + ['HF_OBSERVED_MEMBERSHIP_INVALID'])), 'delta': delta}
    manifest_counts = manifest.get('counts')
    manifest_items = manifest.get('inventory')
    if not isinstance(manifest_counts, Mapping) or not isinstance(manifest_items, Mapping):
        reasons.append('HF_MANIFEST_MEMBERSHIP_UNAVAILABLE')
    else:
        for kind in KINDS:
            rows = manifest_items.get(kind)
            if not isinstance(rows, list):
                reasons.append(f'HF_MANIFEST_INVALID:{kind}')
                continue
            names = []
            valid = True
            for row in rows:
                name = row.get('id') if isinstance(row, Mapping) else None
                if (not isinstance(name, str) or not REPO.fullmatch(name)
                        or name.split('/', 1)[0] != org or row.get('private') is not False):
                    valid = False
                    break
                names.append(name)
            count = manifest_counts.get(kind)
            if not valid or len(names) != len(set(names)) or type(count) is not int or count != len(names):
                reasons.append(f'HF_MANIFEST_INVALID:{kind}')
                continue
            if observed_counts.get(kind) is None:
                delta[kind] = {'state': 'UNAVAILABLE', 'added': None, 'removed': None}
                continue
            observed_rows = observed_items.get(kind)
            if not isinstance(observed_rows, list):
                reasons.append(f'HF_OBSERVED_MEMBERSHIP_INVALID:{kind}')
                continue
            if any(not isinstance(row, Mapping)
                   or not isinstance(row.get('id'), str) or not REPO.fullmatch(row['id'])
                   or row['id'].split('/', 1)[0] != org or row.get('private') is not False
                   for row in observed_rows):
                reasons.append(f'HF_OBSERVED_MEMBERSHIP_INVALID:{kind}')
                continue
            actual_names = [row['id'] for row in observed_rows]
            actual_count = observed_counts.get(kind)
            if (len(actual_names) != len(observed_rows) or len(actual_names) != len(set(actual_names))
                    or type(actual_count) is not int or actual_count != len(actual_names)):
                reasons.append(f'HF_OBSERVED_MEMBERSHIP_INVALID:{kind}')
                continue
            added, removed = sorted(set(actual_names) - set(names)), sorted(set(names) - set(actual_names))
            delta[kind] = {'state': 'MATCH' if not added and not removed else 'DRIFT',
                           'added': added, 'removed': removed}
            if added or removed:
                reasons.append(f'HF_PUBLIC_MEMBERSHIP_DRIFT:{kind}')
    if (not isinstance(declared, Mapping) or set(declared) != set(KINDS)
            or any(type(declared.get(k)) is not int for k in KINDS)):
        reasons.append('HF_PROFILE_COUNTS_UNAVAILABLE')
    elif declared != inventory.get('counts') or declared != manifest_counts:
        reasons.append('HF_PUBLIC_COUNTS_DRIFT')
    return {'aligned': not reasons, 'blockers': sorted(set(reasons)), 'delta': delta}


def main() -> int:
    import argparse
    from datetime import datetime, timezone
    from pathlib import Path
    import subprocess

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--estate-report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--soft', action='store_true')
    args = parser.parse_args()
    report: dict[str, Any] = {
        'schema': 'szl.public-inventory-preflight/v1',
        'observed_at': datetime.now(timezone.utc).isoformat(),
        'state': 'UNAVAILABLE', 'production_authorization': False,
        'provider_writes_performed': False, 'credentials_used': False,
        'scope': json.loads(canonical(PREDICATE)), 'scope_sha256': digest(PREDICATE),
    }
    try:
        def load(path: Path):
            with path.open('rb') as handle:
                raw = handle.read(10 * MAX_BYTES + 1)
            if len(raw) > 10 * MAX_BYTES:
                raise InventoryError('INPUT_BYTE_BUDGET')
            value = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=_nonfinite)
            canonical(value)
            return value, hashlib.sha256(raw).hexdigest()
        config, config_hash = load(args.config)
        if config.get('public_inventory_scope') != PREDICATE:
            raise InventoryError('CONFIG_SCOPE_MISMATCH')
        manifest, manifest_hash = load(args.manifest)
        estate, estate_hash = load(args.estate_report)
        expected_digest = estate.get('proof_chain_sha256')
        if expected_digest != digest({k: v for k, v in estate.items() if k != 'proof_chain_sha256'}):
            raise InventoryError('ESTATE_RECEIPT_DIGEST_MISMATCH')
        source_sha = subprocess.run(['git', 'rev-parse', 'HEAD'], check=True,
                                    capture_output=True, text=True).stdout.strip()
        if not re.fullmatch(r'[0-9a-f]{40}', source_sha):
            raise InventoryError('INVALID_CHECKOUT_REVISION')
        inventory = collect(config['huggingface_organization'])
        profile = estate.get('profile_inventory', {})
        comparison = compare_manifest(inventory, manifest, profile.get('declared_counts'))
        report.update({
            'state': 'ALIGNED' if comparison['aligned'] else 'DIVERGENT' if inventory['observed'] else 'UNAVAILABLE',
            'checkout_source_revision': source_sha,
            'source_binding': 'CHECKOUT_ID_AND_INPUT_HASHES_NOT_RUNTIME_ATTESTATION',
            'collector_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'estate_source_revision': estate.get('source_vector', {}).get('a11oy'),
            'profile_source_revision': profile.get('profile_sha'),
            'config_sha256': config_hash, 'manifest_sha256': manifest_hash,
            'estate_receipt_sha256': estate_hash,
            'declared_counts': profile.get('declared_counts'),
            'manifest_counts': manifest.get('counts'),
            'inventory': inventory, 'comparison': comparison,
            'card_semantics_refreshed': False,
            'official_authenticated_inventory_v2': 'SEPARATE_SCOPE_NOT_REPLACED',
        })
    except Exception as exc:
        report['error'] = str(exc) if isinstance(exc, InventoryError) else type(exc).__name__
    report['record_sha256'] = digest(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(report, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'state': report['state'], 'record_sha256': report['record_sha256'],
                      'blockers': report.get('comparison', {}).get('blockers', [report.get('error')])}))
    return 0 if args.soft or report['state'] == 'ALIGNED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
