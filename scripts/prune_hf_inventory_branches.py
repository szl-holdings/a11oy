#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Prune superseded per-run HF inventory review refs. Dispatch-only; dry run by default.

A legacy ``szl/hf-inventory-<source>-<candidate>`` ref is a deletion candidate only
when no open pull request uses it, every commit ahead of main passes the same
controller-commit predicate the rolling branch uses, and main already carries a
newer observation. The rolling ref and every other name are always kept.

Every decision is written to a hash-chained receipt before and after each
deletion, with the pruned manifest bytes archived beside it. The receipt is
DSSE-enveloped and UNSIGNED unless the runtime holds a signing key; the workflow
passes none. GitHub ref deletion carries no expected sha, so the ref is re-read
immediately before deleting, which narrows but does not close that race.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.append(str(ROOT))
import szl_dsse as dsse  # noqa: E402

_SPEC = importlib.util.spec_from_file_location('prepare_hf_inventory_refresh', ROOT/'scripts/prepare_hf_inventory_refresh.py')
refresh = importlib.util.module_from_spec(_SPEC); _SPEC.loader.exec_module(refresh)

SCHEMA = 'szl.hf-inventory-branch-prune/v1'
PAYLOAD_TYPE = 'application/vnd.szl.hf-inventory-branch-prune+json'
PREFIX = 'szl/hf-inventory-'
LEGACY = re.compile(r'refs/heads/szl/hf-inventory-[a-f0-9]{12}-[a-f0-9]{12}\Z')
ERRORS = (refresh.PreparationError, ValueError, OSError, KeyError, TypeError, AttributeError, subprocess.SubprocessError)


def utc(value: Any) -> datetime:
    refresh.require(type(value) is str, 'missing observation time')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    refresh.require(parsed.tzinfo is not None and parsed.utcoffset().total_seconds() == 0, 'UTC observation required')
    return parsed


def classify(entry: Any, main: str, main_seen: datetime, archive: Path) -> dict[str, Any]:
    """Return one KEEP or PRUNE decision; any doubt keeps the ref."""
    name = entry.get('ref') if type(entry) is dict else None
    target = entry.get('object') if type(entry) is dict and type(entry.get('object')) is dict else {}
    record = {'ref': name, 'sha': target.get('sha'), 'decision': 'KEEP'}
    if name == 'refs/heads/' + refresh.ROLLING: return {**record, 'reason': 'ROLLING_REF'}
    if type(name) is not str or LEGACY.fullmatch(name) is None:
        return {**record, 'reason': 'NAME_OUTSIDE_LEGACY_PATTERN'}
    if target.get('type') != 'commit' or type(record['sha']) is not str or refresh.SHA.fullmatch(record['sha']) is None:
        return {**record, 'reason': 'NOT_A_COMMIT_REF'}
    branch = name[len('refs/heads/'):]
    try:
        pulls = refresh.open_pull_requests(branch)
        if pulls: return {**record, 'reason': 'OPEN_PULL_REQUEST_HEAD', 'pullRequests': sorted(p['number'] for p in pulls)}
        try: refresh.verify_bot_chain(main, record['sha'])
        except refresh.ForeignCommitError as exc:
            return {**record, 'reason': 'NOT_PROVABLY_BOT_ONLY', 'detail': str(exc)[:200]}
        raw = refresh.blob_at(record['sha'], refresh.CANONICAL)
        manifest = refresh.strict(raw)
        seen = manifest.get('observedAt') if type(manifest) is dict else None
        record.update(manifestSha256=refresh.digest(raw), observedAt=seen)
        if not utc(seen) < main_seen: return {**record, 'reason': 'NOT_SUPERSEDED_BY_MAIN'}
    except ERRORS as exc:
        return {**record, 'reason': 'OBSERVATION_UNAVAILABLE', 'detail': f'{type(exc).__name__}: {str(exc)[:200]}'}
    archived = archive/'manifests'/(branch[len('szl/'):] + '.json')
    archived.parent.mkdir(parents=True, exist_ok=True)
    archived.write_bytes(raw)
    return {**record, 'decision': 'PRUNE', 'reason': 'SUPERSEDED_BOT_REFRESH',
            'archivedManifest': archived.relative_to(archive).as_posix()}


def chain(entries: list[dict[str, Any]]) -> str:
    """Re-link entries in place; each digest covers the entry and its predecessor's digest."""
    previous = '0' * 64
    for entry in entries:
        entry.pop('entrySha256', None); entry['previousEntrySha256'] = previous
        previous = hashlib.sha256(dsse.canonical_json(entry)).hexdigest()
        entry['entrySha256'] = previous
    return previous


def persist(receipt: dict[str, Any], output: Path) -> None:
    receipt['headEntrySha256'] = chain(receipt['entries'])
    for name, value in (('receipt.json', receipt), ('receipt.dsse.json', dsse.sign_payload(receipt, PAYLOAD_TYPE))):
        partial = output/(name + '.partial')
        partial.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        os.replace(partial, output/name)


def prune(apply: bool, receipt: dict[str, Any], output: Path) -> None:
    main = refresh.current_main()
    refresh.require(refresh.SHA.fullmatch(main) is not None, 'main observation unavailable')
    main_manifest = refresh.strict(refresh.blob_at(main, refresh.CANONICAL))
    main_seen = utc(main_manifest.get('observedAt') if type(main_manifest) is dict else None)
    receipt.update(mainRevision=main, mainObservedAt=main_manifest['observedAt'], state='DECIDING')
    refs = refresh.github(f'repos/{refresh.REPOSITORY}/git/matching-refs/heads/{PREFIX}')
    refresh.require(type(refs) is list, 'branch observation unavailable')
    receipt['entries'] = [classify(entry, main, main_seen, output) for entry in refs]
    pending = 'NOT_ATTEMPTED' if apply else 'NOT_DELETED_DRY_RUN'
    for entry in receipt['entries']: entry['outcome'] = 'KEPT' if entry['decision'] == 'KEEP' else pending
    receipt['state'] = 'DECIDED'
    persist(receipt, output)
    if not apply:
        receipt['state'] = 'DRY_RUN_COMPLETE'; return
    for entry in receipt['entries']:
        if entry['decision'] != 'PRUNE': continue
        branch = entry['ref'][len('refs/heads/'):]
        if refresh.ref_head(branch) != entry['sha']:
            entry['outcome'] = 'KEPT_REF_MOVED'; persist(receipt, output); continue
        entry['outcome'] = 'DELETE_UNCERTAIN'; persist(receipt, output)
        # One DELETE per ref and no retry; the readback decides what the receipt says.
        try: refresh.github(f'repos/{refresh.REPOSITORY}/git/refs/heads/{branch}', method='DELETE')
        except ERRORS as exc: entry['detail'] = f'{type(exc).__name__}: {str(exc)[:200]}'
        try: after = refresh.ref_head(branch)
        except ERRORS: after = 'UNAVAILABLE'
        entry['readback'] = 'ABSENT' if after is None else after
        if after is None: entry['outcome'] = 'PRUNED'
        persist(receipt, output)
    receipt['state'] = 'APPLY_COMPLETE'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='delete PRUNE decisions (default: dry run)')
    parser.add_argument('--output', type=Path, required=True); args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    receipt = {'schema': SCHEMA, 'repository': refresh.REPOSITORY, 'mode': 'APPLY' if args.apply else 'DRY_RUN',
               'rollingRef': 'refs/heads/' + refresh.ROLLING, 'startedAt': datetime.now(timezone.utc).isoformat(),
               'state': 'NOT_STARTED', 'entries': []}
    code = 0
    try: prune(args.apply, receipt, args.output)
    except ERRORS as exc:
        receipt.update(state='STOPPED', errorType=type(exc).__name__, reason=str(exc)[:300]); code = 1
    persist(receipt, args.output)
    print(json.dumps({key: receipt[key] for key in ('state', 'mode', 'headEntrySha256')}, sort_keys=True))
    return code


if __name__ == '__main__': raise SystemExit(main())
