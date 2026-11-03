# SPDX-License-Identifier: Apache-2.0
"""Exercise source-branch sequencing with controlled GitHub and generator fixtures.

No real Git refs are changed. Separate native CI must verify actual generators.
That GitHub rejects a PATCH force:false that is not a fast-forward is MODELED from
its documented REST contract here; these fakes do not measure it.
"""
from contextlib import ExitStack
from datetime import datetime, timezone
import base64
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('refresh_sequence',ROOT/'scripts/prepare_hf_inventory_refresh.py')
M=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(M)
SHA='a'*40
COMMIT='c'*40
OLD_SOURCE='9'*40
H1='1'*40
H2='2'*40
ROLLING_REF='refs/heads/szl/hf-inventory-refresh'


def bot_commit(sha, parents, *, author='github-actions[bot]', committer='web-flow', verified=True,
               message=None, files=(M.CANONICAL,)):
    return {'sha':sha,'author':{'login':author} if author else None,'committer':{'login':committer},
            'parents':[{'sha':parent} for parent in parents],
            'commit':{'message':message or M.refresh_message(41,parents[0],'e'*64),
                      'verification':{'verified':verified,'reason':'valid' if verified else 'unsigned'}},
            '_files':[{'filename':name,'status':'modified'} if type(name) is str else name for name in files]}


class SequenceTests(unittest.TestCase):
    def run_case(self, **controls):
        self.calls=[]; self.methods=[]; self.report={}; mains=0
        now=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
        value={'schemaVersion':2,'org':'SZLHOLDINGS','generatedBy':'scripts/audit_huggingface_ecosystem.py',
            'observedAt':now,'inventoryScope':{'visibility':'public-only','authenticated':False,'privateAssetsIncluded':False},
            'inventory':{},'counts':{}}
        for kind in ('model','dataset','space','kernel'):
            value['inventory'][kind+'s']=[{'id':'SZLHOLDINGS/item','repoType':kind,'private':False,'sha':'b'*40}]
            value['counts'][kind+'s']=1
        old=json.loads(json.dumps(value)); old['priorRecord']=True
        if controls.get('empty'):
            value['inventory']['models']=[]; value['counts']['models']=0
        candidate=(json.dumps(value,indent=2)+'\n').encode()
        memory=io.BytesIO()
        with zipfile.ZipFile(memory,'w') as z: z.writestr('huggingface-ecosystem-manifest.candidate.json',candidate)
        archive=memory.getvalue(); h=M.digest(archive)
        metadata={'expired':False,'name':'huggingface-ecosystem-manifest-candidate-123','digest':'sha256:'+h,
            'workflow_run':{'id':123,'head_sha':SHA,'head_branch':'main'},'size_in_bytes':len(archive)}
        collector=SimpleNamespace(validate_observed_at=lambda x:x, validate_generated_revision_evidence=lambda *a,**k:None,
                                  semantic_manifest=lambda x: {} if controls.get('same') else x)
        rolling=controls.get('rolling') or []
        state={'ref':rolling[-1]['sha'] if rolling else None}
        rolling_raw=candidate if controls.get('rolling_equal') else json.dumps(old).encode()
        rolling_blob=hashlib.sha1(f'blob {len(rolling_raw)}\0'.encode()+rolling_raw).hexdigest()
        by_sha={item['sha']:item for item in rolling}
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root=Path(directory); (root/'docs').mkdir()
            (root/M.CANONICAL).write_text(json.dumps(old))
            support_path=root/'docs/model-inference-support.json'
            support_path.write_bytes((ROOT/'docs/model-inference-support.json').read_bytes())
            support_before=support_path.read_bytes()
            def github(path, *, body=None, method=None):
                nonlocal mains
                self.calls.append((path,body)); self.methods.append((method or ('POST' if body is not None else 'GET'),path))
                if path.endswith('/git/ref/heads/main'):
                    mains+=1
                    return {'object':{'sha':'d'*40 if mains==controls.get('move_at') else SHA}}
                if '/actions/artifacts/' in path: return metadata
                if path.endswith('/git/matching-refs/heads/szl/hf-inventory-refresh'):
                    decoy=[{'ref':ROLLING_REF+'-old','object':{'sha':'8'*40,'type':'commit'}}]
                    return decoy+([{'ref':ROLLING_REF,'object':{'sha':state['ref'],'type':'commit'}}] if rolling else [])
                if '/compare/' in path:
                    if controls.get('compare_unavailable'): raise M.PreparationError('gh failed with exit 1')
                    base,head=path.split('/compare/',1)[1].split('?',1)[0].split('...')
                    if path.endswith(f'?per_page={M.MAX_ROLLING_COMMITS}'):
                        self.assertEqual((base,head),(SHA,rolling[-1]['sha']))
                        listed=rolling+controls.get('stray',[])
                        return {'total_commits':controls.get('total',len(listed)),'commits':[
                            {key:value for key,value in item.items() if key!='_files'} for item in listed]}
                    self.assertEqual(base,by_sha[head]['parents'][0]['sha'])
                    return {'files':by_sha[head]['_files']}
                if '/contents/' in path:
                    self.assertTrue(path.endswith(f'/contents/{M.CANONICAL}?ref={rolling[-1]["sha"]}'))
                    return {'type':'file','path':M.CANONICAL,'sha':rolling_blob,'size':len(rolling_raw)}
                if path.endswith('/git/blobs/'+rolling_blob):
                    return {'encoding':'base64','content':base64.encodebytes(rolling_raw).decode()}
                if '/pulls?state=open&head=szl-holdings:szl/hf-inventory-refresh&' in path: return controls.get('pulls',[])
                if '/reviews?' in path: return controls.get('reviews',[])
                if path.endswith('/git/blobs'):
                    raw=base64.b64decode(body['content']); sha=hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()
                    return {'sha':'d'*40 if controls.get('bad_blob') else sha}
                if path.endswith('/git/trees'): return {'sha':'b'*40}
                if path.endswith('/git/commits'): return {'sha':COMMIT}
                if path.endswith('/git/refs'):
                    if controls.get('uncertain'): raise M.PreparationError('controlled lost response')
                    state['ref']=body['sha']; return {'object':{'sha':COMMIT}}
                if path.endswith('/git/refs/heads/szl/hf-inventory-refresh') and method=='PATCH':
                    if controls.get('non_ff'): raise M.PreparationError('gh failed with exit 1')
                    state['ref']=body['sha']; return {'object':{'sha':body['sha']}}
                if path.endswith('/git/ref/heads/szl/hf-inventory-refresh'):
                    if state['ref'] is None: raise M.PreparationError('gh failed with exit 1')
                    return {'object':{'sha':state['ref']}}
                raise AssertionError(path)
            def preflight(observed,report):
                report['preparationStep']='PUBLIC_ESTATE_PREFLIGHT'
                if controls.get('classification_fail'):
                    raise M.PreparationError('public estate classification or policy contract requires source review')
            def model_support_preflight(observed,report):
                report['preparationStep']='INFERENCE_SUPPORT_PREFLIGHT'
                report['modelInferenceSupport']={'state':'VALIDATED'}
            def governed_preflight(old,observed,report):
                report['preparationStep']='GOVERNED_REVISION_PREFLIGHT'
                if controls.get('governed_change'):
                    report['state']='SOURCE_REVIEW_REQUIRED'
                    raise M.PreparationError('governed Hugging Face revision changed; source review required, no routine refresh branch')
                report['governedRevisions']={'state':'VALIDATED'}
            def command(args, **kwargs):
                if args[:2]==['gh','api']: return archive
                if args[:2]==['git','rev-parse']: return SHA.encode()
                if args[:2]==['git','status']: return b' M local.py' if controls.get('dirty') else b''
                if args[:2]==['git','diff']:
                    return ('.github/workflows/hf-sync.yml\0' if controls.get('out_of_scope') else M.CANONICAL+'\0').encode()
                if args[:2]==['git','ls-files']: return b'rogue.py' if controls.get('untracked') else b''
                if args[:2]==['git','show']: return ('b'*40).encode()
                if args[0]==sys.executable:
                    if controls.get('generator_fail') in (True,args[2]):
                        raise M.PreparationError('controlled generator failure')
                    return b''
                raise AssertionError(args)
            stack.enter_context(patch.object(M,'ROOT',root))
            stack.enter_context(patch.object(M,'github',github))
            stack.enter_context(patch.object(M,'command',command))
            stack.enter_context(patch.object(M,'validate_public_estate_candidate',preflight))
            stack.enter_context(patch.object(M,'validate_governed_revision_candidate',governed_preflight))
            if not controls.get('model_support_mismatch'):
                stack.enter_context(patch.object(M,'validate_model_support_candidate',model_support_preflight))
            stack.enter_context(patch.dict(sys.modules,{'audit_huggingface_ecosystem':collector}))
            # The source helper prepends an owner path; restore the interpreter
            # search list after this isolated test, including failure paths.
            original=list(sys.path)
            try: M.prepare(SHA,123,456,h,self.report)
            finally:
                self.manifest_after=(root/M.CANONICAL).read_bytes()
                self.manifest_before=json.dumps(old).encode()
                self.support_after=support_path.read_bytes()
                self.support_before=support_before
                sys.path[:]=original

    def ref_writes(self): return [(p,b) for p,b in self.calls if '/git/refs' in p and b is not None]
    def writes(self): return [(p,b) for p,b in self.calls if b is not None]
    def commit_body(self): return next(b for p,b in self.calls if p.endswith('/git/commits'))

    def test_positive_creates_only_new_review_ref(self):
        self.run_case(); writes=self.ref_writes()
        self.assertEqual(len(writes),1)
        self.assertEqual(writes[0][1]['ref'],ROLLING_REF)
        self.assertNotEqual(writes[0][1]['ref'],'refs/heads/main')
        self.assertEqual(self.commit_body()['parents'],[SHA])
        self.assertIsNotNone(M.REFRESH_MESSAGE.match(self.commit_body()['message']))
        self.assertEqual(self.report['state'],'REVIEW_BRANCH_CREATED')
        self.assertEqual(self.report['refUpdate'],'CREATE')
        self.assertEqual(self.report['refReadback'],COMMIT)
        self.assertEqual(set(self.report['changedFiles']),{M.CANONICAL})
        self.assertTrue(self.report['branchCreated'])
        self.assertNotIn('PATCH',[method for method,_ in self.methods])

    def test_same_semantics_does_not_create_objects(self):
        self.run_case(same=True)
        self.assertEqual(self.report['state'],'NO_SEMANTIC_REFRESH_REQUIRED')
        self.assertFalse(any(body is not None for _,body in self.calls))

    def test_dirty_checkout_stops_before_remote_read(self):
        with self.assertRaises(M.PreparationError): self.run_case(dirty=True)
        self.assertEqual(self.calls,[])

    def test_source_movement_before_preparation(self):
        with self.assertRaises(M.PreparationError): self.run_case(move_at=1)
        self.assertFalse(any(body is not None for _,body in self.calls))

    def test_source_movement_before_ref(self):
        with self.assertRaises(M.PreparationError): self.run_case(move_at=3)
        self.assertEqual(self.ref_writes(),[])

    def test_source_movement_after_ref_is_not_rolled_back(self):
        self.run_case(move_at=4)
        self.assertEqual(self.report['state'],'BASE_MOVED_REVIEW_REQUIRED')
        self.assertTrue(self.report['branchCreated']); self.assertEqual(len(self.ref_writes()),1)

    def test_generator_failure_never_creates_ref(self):
        with self.assertRaises(M.PreparationError): self.run_case(generator_fail=True)
        self.assertFalse(any(body is not None for _,body in self.calls))

    def test_classification_failure_keeps_snapshot_unchanged_and_creates_no_objects(self):
        with self.assertRaises(M.PreparationError): self.run_case(classification_fail=True)
        self.assertEqual(self.manifest_after,self.manifest_before)
        self.assertEqual(self.report['preparationStep'],'PUBLIC_ESTATE_PREFLIGHT')
        self.assertFalse(any(body is not None for _,body in self.calls))

    def test_failed_generator_is_identified_without_exposing_its_output(self):
        with self.assertRaises(M.PreparationError):
            self.run_case(generator_fail='scripts/render_public_estate_alignment.py')
        self.assertEqual(self.report['preparationStep'],'GENERATE_PROJECTIONS')
        self.assertEqual(self.report['generator'],'scripts/render_public_estate_alignment.py')
        self.assertEqual(self.report['generatorMode'],'WRITE')
        self.assertFalse(any(body is not None for _,body in self.calls))

    def test_model_support_mismatch_keeps_original_files_and_creates_no_objects(self):
        with self.assertRaisesRegex(M.PreparationError,'model inference support source or inventory coverage requires source review'):
            self.run_case(model_support_mismatch=True)
        self.assertEqual(self.manifest_after,self.manifest_before)
        self.assertEqual(self.support_after,self.support_before)
        self.assertEqual(self.report['preparationStep'],'INFERENCE_SUPPORT_PREFLIGHT')
        self.assertEqual(self.report['modelInferenceSupport'],{'state':'SOURCE_REVIEW_REQUIRED'})
        self.assertFalse(any(body is not None for _,body in self.calls))

    def test_out_of_scope_diff_never_creates_objects(self):
        with self.assertRaises(M.PreparationError): self.run_case(out_of_scope=True)
        self.assertFalse(any(body is not None for _,body in self.calls))

    def test_untracked_output_never_creates_objects(self):
        with self.assertRaises(M.PreparationError): self.run_case(untracked=True)
        self.assertFalse(any(body is not None for _,body in self.calls))

    # Replaces the former "an existing ref is never overwritten" invariant, which
    # allowed no update at all. An existing ref may now only be fast-forwarded from
    # a head whose every commit is a verified controller commit; any other commit
    # stops the run with no write.
    def test_existing_ref_is_only_fast_forwarded_from_previous_head(self):
        self.run_case(rolling=[bot_commit(H1,[OLD_SOURCE])])
        self.assertEqual(self.commit_body()['parents'],[SHA,H1])
        patches=[(p,b) for (method,p),(_,b) in zip(self.methods,self.calls) if method=='PATCH']
        self.assertEqual(patches,[(f'repos/{M.REPOSITORY}/git/refs/heads/szl/hf-inventory-refresh',{'sha':COMMIT,'force':False})])
        self.assertEqual(self.ref_writes(),patches)
        self.assertFalse(any(p.endswith('/git/refs') for p,_ in self.writes()))
        self.assertEqual(self.report['state'],'REVIEW_BRANCH_ADVANCED')
        self.assertEqual(self.report['refUpdate'],'FAST_FORWARD')
        self.assertEqual((self.report['previousHead'],self.report['refReadback']),(H1,COMMIT))
        self.assertTrue(self.report['branchAdvanced'])
        self.assertNotIn('branchCreated',self.report)

    def test_existing_bot_chain_advances_from_its_newest_head(self):
        self.run_case(rolling=[bot_commit(H1,[OLD_SOURCE]),bot_commit(H2,['8'*40,H1])])
        self.assertEqual(self.commit_body()['parents'],[SHA,H2])
        self.assertEqual(self.report['state'],'REVIEW_BRANCH_ADVANCED')

    def test_existing_ref_with_foreign_commit_is_never_written(self):
        update=bot_commit('f'*40,[H1,OLD_SOURCE],author='stephenlutar2-hash',message='Merge branch main into szl/hf-inventory-refresh')
        identity='not a GitHub-verified refresh bot commit'; template='differs from the refresh template'
        cases={
            'human update-branch merge':([bot_commit(H1,[OLD_SOURCE]),update],identity),
            'git CLI identity copy':([bot_commit(H1,[OLD_SOURCE],committer='github-actions[bot]',verified=False)],identity),
            'verified commit not committed by web-flow':([bot_commit(H1,[OLD_SOURCE],committer='github-actions[bot]')],identity),
            'web-flow commit by a person':([bot_commit(H1,[OLD_SOURCE],author='stephenlutar2-hash')],identity),
            'author without GitHub account':([bot_commit(H1,[OLD_SOURCE],author=None)],identity),
            'message outside refresh template':([bot_commit(H1,[OLD_SOURCE],message='chore(hf): adjust manifest by hand\n')],template),
            'collector source is not first parent':([bot_commit(H1,[OLD_SOURCE],message=M.refresh_message(41,SHA,'e'*64))],template),
            'second parent is not previous head':([bot_commit(H1,[OLD_SOURCE]),bot_commit(H2,[SHA,'7'*40])],'second parent'),
            'first parent is not on main':([bot_commit(H1,[OLD_SOURCE]),bot_commit(H2,[H1,H1])],template),
            'three parents':([bot_commit(H1,[OLD_SOURCE]),bot_commit(H2,[SHA,H1,OLD_SOURCE])],template),
        }
        for name,(rolling,reason) in cases.items():
            with self.subTest(name=name):
                with self.assertRaisesRegex(M.ForeignCommitError,reason): self.run_case(rolling=rolling)
                self.assertEqual(self.report['state'],'ROLLING_BRANCH_HAS_FOREIGN_COMMITS')
                self.assertEqual(self.writes(),[])
                self.assertNotIn('PATCH',[method for method,_ in self.methods])
                self.assertEqual(self.manifest_after,self.manifest_before)

    def test_commit_outside_the_refresh_chain_stops(self):
        stray=bot_commit('5'*40,[OLD_SOURCE])
        with self.assertRaises(M.ForeignCommitError): self.run_case(rolling=[bot_commit(H1,[OLD_SOURCE])],stray=[stray])
        self.assertEqual(self.report['state'],'ROLLING_BRANCH_HAS_FOREIGN_COMMITS')
        self.assertEqual(self.writes(),[])

    def test_bot_commit_leaving_allowed_files_stops(self):
        for files in (('docs/series-a/hf-space-keep-list.yaml',),(M.CANONICAL,'.github/workflows/hf-sync.yml'),
                      ({'filename':M.CANONICAL,'status':'removed'},),
                      ({'filename':M.CANONICAL,'status':'renamed','previous_filename':'routers/app.py'},),()):
            with self.subTest(files=files):
                with self.assertRaises(M.ForeignCommitError): self.run_case(rolling=[bot_commit(H1,[OLD_SOURCE],files=files)])
                self.assertEqual(self.report['state'],'ROLLING_BRANCH_HAS_FOREIGN_COMMITS')
                self.assertEqual(self.writes(),[])

    def test_unverified_bot_commit_stops(self):
        with self.assertRaises(M.ForeignCommitError): self.run_case(rolling=[bot_commit(H1,[OLD_SOURCE],verified=False)])
        self.assertEqual(self.report['state'],'ROLLING_BRANCH_HAS_FOREIGN_COMMITS')
        self.assertEqual(self.writes(),[])

    def test_unverifiable_history_or_outage_stops_without_a_foreign_label(self):
        for controls in ({'total':M.MAX_ROLLING_COMMITS+1},{'compare_unavailable':True}):
            with self.subTest(controls=controls):
                with self.assertRaises(M.PreparationError) as raised: self.run_case(rolling=[bot_commit(H1,[OLD_SOURCE])],**controls)
                self.assertNotIsInstance(raised.exception,M.ForeignCommitError)
                self.assertNotIn('state',self.report)
                self.assertEqual(self.writes(),[])

    def test_non_fast_forward_rejection_is_not_retried(self):
        with self.assertRaises(M.PreparationError): self.run_case(rolling=[bot_commit(H1,[OLD_SOURCE])],non_ff=True)
        self.assertEqual([method for method,_ in self.methods].count('PATCH'),1)
        self.assertEqual(len(self.ref_writes()),1)
        self.assertEqual(self.report['state'],'REF_WRITE_UNCERTAIN')
        self.assertIsNone(self.report['branchAdvanced'])
        self.assertEqual(self.methods[-1],('GET',f'repos/{M.REPOSITORY}/git/ref/heads/szl/hf-inventory-refresh'))
        self.assertEqual(self.report['refReadback'],H1)

    def test_candidate_equal_to_rolling_head_writes_nothing(self):
        self.run_case(rolling=[bot_commit(H1,[OLD_SOURCE])],rolling_equal=True)
        self.assertEqual(self.report['state'],'NO_ROLLING_REFRESH_REQUIRED')
        self.assertEqual(self.writes(),[])
        self.assertEqual(self.manifest_after,self.manifest_before)

    def test_rolling_head_under_review_is_never_moved(self):
        pull={'number':7,'auto_merge':None,'head':{'ref':'szl/hf-inventory-refresh','repo':{'full_name':M.REPOSITORY}}}
        for state,controls in (('ROLLING_PR_AUTO_MERGE_ENABLED',{'pulls':[{**pull,'auto_merge':{'merge_method':'squash'}}]}),
                               ('ROLLING_PR_APPROVED',{'pulls':[pull],'reviews':[{'state':'COMMENTED'},{'state':'APPROVED'}]})):
            with self.subTest(state=state):
                with self.assertRaises(M.PreparationError): self.run_case(rolling=[bot_commit(H1,[OLD_SOURCE])],**controls)
                self.assertEqual((self.report['state'],self.report['pullRequests']),(state,[7]))
                self.assertEqual(self.writes(),[])

    def test_open_unapproved_rolling_pr_is_advanced(self):
        pull={'number':7,'auto_merge':None,'head':{'ref':'szl/hf-inventory-refresh','repo':{'full_name':M.REPOSITORY}}}
        self.run_case(rolling=[bot_commit(H1,[OLD_SOURCE])],pulls=[pull],reviews=[{'state':'COMMENTED'}])
        self.assertEqual((self.report['state'],self.report['pullRequests']),('REVIEW_BRANCH_ADVANCED',[7]))

    def test_unapplied_pull_request_filter_is_not_read_as_absence(self):
        other={'number':8,'auto_merge':None,'head':{'ref':'feature','repo':{'full_name':M.REPOSITORY}}}
        with self.assertRaisesRegex(M.PreparationError,'head filter'): self.run_case(rolling=[bot_commit(H1,[OLD_SOURCE])],pulls=[other])
        self.assertEqual(self.writes(),[])

    def test_bad_blob_readback_never_creates_ref(self):
        with self.assertRaises(M.PreparationError): self.run_case(bad_blob=True)
        self.assertEqual(self.ref_writes(),[])

    def test_uncertain_creation_not_retried_or_declared_absent(self):
        with self.assertRaises(M.PreparationError): self.run_case(uncertain=True)
        self.assertEqual(len(self.ref_writes()),1)
        self.assertEqual(self.report['state'],'REF_WRITE_UNCERTAIN')
        self.assertIsNone(self.report['branchCreated'])
        self.assertEqual(self.report['refReadback'],'UNAVAILABLE')

    def test_governed_revision_change_stops_before_any_object_or_file_write(self):
        for same in (False,True):
            with self.subTest(same_semantics=same):
                with self.assertRaisesRegex(M.PreparationError,'source review required'):
                    self.run_case(governed_change=True,same=same)
                self.assertEqual(self.report['state'],'SOURCE_REVIEW_REQUIRED')
                self.assertEqual(self.report['preparationStep'],'GOVERNED_REVISION_PREFLIGHT')
                self.assertEqual(self.manifest_after,self.manifest_before)
                self.assertFalse(any(body is not None for _,body in self.calls))
                self.assertEqual(self.ref_writes(),[])

    def test_empty_scope_replacement_needs_review(self):
        with self.assertRaises(M.PreparationError): self.run_case(empty=True)
        self.assertFalse(any(body is not None for _,body in self.calls))


if __name__=='__main__': unittest.main()
