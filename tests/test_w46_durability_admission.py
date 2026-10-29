"""W46: Lyte durability admission must fail closed.

Stdlib unittest only. Loads the real scripts/hf_vertical_convergence.py (its
top-level imports are stdlib only) and replaces just the network reads, the
same seams the protected fixture tests/test_hf_vertical_convergence.py uses.
It does not modify or import that protected file.

Target module: $W46_TARGET if set, else ../scripts/hf_vertical_convergence.py
relative to this file. Synthetic revisions only; no network, no writes.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import os
import unittest
from pathlib import Path

TARGET = Path(os.environ.get("W46_TARGET") or
              Path(__file__).resolve().parent.parent / "scripts" / "hf_vertical_convergence.py")
SERVED = "a" * 40
HEAD = "b" * 40
KNOWN_NON_DURABLE = ("FILE_OR_PROCESS_SCOPED", "PROCESS_SCOPED", "EPHEMERAL")
# DEPLOYMENT_MANAGED: what lyte-services emits for postgresql (lyte/app.py
# persistence_contract at c1b9c891). DURABLE_VOLUME: the protected fixture default.
DURABLE = ("DEPLOYMENT_MANAGED", "DURABLE_VOLUME")
_MISSING = object()


def load():
    spec = importlib.util.spec_from_file_location("w46_hf_vertical_convergence", TARGET)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assess(durability=_MISSING, *, persistence=_MISSING, served=SERVED, tip=HEAD):
    conv = load()
    if persistence is _MISSING:
        persistence = {"backend": "sqlite", "state": "READY"}
        if durability is not _MISSING:
            persistence["durability"] = durability
    live = {"source_revision": served, "runtime_source_revision": served}
    if persistence is not None:
        live["persistence"] = persistence
    conv.live_build_info = lambda slug: live
    conv.space_info = lambda slug: {"sha": "f" * 40, "stage": "RUNNING",
                                    "last_modified": "2026-10-13T00:00:00Z"}
    conv._lyte_drift_since = lambda s, t: dt.datetime(2026, 10, 10, tzinfo=dt.timezone.utc)
    return conv, conv.assess_lyte(resolve=lambda: (tip, {}), source_tip=lambda: {"sha": tip})


class DurableLabelStillPublishes(unittest.TestCase):
    """Preserved behaviour: the durable label keeps its current outcome."""

    def test_durable_labels_drift_publishes(self):
        for value in DURABLE:
            with self.subTest(durability=value):
                _, row = assess(value)
                self.assertEqual(row["state"], "DRIFT")
                self.assertIs(row["publish"], True)
                self.assertEqual(row["expected_revision"], HEAD)
                self.assertNotIn("unplanned_reason", row)

    def test_lyte_emitter_shapes(self):
        """The two persistence blocks lyte-services persistence_contract() can emit."""
        postgres = {"backend": "postgresql", "state": "READY", "durability": "DEPLOYMENT_MANAGED",
                    "tenant_workspace_scoped": True}
        sqlite = {"backend": "sqlite", "state": "READY", "durability": "FILE_OR_PROCESS_SCOPED",
                  "tenant_workspace_scoped": True}
        _, row = assess(persistence=postgres)
        self.assertEqual((row["state"], row["publish"]), ("DRIFT", True))
        _, row = assess(persistence=sqlite)
        self.assertEqual((row["state"], row["publish"]), ("UNPLANNED", False))

    def test_converged_is_unaffected_by_durability(self):
        for value in ("DURABLE_VOLUME", "UNKNOWN", None):
            with self.subTest(durability=value):
                _, row = assess(value, tip=SERVED)
                self.assertEqual(row["state"], "CONVERGED")
                self.assertIs(row["publish"], False)


class RefusalCases(unittest.TestCase):
    def assertRefused(self, row, value):
        self.assertEqual(row["state"], "UNPLANNED", f"durability {value!r} was admitted")
        self.assertIs(row["publish"], False)
        self.assertEqual(row["automatic_writer"], "EXCLUDED")
        self.assertEqual(row["unplanned_reason"], "NON_DURABLE_PERSISTENCE")
        self.assertEqual(row["expected_revision"], HEAD)
        self.assertIn(repr(value), row["reason"])


class KnownNonDurableRefused(RefusalCases):
    """Already refused before W46; must stay refused."""

    def test_known_non_durable_labels(self):
        for value in KNOWN_NON_DURABLE:
            with self.subTest(durability=value):
                self.assertRefused(assess(value)[1], value)

    def test_none_and_absent(self):
        self.assertRefused(assess(None)[1], None)
        self.assertRefused(assess()[1], None)                       # key absent
        self.assertRefused(assess(persistence=None)[1], None)       # block absent
        self.assertRefused(assess(persistence="DURABLE_VOLUME")[1], None)  # not a dict


class UnrecognisedLabelsRefused(RefusalCases):
    """The W46 fail-open: unrecognised strings were admitted by the deny-tuple."""

    def test_unknown_and_new_labels(self):
        for value in ("UNKNOWN", "DURABLE", "VOLUME", "DEPLOYMENT", "MANAGED", "NOT_REPORTED",
                      "DURABLE_VOLUME_PENDING", "DEPLOYMENT_MANAGED_PENDING"):
            with self.subTest(durability=value):
                self.assertRefused(assess(value)[1], value)

    def test_empty_and_whitespace(self):
        for value in ("", " ", "\t", "\n"):
            with self.subTest(durability=value):
                self.assertRefused(assess(value)[1], value)

    def test_padded_durable_label(self):
        for value in (" DURABLE_VOLUME", "DURABLE_VOLUME ", "DURABLE_VOLUME\n", "\u200bDURABLE_VOLUME",
                      " DEPLOYMENT_MANAGED", "DEPLOYMENT_MANAGED\t"):
            with self.subTest(durability=value):
                self.assertRefused(assess(value)[1], value)

    def test_case_variants(self):
        for value in ("durable_volume", "Durable_Volume", "DURABLE_volume", "deployment_managed",
                      "Deployment_Managed", "ephemeral", "process_scoped"):
            with self.subTest(durability=value):
                self.assertRefused(assess(value)[1], value)

    def test_non_string_values(self):
        for value in (0, 1, True, b"DURABLE_VOLUME", ["DURABLE_VOLUME"], ("DURABLE_VOLUME",),
                      {"DURABLE_VOLUME": True}):
            with self.subTest(durability=value):
                self.assertRefused(assess(value)[1], value)


class AllowlistShape(unittest.TestCase):
    """The gate is an explicit allowlist and contains nothing a refusal needs."""

    def test_allowlist_is_explicit_and_clean(self):
        conv = load()
        allow = getattr(conv, "DURABLE_PERSISTENCE", None)
        self.assertIsInstance(allow, tuple, "no explicit DURABLE_PERSISTENCE allowlist tuple")
        self.assertEqual(set(allow), set(DURABLE), "allowlist differs from the reviewed durable labels")
        for label in allow:
            self.assertIsInstance(label, str)
            self.assertTrue(label and label == label.strip() and label == label.upper())
            self.assertNotIn(label, KNOWN_NON_DURABLE + ("UNKNOWN",))


if __name__ == "__main__":
    unittest.main()
