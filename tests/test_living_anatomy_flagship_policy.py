from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SERIES_A_POLICY = ROOT / "docs" / "series-a" / "hf-space-keep-list.yaml"
ESTATE_POLICY = ROOT / "docs" / "estate" / "hf-nine-flagship-keep.yaml"
GUARDIAN = ROOT / ".github" / "workflows" / "hf-living-anatomy-guardian.yml"
CONSOLIDATOR = ROOT / "scripts" / "hf_consolidate_fleet.py"
SITE = ROOT / "web" / "living-anatomy.html"

EXPECTED_KEEP = {
    "SZLHOLDINGS/a11oy",
    "SZLHOLDINGS/killinchu",
    "SZLHOLDINGS/terra",
    "SZLHOLDINGS/counsel",
    "SZLHOLDINGS/finance",
    "SZLHOLDINGS/lyte",
    "SZLHOLDINGS/david-leads",
    "SZLHOLDINGS/vertical-services",
}


class LivingAnatomyFlagshipPolicyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.series_a = SERIES_A_POLICY.read_text(encoding="utf-8")
        cls.estate = ESTATE_POLICY.read_text(encoding="utf-8")
        cls.guardian = GUARDIAN.read_text(encoding="utf-8")
        cls.consolidator = CONSOLIDATOR.read_text(encoding="utf-8")
        cls.site = SITE.read_text(encoding="utf-8")

    def test_org_keep_set_and_creator_profile_surface_are_separate(self) -> None:
        for name, policy in (("series-a", self.series_a), ("estate", self.estate)):
            keep_section = policy.split("keep:", 1)[1].split("creator_profile_surface:", 1)[0]
            ids = set(re.findall(r"^\s*- id: (SZLHOLDINGS/[A-Za-z0-9._-]+)$", keep_section, re.MULTILINE))
            with self.subTest(policy=name):
                self.assertEqual(ids, EXPECTED_KEEP)
                self.assertNotIn("betterwithage/anatomy", keep_section)
                self.assertIn("creator_profile_surface:", policy)
                self.assertIn("repository: betterwithage/anatomy", policy)
                self.assertIn("role: living_system_atlas", policy)
                self.assertIn("source: szl-holdings/anatomy", policy)
                self.assertIn("- szl-holdings/szl-second-brain", policy)
                self.assertIn("runtime: https://betterwithage-anatomy.hf.space", policy)

    def test_canonical_org_fleet_count_is_eight(self) -> None:
        self.assertIn("spaces_public_target: 8", self.series_a)
        self.assertIn("spaces_private_target: 49", self.series_a)
        self.assertEqual(8, len(EXPECTED_KEEP))

    def test_resilience_family_has_one_public_keeper_and_honest_states(self) -> None:
        for name, policy in (("series-a", self.series_a), ("estate", self.estate)):
            keep_section = policy.split("keep:", 1)[1].split("creator_profile_surface:", 1)[0]
            retire_section = policy.split("retire_into_killinchu:", 1)[1]
            with self.subTest(policy=name):
                self.assertEqual(1, keep_section.count("- id: SZLHOLDINGS/killinchu"))
                self.assertIn("- defend", keep_section)
                self.assertIn("- maritime", keep_section)
                self.assertIn("- immune", keep_section)
                self.assertIn("state: RETIRED_VERIFIED", retire_section)
                self.assertIn("state: FOLD_PRIVATE_PAUSED_AFTER_LIVE_DEFEND_GATE", retire_section)
                for legacy in (
                    "SZLHOLDINGS/vessels",
                    "SZLHOLDINGS/sentra",
                    "SZLHOLDINGS/immune",
                    "SZLHOLDINGS/immune-lattice",
                    "SZLHOLDINGS/aegis-assurance",
                ):
                    self.assertNotIn(f"- id: {legacy}", keep_section)
                    self.assertIn(f"- id: {legacy}", retire_section)

    def test_consolidator_rejects_foreign_ids_and_preserves_keep_targets(self) -> None:
        self.assertIn('Path("docs/series-a/hf-space-keep-list.yaml")', self.consolidator)
        self.assertIn("policy contains foreign repo ids", self.consolidator)
        self.assertIn("if rid in keep", self.consolidator)
        self.assertIn('row["operations"].append("set_private")', self.consolidator)
        self.assertIn('row["operations"].append("pause_if_supported")', self.consolidator)
        self.assertIn('row["operations"].append("restart")', self.consolidator)

    def test_guardian_targets_creator_profile_and_recovers_live_contract(self) -> None:
        for contract in (
            'cron: "*/30 * * * *"',
            "SPACE_ID: betterwithage/anatomy",
            "SPACE_ORIGIN: https://betterwithage-anatomy.hf.space",
            '"HF_TOKEN",',
            "private=False",
            "api.restart_space(",
            "api.set_space_sleep_time(repo_id=SPACE, sleep_time=-1)",
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

    def test_site_uses_creator_profile_runtime(self) -> None:
        self.assertIn("https://betterwithage-anatomy.hf.space#estate", self.site)
        self.assertIn("https://betterwithage-anatomy.hf.space", self.site)
        self.assertNotIn("szlholdings-anatomy.hf.space", self.site)


if __name__ == "__main__":
    unittest.main(verbosity=2)
