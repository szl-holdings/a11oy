# SPDX-License-Identifier: Apache-2.0
"""Actual UI middleware composition; no full app startup, provider or model calls.

Fixed source AST nodes are selected to avoid serve.py's unrelated boot effects.
The separate existing image smoke remains the whole-application acceptance gate.
"""
from __future__ import annotations
import ast
import asyncio
import itertools
from pathlib import Path
from types import SimpleNamespace
import unittest

from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.testclient import TestClient
from starlette.datastructures import Headers
from starlette.middleware.base import BaseHTTPMiddleware

ROOT = Path(__file__).resolve().parents[1]
PAGE = '/frontier-tooling/models'


def selected(path: Path, definitions: tuple[str, ...], constants: tuple[str, ...], env=None):
    """Load a closed set of named nodes from test-owned repository paths only."""
    tree=ast.parse(path.read_text(encoding='utf-8'))
    nodes=[]
    for name in constants:
        found=[n for n in ast.walk(tree) if isinstance(n,ast.Assign)
               and any(isinstance(t,ast.Name) and t.id==name for t in n.targets)]
        if len(found)!=1: raise RuntimeError('missing/duplicate constant '+name)
        nodes.append(found[0])
    for name in definitions:
        found=[n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name]
        if len(found)!=1: raise RuntimeError('missing/duplicate definition '+name)
        nodes.append(found[0])
    scope={'__name__':'_reviewed_middleware_slice',**(env or {})}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),scope)
    return scope


def factories(root: Path):
    op=selected(root/'serve.py',('_OperatorWidgetInjector',),('_OPW_TAG','_OPW_MARKER'),
                {'_OPW_Base':BaseHTTPMiddleware,'_OPW_Response':Response})
    gr=selected(root/'a11oy_grc.py',('_make_injector',),
                ('_NAV_MARKER','_NAV_LINK','_GOVERN_ANCHOR','_GROUP_ANCHOR'))
    sp=selected(root/'szl_spaces_surface.py',('_nav_item','_make_injector'),
                ('_NAV_MARKER','_FOOT_ANCHOR','_GROUP_ANCHOR','_NAVITEM_ANCHOR'))
    return (gr['_make_injector'](),op['_OperatorWidgetInjector'],sp['_make_injector']())


def headers(root: Path):
    return selected(root/'routers/model_pretraining.py',(),('HEADERS','PAGE_HEADERS'))


def client_for(classes, raw: bytes, response_headers: dict, status=200):
    app=FastAPI()
    def document(): return Response(raw,status_code=status,media_type='text/html',headers=response_headers)
    app.add_api_route(PAGE,document,methods=['GET','HEAD'])
    app.add_api_route(PAGE+'/',document,methods=['GET','HEAD'])
    for cls in classes: app.add_middleware(cls)
    return TestClient(app)


class ResponseOwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.classes=factories(ROOT)
        cls.raw=(ROOT/'pages/model-pretraining.html').read_bytes()
        cls.declared=headers(ROOT)

    def test_page_declaration_is_no_transform_but_api_remains_no_store(self):
        self.assertEqual(self.declared['HEADERS']['Cache-Control'],'no-store')
        self.assertEqual(self.declared['PAGE_HEADERS']['Cache-Control'],'no-store, no-transform')
        self.assertIn("script-src 'self'",self.declared['PAGE_HEADERS']['Content-Security-Policy'])
        self.assertNotIn('unsafe-inline',self.declared['PAGE_HEADERS']['Content-Security-Policy'])

    def test_all_six_injector_orders_preserve_exact_page_and_security_headers(self):
        for order in itertools.permutations(self.classes):
            with self.subTest(order=tuple(c.__name__ for c in order)):
                with client_for(order,self.raw,self.declared['PAGE_HEADERS']) as client:
                    response=client.get(PAGE)
                    self.assertEqual(response.status_code,200)
                    self.assertEqual(response.content,self.raw)
                    for name,value in self.declared['PAGE_HEADERS'].items():
                        self.assertEqual(response.headers[name],value)
                    self.assertEqual(int(response.headers['content-length']),len(self.raw))

    def test_trailing_alias_is_same_exact_document(self):
        with client_for(self.classes,self.raw,self.declared['PAGE_HEADERS']) as client:
            self.assertEqual(client.get(PAGE+'/').content,self.raw)

    def test_head_does_not_create_a_body(self):
        with client_for(self.classes,self.raw,self.declared['PAGE_HEADERS']) as client:
            r=client.head(PAGE)
            self.assertEqual(r.status_code,200);self.assertEqual(r.content,b'')

    def test_legacy_unowned_html_retains_optional_injection(self):
        with client_for(self.classes,self.raw,{'Cache-Control':'no-store'}) as client:
            body=client.get(PAGE).content
            self.assertIn(b'a11oy-operator-widget.js',body)
            self.assertIn(b'data-view-grc="grc"',body)
            self.assertIn(b'data-nav-spaces="hf1"',body)
            self.assertEqual(len(body)-len(self.raw),463)

    def test_request_cache_directive_cannot_opt_out_for_the_response_owner(self):
        with client_for(self.classes,self.raw,{'Cache-Control':'no-store'}) as client:
            r=client.get(PAGE,headers={'Cache-Control':'no-transform'})
            self.assertNotEqual(r.content,self.raw)

    def test_quoted_extension_value_is_not_no_transform_directive(self):
        with client_for(self.classes,self.raw,{'Cache-Control':'x="foo,no-transform,bar", no-store'}) as client:
            self.assertNotEqual(client.get(PAGE).content,self.raw)

    def test_case_and_whitespace_are_recognized(self):
        with client_for(self.classes,self.raw,{'Cache-Control':'no-store,  No-Transform '}) as client:
            self.assertEqual(client.get(PAGE).content,self.raw)

    def test_marked_error_response_preserves_status_and_bytes(self):
        with client_for(self.classes,self.raw,self.declared['PAGE_HEADERS'],status=503) as client:
            r=client.get(PAGE);self.assertEqual(r.status_code,503);self.assertEqual(r.content,self.raw)

    def test_marked_missing_html_does_not_gain_widget_markup(self):
        raw=b'bounded unavailable document'
        with client_for(self.classes,raw,self.declared['PAGE_HEADERS']) as client:
            self.assertEqual(client.get(PAGE).content,raw)

    def test_no_transform_returns_the_original_unconsumed_response(self):
        async def exercise(cls):
            calls=[]
            class NeverRead:
                def __aiter__(self):
                    calls.append('body-read');raise AssertionError('body must not be consumed')
            response=SimpleNamespace(headers=Headers(raw=[(b'cache-control',b'no-store'),
                (b'cache-control',b'no-transform')]),body_iterator=NeverRead())
            async def next_response(_): return response
            observed=await cls(lambda *_:None).dispatch(SimpleNamespace(),next_response)
            self.assertIs(observed,response);self.assertEqual(calls,[])
        for cls in self.classes:
            with self.subTest(owner=cls.__name__):asyncio.run(exercise(cls))

    def test_marked_page_remains_get_head_only(self):
        with client_for(self.classes,self.raw,self.declared['PAGE_HEADERS']) as client:
            for method in ('POST','PUT','PATCH','DELETE'):
                self.assertEqual(client.request(method,PAGE).status_code,405)

    def test_each_known_unmarked_injector_has_a_working_positive_control(self):
        markup=b'<html><body><div class="nav-item">Existing</div></body></html>'
        for cls in self.classes:
            with self.subTest(owner=cls.__name__):
                with client_for((cls,),markup,{}) as client:
                    self.assertNotEqual(client.get(PAGE).content,markup)


if __name__=='__main__': unittest.main()
