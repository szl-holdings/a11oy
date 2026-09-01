#!/usr/bin/env python3
"""Regression contract for the shared integrations source boundary."""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "szl_connectors_serve.py"
PAGE = ROOT / "pages" / "integrations.html"
STYLE_MARKER = 'data-szl-flow-asset="style"'
SCRIPT_MARKER = 'data-szl-flow-asset="script"'


class IntegrationsFlowBoundaryContract(unittest.TestCase):
    def _helper(self):
        source = MODULE.read_text(encoding="utf-8")
        tree = ast.parse(source)
        wanted = []
        for node in tree.body:
            if isinstance(node, ast.Assign):
                names = {target.id for target in node.targets if isinstance(target, ast.Name)}
                if names & {"_FLOW_STYLE", "_FLOW_SCRIPT"}:
                    wanted.append(node)
            elif isinstance(node, ast.FunctionDef) and node.name == "_with_a11oy_flow_shell":
                wanted.append(node)
        namespace = {}
        selected = ast.Module(body=wanted, type_ignores=[])
        ast.fix_missing_locations(selected)
        exec(compile(selected, str(MODULE), "exec"), namespace)
        return namespace["_with_a11oy_flow_shell"]

    def test_helper_is_idempotent_and_exact(self) -> None:
        bind = self._helper()
        original = "<html><head><title>x</title></head><body>y</body></html>"
        bound = bind(original)
        self.assertEqual(bound.count(STYLE_MARKER), 1)
        self.assertEqual(bound.count(SCRIPT_MARKER), 1)
        self.assertEqual(bind(bound), bound)

    def test_shared_page_remains_product_asset_free(self) -> None:
        page = PAGE.read_text(encoding="utf-8")
        self.assertNotIn(STYLE_MARKER, page)
        self.assertNotIn(SCRIPT_MARKER, page)

    def test_route_binds_only_the_a11oy_namespace(self) -> None:
        source = MODULE.read_text(encoding="utf-8")
        self.assertIn('if ns == "a11oy":', source)
        self.assertIn('return HTMLResponse(page, media_type="text/html")', source)
        self.assertIn('return FileResponse(f, media_type="text/html")', source)


if __name__ == "__main__":
    unittest.main()
