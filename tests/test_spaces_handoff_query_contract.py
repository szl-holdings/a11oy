# SPDX-License-Identifier: Apache-2.0
"""Network-free regression of the exact source-owned handoff URL builder.

Extract only the pure function to avoid importing the full application and its
optional runtime integrations. These are URL-contract tests, not live probes.
"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest
from urllib.parse import quote, urlsplit, urlunsplit


SOURCE = Path(__file__).resolve().parents[1] / "szl_spaces_proxy.py"


def builder(destination: str):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name == "_canonical_target"]
    if len(functions) != 1:
        raise AssertionError("require exactly one source-owned handoff builder")
    namespace = {
        "quote": quote, "urlsplit": urlsplit, "urlunsplit": urlunsplit,
        "_SPACE_BY_SLUG": {"audited": {}}, "HANDOFF_SPACES": ["audited"],
        "_destination_url": lambda _name: destination,
    }
    module = ast.Module(body=functions, type_ignores=[])
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace["_canonical_target"]


class HandoffQueryContractTests(unittest.TestCase):
    def test_query_precedes_vertical_fragment(self):
        target = builder("https://a-11-oy.com/spaces#verticals")
        self.assertEqual(target("audited", "ignored/subpath", "cursor=a%2Fb&cursor=two+words"),
                         "https://a-11-oy.com/spaces?cursor=a%2Fb&cursor=two+words#verticals")

    def test_atlas_root_and_anchor_remain_intact(self):
        target = builder("https://a11oy.net/#atlas")
        self.assertEqual(target("audited", "ignored", "q=kernel"),
                         "https://a11oy.net/?q=kernel#atlas")
        self.assertEqual(target("audited"), "https://a11oy.net/#atlas")

    def test_existing_query_and_duplicate_parameters_are_preserved(self):
        target = builder("https://a-11-oy.com/spaces?view=all#verticals")
        self.assertEqual(target("audited", "", "view=one&view=two"),
                         "https://a-11-oy.com/spaces?view=all&view=one&view=two#verticals")

    def test_nonfragment_subpath_comes_before_existing_query(self):
        target = builder("https://a-11-oy.com/console/?mode=demo")
        self.assertEqual(target("audited", "/api/events", "cursor=2"),
                         "https://a-11-oy.com/console/api/events?mode=demo&cursor=2")

    def test_caller_fragment_is_encoded_not_used_as_an_anchor(self):
        target = builder("https://a-11-oy.com/spaces#verticals")
        self.assertEqual(target("audited", "", "q=#other"),
                         "https://a-11-oy.com/spaces?q=%23other#verticals")

    def test_caller_host_like_values_never_change_fixed_origin(self):
        target = builder("https://szlholdings-killinchu.hf.space/elite")
        result = target("audited", "//example.invalid/a?x=1#other", "next=https://example.invalid/")
        parsed = urlsplit(result)
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "szlholdings-killinchu.hf.space")
        self.assertEqual(parsed.path, "/elite/example.invalid/a%3Fx=1%23other")
        self.assertEqual(parsed.fragment, "")

    def test_normal_handoff_compatibility_is_unchanged(self):
        target = builder("https://a-11-oy.com/immune/")
        self.assertEqual(target("audited"), "https://a-11-oy.com/immune")
        self.assertEqual(target("audited", "api/events", "cursor=a%2Fb&cursor=two+words"),
                         "https://a-11-oy.com/immune/api/events?cursor=a%2Fb&cursor=two+words")

    def test_unknown_identifier_still_fails_closed(self):
        with self.assertRaises(ValueError):
            builder("https://a-11-oy.com/spaces#verticals")("not-audited", "", "q=1")


if __name__ == "__main__":
    unittest.main()
