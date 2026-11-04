#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Superseded review-ref pruning with controlled GitHub fakes; no real ref is changed."""
from contextlib import ExitStack
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('inventory_prune',ROOT/'scripts/prune_hf_inventory_branches.py')
P=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(P)
R=P.refresh
MAIN='a'*40
OLD='9'*40
WORKFLOWS=ROOT/'.github/workflows'
PRUNE_WORKFLOW=WORKFLOWS/'hf-inventory-branch-prune.yml'
DRIFT_WORKFLOW=WORKFLOWS/'hf-ecosystem-drift.yml'


def ref(name): return 'refs/heads/szl/hf-inventory-'+name


def commit(sha, parents, *, author='github-actions[bot]', verified=True, message=None):
    return {'sha':sha,'author':{'login':author},'committer':{'login':'web-flow'},
            'parents':[{'sha':parent} for parent in parents],
            'commit':{'message':message or R.refresh_message(41,parents[0],'e'*64),'verification':{'verified':verified}}}


def manifest(observed): return (json.dumps({'schemaVersion':2,'observedAt':observed},indent=2)+'\n').encode()


ROLLING=R.ROLLING
SUPERSEDED=ref('111111111111-111111111111')
WITH_PR=ref('222222222222-222222222222')
HUMAN=ref('333333333333-333333333333')
NEWER=ref('444444444444-444444444444')
UNVERIFIED=ref('555555555555-555555555555')
OTHER_NAME=ref('notes')


class PruneTests(unittest.TestCase):
    def setUp(self):
        self.refs={'refs/heads/'+ROLLING:'1'*40,SUPERSEDED:'b'*40,WITH_PR:'c'*40,HUMAN:'d'*40,
                   NEWER:'e'*40,UNVERIFIED:'f'*40,OTHER_NAME:'6'*40}
        self.history={
            '1'*40:[commit('1'*40,[OLD])],
            'b'*40:[commit('b'*40,[OLD])],
            'c'*40:[commit('c'*40,[OLD])],
            'd'*40:[commit('7'*40,[OLD]),commit('d'*40,['7'*40,OLD],author='stephenlutar2-hash',
                                             message='Merge main into public inventory reconciliation')],
            'e'*40:[commit('e'*40,[OLD])],
            'f'*40:[commit('f'*40,[OLD],verified=False)],
        }
        self.files={sha:[{'filename':R.CANONICAL,'status':'modified'}] for sha in ('1'*40,'b'*40,'c'*40,'7'*40,'d'*40,'e'*40,'f'*40)}
        self.manifests={MAIN:manifest('2026-11-03T18:19:43Z'),'b'*40:manifest('2026-11-02T04:22:44Z'),
                        'e'*40:manifest('2026-11-03T19:00:00Z'),'1'*40:manifest('2026-11-01T00:00:00Z')}
        self.pulls={'szl/hf-inventory-222222222222-222222222222':[
            {'number':9,'auto_merge':None,'head':{'ref':'szl/hf-inventory-222222222222-222222222222',
                                                   'repo':{'full_name':R.REPOSITORY}}}]}
        self.calls=[]; self.move_on_lookup=None; self.delete_fails=False; self.main_unreadable=False

    def github(self, path, *, body=None, method=None):
        method=method or ('POST' if body is not None else 'GET'); self.calls.append((method,path))
        self.assertTrue(path.startswith(f'repos/{R.REPOSITORY}/'))
        tail=path[len(f'repos/{R.REPOSITORY}/'):]
        if tail=='git/ref/heads/main': return {'object':{'sha':MAIN}}
        if tail=='git/matching-refs/heads/szl/hf-inventory-':
            return [{'ref':name,'object':{'sha':sha,'type':'commit'}} for name,sha in self.refs.items()]
        if tail.startswith('git/matching-refs/heads/'):
            name='refs/heads/'+tail[len('git/matching-refs/heads/'):]
            if name==self.move_on_lookup: return [{'ref':name,'object':{'sha':'0'*40,'type':'commit'}}]
            return [{'ref':key,'object':{'sha':sha,'type':'commit'}} for key,sha in self.refs.items() if key.startswith(name)]
        if tail.startswith('pulls?state=open&head=szl-holdings:'):
            return self.pulls.get(tail.split('head=szl-holdings:',1)[1].split('&',1)[0],[])
        if tail.startswith('compare/'):
            base,head=tail[len('compare/'):].split('?',1)[0].split('...')
            if tail.endswith(f'?per_page={R.MAX_ROLLING_COMMITS}'):
                self.assertEqual(base,MAIN)
                items=self.history[head]; return {'total_commits':len(items),'commits':items}
            return {'files':self.files[head]}
        if tail.startswith('contents/'):
            revision=tail.split('?ref=',1)[1]
            if self.main_unreadable and revision==MAIN: raise R.PreparationError('gh failed with exit 1')
            raw=self.manifests[revision]
            return {'type':'file','path':R.CANONICAL,'size':len(raw),
                    'sha':hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()}
        if tail.startswith('git/blobs/'):
            raw=next(raw for raw in self.manifests.values()
                     if hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()==tail[len('git/blobs/'):])
            return {'encoding':'base64','content':base64.encodebytes(raw).decode()}
        if method=='DELETE' and tail.startswith('git/refs/heads/szl/'):
            if self.delete_fails: raise R.PreparationError('gh failed with exit 1')
            del self.refs['refs/heads/'+tail[len('git/refs/heads/'):]]; return None
        raise AssertionError((method,path))

    def run_prune(self, *flags):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            out=Path(directory)/'receipt'
            stack.enter_context(patch.object(R,'github',self.github))
            stack.enter_context(patch.object(P.dsse,'_load_private_key',lambda:None))
            stack.enter_context(patch.object(sys,'argv',['prune',*flags,'--output',str(out)]))
            stack.enter_context(patch('builtins.print'))
            self.code=P.main()
            self.receipt=json.loads((out/'receipt.json').read_text())
            self.envelope=json.loads((out/'receipt.dsse.json').read_text())
            self.archived={path.relative_to(out).as_posix():path.read_bytes() for path in (out/'manifests').glob('*')} \
                if (out/'manifests').is_dir() else {}
        self.by_ref={entry['ref']:entry for entry in self.receipt['entries']}

    def deletes(self): return [path for method,path in self.calls if method=='DELETE']

    def test_dry_run_records_every_ref_and_deletes_nothing(self):
        self.run_prune()
        self.assertEqual(self.code,0)
        self.assertEqual((self.receipt['state'],self.receipt['mode']),('DRY_RUN_COMPLETE','DRY_RUN'))
        self.assertEqual(self.deletes(),[])
        self.assertEqual(set(self.by_ref),set(self.refs))
        for name,sha in self.refs.items(): self.assertEqual(self.by_ref[name]['sha'],sha)
        self.assertEqual({name:(entry['decision'],entry['reason']) for name,entry in self.by_ref.items()},{
            'refs/heads/'+ROLLING:('KEEP','ROLLING_REF'),
            SUPERSEDED:('PRUNE','SUPERSEDED_BOT_REFRESH'),
            WITH_PR:('KEEP','OPEN_PULL_REQUEST_HEAD'),
            HUMAN:('KEEP','NOT_PROVABLY_BOT_ONLY'),
            NEWER:('KEEP','NOT_SUPERSEDED_BY_MAIN'),
            UNVERIFIED:('KEEP','NOT_PROVABLY_BOT_ONLY'),
            OTHER_NAME:('KEEP','NAME_OUTSIDE_LEGACY_PATTERN')})
        self.assertEqual(self.by_ref[SUPERSEDED]['outcome'],'NOT_DELETED_DRY_RUN')
        self.assertEqual(self.by_ref[WITH_PR]['pullRequests'],[9])

    def test_apply_deletes_only_superseded_bot_refs_once_and_reads_back(self):
        self.run_prune('--apply')
        self.assertEqual(self.receipt['state'],'APPLY_COMPLETE')
        self.assertEqual(self.deletes(),[f'repos/{R.REPOSITORY}/git/refs/heads/szl/hf-inventory-111111111111-111111111111'])
        self.assertEqual((self.by_ref[SUPERSEDED]['outcome'],self.by_ref[SUPERSEDED]['readback']),('PRUNED','ABSENT'))
        self.assertIn('refs/heads/'+ROLLING,self.refs)
        for name in (WITH_PR,HUMAN,NEWER,UNVERIFIED,OTHER_NAME,'refs/heads/'+ROLLING):
            self.assertEqual(self.by_ref[name]['outcome'],'KEPT')

    def test_rolling_ref_is_never_examined_or_deleted_even_if_bot_only_and_older(self):
        self.run_prune('--apply')
        rolling='refs/heads/'+ROLLING
        self.assertEqual(self.by_ref[rolling]['reason'],'ROLLING_REF')
        self.assertFalse(any(ROLLING in path and method=='DELETE' for method,path in self.calls))
        self.assertFalse(any(path.endswith('...'+'1'*40+'?per_page=100') for _,path in self.calls))
        self.assertIsNone(P.LEGACY.fullmatch(rolling))
        self.assertIsNone(P.LEGACY.fullmatch('refs/heads/main'))
        self.assertIsNotNone(P.LEGACY.fullmatch(SUPERSEDED))

    def test_ref_moved_after_decision_is_kept(self):
        self.move_on_lookup=SUPERSEDED
        self.run_prune('--apply')
        self.assertEqual(self.deletes(),[])
        self.assertEqual(self.by_ref[SUPERSEDED]['outcome'],'KEPT_REF_MOVED')

    def test_failed_delete_is_not_retried_and_stays_uncertain(self):
        self.delete_fails=True
        self.run_prune('--apply')
        self.assertEqual(len(self.deletes()),1)
        self.assertEqual(self.by_ref[SUPERSEDED]['outcome'],'DELETE_UNCERTAIN')
        self.assertEqual(self.by_ref[SUPERSEDED]['readback'],'b'*40)

    def test_unreadable_main_observation_stops_before_any_decision(self):
        self.main_unreadable=True
        self.run_prune('--apply')
        self.assertEqual((self.code,self.receipt['state']),(1,'STOPPED'))
        self.assertEqual((self.receipt['entries'],self.deletes()),([],[]))

    def test_receipt_is_hash_chained_archived_and_honestly_unsigned(self):
        self.run_prune('--apply')
        previous='0'*64
        for entry in self.receipt['entries']:
            body={key:value for key,value in entry.items() if key!='entrySha256'}
            self.assertEqual(body['previousEntrySha256'],previous)
            previous=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            self.assertEqual(entry['entrySha256'],previous)
        self.assertEqual(self.receipt['headEntrySha256'],previous)
        self.assertEqual((self.envelope['signed'],self.envelope['signatures']),(False,[]))
        self.assertIn('UNSIGNED',self.envelope['honesty'])
        self.assertEqual(self.envelope['payloadType'],P.PAYLOAD_TYPE)
        self.assertEqual(json.loads(base64.b64decode(self.envelope['payload'])),self.receipt)
        entry=self.by_ref[SUPERSEDED]
        self.assertEqual(self.archived,{entry['archivedManifest']:self.manifests['b'*40]})
        self.assertEqual(entry['manifestSha256'],hashlib.sha256(self.manifests['b'*40]).hexdigest())
        self.assertEqual(entry['observedAt'],'2026-11-02T04:22:44Z')


def trigger_keys(text):
    block=re.search(r'(?ms)^on:\n(.*?)(?=^\S)',text)
    return set(re.findall(r'(?m)^  ([A-Za-z_][\w-]*):',block.group(1)))


class PruneWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.prune=PRUNE_WORKFLOW.read_text(encoding='utf-8')
        self.drift=DRIFT_WORKFLOW.read_text(encoding='utf-8')

    def test_prune_runs_only_on_manual_dispatch_and_defaults_to_dry_run(self):
        self.assertEqual(trigger_keys(self.prune),{'workflow_dispatch'})
        for trigger in ('push:','schedule:','pull_request','workflow_run','merge_group','repository_dispatch'):
            self.assertNotIn(trigger,self.prune)
        job=self.prune.split('\njobs:\n',1)[1]
        self.assertIn("if: >-\n      github.event_name == 'workflow_dispatch' &&\n      github.ref == 'refs/heads/main'",job)
        self.assertRegex(self.prune,r"apply:\n\s+description: [^\n]+\n\s+type: boolean\n\s+default: false\n")
        self.assertIn("if [ \"${APPLY}\" = 'true' ]; then set -- --apply; fi",self.prune)
        self.assertIn('if-no-files-found: error',self.prune)
        self.assertNotIn('secrets.',self.prune)

    def test_only_the_dispatch_workflow_can_reach_the_prune_script(self):
        self.assertEqual(self.prune.count('python -B scripts/prune_hf_inventory_branches.py'),1)
        for path in sorted(WORKFLOWS.glob('*.y*ml')):
            if path==PRUNE_WORKFLOW: continue
            with self.subTest(workflow=path.name):
                # Other workflows may name the script only as a test-trigger path filter.
                lines=[line for line in path.read_text(encoding='utf-8').splitlines() if 'prune_hf_inventory' in line]
                for line in lines: self.assertRegex(line,r"\A {6}- 'scripts/prune_hf_inventory_branches\.py'\Z")
        self.assertNotIn('prune',self.drift.lower())

    def test_drift_upload_survives_issue_sync_failure_and_gate_is_unchanged(self):
        upload=self.drift.split('      - name: Upload candidate evidence\n',1)[1].split('      - name:',1)[0]
        self.assertIn("if: always() && steps.check.outputs.state != 'CURRENT'\n",upload)
        enforce=self.drift.split('      - name: Enforce current public manifest\n',1)[1].split('\n\n',1)[0]
        self.assertEqual(enforce,'        if: always()\n        env:\n          STATE: ${{ steps.check.outputs.state }}\n'
                                 '        run: test "${STATE}" = "CURRENT"')
        prepare=self.drift.split('\n  prepare-source-review:\n',1)[1]
        self.assertIn('    permissions:\n      contents: write\n      actions: read\n      pull-requests: read\n    steps:',prepare)
        self.assertNotIn('pull-requests: write',self.drift)


if __name__=='__main__': unittest.main()
