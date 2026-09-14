# SPDX-License-Identifier: Apache-2.0
"""Apply reviewed response-ownership edits to a NEW review branch only.

This staging-branch utility is not included in its output commit. It has no
Space, model, secret, deployment, main-branch or PR-merge operation. Tests run
before the sole credential-scoped source-proposal step. No request is retried.
"""
from __future__ import annotations
import argparse
import ast
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

PREP_BRANCH = 'work/html-owner-preparation-20260914-v1'
TARGET_BRANCH = 'fix/html-response-ownership-20260914-v1'
SHARED = ('f235dd5bb0a54c6d653b11a0999205f518bb8617', '_SpacesNavInjector')
CONFIG = {
    'szl-holdings/a11oy': {
        'base': '85105162265e205780973c9355c5518fc639b04a',
        'base_branch': 'fix/model-source-first-closure-20260913',
        'files': {
            'serve.py': ('560e932f9708fb88318e7ab93a76f827cc0eefcf', '_OperatorWidgetInjector'),
            'a11oy_grc.py': ('976a47cd0cd3f89e4f9ee0734c449f67e2b2fc40', '_GrcNavInjector'),
            'szl_spaces_surface.py': SHARED,
            'routers/model_pretraining.py': ('4d24a3e2024df26aacd4b00d828c86eb0a847b14', None),
        },
        'tests': ['test_model_pretraining_response_ownership.py', 'test_spaces_response_ownership.py'],
    },
    'szl-holdings/killinchu': {
        'base': '158ac3995196c4328de9a23f21749bbf78e942d1',
        'base_branch': 'main',
        'files': {'szl_spaces_surface.py': SHARED},
        'tests': ['test_spaces_response_ownership.py'],
    },
}
GUARD = '''# The response owner, not an incoming request, opts out of UI mutation.
from urllib.request import parse_http_list
if any(directive.strip().lower() == "no-transform"
       for field in resp.headers.getlist("cache-control")
       for directive in parse_http_list(field)):
    return resp
'''
LIMIT = 4 * 1024 * 1024


class Stop(ValueError):
    pass


def check(ok, reason):
    if not ok:
        raise Stop(reason)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def blob(raw):
    return hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest()


def git(*args):
    result = subprocess.run(['git', *args], check=False, capture_output=True, timeout=25)
    check(result.returncode == 0, 'local Git read failed')
    return result.stdout


def transform(raw, cls):
    check(type(raw) is bytes and 0 < len(raw) <= LIMIT, 'invalid source size')
    text = raw.decode('utf-8')
    check('\r' not in text, 'source newline identity changed')
    if cls is None:
        anchor = 'PAGE_HEADERS = {**HEADERS, "Content-Security-Policy": ('
        check(text.count(anchor) == 1, 'page header declaration changed')
        text = text.replace(anchor, 'PAGE_HEADERS = {**HEADERS, "Cache-Control": "no-store, no-transform", "Content-Security-Policy": (', 1)
    else:
        tree = ast.parse(text)
        found = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == cls]
        check(len(found) == 1, 'injector identity changed')
        methods = [n for n in found[0].body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'dispatch']
        check(len(methods) == 1, 'dispatch identity changed')
        method = methods[0]
        check('parse_http_list' not in ast.get_source_segment(text, method), 'guard already present')
        first = method.body[0]
        check(isinstance(first, ast.Assign) and len(first.targets) == 1
              and isinstance(first.targets[0], ast.Name) and first.targets[0].id == 'resp'
              and isinstance(first.value, ast.Await) and isinstance(first.value.value, ast.Call)
              and isinstance(first.value.value.func, ast.Name) and first.value.value.func.id == 'call_next'
              and len(first.value.value.args) == 1 and isinstance(first.value.value.args[0], ast.Name)
              and first.value.value.args[0].id == 'request' and not first.value.value.keywords,
              'response acquisition changed')
        lines = text.splitlines(keepends=True)
        addition = ''.join(' ' * first.col_offset + line + '\n' for line in GUARD.splitlines())
        lines.insert(first.end_lineno, addition)
        text = ''.join(lines)
    ast.parse(text, feature_version=(3, 11))
    return text.encode('utf-8')


def identity():
    repo, revision = os.environ.get('GITHUB_REPOSITORY'), os.environ.get('GITHUB_SHA', '')
    check(repo in CONFIG and re.fullmatch('[0-9a-f]{40}', revision), 'unexpected repository/source')
    check(os.environ.get('GITHUB_REF') == 'refs/heads/' + PREP_BRANCH, 'not the fixed staging branch')
    check(git('rev-parse', 'HEAD').decode().strip() == revision, 'checkout moved')
    parent = git('rev-list', '--parents', '-n', '1', 'HEAD').decode().split()
    check(parent == [revision, CONFIG[repo]['base']], 'preparation parent differs')
    return repo, revision, CONFIG[repo]


def candidate(config):
    result = {}
    for path, (expected, cls) in config['files'].items():
        original = git('show', config['base'] + ':' + path)
        check(blob(original) == expected, 'original blob differs: ' + path)
        result[path] = transform(original, cls)
    for name in config['tests']:
        path = 'tests/' + name
        check(git('ls-tree', '-z', config['base'], '--', path) == b'',
              'test destination already exists')
        test = git('show', 'HEAD:.szl-source-prep/' + name)
        check(0 < len(test) <= LIMIT, 'test source size')
        ast.parse(test, feature_version=(3, 11))
        result[path] = test
    return result


def prepare():
    _, _, config = identity()
    check(git('status', '--porcelain', '--untracked-files=all') == b'', 'dirty staging checkout')
    changes = candidate(config)
    for relative, raw in changes.items():
        path = Path(relative)
        check(path.parent.is_dir() and not path.is_symlink(), 'invalid destination')
        path.write_bytes(raw)
    return {'state': 'LOCAL_SOURCE_PREPARED_NOT_PUBLISHED', 'files': {
        path: {'sha256': sha256(raw), 'git_blob': blob(raw)} for path, raw in changes.items()}}


def api(repo, suffix, payload=None, allow_missing=False):
    command = ['gh', 'api', '--hostname', 'github.com', '--include',
               'repos/' + repo + '/' + suffix]
    data = None
    if payload is not None:
        command += ['--method', 'POST', '--input', '-']
        data = json.dumps(payload).encode()
    result = subprocess.run(command, input=data, capture_output=True, check=False, timeout=60)
    text = result.stdout.decode('utf-8')
    match = re.match(r'HTTP/[0-9.]+ (\d{3})[^\r\n]*\r?\n', text)
    check(match is not None, 'GitHub response status unavailable')
    status = int(match.group(1))
    if allow_missing and status == 404:
        return None
    check(result.returncode == 0 and status in (200, 201), 'GitHub request not confirmed')
    parts = re.split(r'\r?\n\r?\n', text, maxsplit=1)
    check(len(parts) == 2, 'GitHub response body unavailable')
    value = json.loads(parts[1])
    check(type(value) is dict, 'GitHub response shape')
    return value


def publish(report, save):
    repo, revision, config = identity()
    changes = candidate(config)
    expected_digest = os.environ.get('EXPECTED_FILE_SET_DIGEST', '')
    file_set = {p: {'sha256': sha256(b), 'git_blob': blob(b)} for p,b in changes.items()}
    actual_digest = sha256(json.dumps(file_set, sort_keys=True, separators=(',', ':')).encode())
    check(re.fullmatch('[0-9a-f]{64}', expected_digest) and actual_digest == expected_digest,
          'source differs from the read-only tested preparation')
    allowed = set(changes)
    changed = set(git('diff', '--name-only').decode().splitlines())
    untracked = set(git('ls-files', '--others', '--exclude-standard').decode().splitlines())
    check(changed | untracked == allowed, 'unexpected or incomplete working-tree diff')
    for path, raw in changes.items():
        check(Path(path).read_bytes() == raw, 'tested source changed: ' + path)
    report.update(repository=repo, preparation_revision=revision, base=config['base'],
                  target_branch=TARGET_BRANCH, model_training=False, provider_publication=False)
    target = 'git/ref/heads/' + TARGET_BRANCH
    check(api(repo, target, allow_missing=True) is None, 'review branch already exists; do not overwrite')
    for name, expected in ((PREP_BRANCH, revision), (config['base_branch'], config['base'])):
        check(api(repo, 'git/ref/heads/' + name)['object']['sha'] == expected, 'source branch moved')
    base = api(repo, 'git/commits/' + config['base'])
    check(base.get('sha') == config['base'], 'base identity differs')
    elements = []
    report['state'] = 'SOURCE_OBJECT_PREPARATION'; save()
    for path, raw in changes.items():
        result = api(repo, 'git/blobs', {'content': base64.b64encode(raw).decode(), 'encoding': 'base64'})
        check(result.get('sha') == blob(raw), 'created blob differs')
        elements.append({'path': path, 'mode': '100644', 'type': 'blob', 'sha': result['sha']})
    tree = api(repo, 'git/trees', {'base_tree': base['tree']['sha'], 'tree': elements})
    check(re.fullmatch('[0-9a-f]{40}', tree.get('sha', '')), 'invalid candidate tree')
    message = ('fix(ui): honor route-owned no-transform HTML\n\n'
               'Apply the reviewed response-ownership repair directly in existing UI middleware. '
               'Preserve normal console injection, source bytes, CSP and shared-module parity. '
               'The staging utility/workflow is NOT part of this commit or its ancestry.\n\n'
               'Source preparation and focused tests do not establish whole-app/public deployment. '
               'Normal native CI/review and all publication holds remain. No model or GPU work.\n\n'
               'Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>')
    commit = api(repo, 'git/commits', {'message': message, 'tree': tree['sha'], 'parents': [config['base']]})
    new = commit.get('sha', '')
    check(re.fullmatch('[0-9a-f]{40}', new), 'invalid candidate commit')
    check(api(repo, 'git/ref/heads/' + config['base_branch'])['object']['sha'] == config['base'], 'base moved before proposal')
    check(api(repo, 'git/ref/heads/' + PREP_BRANCH)['object']['sha'] == revision, 'staging source moved')
    check(api(repo, target, allow_missing=True) is None, 'review branch appeared; do not overwrite')
    report.update(state='REF_CREATE_ATTEMPTED_READBACK_REQUIRED', commit=new, tree=tree['sha'],
                  changed_files={p: {'git_blob': blob(b), 'sha256': sha256(b)} for p,b in changes.items()})
    save()
    # Single create, never update/force/retry. Failure remains uncertain until readback.
    api(repo, 'git/refs', {'ref': 'refs/heads/' + TARGET_BRANCH, 'sha': new})
    readback = api(repo, target)
    check(readback.get('object', {}).get('sha') == new, 'proposal readback differs')
    observed = api(repo, 'git/commits/' + new)
    check(observed.get('tree', {}).get('sha') == tree['sha']
          and [p.get('sha') for p in observed.get('parents', [])] == [config['base']], 'proposal ancestry differs')
    report['state'] = 'SOURCE_REVIEW_BRANCH_CREATED_NOT_MERGED'
    report['base_still_matches'] = api(repo, 'git/ref/heads/' + config['base_branch'])['object']['sha'] == config['base']
    save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare','publish'))
    args = parser.parse_args()
    output = Path(os.environ['RUNNER_TEMP']) / 'html-source-proposal.json'
    report = {'schema':'szl.reviewed-html-source-proposal/v1', 'state':'NOT_ATTEMPTED',
              'run_id': os.environ.get('GITHUB_RUN_ID'), 'run_attempt':os.environ.get('GITHUB_RUN_ATTEMPT'),
              'main_mutated':False, 'provider_publication':False, 'model_training':False}
    def save():
        temporary = output.with_suffix('.tmp')
        temporary.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        temporary.replace(output)
    try:
        if args.phase == 'prepare':
            report.update(prepare()); save()
        else:
            publish(report, save)
    except Exception as exc:
        report.update(error_type=type(exc).__name__, reason=str(exc)[:300]); save()
        print(json.dumps(report, sort_keys=True)); return 1
    print(json.dumps(report, sort_keys=True)); return 0


if __name__ == '__main__':
    raise SystemExit(main())
