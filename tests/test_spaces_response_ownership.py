# SPDX-License-Identifier: Apache-2.0
"""Shared Spaces injector honors response ownership; no runtime/provider calls."""
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace
import unittest
from starlette.datastructures import Headers

ROOT=Path(__file__).resolve().parents[1]


def factory():
    path=ROOT/'szl_spaces_surface.py'
    tree=ast.parse(path.read_text(encoding='utf-8'))
    wanted={'_NAV_MARKER','_FOOT_ANCHOR','_GROUP_ANCHOR','_NAVITEM_ANCHOR'}
    nodes=[n for n in tree.body if isinstance(n,ast.Assign)
           and any(isinstance(t,ast.Name) and t.id in wanted for t in n.targets)]
    nodes += [n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'_nav_item','_make_injector'}]
    if len(nodes)!=6:raise RuntimeError('shared source grammar changed')
    env={'__name__':'_shared_nav_slice'}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),env)
    return env['_make_injector']()


class SpacesOwnershipTests(unittest.TestCase):
    def test_owned_response_is_returned_without_body_consumption(self):
        async def run():
            class Unread:
                def __aiter__(self):raise AssertionError('owned response was consumed')
            response=SimpleNamespace(headers=Headers({'cache-control':'no-store, no-transform'}),body_iterator=Unread())
            async def downstream(_):return response
            observed=await factory()(lambda *_:None).dispatch(SimpleNamespace(),downstream)
            self.assertIs(observed,response)
        asyncio.run(run())

    def test_normal_console_still_receives_spaces_navigation(self):
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse
        from fastapi.testclient import TestClient
        app=FastAPI()
        app.add_api_route('/console',lambda:HTMLResponse('<html><body><div class="nav-item">Home</div></body></html>'))
        app.add_middleware(factory())
        with TestClient(app) as client:
            self.assertIn('data-nav-spaces="hf1"',client.get('/console').text)


if __name__=='__main__':unittest.main()
