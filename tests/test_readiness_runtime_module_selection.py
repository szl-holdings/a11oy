#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Exercise only the extracted generic registration with fake imports/app."""
import ast
import io
from pathlib import Path
from types import SimpleNamespace
import unittest


def registration_block():
    source = (Path(__file__).resolve().parents[1] / "serve.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    matches = [node for node in tree.body if isinstance(node, ast.Try) and any(
        isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute)
        and isinstance(child.func.value, ast.Name)
        and child.func.value.id == "_szl_readiness" and child.func.attr == "register"
        for child in ast.walk(node))]
    if len(matches) != 1:
        raise AssertionError("Expected one generic readiness registration block")
    return ast.Module(body=matches, type_ignores=[])


class RuntimeModuleSelectionTests(unittest.TestCase):
    def run_registration(self, *, missing=False, register_error=False):
        calls = []
        imports = []
        app = object()
        stderr = io.StringIO()

        def canonical_register(candidate, **kwargs):
            calls.append(("canonical", candidate, kwargs))
            if register_error:
                raise RuntimeError("synthetic registration failure")

        def stale_register(candidate, **kwargs):
            calls.append(("stale", candidate, kwargs))

        canonical = SimpleNamespace(register=canonical_register)
        stale = SimpleNamespace(register=stale_register)

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            imports.append(name)
            if name == "szl_readiness":
                if missing:
                    raise ImportError("canonical readiness unavailable")
                return canonical
            if name == "szl_substrate":
                return SimpleNamespace(szl_readiness=stale)
            if name == "sys":
                return SimpleNamespace(stderr=stderr)
            raise AssertionError("Unexpected import from isolated registration: " + name)

        namespace = {"app": app, "__builtins__": {
            "__import__": fake_import, "print": print, "Exception": Exception}}
        # Only this generic import/register/error-reporting node executes.
        # Both providers and the app are fakes; full serve.py never imports.
        exec(compile(registration_block(), "<isolated-readiness-registration>", "exec"), namespace)
        return calls, imports, app, stderr.getvalue()

    def test_stale_installed_package_cannot_shadow_canonical_root(self):
        calls, imports, _app, _stderr = self.run_registration()
        self.assertEqual([call[0] for call in calls], ["canonical"])
        self.assertNotIn("szl_substrate", imports)

    def test_registration_preserves_exact_app_and_namespace(self):
        calls, _imports, app, stderr = self.run_registration()
        self.assertEqual(calls, [("canonical", app, {"ns": "a11oy"})])
        self.assertIn("Operational Readiness registered:", stderr)

    def test_missing_root_module_is_visible_without_stale_fallback(self):
        calls, _imports, _app, stderr = self.run_registration(missing=True)
        self.assertEqual(calls, [])
        self.assertIn("Operational Readiness NOT registered:", stderr)
        self.assertIn("canonical readiness unavailable", stderr)
        self.assertNotIn("Operational Readiness registered:", stderr)

    def test_registration_failure_stays_visible(self):
        calls, _imports, _app, stderr = self.run_registration(register_error=True)
        self.assertEqual([call[0] for call in calls], ["canonical"])
        self.assertIn("Operational Readiness NOT registered:", stderr)
        self.assertIn("synthetic registration failure", stderr)
        self.assertNotIn("Operational Readiness registered:", stderr)


if __name__ == "__main__":
    unittest.main()
