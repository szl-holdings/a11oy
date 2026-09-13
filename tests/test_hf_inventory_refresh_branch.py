# SPDX-License-Identifier: Apache-2.0
"""Offline artifact/scope validation; no GitHub or Hugging Face mutations."""
from datetime import datetime, timezone
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('inventory_refresh',ROOT/'scripts/prepare_hf_inventory_refresh.py')
M=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(M)
SHA='a'*40
NOW=datetime(2026,9,13,13,tzinfo=timezone.utc)


def fixture():
    value={'schemaVersion':2,'org':'SZLHOLDINGS','generatedBy':'scripts/audit_huggingface_ecosystem.py',
           'observedAt':'2026-09-13T12:00:00Z','inventoryScope':{'visibility':'public-only','authenticated':False,'privateAssetsIncluded':False},
           'inventory':{},'counts':{}}
    for kind in ('model','dataset','space'):
        value['inventory'][kind+'s']=[{'id':'SZLHOLDINGS/item','repoType':kind,'private':False,'sha':'b'*40}]
        value['counts'][kind+'s']=1
    return value


def raw(value): return (json.dumps(value,indent=2)+'\n').encode()


def artifact(name='huggingface-ecosystem-manifest.candidate.json'):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z: z.writestr(name,raw(fixture()))
    data=stream.getvalue()
    meta={'expired':False,'name':'huggingface-ecosystem-manifest-candidate-123','digest':'sha256:'+M.digest(data),
          'workflow_run':{'id':123,'head_sha':SHA,'head_branch':'main'},'size_in_bytes':len(data)}
    return meta,data


class CandidateTests(unittest.TestCase):
    def test_valid_all_three_scopes(self): self.assertEqual(M.validate_candidate(raw(fixture()),now=NOW)['counts']['models'],1)
    def test_missing_scope(self):
        v=fixture(); del v['inventory']['spaces']
        with self.assertRaises(M.PreparationError): M.validate_candidate(raw(v),now=NOW)
    def test_private_inventory(self):
        v=fixture(); v['inventoryScope']['privateAssetsIncluded']=True
        with self.assertRaises(M.PreparationError): M.validate_candidate(raw(v),now=NOW)
    def test_scope_boolean_not_numeric(self):
        v=fixture(); v['inventoryScope']['authenticated']=0
        with self.assertRaises(M.PreparationError): M.validate_candidate(raw(v),now=NOW)
    def test_duplicate_id(self):
        v=fixture(); v['inventory']['models']*=2; v['counts']['models']=2
        with self.assertRaises(M.PreparationError): M.validate_candidate(raw(v),now=NOW)
    def test_foreign_id(self):
        v=fixture(); v['inventory']['models'][0]['id']='other/item'
        with self.assertRaises(M.PreparationError): M.validate_candidate(raw(v),now=NOW)
    def test_wrong_type(self):
        v=fixture(); v['inventory']['models'][0]['repoType']='kernel'
        with self.assertRaises(M.PreparationError): M.validate_candidate(raw(v),now=NOW)
    def test_private_row(self):
        v=fixture(); v['inventory']['models'][0]['private']=True
        with self.assertRaises(M.PreparationError): M.validate_candidate(raw(v),now=NOW)
    def test_missing_revision(self):
        v=fixture(); v['inventory']['models'][0]['sha']='main'
        with self.assertRaises(M.PreparationError): M.validate_candidate(raw(v),now=NOW)
    def test_count_mismatch(self):
        v=fixture(); v['counts']['models']=5
        with self.assertRaises(M.PreparationError): M.validate_candidate(raw(v),now=NOW)
    def test_boolean_count(self):
        v=fixture(); v['counts']['models']=True
        with self.assertRaises(M.PreparationError): M.validate_candidate(raw(v),now=NOW)
    def test_future_time(self):
        v=fixture(); v['observedAt']='2026-09-14T12:00:00Z'
        with self.assertRaises(M.PreparationError): M.validate_candidate(raw(v),now=NOW)
    def test_old_candidate(self):
        v=fixture(); v['observedAt']='2026-09-10T12:00:00Z'
        with self.assertRaises(M.PreparationError): M.validate_candidate(raw(v),now=NOW)
    def test_naive_time(self):
        v=fixture(); v['observedAt']='2026-09-13T12:00:00'
        with self.assertRaises(M.PreparationError): M.validate_candidate(raw(v),now=NOW)
    def test_rendering_not_silently_changed(self):
        with self.assertRaises(M.PreparationError): M.validate_candidate(json.dumps(fixture()).encode(),now=NOW)
    def test_strict_json(self):
        for value in (b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":1e999}',b'\xff',b''):
            with self.subTest(value=value),self.assertRaises(M.PreparationError): M.strict(value)


class ArtifactTests(unittest.TestCase):
    def test_exact_archive(self):
        m,b=artifact(); self.assertEqual(M.validate_artifact(m,b,source=SHA,run_id=123,expected_digest=M.digest(b)),raw(fixture()))
    def test_wrong_digest(self):
        m,b=artifact()
        with self.assertRaises(M.PreparationError): M.validate_artifact(m,b,source=SHA,run_id=123,expected_digest='b'*64)
    def test_expired(self):
        m,b=artifact(); m['expired']=True
        with self.assertRaises(M.PreparationError): M.validate_artifact(m,b,source=SHA,run_id=123,expected_digest=M.digest(b))
    def test_wrong_source(self):
        m,b=artifact(); m['workflow_run']['head_sha']='b'*40
        with self.assertRaises(M.PreparationError): M.validate_artifact(m,b,source=SHA,run_id=123,expected_digest=M.digest(b))
    def test_pr_artifact(self):
        m,b=artifact(); m['workflow_run']['head_branch']='feature'
        with self.assertRaises(M.PreparationError): M.validate_artifact(m,b,source=SHA,run_id=123,expected_digest=M.digest(b))
    def test_wrong_run(self):
        m,b=artifact()
        with self.assertRaises(M.PreparationError): M.validate_artifact(m,b,source=SHA,run_id=124,expected_digest=M.digest(b))
    def test_wrong_size(self):
        m,b=artifact(); m['size_in_bytes']+=1
        with self.assertRaises(M.PreparationError): M.validate_artifact(m,b,source=SHA,run_id=123,expected_digest=M.digest(b))
    def test_zip_traversal_member(self):
        m,b=artifact('../../source.py')
        with self.assertRaises(M.PreparationError): M.validate_artifact(m,b,source=SHA,run_id=123,expected_digest=M.digest(b))
    def test_deterministic_branch_not_main(self):
        self.assertEqual(M.branch_name(SHA,'b'*64),'szl/hf-inventory-aaaaaaaaaaaa-bbbbbbbbbbbb')
    def test_malformed_branch_inputs(self):
        for value in ('main','../refs','A'*40,''):
            with self.subTest(value=value),self.assertRaises(M.PreparationError): M.branch_name(value,'b'*64)
    def test_paths_exclude_policy_and_runtime_code(self):
        self.assertEqual(len(M.ALLOWED),6)
        self.assertNotIn('.github/workflows/hf-sync.yml',M.ALLOWED)
        self.assertNotIn('docs/series-a/hf-space-keep-list.yaml',M.ALLOWED)


if __name__=='__main__': unittest.main()
