# SPDX-License-Identifier: Apache-2.0
"""Prepare a review branch from the existing native HF collector artifact.

Runs only in the source-owned drift workflow. It changes six allowlisted derived
source files at most, never main, model bytes, a Space, secrets, or provider policy.
No PR is merged or created here; a maintainer opens/reviews the returned branch.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'szl-holdings/a11oy'
CANONICAL = 'docs/huggingface-ecosystem-manifest.json'
ALLOWED = {CANONICAL, 'docs/ecosystem-stage-matrix.json',
    'routers/data/model-pretraining-snapshot.json',
    'docs/generated/github-org-public-estate.md', 'docs/generated/huggingface-org-card.md',
    'docs/generated/a11oy-net-public-estate.md'}
SHA = re.compile(r'[a-f0-9]{40}\Z')
HASH = re.compile(r'[a-f0-9]{64}\Z')
LIMIT = 8 * 1024 * 1024


class PreparationError(ValueError):
    """No source admission is authorized by an incomplete observation."""


def require(ok: bool, reason: str) -> None:
    if not ok: raise PreparationError(reason)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def strict(raw: bytes) -> Any:
    require(type(raw) is bytes and 0 < len(raw) <= LIMIT, 'invalid JSON size')
    def pairs(items):
        result = {}
        for key,value in items:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def bad(_): raise PreparationError('nonfinite JSON')
    import math
    def finite(value):
        number=float(value); require(math.isfinite(number),'nonfinite JSON'); return number
    try: return json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=bad,parse_float=finite)
    except (ValueError, UnicodeError, RecursionError) as exc: raise PreparationError('invalid JSON') from exc


def validate_candidate(raw: bytes, *, now: datetime) -> dict[str, Any]:
    value = strict(raw)
    require(type(value) is dict and value.get('schemaVersion') == 2
            and value.get('generatedBy') == 'scripts/audit_huggingface_ecosystem.py'
            and value.get('org') == 'SZLHOLDINGS', 'collector/schema differs')
    scope = value.get('inventoryScope')
    require(type(scope) is dict and scope.get('visibility') == 'public-only'
            and scope.get('authenticated') is False and scope.get('privateAssetsIncluded') is False,
            'scope must remain anonymous public-only')
    try:
        observed = datetime.fromisoformat(value['observedAt'].replace('Z','+00:00'))
        require(observed.tzinfo is not None and observed.utcoffset().total_seconds() == 0, 'UTC observation required')
        age = (now-observed).total_seconds()
        require(0 <= age <= 86400, 'candidate is future-dated or older than 24 hours')
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise PreparationError('invalid observation time') from exc
    inventory,counts=value.get('inventory'),value.get('counts')
    require(type(inventory) is dict and set(inventory)=={'models','datasets','spaces'}
            and type(counts) is dict, 'incomplete scope')
    for plural,kind in (('models','model'),('datasets','dataset'),('spaces','space')):
        rows=inventory[plural]; seen=set()
        require(type(rows) is list and type(counts.get(plural)) is int
                and counts[plural]==len(rows) and len(rows)<=5000, 'incomplete count')
        for row in rows:
            require(type(row) is dict and type(row.get('id')) is str
                    and re.fullmatch(r'SZLHOLDINGS/[A-Za-z0-9][A-Za-z0-9._-]{0,159}',row['id']) is not None
                    and '..' not in row['id'] and row['id'] not in seen
                    and row.get('repoType')==kind and row.get('private') is False,
                    'invalid/duplicate/foreign item')
            seen.add(row['id'])
            require(type(row.get('sha')) is str and SHA.fullmatch(row['sha']) is not None, 'missing revision')
    require(raw == (json.dumps(value,indent=2,sort_keys=False)+'\n').encode('utf-8'), 'collector rendering differs')
    return value


def validate_artifact(meta: Any, archive: bytes, *, source: str, run_id: int, expected_digest: str) -> bytes:
    require(SHA.fullmatch(source) is not None and HASH.fullmatch(expected_digest) is not None, 'invalid artifact identity')
    require(type(meta) is dict and meta.get('expired') is False
            and meta.get('name')==f'huggingface-ecosystem-manifest-candidate-{run_id}'
            and meta.get('digest')=='sha256:'+expected_digest, 'artifact metadata differs')
    run=meta.get('workflow_run')
    require(type(run) is dict and run.get('id')==run_id and run.get('head_sha')==source
            and run.get('head_branch')=='main', 'artifact is not from selected main run')
    require(type(archive) is bytes and 0 < len(archive) <= LIMIT
            and meta.get('size_in_bytes')==len(archive) and digest(archive)==expected_digest,
            'archive size/digest differs')
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            members=z.infolist()
            require(len(members)==1 and members[0].filename=='huggingface-ecosystem-manifest.candidate.json'
                    and 0 < members[0].file_size <= LIMIT and not members[0].is_dir(), 'unexpected archive member')
            # Read in memory only. No archive path is extracted or executed.
            return z.read(members[0])
    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
        raise PreparationError('invalid candidate archive') from exc


def branch_name(source: str, candidate: str) -> str:
    require(SHA.fullmatch(source) is not None and HASH.fullmatch(candidate) is not None,'invalid branch identity')
    return f'szl/hf-inventory-{source[:12]}-{candidate[:12]}'


def command(args: list[str], *, data: bytes | None = None, timeout: int = 60) -> bytes:
    result=subprocess.run(args,cwd=ROOT,input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
    if result.returncode:
        # Do not print token-bearing environment or arbitrary remote response bodies.
        raise PreparationError(f'{args[0]} failed with exit {result.returncode}')
    require(len(result.stdout)<=LIMIT, 'command output too large')
    return result.stdout


def github(path: str, *, body: dict | None = None) -> Any:
    require(path.startswith(f'repos/{REPOSITORY}/'), 'GitHub endpoint outside owner')
    args=['gh','api','--method','POST' if body is not None else 'GET',path]
    data=None
    if body is not None:
        args += ['--input','-']; data=json.dumps(body,allow_nan=False).encode()
    return strict(command(args,data=data))


def current_main() -> str:
    value=github(f'repos/{REPOSITORY}/git/ref/heads/main')
    return value.get('object',{}).get('sha','')


def prepare(source: str, run_id: int, artifact_id: int, archive_digest: str, report: dict) -> None:
    require(SHA.fullmatch(source) is not None and run_id>0 and artifact_id>0, 'invalid selected source/run')
    require(command(['git','rev-parse','HEAD']).decode().strip()==source, 'checkout mismatch')
    require(not command(['git','status','--porcelain','--untracked-files=all']).strip(), 'checkout not clean')
    require(current_main()==source, 'source moved before preparation')
    meta=github(f'repos/{REPOSITORY}/actions/artifacts/{artifact_id}')
    require(type(meta.get('size_in_bytes')) is int and 0<meta['size_in_bytes']<=LIMIT, 'artifact too large')
    archive=command(['gh','api',f'repos/{REPOSITORY}/actions/artifacts/{artifact_id}/zip'])
    candidate=validate_artifact(meta,archive,source=source,run_id=run_id,expected_digest=archive_digest)
    observed=validate_candidate(candidate,now=datetime.now(timezone.utc))
    sys.path.insert(0,str(ROOT/'scripts'))
    import audit_huggingface_ecosystem as collector
    collector.validate_generated_revision_evidence(observed, observed_at=collector.validate_observed_at(observed['observedAt']))
    old=strict((ROOT/CANONICAL).read_bytes())
    for kind in ('models','datasets','spaces'):
        require(not old.get('inventory',{}).get(kind) or observed['inventory'][kind],
                'empty replacement requires explicit inventory review')
    if collector.semantic_manifest(old)==collector.semantic_manifest(observed):
        report.update(state='NO_SEMANTIC_REFRESH_REQUIRED',branchCreated=False); return
    report.update(candidateSha256=digest(candidate),inventoryObservedAt=observed['observedAt'],counts=observed['counts'])
    (ROOT/CANONICAL).write_bytes(candidate)
    # Existing owner generators only; no speculative reconstruction of their outputs.
    for script,args in (
        ('scripts/build_ecosystem_stage_matrix.py',[]),
        ('scripts/render_public_estate_alignment.py',[]),
        ('scripts/build_model_pretraining_projection.py',['--write']),
        ('scripts/build_ecosystem_stage_matrix.py',['--check']),
        ('scripts/render_public_estate_alignment.py',['--check']),
        ('scripts/build_model_pretraining_projection.py',['--check'])):
        command([sys.executable,'-B',script,*args],timeout=120)
    changed=command(['git','diff','--name-only','-z']).decode().split('\0')
    paths=sorted(p for p in changed if p)
    require(paths and set(paths)<=ALLOWED and CANONICAL in paths, 'generated diff outside allowed files')
    require(not command(['git','ls-files','--others','--exclude-standard']).strip(),'untracked generator output')
    for path in paths:
        require(not (ROOT/path).is_symlink() and (ROOT/path).is_file(),'nonregular generated file')
    require(current_main()==source, 'source moved before branch preparation')
    name=branch_name(source,digest(candidate))
    refs=github(f'repos/{REPOSITORY}/git/matching-refs/heads/{name}')
    require(type(refs) is list, 'branch observation unavailable')
    require(not refs, 'deterministic branch already exists; review it instead of overwriting')
    elements=[]; hashes={}
    for path in paths:
        content=(ROOT/path).read_bytes(); require(len(content)<=LIMIT,'generated file too large')
        sha=github(f'repos/{REPOSITORY}/git/blobs',body={'content':base64.b64encode(content).decode(),'encoding':'base64'})['sha']
        expected=hashlib.sha1(f'blob {len(content)}\0'.encode()+content).hexdigest()
        require(sha==expected,'blob readback differs')
        elements.append({'path':path,'mode':'100644','type':'blob','sha':sha}); hashes[path]=digest(content)
    base_tree=command(['git','show','-s','--format=%T',source]).decode().strip()
    tree=github(f'repos/{REPOSITORY}/git/trees',body={'base_tree':base_tree,'tree':elements})['sha']
    require(SHA.fullmatch(tree) is not None,'invalid tree')
    message=(f'chore(hf): refresh source-owned public inventory from run {run_id}\n\n'
        f'Collector source {source}; candidate SHA256 {digest(candidate)}.\n'
        'Regenerate existing dependent source views. Public metadata only; no model, training, '
        'keep-list, runtime, or publication eligibility change. Review and native checks are required.\n\n'
        'Signed-off-by: github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>')
    commit=github(f'repos/{REPOSITORY}/git/commits',body={'tree':tree,'parents':[source],'message':message})['sha']
    require(SHA.fullmatch(commit) is not None and current_main()==source,'source moved before ref mutation')
    report.update(branch=name,commit=commit,changedFiles=hashes,state='REF_WRITE_UNCERTAIN',branchCreated=None)
    # Exactly one ref creation; never update an existing branch or retry a POST.
    github(f'repos/{REPOSITORY}/git/refs',body={'ref':'refs/heads/'+name,'sha':commit})
    observed_ref=github(f'repos/{REPOSITORY}/git/ref/heads/{name}')
    require(observed_ref.get('object',{}).get('sha')==commit,'branch readback differs')
    report.update(branchCreated=True,state='REVIEW_BRANCH_CREATED' if current_main()==source else 'BASE_MOVED_REVIEW_REQUIRED')


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True); parser.add_argument('--run-id',type=int,required=True)
    parser.add_argument('--artifact-id',type=int,required=True); parser.add_argument('--artifact-digest',required=True)
    parser.add_argument('--output',type=Path,required=True); args=parser.parse_args()
    report={'schema':'szl.hf-inventory-review-branch/v1','state':'NOT_CREATED','branchCreated':False,
            'sourceRevision':args.source,'collectorRunId':args.run_id,'artifactId':args.artifact_id,
            'providerWrites':False,'trainingAllowed':False,'autoMerge':False,'wholeEstateAligned':False}
    code=0
    try: prepare(args.source,args.run_id,args.artifact_id,args.artifact_digest,report)
    except (PreparationError, ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        report.update(errorType=type(exc).__name__,reason=str(exc)[:300]); code=1
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream: stream.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,sort_keys=True))
    return code


if __name__=='__main__': raise SystemExit(main())
