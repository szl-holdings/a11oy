from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SERIES_A_POLICY = ROOT / "docs" / "series-a" / "hf-space-keep-list.yaml"
ESTATE_POLICY = ROOT / "docs" / "estate" / "hf-nine-flagship-keep.yaml"
GUARDIAN = ROOT / ".github" / "workflows" / "hf-living-anatomy-guardian.yml"
CONSOLIDATOR = ROOT / "scripts" / "hf_consolidate_fleet.py"
SITE = ROOT / "web" / "living-anatomy.html"


class LivingAnatomyFlagshipPolicyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.series_a = SERIES_A_POLICY.read_text(encoding="utf-8")
        cls.estate = ESTATE_POLICY.read_text(encoding="utf-8")
        cls.guardian = GUARDIAN.read_text(encoding="utf-8")
        cls.consolidator = CONSOLIDATOR.read_text(encoding="utf-8")
        cls.site = SITE.read_text(encoding="utf-8")

    def test_both_lifecycle_policies_keep_anatomy(self) -> None:
        for name, policy in (
            ("series-a", self.series_a),
            ("estate", self.estate),
        ):
            with self.subTest(policy=name):
                self.assertEqual(1, policy.count("- id: SZLHOLDINGS/anatomy"))
                self.assertIn("role: living_system_atlas", policy)
                self.assertIn("source: szl-holdings/anatomy", policy)
                self.assertIn("- szl-holdings/szl-second-brain", policy)
                self.assertIn("dest: https://a-11-oy.com/living-anatomy", policy)

    def test_canonical_fleet_count_includes_anatomy(self) -> None:
        self.assertIn("spaces_public_target: 10", self.series_a)
        self.assertIn("spaces_private_target: 47", self.series_a)
        self.assertEqual(10, self.series_a.count("  - id: SZLHOLDINGS/"))
        self.assertEqual(10, self.estate.count("  - id: SZLHOLDINGS/"))

    def test_consolidator_consumes_the_canonical_keep_policy(self) -> None:
        self.assertIn('Path("docs/series-a/hf-space-keep-list.yaml")', self.consolidator)
        self.assertIn("if rid in keep", self.consolidator)
        self.assertIn('row["operations"].append("set_private")', self.consolidator)
        self.assertIn('row["operations"].append("pause_if_supported")', self.consolidator)
        self.assertIn('row["operations"].append("restart")', self.consolidator)

    def test_guardian_is_bounded_and_recovers_the_live_contract(self) -> None:
        for contract in (
            'cron: "*/30 * * * *"',
            "SPACE_ID: SZLHOLDINGS/anatomy",
            "private=False",
            "api.restart_space(",
            "api.set_space_sleep_time(repo_id=SPACE, sleep_time=-1)",
            'current_hardware not in {"unknown", "none", "cpu-basic"}',
            "/api/anatomy/v1/living-health?refresh=1",
            "/api/anatomy/v1/brain/health?refresh=1",
            'int(brain.get("chunk_count") or 0) != 575',
            'brain.get("private_graph_nodes_loaded") != 0',
            'brain.get("content_access") != "HANDLES_ONLY"',
            '"hardware_mutation": "FORBIDDEN"',
        ):
            self.assertIn(contract, self.guardian)
        self.assertNotIn("request_space_hardware", self.guardian)
        self.assertNotIn("request_space_storage", self.guardian)

    def test_site_uses_the_same_hugging_face_runtime(self) -> None:
        self.assertIn("https://szlholdings-anatomy.hf.space#estate", self.site)
        self.assertIn("https://szlholdings-anatomy.hf.space", self.site)


if __name__ == "__main__":
    unittest.main(verbosity=2)
