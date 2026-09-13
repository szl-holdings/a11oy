# SPDX-License-Identifier: Apache-2.0
"""Offline positives and failure controls for the selected delivery observer."""
import copy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('model_live', ROOT/'scripts/verify_model_pretraining_live.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
SHA = 'a'*40
STAMP = '2026-09-13T12:00:00Z'
NOW = datetime(2026,9,13,13,tzinfo=timezone.utc)


def raw(value):
    return json.dumps(value, separators=(',', ':')).encode()


def fixture():
    record = {'id':'SZLHOLDINGS/test', 'repoType':'model', 'private':False, 'sha':'b'*40,
              'gated':False,'disabled':False}
    manifest = raw({'schemaVersion':2,'org':'SZLHOLDINGS','observedAt':STAMP,
                    'inventory':{'models':[record]},'counts':{'models':1}})
    projection = raw({'schema':'szl.model-pretraining-input/v1','sourceManifestSha256':M.sha256(manifest)})
    row = {'id':record['id'],'hubRevision':record['sha'],'hubUrl':f"https://huggingface.co/{record['id']}/tree/{record['sha']}",
           'hubRevisionState':'RECORDED_SNAPSHOT_NOT_LIVE','categoryHint':'ADAPTER_HINT',
           'sourceState':'DECLARED_POINTER_ONLY','sourceUrl':'https://github.com/szl-holdings/szl-forge',
           'gated':False,'disabled':False}
    row.update(dict.fromkeys(('weightsVerified','sourceBytesVerified','evaluationVerified','publicationVerified',
                             'runtimeVerified','trainingAllowed','categoryIsVerified'),False))
    data = {'schema':'szl.model-pretraining-view/v1','available':True,'state':'PRETRAINING_REVIEW_NOT_ALIGNMENT',
            'authority':dict(M.AUTHORITY),'manifestSha256':M.sha256(manifest),'projectionSha256':M.sha256(projection),
            'manifestDigestState':'BUILD_DERIVED_SOURCE_DIGEST_NOT_REHASHED_AT_RUNTIME',
            'productSourceRevisionReported':SHA,'observedAt':STAMP,'snapshotFreshness':'SNAPSHOT_NOT_LIVE',
            'inventoryScope':{'visibility':'public-only','authenticated':False,'privateAssetsIncluded':False},
            'returned':1,'sourcePointersDeclared':1,'categoryCounts':{'ADAPTER_HINT':1},'models':[row]}
    data.update(dict.fromkeys(('trainingAllowed','sourceAlignmentVerified','wholeOrganizationInventoryVerified',
                              'productSourceIndependentlyAttested'),False))
    return data,manifest,projection


class CatalogTests(unittest.TestCase):
    def test_valid_recorded_projection(self):
        d,m,p=fixture(); M.validate_catalog(d,m,p,SHA,NOW)

    def test_honestly_stale_delivery_can_pass_without_inventory_promotion(self):
        d,m,p=fixture(); d['snapshotFreshness']='STALE_SNAPSHOT'
        M.validate_catalog(d,m,p,SHA,datetime(2026,9,15,tzinfo=timezone.utc))
        self.assertFalse(d['wholeOrganizationInventoryVerified'])

    def test_unresolved_is_not_absence(self):
        d,m,p=fixture(); d['models'][0].update(sourceState='NOT_RESOLVED_BY_THIS_CATALOG',sourceUrl=None)
        d['sourcePointersDeclared']=0; M.validate_catalog(d,m,p,SHA,NOW)

    def test_hidden_staleness(self):
        d,m,p=fixture()
        with self.assertRaises(M.VerificationError): M.validate_catalog(d,m,p,SHA,datetime(2026,9,15,tzinfo=timezone.utc))

    def test_future_snapshot_hidden(self):
        d,m,p=fixture()
        with self.assertRaises(M.VerificationError): M.validate_catalog(d,m,p,SHA,datetime(2026,9,12,tzinfo=timezone.utc))

    def test_wrong_source(self):
        d,m,p=fixture(); d['productSourceRevisionReported']='c'*40
        with self.assertRaises(M.VerificationError): M.validate_catalog(d,m,p,SHA,NOW)

    def test_changed_manifest_digest(self):
        d,m,p=fixture(); d['manifestSha256']='0'*64
        with self.assertRaises(M.VerificationError): M.validate_catalog(d,m,p,SHA,NOW)

    def test_changed_projection_digest(self):
        d,m,p=fixture(); d['projectionSha256']='0'*64
        with self.assertRaises(M.VerificationError): M.validate_catalog(d,m,p,SHA,NOW)

    def test_wrong_projection_parent(self):
        d,m,p=fixture(); p=raw({'schema':'szl.model-pretraining-input/v1','sourceManifestSha256':'0'*64})
        d['projectionSha256']=M.sha256(p)
        with self.assertRaises(M.VerificationError): M.validate_catalog(d,m,p,SHA,NOW)

    def test_missing_model(self):
        d,m,p=fixture(); d['models']=[]; d['returned']=0
        with self.assertRaises(M.VerificationError): M.validate_catalog(d,m,p,SHA,NOW)

    def test_duplicate_models(self):
        d,m,p=fixture(); d['models']*=2; d['returned']=2
        with self.assertRaises(M.VerificationError): M.validate_catalog(d,m,p,SHA,NOW)

    def test_foreign_model(self):
        d,m,p=fixture(); d['models'][0]['id']='foreign/test'
        with self.assertRaises(M.VerificationError): M.validate_catalog(d,m,p,SHA,NOW)

    def test_wrong_model_revision(self):
        d,m,p=fixture(); d['models'][0]['hubRevision']='c'*40
        with self.assertRaises(M.VerificationError): M.validate_catalog(d,m,p,SHA,NOW)

    def test_private_scope(self):
        d,m,p=fixture(); d['inventoryScope']['privateAssetsIncluded']=True
        with self.assertRaises(M.VerificationError): M.validate_catalog(d,m,p,SHA,NOW)

    def test_changed_access_control(self):
        d,m,p=fixture(); d['models'][0]['gated']=True
        with self.assertRaises(M.VerificationError): M.validate_catalog(d,m,p,SHA,NOW)

    def test_boolean_count(self):
        d,m,p=fixture(); d['returned']=True
        with self.assertRaises(M.VerificationError): M.validate_catalog(d,m,p,SHA,NOW)

    def test_boolean_category_count(self):
        d,m,p=fixture(); d['categoryCounts']['ADAPTER_HINT']=True
        with self.assertRaises(M.VerificationError): M.validate_catalog(d,m,p,SHA,NOW)

    def test_unresolved_url_injection(self):
        d,m,p=fixture(); d['models'][0]['sourceState']='AMBIGUOUS'
        with self.assertRaises(M.VerificationError): M.validate_catalog(d,m,p,SHA,NOW)

    def test_foreign_source_url(self):
        d,m,p=fixture(); d['models'][0]['sourceUrl']='https://github.com/another/repo'
        with self.assertRaises(M.VerificationError): M.validate_catalog(d,m,p,SHA,NOW)

    def test_path_traversal_pointer(self):
        d,m,p=fixture(); d['models'][0]['sourceUrl']='https://github.com/szl-holdings/../another'
        with self.assertRaises(M.VerificationError): M.validate_catalog(d,m,p,SHA,NOW)

    def test_top_level_authority_amplification(self):
        for key in ('trainingAllowed','sourceAlignmentVerified','wholeOrganizationInventoryVerified','productSourceIndependentlyAttested'):
            for bad in (True,0,None):
                d,m,p=fixture(); d[key]=bad
                with self.subTest(key=key,bad=bad), self.assertRaises(M.VerificationError): M.validate_catalog(d,m,p,SHA,NOW)

    def test_authority_and_row_negative_controls(self):
        for key in M.AUTHORITY:
            d,m,p=fixture(); d['authority'][key]=0
            with self.subTest(key=key), self.assertRaises(M.VerificationError): M.validate_catalog(d,m,p,SHA,NOW)
        for key in ('weightsVerified','sourceBytesVerified','evaluationVerified','publicationVerified','runtimeVerified','trainingAllowed','categoryIsVerified'):
            d,m,p=fixture(); d['models'][0][key]=True
            with self.subTest(key=key), self.assertRaises(M.VerificationError): M.validate_catalog(d,m,p,SHA,NOW)


class TransportTests(unittest.TestCase):
    def test_valid_asset(self):
        M.validate_asset('/assets/szl-flow.css',200,'text/css; charset=utf-8',b'a{}',b'a{}')

    def test_html_fallback_is_not_css(self):
        with self.assertRaises(M.VerificationError): M.validate_asset('/assets/szl-flow.css',200,'text/html',b'a{}',b'a{}')

    def test_changed_asset_bytes(self):
        with self.assertRaises(M.VerificationError): M.validate_asset('/assets/szl-flow.css',200,'text/css',b'b{}',b'a{}')

    def test_failed_status(self):
        with self.assertRaises(M.VerificationError): M.validate_asset('/assets/szl-flow.css',503,'text/css',b'a{}',b'a{}')

    def test_empty_asset(self):
        with self.assertRaises(M.VerificationError): M.validate_asset('/assets/szl-flow.css',200,'text/css',b'',b'')

    def test_redirect_is_not_followed(self):
        with self.assertRaises(M.VerificationError): M.NoRedirect().redirect_request(None,None,302,'',{},'https://other.example')

    def test_strict_json_failures(self):
        for b in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}', b'\xff', b'', b'{'*(2000), b'[]'+b' '*(M.LIMIT)):
            with self.subTest(body=b[:20]),self.assertRaises(M.VerificationError): M.strict_json(b)

    def test_build_witness_rejects_empty_object(self):
        with self.assertRaises(M.VerificationError): M.source_revision({},SHA)

    def test_build_witness_rejects_weak_revision_source(self):
        value={'status':'OBSERVED','receipt_minted':False,'build':{'state':'OBSERVED','revision':SHA,'revision_source':'guess'}}
        with self.assertRaises(M.VerificationError): M.source_revision(value,SHA)


class SequenceTests(unittest.TestCase):
    def setup_source(self, root):
        d,m,p=fixture()
        d['snapshotFreshness']='STALE_SNAPSHOT'
        (root/'docs').mkdir(); (root/'docs/huggingface-ecosystem-manifest.json').write_bytes(m)
        (root/'routers/data').mkdir(parents=True); (root/'routers/data/model-pretraining-snapshot.json').write_bytes(p)
        for path,(file,types) in M.ASSETS.items():
            target=root/file; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(b'reviewed source')
        # Use the actual current clock so the control does not age into failure.
        stamp=datetime.fromisoformat(STAMP.replace('Z','+00:00'))
        age=(datetime.now(timezone.utc)-stamp).total_seconds()
        d['snapshotFreshness']='CLOCK_SKEW' if age<0 else 'STALE_SNAPSHOT' if age>86400 else 'SNAPSHOT_NOT_LIVE'
        def fetch(path, method='GET'):
            if path=='/api/build-info':
                return 200,'application/json',raw({'status':'OBSERVED','receipt_minted':False,'build':{'state':'OBSERVED','revision':SHA,'revision_source':'env:SZL_GIT_SHA'}})
            if path==M.API: return 200,'application/json',b'' if method=='HEAD' else raw(d)
            return 200,sorted(M.ASSETS[path][1])[0],b'' if method=='HEAD' else b'reviewed source'
        return fetch

    def test_whole_positive_sequence_has_no_authority(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); fetch=self.setup_source(root)
            result=M.probe(root,M.ORIGINS['canonical'],SHA,fetch=fetch)
            self.assertEqual(result['state'],'PASS_SELECTED_SOURCE_AND_DELIVERY')
            self.assertEqual(len(result['assets']),7)
            self.assertFalse(result['trainingAllowed']); self.assertFalse(result['wholeEstateAligned'])

    def test_source_moves_during_observation(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); fetch=self.setup_source(root); calls=0
            def move(path,method='GET'):
                nonlocal calls
                status,media,body=fetch(path,method)
                if path=='/api/build-info':
                    calls+=1
                    if calls==2: body=body.replace(SHA.encode(),('b'*40).encode())
                return status,media,body
            with self.assertRaises(M.VerificationError): M.probe(root,M.ORIGINS['canonical'],SHA,fetch=move)

    def test_http_failure_stops_sequence(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); fetch=self.setup_source(root)
            def fail(path,method='GET'):
                return (503,'application/json',b'{}') if path==M.API else fetch(path,method)
            with self.assertRaises(M.VerificationError): M.probe(root,M.ORIGINS['canonical'],SHA,fetch=fail)

    def test_bad_head_stops_sequence(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); fetch=self.setup_source(root)
            def fail(path,method='GET'):
                return (200,'text/html',b'body') if method=='HEAD' else fetch(path,method)
            with self.assertRaises(M.VerificationError): M.probe(root,M.ORIGINS['canonical'],SHA,fetch=fail)

    def test_arbitrary_origin_denied_before_reads(self):
        with self.assertRaises(M.VerificationError): M.probe(Path('/nonexistent'),'http://127.0.0.1',SHA)

    def test_invalid_source_denied_before_reads(self):
        with self.assertRaises(M.VerificationError): M.probe(Path('/nonexistent'),M.ORIGINS['canonical'],'main')


if __name__ == '__main__': unittest.main()
