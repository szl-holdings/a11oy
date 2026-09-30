# SPDX-License-Identifier: Apache-2.0
"""Exercise source-branch sequencing with controlled GitHub and generator fixtures.

No real Git refs are changed. Separate native CI must verify actual generators.
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


class SequenceTests(unittest.TestCase):
    def run_case(self, **controls):
        self.calls=[]; self.report={}; mains=0
        now=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
        value={'schemaVersion':2,'org':'SZLHOLDINGS','generatedBy':'scripts/audit_huggingface_ecosystem.py',
            'observedAt':now,'inventoryScope':{'visibility':'public-only','authenticated':False,'privateAssetsIncluded':False},
            'inventory':{},'counts':{}}
        for kind in ('model','dataset','space'):
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
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root=Path(directory); (root/'docs').mkdir()
            (root/M.CANONICAL).write_text(json.dumps(old))
            def github(path, *, body=None):
                nonlocal mains
                self.calls.append((path,body))
                if path.endswith('/git/ref/heads/main'):
                    mains+=1
                    return {'object':{'sha':'d'*40 if mains==controls.get('move_at') else SHA}}
                if '/actions/artifacts/' in path: return metadata
                if '/git/matching-refs/' in path: return [{}] if controls.get('exists') else []
                if path.endswith('/git/blobs'):
                    raw=base64.b64decode(body['content']); sha=hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()
                    return {'sha':'d'*40 if controls.get('bad_blob') else sha}
                if path.endswith('/git/trees'): return {'sha':'b'*40}
                if path.endswith('/git/commits'): return {'sha':COMMIT}
                if path.endswith('/git/refs'):
                    if controls.get('uncertain'): raise M.PreparationError('controlled lost response')
                    return {'object':{'sha':COMMIT}}
                if '/git/ref/heads/szl/' in path: return {'object':{'sha':COMMIT}}
                raise AssertionError(path)
            def command(args, **kwargs):
                if args[:2]==['gh','api']: return archive
                if args[:2]==['git','rev-parse']: return SHA.encode()
                if args[:2]==['git','status']: return b' M local.py' if controls.get('dirty') else b''
                if args[:2]==['git','diff']:
                    return ('.github/workflows/hf-sync.yml\0' if controls.get('out_of_scope') else M.CANONICAL+'\0').encode()
                if args[:2]==['git','ls-files']: return b'rogue.py' if controls.get('untracked') else b''
                if args[:2]==['git','show']: return ('b'*40).encode()
                if args[0]==sys.executable:
                    if controls.get('generator_fail'): raise M.PreparationError('controlled generator failure')
                    return b''
                raise AssertionError(args)
            stack.enter_context(patch.object(M,'ROOT',root))
            stack.enter_context(patch.object(M,'github',github))
            stack.enter_context(patch.object(M,'command',command))
            stack.enter_context(patch.dict(sys.modules,{'audit_huggingface_ecosystem':collector}))
            # The source helper prepends an owner path; restore the interpreter
            # search list after this isolated test, including failure paths.
            original=list(sys.path)
            try: M.prepare(SHA,123,456,h,self.report)
            finally: sys.path[:]=original

    def ref_writes(self): return [(p,b) for p,b in self.calls if p.endswith('/git/refs') and b is not None]

    def test_positive_creates_only_new_review_ref(self):
        self.run_case(); writes=self.ref_writes()
        self.assertEqual(len(writes),1)
        self.assertTrue(writes[0][1]['ref'].startswith('refs/heads/szl/hf-inventory-'))
        self.assertNotEqual(writes[0][1]['ref'],'refs/heads/main')
        self.assertEqual(self.report['state'],'REVIEW_BRANCH_CREATED')
        self.assertEqual(set(self.report['changedFiles']),{M.CANONICAL})
        self.assertTrue(self.report['branchCreated'])

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

    def test_out_of_scope_diff_never_creates_objects(self):
        with self.assertRaises(M.PreparationError): self.run_case(out_of_scope=True)
        self.assertFalse(any(body is not None for _,body in self.calls))

    def test_untracked_output_never_creates_objects(self):
        with self.assertRaises(M.PreparationError): self.run_case(untracked=True)
        self.assertFalse(any(body is not None for _,body in self.calls))

    def test_existing_ref_never_overwritten(self):
        with self.assertRaises(M.PreparationError): self.run_case(exists=True)
        self.assertFalse(any(body is not None for _,body in self.calls))

    def test_bad_blob_readback_never_creates_ref(self):
        with self.assertRaises(M.PreparationError): self.run_case(bad_blob=True)
        self.assertEqual(self.ref_writes(),[])

    def test_uncertain_creation_not_retried_or_declared_absent(self):
        with self.assertRaises(M.PreparationError): self.run_case(uncertain=True)
        self.assertEqual(len(self.ref_writes()),1)
        self.assertEqual(self.report['state'],'REF_WRITE_UNCERTAIN')
        self.assertIsNone(self.report['branchCreated'])

    def test_empty_scope_replacement_needs_review(self):
        with self.assertRaises(M.PreparationError): self.run_case(empty=True)
        self.assertFalse(any(body is not None for _,body in self.calls))


if __name__=='__main__': unittest.main()
