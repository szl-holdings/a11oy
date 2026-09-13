# SPDX-License-Identifier: Apache-2.0
"""Network-free card regressions against the actual source-owned function.

AST selection deliberately avoids importing the application. The Hub URL
helper is a fixed test double; these tests do not qualify URL construction,
provider state, full-page rendering, or a deployed runtime.
"""
from __future__ import annotations

import ast
import unittest
from html import escape, unescape
from html.parser import HTMLParser
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "szl_spaces_surface.py"


class Document(HTMLParser):
    def __init__(self, markup: str):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.text = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def handle_data(self, text):
        self.text.append(text)


def load_card():
    source = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_destination_ledger_card"]
    if len(nodes) != 1:
        raise ValueError("exact card function missing or duplicated")
    scope = {
        "html_escape": escape,
        "hf_repo_url": lambda name: "https://huggingface.co/spaces/SZLHOLDINGS/" + name,
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "observed-card-function", "exec"), scope)
    return scope["_destination_ledger_card"]


class CardTests(unittest.TestCase):
    def setUp(self):
        self.card = load_card()
        self.record = dict(name="cosmos", title="Cosmos", dest="https://a-11-oy.com/living-anatomy", sdk="docker", sink="product", why="Plan: bind as anatomy.")

    def test_fold_always_explicitly_unobserved(self):
        text = unescape(self.card(self.record, "FOLD"))
        self.assertIn("FOLD · PLANNED · provider state UNOBSERVED", text)

    def test_unify_always_explicitly_unobserved(self):
        text = unescape(self.card(self.record, "UNIFY"))
        self.assertIn("UNIFY · PLANNED · provider state UNOBSERVED", text)

    def test_no_paused_or_private_status_in_default_card(self):
        markup = self.card(self.record, "FOLD")
        self.assertNotIn("PAUSED", markup)
        self.assertNotIn("PRIVATE", markup)
        self.assertNotIn("Hub (private)", markup)

    def test_scope_note_cannot_remove_unobserved_status(self):
        self.record["honesty"] = "Occupancy UNAVAILABLE"
        markup = self.card(self.record, "FOLD")
        self.assertIn("provider state UNOBSERVED", markup)
        self.assertIn("Scope note: Occupancy UNAVAILABLE", markup)

    def test_semantic_scope_disclaimer_is_preserved(self):
        self.record["honesty"] = "8/8 SIMULATED"
        self.assertIn("8/8 SIMULATED", self.card(self.record, "FOLD"))

    def test_destination_and_existing_hub_identity_preserved(self):
        doc = Document(self.card(self.record, "FOLD"))
        links = [attrs["href"] for tag, attrs in doc.tags if tag == "a"]
        self.assertEqual(links, [self.record["dest"], "https://huggingface.co/spaces/SZLHOLDINGS/cosmos"])

    def test_card_contains_no_script_or_embedded_runtime(self):
        doc = Document(self.card(self.record, "FOLD"))
        self.assertFalse({tag for tag, _ in doc.tags} & {"script", "iframe", "object", "embed"})

    def test_notes_titles_and_sink_do_not_create_html(self):
        value = '<img src=x onerror="alert(1)">'
        self.record.update(title=value, why=value, honesty=value, sink=value)
        doc = Document(self.card(self.record, "FOLD"))
        self.assertNotIn("img", [tag for tag, _ in doc.tags])
        self.assertIn(value, " ".join(doc.text))

    def test_destination_quote_is_not_an_event_attribute(self):
        self.record["dest"] = 'https://a-11-oy.com/" onclick="alert(1)'
        doc = Document(self.card(self.record, "FOLD"))
        for _, attrs in doc.tags:
            self.assertNotIn("onclick", attrs)
        self.assertEqual([a["href"] for t, a in doc.tags if t == "a"][0], self.record["dest"])

    def test_unknown_kind_rejected_without_unify_fallback(self):
        for kind in ("KEEP", "ARCHIVE", "", '<script>x</script>'):
            with self.subTest(kind=kind):
                with self.assertRaises(ValueError):
                    self.card(self.record, kind)

    def test_plan_rationale_is_labeled(self):
        self.assertIn("Plan rationale: Plan: bind as anatomy.", self.card(self.record, "FOLD"))

    def test_runtime_claims_supplied_as_extra_fields_are_not_admitted(self):
        self.record.update(private="true", stage="PAUSED", state="LIVE")
        doc = Document(self.card(self.record, "FOLD"))
        text = " ".join(doc.text)
        self.assertIn("provider state UNOBSERVED", text)
        self.assertNotIn("PAUSED", text)
        self.assertNotIn("LIVE", text)


class FullSurfaceTests(unittest.TestCase):
    """Exercise complete source-owned rendering and registered routes offline."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        spec = importlib.util.spec_from_file_location("visibility_surface_under_test", SOURCE)
        cls.surface = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.surface)

    def test_every_plan_card_has_unobserved_status_and_original_links(self):
        from unittest.mock import patch
        s = self.surface
        with patch.object(s, "_resolve_client", side_effect=AssertionError("no probe")):
            for kind, records in (("FOLD", s.FOLD_SPACES), ("UNIFY", s.UNIFY_SPACES)):
                for record in records:
                    with self.subTest(kind=kind, slug=record["slug"]):
                        doc = Document(s._destination_ledger_card(record, kind))
                        self.assertIn(kind + " · PLANNED · provider state UNOBSERVED", " ".join(doc.text))
                        self.assertEqual([a["href"] for t, a in doc.tags if t == "a"],
                                         [record["dest"], s.hf_repo_url(record["name"])])

    def test_complete_tiles_page_distinguishes_plan_from_provider_state(self):
        s = self.surface
        doc = Document(s._tiles_page("a11oy").decode("utf-8"))
        text = " ".join(doc.text)
        self.assertEqual(text.count("PLANNED · provider state UNOBSERVED"),
                         len(s.FOLD_SPACES) + len(s.UNIFY_SPACES))
        self.assertIn("Fold plan · provider state UNOBSERVED", text)
        for false_claim in ("Hub (private)", "PAUSED + PRIVATE", "Hub Space is PAUSED+PRIVATE",
                            "Hub Space re-privatized", "Unmapped RUNNING Space", "Not public Hub."):
            self.assertNotIn(false_claim, text)
        links = [a["href"] for t, a in doc.tags if t == "a"]
        self.assertIn("https://szlholdings-killinchu.hf.space/elite", links)
        self.assertIn("https://huggingface.co/spaces/SZLHOLDINGS/killinchu", links)
        self.assertIn("stage: ", text)
        self.assertIn("CHECKING", text)

    def test_unify_page_and_ledger_disclose_unobserved_plan(self):
        s = self.surface
        ledger = s.unify_ledger()
        self.assertIn("consolidation plan, not a provider observation", ledger["note"])
        self.assertFalse(ledger["hub_write"])
        self.assertFalse(ledger["hub_space_created"])
        self.assertFalse(ledger["certified"])
        self.assertFalse(ledger["proven_trust"])
        self.assertIsNone(ledger["winner"])
        page = s._unify_page().decode("utf-8")
        self.assertIn("Provider state UNOBSERVED", page)
        self.assertIn("planned to fold", page)

    def test_registered_pages_keep_read_only_methods_no_store_and_no_network(self):
        from unittest.mock import patch
        from starlette.applications import Starlette
        from starlette.testclient import TestClient
        s = self.surface
        with patch.object(s, "_resolve_client", side_effect=AssertionError("no probe")), \
             patch.object(s, "_urllib_probe", side_effect=AssertionError("no network")):
            app = Starlette()
            self.assertTrue(s.register(app, ns="killinchu").startswith("ok:"))
            with TestClient(app) as client:
                for route in ("/spaces", "/unify", "/a11oy/unify"):
                    with self.subTest(route=route):
                        response = client.get(route)
                        self.assertEqual(response.status_code, 200)
                        self.assertEqual(response.headers["cache-control"], "no-store")
                        self.assertIn("UNOBSERVED", response.text)
                        self.assertNotIn('data-nav-spaces="hf1"', response.text)
                        head = client.head(route)
                        self.assertEqual(head.status_code, 200)
                        self.assertEqual(head.content, b"")
                        self.assertEqual(client.post(route).status_code, 405)


if __name__ == "__main__":
    unittest.main()
