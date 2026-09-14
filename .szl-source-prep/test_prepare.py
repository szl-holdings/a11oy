import ast
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

P=Path(__file__).with_name('prepare.py')
spec=importlib.util.spec_from_file_location('prepare', P)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
RAW=b'class Target:\n    async def dispatch(self, request, call_next):\n        resp = await call_next(request)\n        return resp\n'

class TestTransformation(unittest.TestCase):
 def test_direct_guard_is_before_any_original_response_use(self):
  result=m.transform(RAW,'Target').decode()
  self.assertEqual(result.count('parse_http_list'),2)
  self.assertLess(result.index('getlist('),result.rindex('return resp'))
  self.assertIn('resp.headers.getlist',result)
  self.assertNotIn('request.headers',result)
  self.assertEqual(ast.dump(ast.parse(RAW).body[0].body[0].body[0]),
                   ast.dump(ast.parse(result).body[0].body[0].body[0]))
 def test_missing_class(self):
  with self.assertRaises(m.Stop):m.transform(RAW,'Other')
 def test_duplicate_class(self):
  with self.assertRaises(m.Stop):m.transform(RAW+RAW,'Target')
 def test_changed_acquisition(self):
  with self.assertRaises(m.Stop):m.transform(RAW.replace(b'resp =',b'value ='),'Target')
 def test_foreign_call(self):
  with self.assertRaises(m.Stop):m.transform(RAW.replace(b'call_next(request)',b'other(request)'),'Target')
 def test_already_guarded(self):
  with self.assertRaises(m.Stop):m.transform(m.transform(RAW,'Target'),'Target')
 def test_missing_dispatch(self):
  with self.assertRaises(m.Stop):m.transform(RAW.replace(b'dispatch(',b'other('),'Target')
 def test_windows_newlines(self):
  with self.assertRaises(m.Stop):m.transform(RAW.replace(b'\n',b'\r\n'),'Target')
 def test_page_change_is_only_header_declaration(self):
  b=b'HEADERS = {}\nPAGE_HEADERS = {**HEADERS, "Content-Security-Policy": ("self")}\n'
  expected=b.replace(b'**HEADERS, ',b'**HEADERS, "Cache-Control": "no-store, no-transform", ')
  self.assertEqual(m.transform(b,None),expected)
 def test_unknown_page_shape(self):
  with self.assertRaises(m.Stop):m.transform(b'PAGE_HEADERS = {}',None)
 def test_fixed_owner_and_path_scope(self):
  self.assertEqual(set(m.CONFIG),{'szl-holdings/a11oy','szl-holdings/killinchu'})
  self.assertEqual(set(m.CONFIG['szl-holdings/a11oy']['files']),{'serve.py','a11oy_grc.py','szl_spaces_surface.py','routers/model_pretraining.py'})
  self.assertEqual(set(m.CONFIG['szl-holdings/killinchu']['files']),{'szl_spaces_surface.py'})
  self.assertNotEqual(m.TARGET_BRANCH,'main')
 def test_source_identity_required(self):
  with patch.dict(m.os.environ,{},clear=True),self.assertRaises(m.Stop):m.identity()
 def test_foreign_repo_rejected(self):
  with patch.dict(m.os.environ,{'GITHUB_REPOSITORY':'other/repo','GITHUB_SHA':'a'*40},clear=True),self.assertRaises(m.Stop):m.identity()
 def test_main_ref_rejected(self):
  env={'GITHUB_REPOSITORY':'szl-holdings/a11oy','GITHUB_SHA':'a'*40,'GITHUB_REF':'refs/heads/main'}
  with patch.dict(m.os.environ,env,clear=True),self.assertRaises(m.Stop):m.identity()
 def test_no_force_update_merge_deployment_or_http_secret_code(self):
  s=P.read_text()
  self.assertNotIn('--force',s);self.assertNotIn("'PATCH'",s)
  self.assertNotIn('/merges',s);self.assertNotIn('huggingface.co',s)
  self.assertNotIn('HF_TOKEN',s);self.assertNotIn('HF_ORG_TOKEN',s)

if __name__=='__main__':unittest.main()
