# SPDX-License-Identifier: Apache-2.0
"""Selected-source pointer binding, including plausible same-org substitutions.

Every HTTP response here is a transport fixture, not a public observation. The
existing observer sequence executes; no model, provider write or GPU is involved.
"""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_model_pretraining_live as base

M = base.M


def catalog(cards):
    return ("_FORGE = 'https://github.com/szl-holdings/szl-forge'\n"
            'SERIES_A_CARDS = ' + repr(tuple(cards)) + '\n').encode()


def card(url='https://github.com/szl-holdings/szl-forge', identity='SZLHOLDINGS/test', kind='model'):
    return {'hub_kind': kind, 'hub_id': identity, 'github': url}


class SourceGrammarTests(unittest.TestCase):
    def test_existing_literal_fstring_grammar(self):
        self.assertEqual(M.declared_source_pointers(base.CATALOG), {
            'SZLHOLDINGS/test': ('DECLARED_POINTER_ONLY', 'https://github.com/szl-holdings/szl-forge')})

    def test_annotated_tuple_supported_without_importing(self):
        raw=base.CATALOG.replace(b'SERIES_A_CARDS =', b'SERIES_A_CARDS: tuple[dict[str, Any], ...] =')
        self.assertEqual(M.declared_source_pointers(raw), M.declared_source_pointers(base.CATALOG))

    def test_empty_tuple_is_known_empty_not_unavailable(self):
        self.assertEqual(M.declared_source_pointers(catalog([])), {})

    def test_missing_declaration_fails(self):
        with self.assertRaises(M.VerificationError): M.declared_source_pointers(b'_FORGE = "x"\n')

    def test_duplicate_assignment_fails(self):
        with self.assertRaises(M.VerificationError): M.declared_source_pointers(base.CATALOG+b'SERIES_A_CARDS = ()\n')

    def test_augmented_assignment_fails(self):
        with self.assertRaises(M.VerificationError): M.declared_source_pointers(base.CATALOG+b'SERIES_A_CARDS += ()\n')

    def test_duplicate_dict_key_fails(self):
        raw=base.CATALOG.replace(b"'hub_kind':'model'",b"'hub_kind':'model','hub_kind':'space'")
        with self.assertRaises(M.VerificationError): M.declared_source_pointers(raw)

    def test_unpacking_fails(self):
        raw=base.CATALOG.replace(b"'hub_kind':'model'",b"**dict(hub_kind='model')")
        with self.assertRaises(M.VerificationError): M.declared_source_pointers(raw)

    def test_no_function_call_is_executed(self):
        raw=base.CATALOG.replace(b"f'{_FORGE}'",b"__import__('os').system('not-executed')")
        with patch('os.system',side_effect=AssertionError('must not execute')) as call:
            with self.assertRaises(M.VerificationError): M.declared_source_pointers(raw)
            call.assert_not_called()

    def test_no_formatted_value_call_is_executed(self):
        raw=base.CATALOG.replace(b"f'{_FORGE}'",b"f'{__import__(\"os\").system(\"not-executed\")}'")
        with patch('os.system',side_effect=AssertionError('must not execute')) as call:
            with self.assertRaises(M.VerificationError): M.declared_source_pointers(raw)
            call.assert_not_called()

    def test_nonliteral_prefix_fails(self):
        raw=base.CATALOG.replace(b"'https://github.com/szl-holdings/szl-forge'", b"str('x')",1)
        with self.assertRaises(M.VerificationError): M.declared_source_pointers(raw)

    def test_unknown_interpolation_fails(self):
        raw=base.CATALOG.replace(b"f'{_FORGE}'",b"f'{OTHER}'")
        with self.assertRaises(M.VerificationError): M.declared_source_pointers(raw)

    def test_interpolation_conversion_fails(self):
        raw=base.CATALOG.replace(b"f'{_FORGE}'",b"f'{_FORGE!r}'")
        with self.assertRaises(M.VerificationError): M.declared_source_pointers(raw)

    def test_foreign_or_malformed_sources_remain_unresolved(self):
        for value in ('https://example.com/x', 'https://github.com/other/repo',
                      'https://github.com/szl-holdings/a/../b', 'https://github.com/szl-holdings/a?x=1',
                      'https://github.com/szl-holdings/a%2Fb', None, 5):
            with self.subTest(value=value):
                self.assertEqual(M.declared_source_pointers(catalog([card(value)]))['SZLHOLDINGS/test'],
                                 ('NOT_RESOLVED_BY_THIS_CATALOG',None))

    def test_duplicate_cards_preserve_ambiguity(self):
        self.assertEqual(M.declared_source_pointers(catalog([card(),card()])),
                         {'SZLHOLDINGS/test':('AMBIGUOUS',None)})

    def test_other_repository_type_does_not_claim_model(self):
        self.assertEqual(M.declared_source_pointers(catalog([card(kind='space')])),{})

    def test_module_side_effects_are_never_executed(self):
        raw=b"raise RuntimeError('product import forbidden')\n"+base.CATALOG
        self.assertEqual(M.declared_source_pointers(raw),M.declared_source_pointers(base.CATALOG))

    def test_malformed_utf8_fails(self):
        with self.assertRaises(M.VerificationError): M.declared_source_pointers(b'\xff')

    def test_wrong_type_fails(self):
        with self.assertRaises(M.VerificationError): M.declared_source_pointers(base.CATALOG.decode())


class BindingTests(unittest.TestCase):
    def test_valid_pointer_remains_a_declaration_not_lineage(self):
        data,_,_=base.fixture()
        M.validate_source_pointers(data,M.declared_source_pointers(base.CATALOG))
        self.assertFalse(data['sourceAlignmentVerified'])
        self.assertFalse(data['models'][0]['sourceBytesVerified'])

    def test_same_org_different_repository_fails(self):
        data,manifest,projection=base.fixture()
        data['models'][0]['sourceUrl']='https://github.com/szl-holdings/unrelated'
        # The prior metadata-only check accepted this; new binding rejects it.
        M.validate_catalog(data,manifest,projection,base.SHA,base.NOW)
        with self.assertRaises(M.VerificationError):
            M.validate_source_pointers(data,M.declared_source_pointers(base.CATALOG))

    def test_same_org_wrong_training_path_fails(self):
        data,_,_=base.fixture(); data['models'][0]['sourceUrl']+='/tree/main/wrong-training-path'
        with self.assertRaises(M.VerificationError):
            M.validate_source_pointers(data,M.declared_source_pointers(base.CATALOG))

    def test_removing_a_known_pointer_and_adjusting_count_fails(self):
        data,_,_=base.fixture();data['models'][0].update(sourceState='NOT_RESOLVED_BY_THIS_CATALOG',sourceUrl=None)
        data['sourcePointersDeclared']=0
        with self.assertRaises(M.VerificationError):
            M.validate_source_pointers(data,M.declared_source_pointers(base.CATALOG))

    def test_inventing_pointer_for_unresolved_model_fails(self):
        data,_,_=base.fixture()
        with self.assertRaises(M.VerificationError): M.validate_source_pointers(data,{})

    def test_known_unresolved_passes(self):
        data,_,_=base.fixture();data['models'][0].update(sourceState='NOT_RESOLVED_BY_THIS_CATALOG',sourceUrl=None)
        data['sourcePointersDeclared']=0
        M.validate_source_pointers(data,{})

    def test_ambiguity_must_match_actual_duplicate_declarations(self):
        data,_,_=base.fixture();data['models'][0].update(sourceState='AMBIGUOUS',sourceUrl=None)
        data['sourcePointersDeclared']=0
        M.validate_source_pointers(data,M.declared_source_pointers(catalog([card(),card()])))
        with self.assertRaises(M.VerificationError):
            M.validate_source_pointers(data,M.declared_source_pointers(base.CATALOG))

    def test_unavailable_source_catalog_fails(self):
        data,_,_=base.fixture();data['sourcePointerCatalogState']='UNAVAILABLE'
        with self.assertRaises(M.VerificationError):
            M.validate_source_pointers(data,M.declared_source_pointers(base.CATALOG))

    def test_missing_catalog_status_fails(self):
        data,_,_=base.fixture();del data['sourcePointerCatalogState']
        with self.assertRaises(M.VerificationError):
            M.validate_source_pointers(data,M.declared_source_pointers(base.CATALOG))

    def test_reordered_rows_are_not_a_mapping_change(self):
        data,_,_=base.fixture();other=copy.deepcopy(data['models'][0]);other['id']='SZLHOLDINGS/other'
        data['models'].append(other);data['sourcePointersDeclared']=2
        declared=M.declared_source_pointers(catalog([card(),card(identity='SZLHOLDINGS/other')]))
        M.validate_source_pointers(data,declared)
        data['models'].reverse();M.validate_source_pointers(data,declared)

    def test_boolean_count_is_not_one(self):
        data,_,_=base.fixture();data['sourcePointersDeclared']=True
        with self.assertRaises(M.VerificationError):
            M.validate_source_pointers(data,M.declared_source_pointers(base.CATALOG))

    def test_duplicate_rows_fail(self):
        data,_,_=base.fixture();data['models']*=2;data['sourcePointersDeclared']=2
        with self.assertRaises(M.VerificationError):
            M.validate_source_pointers(data,M.declared_source_pointers(base.CATALOG))


class BoundSequenceTests(unittest.TestCase):
    def test_public_probe_rejects_plausible_wrong_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);fetch=base.SequenceTests().setup_source(root)
            def swapped(path,method='GET'):
                status,media,body=fetch(path,method)
                if path==M.API and method=='GET':
                    data=M.strict_json(body);data['models'][0]['sourceUrl']='https://github.com/szl-holdings/other'
                    body=base.raw(data)
                return status,media,body
            with self.assertRaises(M.VerificationError): M.probe(root,M.ORIGINS['canonical'],base.SHA,fetch=swapped)

    def test_missing_local_catalog_stops_before_http(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);base.SequenceTests().setup_source(root)
            (root/'a11oy_model_intel.py').unlink(); calls=[]
            def forbidden(*args): calls.append(args);raise AssertionError('HTTP not allowed')
            with self.assertRaises(OSError): M.probe(root,M.ORIGINS['canonical'],base.SHA,fetch=forbidden)
            self.assertEqual(calls,[])

    def test_invalid_catalog_stops_before_http(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);base.SequenceTests().setup_source(root)
            (root/'a11oy_model_intel.py').write_bytes(b'bad source');calls=[]
            def forbidden(*args):calls.append(args);raise AssertionError('HTTP not allowed')
            with self.assertRaises(M.VerificationError): M.probe(root,M.ORIGINS['canonical'],base.SHA,fetch=forbidden)
            self.assertEqual(calls,[])

    def test_bound_report_carries_local_catalog_digest_without_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);fetch=base.SequenceTests().setup_source(root)
            data=M.probe(root,M.ORIGINS['canonical'],base.SHA,fetch=fetch)
            self.assertEqual(data['sourcePointerCatalogSha256'],M.sha256(base.CATALOG))
            self.assertEqual(data['sourcePointerCorrespondence'],'DECLARATIONS_MATCH_NOT_LINEAGE_VERIFIED')
            self.assertFalse(data['wholeEstateAligned']);self.assertFalse(data['trainingAllowed'])


if __name__ == '__main__': unittest.main()
