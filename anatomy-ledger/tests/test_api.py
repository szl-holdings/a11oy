from __future__ import annotations

import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class ServerApiTests(unittest.TestCase):
    def test_prove_matrix_is_green(self):
        server = load("anatomy_server", ROOT / "server.py")
        result = server.prove_matrix()
        self.assertEqual(result["schema"], "szl.anatomy.prove.v1")
        self.assertEqual(result["failed"], 0)
        self.assertGreaterEqual(result["passed"], 10)
        self.assertTrue(all(case["pass"] for case in result["results"]))


if __name__ == "__main__":
    unittest.main()
