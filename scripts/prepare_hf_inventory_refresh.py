# SPDX-License-Identifier: Apache-2.0
"""Advance one rolling review branch from the existing native HF collector artifact.

Runs only in the source-owned drift workflow. It changes six allowlisted derived
source files at most, never main, model bytes, a Space, secrets, or provider policy.
The branch is created once, then only fast-forwarded while every commit on it is
provably this controller's; any other commit stops the run without a write.
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
OWNER = REPOSITORY.split('/')[0]
ROLLING = 'szl/hf-inventory-refresh'
CANONICAL = 'docs/huggingface-ecosystem-manifest.json'
ALLOWED = {CANONICAL, 'docs/ecosystem-stage-matrix.json',
    'routers/data/model-pretraining-snapshot.json',
    'docs/generated/github-org-public-estate.md', 'docs/generated/huggingface-org-card.md',
    'docs/generated/a11oy-net-public-estate.md'}
SHA = re.compile(r'[a-f0-9]{40}\Z')
HASH = re.compile(r'[a-f0-9]{64}\Z')
LIMIT = 8 * 1024 * 1024
BOT_AUTHOR = 'github-actions[bot]'
BOT_COMMITTER = 'web-flow'
REFRESH_MESSAGE = re.compile(r'chore\(hf\): refresh source-owned public inventory from run [1-9][0-9]{0,19}\n\n'
    r'Collector source ([a-f0-9]{40}); candidate SHA256 [a-f0-9]{64}\.\n')
MAX_ROLLING_COMMITS = 100


class PreparationError(ValueError):
    """No source admission is authorized by an incomplete observation."""


class ForeignCommitError(PreparationError):
    """A commit on a controller-owned ref is not provably this controller's."""


def require(ok: bool, reason: str) -> None:
    if not ok: raise PreparationError(reason)


def foreign(ok: bool, reason: str) -> None:
    if not ok: raise ForeignCommitError(reason)


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
    require(type(inventory) is dict and set(inventory)=={'models','datasets','spaces','kernels'}
            and type(counts) is dict and set(counts)==set(inventory), 'incomplete scope')
    for plural,kind in (('models','model'),('datasets','dataset'),('spaces','space'),('kernels','kernel')):
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


def refresh_message(run_id: int, source: str, candidate: str) -> str:
    return (f'chore(hf): refresh source-owned public inventory from run {run_id}\n\n'
        f'Collector source {source}; candidate SHA256 {candidate}.\n'
        'Regenerate existing dependent source views. Public metadata only; no model, training, '
        'keep-list, runtime, or publication eligibility change. Review and native checks are required.\n\n'
        'Signed-off-by: github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>')


def command(args: list[str], *, data: bytes | None = None, timeout: int = 60) -> bytes:
    result=subprocess.run(args,cwd=ROOT,input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
    if result.returncode:
        # Do not print token-bearing environment or arbitrary remote response bodies.
        raise PreparationError(f'{args[0]} failed with exit {result.returncode}')
    require(len(result.stdout)<=LIMIT, 'command output too large')
    return result.stdout


def github(path: str, *, body: dict | None = None, method: str | None = None) -> Any:
    require(path.startswith(f'repos/{REPOSITORY}/'), 'GitHub endpoint outside owner')
    method=method or ('POST' if body is not None else 'GET')
    require(method in ('GET','POST','PATCH','DELETE'), 'unsupported GitHub method')
    args=['gh','api','--method',method,path]
    data=None
    if body is not None:
        args += ['--input','-']; data=json.dumps(body,allow_nan=False).encode()
    raw=command(args,data=data)
    if method=='DELETE':
        require(not raw.strip(), 'unexpected ref deletion response'); return None
    return strict(raw)


def current_main() -> str:
    value=github(f'repos/{REPOSITORY}/git/ref/heads/main')
    return value.get('object',{}).get('sha','')


def ref_head(branch: str) -> str | None:
    """Return the branch commit, or None only when GitHub lists no exact match."""
    # matching-refs answers absence with [] instead of a 404 that command() cannot
    # tell apart from an outage; it matches by prefix, so only the exact name counts.
    refs=github(f'repos/{REPOSITORY}/git/matching-refs/heads/{branch}')
    require(type(refs) is list and all(type(item) is dict for item in refs), 'branch observation unavailable')
    exact=[item for item in refs if item.get('ref')=='refs/heads/'+branch]
    if not exact: return None
    target=exact[0].get('object')
    require(len(exact)==1 and type(target) is dict and target.get('type')=='commit'
            and type(target.get('sha')) is str and SHA.fullmatch(target['sha']) is not None,
            'branch observation differs')
    return target['sha']


def ref_readback(branch: str) -> str:
    try: value=github(f'repos/{REPOSITORY}/git/ref/heads/{branch}')
    except (PreparationError, ValueError, OSError, subprocess.SubprocessError): return 'UNAVAILABLE'
    sha=value.get('object',{}).get('sha') if type(value) is dict and type(value.get('object')) is dict else None
    return sha if type(sha) is str and SHA.fullmatch(sha) is not None else 'UNAVAILABLE'


def blob_at(revision: str, path: str) -> bytes:
    require(SHA.fullmatch(revision) is not None, 'invalid revision')
    entry=github(f'repos/{REPOSITORY}/contents/{path}?ref={revision}')
    require(type(entry) is dict and entry.get('type')=='file' and entry.get('path')==path
            and type(entry.get('sha')) is str and SHA.fullmatch(entry['sha']) is not None
            and type(entry.get('size')) is int and 0<entry['size']<=LIMIT, 'branch file observation differs')
    blob=github(f'repos/{REPOSITORY}/git/blobs/{entry["sha"]}')
    require(type(blob) is dict and blob.get('encoding')=='base64' and type(blob.get('content')) is str,
            'branch file unavailable')
    try: raw=base64.b64decode(blob['content'])
    except ValueError as exc: raise PreparationError('branch file unavailable') from exc
    require(len(raw)==entry['size'] and hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()==entry['sha'],
            'branch file readback differs')
    return raw


def verify_bot_chain(base: str, head: str) -> list[str]:
    """Prove every commit in base...head is a refresh commit made by this controller.

    Author name, committer and message are each settable by any writer. Only all
    of them together, with GitHub's own verified signature, a first-parent diff
    inside ALLOWED and a second parent equal to the previous head, identify a
    commit this controller created through the git/commits API.
    """
    require(SHA.fullmatch(base) is not None and SHA.fullmatch(head) is not None, 'invalid comparison identity')
    comparison=github(f'repos/{REPOSITORY}/compare/{base}...{head}?per_page={MAX_ROLLING_COMMITS}')
    commits=comparison.get('commits') if type(comparison) is dict else None
    require(type(commits) is list and all(type(item) is dict for item in commits), 'branch comparison unavailable')
    require(comparison.get('total_commits')==len(commits) and len(commits)<=MAX_ROLLING_COMMITS,
            'branch history exceeds the verifiable bound')
    ahead={item.get('sha'):item for item in commits}
    foreign(len(ahead)==len(commits) and head in ahead, 'branch head is not a refresh commit ahead of main')
    chain=[]; current=head
    while True:
        item=ahead.get(current)
        foreign(item is not None and current not in chain, 'branch carries a commit outside the refresh chain')
        commit=item.get('commit') if type(item.get('commit')) is dict else {}
        verification=commit.get('verification') if type(commit.get('verification')) is dict else {}
        author,committer=item.get('author'),item.get('committer')
        foreign(type(author) is dict and author.get('login')==BOT_AUTHOR
                and type(committer) is dict and committer.get('login')==BOT_COMMITTER
                and verification.get('verified') is True, 'commit is not a GitHub-verified refresh bot commit')
        parents=[parent.get('sha') if type(parent) is dict else None for parent in item.get('parents') or []]
        template=REFRESH_MESSAGE.match(commit['message']) if type(commit.get('message')) is str else None
        foreign(template is not None and len(parents) in (1,2) and template.group(1)==parents[0]
                and parents[0] not in ahead, 'commit message or first parent differs from the refresh template')
        scope=github(f'repos/{REPOSITORY}/compare/{parents[0]}...{current}')
        files=scope.get('files') if type(scope) is dict else None
        foreign(type(files) is list and len(files)>0 and all(
            type(item) is dict and item.get('filename') in ALLOWED and item.get('status') in ('added','modified')
            and item.get('previous_filename') in (None,item.get('filename')) for item in files),
            'first-parent diff leaves the allowed generated files')
        chain.append(current)
        if len(parents)==1: break
        foreign(parents[1] in ahead, 'second parent is not the previous branch head')
        current=parents[1]
    foreign(len(chain)==len(ahead), 'branch carries a commit outside the refresh chain')
    return chain


def open_pull_requests(branch: str) -> list[dict]:
    pulls=github(f'repos/{REPOSITORY}/pulls?state=open&head={OWNER}:{branch}&per_page=100')
    require(type(pulls) is list and len(pulls)<100 and all(
        type(item) is dict and type(item.get('number')) is int and 'auto_merge' in item
        and type(item.get('head')) is dict for item in pulls), 'pull request observation unavailable')
    # A head filter GitHub did not apply must never read as "no PR uses this branch".
    require(all(item['head'].get('ref')==branch and type(item['head'].get('repo')) is dict
                and item['head']['repo'].get('full_name')==REPOSITORY for item in pulls),
            'pull request head filter was not applied')
    return pulls


def hold_for_review(report: dict) -> None:
    """Never move a head that a PR would auto-merge or that a reviewer approved."""
    pulls=open_pull_requests(ROLLING)
    report['pullRequests']=sorted(item['number'] for item in pulls)
    for pull in pulls:
        if pull['auto_merge'] is not None:
            report.update(state='ROLLING_PR_AUTO_MERGE_ENABLED')
            raise PreparationError('an open rolling-branch pull request has auto-merge enabled')
        reviews=github(f'repos/{REPOSITORY}/pulls/{pull["number"]}/reviews?per_page=100')
        require(type(reviews) is list and len(reviews)<100 and all(type(item) is dict for item in reviews),
                'review observation unavailable')
        if any(item.get('state')=='APPROVED' for item in reviews):
            report.update(state='ROLLING_PR_APPROVED')
            raise PreparationError('an open rolling-branch pull request is approved; merge or close it first')


def validate_public_estate_candidate(observed: dict, report: dict) -> None:
    """Require source classifications before changing any generated file.

    The collector can discover new public Spaces, but discovery does not amend
    the topology or keep policy. Record only validated public IDs and fixed
    diagnostics; subprocess output and the token-bearing environment stay out
    of the preparation receipt.
    """
    import render_public_estate_alignment as alignment
    report['preparationStep']='PUBLIC_ESTATE_PREFLIGHT'
    try:
        contract=alignment.load_json(ROOT/'static/shared/public-estate-contract.v1.json')
        declared=set(alignment.topology_spaces(contract)) | set(alignment.inventory_only_spaces(contract))
        public={row['id'] for row in observed['inventory']['spaces']}
        report['publicSpaceClassification']={
            'unclassified':sorted(public-declared),
            'unobserved':sorted(declared-public),
            'state':'SOURCE_REVIEW_REQUIRED',
        }
        alignment.validate(contract,observed)
    except alignment.ContractError as exc:
        raise PreparationError('public estate classification or policy contract requires source review') from exc
    report['publicSpaceClassification']['state']='VALIDATED'


def validate_model_support_candidate(observed: dict, report: dict) -> None:
    """Hold model-ID changes for source review without fabricating observations."""
    import a11oy_model_support as support
    report['preparationStep']='INFERENCE_SUPPORT_PREFLIGHT'
    report['modelInferenceSupport']={'state':'SOURCE_REVIEW_REQUIRED'}
    try:
        document=support.read_json(ROOT/'docs/model-inference-support.json')
        support.validate_document(document,observed)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise PreparationError('model inference support source or inventory coverage requires source review') from exc
    report['modelInferenceSupport']['state']='VALIDATED'


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
    sys.path.insert(0,str(ROOT))
    sys.path.insert(0,str(ROOT/'scripts'))
    import audit_huggingface_ecosystem as collector
    collector.validate_generated_revision_evidence(observed, observed_at=collector.validate_observed_at(observed['observedAt']))
    old=strict((ROOT/CANONICAL).read_bytes())
    for kind in ('models','datasets','spaces','kernels'):
        require(not old.get('inventory',{}).get(kind) or observed['inventory'][kind],
                'empty replacement requires explicit inventory review')
    if collector.semantic_manifest(old)==collector.semantic_manifest(observed):
        report.update(state='NO_SEMANTIC_REFRESH_REQUIRED',branchCreated=False); return
    report.update(candidateSha256=digest(candidate),inventoryObservedAt=observed['observedAt'],counts=observed['counts'])
    validate_public_estate_candidate(observed,report)
    validate_model_support_candidate(observed,report)
    report.update(preparationStep='VERIFY_ROLLING_BRANCH',branch=ROLLING)
    head=ref_head(ROLLING)
    if head is not None:
        report['previousHead']=head
        try: verify_bot_chain(source,head)
        except ForeignCommitError:
            report.update(state='ROLLING_BRANCH_HAS_FOREIGN_COMMITS'); raise
        if collector.semantic_manifest(strict(blob_at(head,CANONICAL)))==collector.semantic_manifest(observed):
            report.update(state='NO_ROLLING_REFRESH_REQUIRED'); return
        hold_for_review(report)
    (ROOT/CANONICAL).write_bytes(candidate)
    # Existing owner generators only; no speculative reconstruction of their outputs.
    for script,args in (
        ('scripts/build_ecosystem_stage_matrix.py',[]),
        ('scripts/render_public_estate_alignment.py',[]),
        ('scripts/build_model_pretraining_projection.py',['--write']),
        ('scripts/build_ecosystem_stage_matrix.py',['--check']),
        ('scripts/render_public_estate_alignment.py',['--check']),
        ('scripts/build_model_pretraining_projection.py',['--check'])):
        report.update(preparationStep='GENERATE_PROJECTIONS',generator=script,
                      generatorMode='CHECK' if '--check' in args else 'WRITE')
        command([sys.executable,'-B',script,*args],timeout=120)
    report.update(preparationStep='VERIFY_GENERATED_SCOPE')
    changed=command(['git','diff','--name-only','-z']).decode().split('\0')
    paths=sorted(p for p in changed if p)
    require(paths and set(paths)<=ALLOWED and CANONICAL in paths, 'generated diff outside allowed files')
    require(not command(['git','ls-files','--others','--exclude-standard']).strip(),'untracked generator output')
    for path in paths:
        require(not (ROOT/path).is_symlink() and (ROOT/path).is_file(),'nonregular generated file')
    require(current_main()==source, 'source moved before branch preparation')
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
    # The first parent keeps the PR diff to the allowed files against the source;
    # the second makes the update a fast-forward of the previous head.
    parents=[source] if head is None else [source,head]
    message=refresh_message(run_id,source,digest(candidate))
    commit=github(f'repos/{REPOSITORY}/git/commits',body={'tree':tree,'parents':parents,'message':message})['sha']
    require(SHA.fullmatch(commit) is not None and current_main()==source,'source moved before ref mutation')
    report.update(commit=commit,changedFiles=hashes,state='REF_WRITE_UNCERTAIN',
                  refUpdate='CREATE' if head is None else 'FAST_FORWARD')
    report['branchCreated' if head is None else 'branchAdvanced']=None
    # Exactly one ref write and no retry. A lost response or a non-fast-forward
    # rejection (a concurrent writer moved the head) stays uncertain for review.
    try:
        if head is None: github(f'repos/{REPOSITORY}/git/refs',body={'ref':'refs/heads/'+ROLLING,'sha':commit})
        else: github(f'repos/{REPOSITORY}/git/refs/heads/{ROLLING}',body={'sha':commit,'force':False},method='PATCH')
    except (PreparationError, ValueError, OSError, subprocess.SubprocessError):
        report['refReadback']=ref_readback(ROLLING); raise
    report['refReadback']=ref_readback(ROLLING)
    require(report['refReadback']==commit,'branch readback differs')
    report['branchCreated' if head is None else 'branchAdvanced']=True
    created='REVIEW_BRANCH_CREATED' if head is None else 'REVIEW_BRANCH_ADVANCED'
    report.update(state=created if current_main()==source else 'BASE_MOVED_REVIEW_REQUIRED')


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True); parser.add_argument('--run-id',type=int,required=True)
    parser.add_argument('--artifact-id',type=int,required=True); parser.add_argument('--artifact-digest',required=True)
    parser.add_argument('--output',type=Path,required=True); args=parser.parse_args()
    report={'schema':'szl.hf-inventory-review-branch/v2','state':'NOT_CREATED','branchCreated':False,
            'branchAdvanced':False,
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
