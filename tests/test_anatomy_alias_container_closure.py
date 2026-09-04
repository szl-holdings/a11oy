# SPDX-License-Identifier: Apache-2.0
"""The shipped anatomy alias binding must be present in the final image."""
import importlib.util
import re
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "szl_anatomy_alias_bind.py"


def load_binding():
    spec = importlib.util.spec_from_file_location("anatomy_container_test_binding", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AnatomyContainerClosureTests(unittest.TestCase):
    def test_binding_is_explicitly_copied_into_final_runtime(self):
        text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        stages = list(re.finditer(r"(?im)^FROM\s+", text))
        self.assertTrue(stages)
        runtime = text[stages[-1].start():]
        self.assertRegex(runtime, r"(?m)^COPY szl_anatomy_alias_bind\.py /app/szl_anatomy_alias_bind\.py\s*$")
        self.assertTrue(MODULE.is_file())

    def test_bind_uses_the_existing_response_class(self):
        serve = ModuleType("serve")
        response = object()
        serve._PTG_Redirect = response
        with patch.dict(sys.modules, {"serve": serve, "__main__": ModuleType("__main__")}):
            module = load_binding()
            self.assertIs(serve.RedirectResponse, response)
            self.assertTrue(module.bind_ptg_redirect())
            self.assertIs(serve.RedirectResponse, response)

    def test_main_entrypoint_is_supported_without_a_serve_import(self):
        serve = ModuleType("serve")
        main = ModuleType("__main__")
        response = object()
        main._PTG_Redirect = response
        with patch.dict(sys.modules, {"serve": serve, "__main__": main}):
            module = load_binding()
            self.assertIs(main.RedirectResponse, response)
            self.assertFalse(hasattr(serve, "RedirectResponse"))
            self.assertTrue(module.bind_ptg_redirect())

    def test_absent_response_class_is_not_invented(self):
        serve, main = ModuleType("serve"), ModuleType("__main__")
        with patch.dict(sys.modules, {"serve": serve, "__main__": main}):
            module = load_binding()
            self.assertFalse(module.bind_ptg_redirect())
            self.assertFalse(hasattr(serve, "RedirectResponse"))
            self.assertFalse(hasattr(main, "RedirectResponse"))


if __name__ == "__main__":
    unittest.main()
