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

    def test_both_lifecycle_policies_keep_creator_profile_anatomy(self) -> None:
        for name, policy in (
            ("series-a", self.series_a),
            ("estate", self.estate),
        ):
            with self.subTest(policy=name):
                self.assertEqual(1, policy.count("- id: betterwithage/anatomy"))
                self.assertIn("owner_class: creator_profile", policy)
                self.assertIn("role: living_system_atlas", policy)
                self.assertIn("source: szl-holdings/anatomy", policy)
                self.assertIn("- szl-holdings/szl-second-brain", policy)
                self.assertIn("dest: https://a-11-oy.com/living-anatomy", policy)
                self.assertIn(
                    "live_origin: https://betterwithage-anatomy.hf.space",
                    policy,
                )
                self.assertNotIn("- id: SZLHOLDINGS/anatomy", policy)

    def test_canonical_fleet_count_separates_org_and_creator_authority(self) -> None:
        self.assertIn("spaces_public_target_org: 7", self.series_a)
        self.assertIn("spaces_private_target_org: 50", self.series_a)
        self.assertIn("spaces_public_target_creator: 1", self.series_a)
        self.assertIn("spaces_public_target_total: 8", self.series_a)
        series_keep = self.series_a.split("keep:", 1)[1].split(
            "retire_into_killinchu:", 1
        )[0]
        estate_keep = self.estate.split("keep:", 1)[1].split(
            "retire_into_killinchu:", 1
        )[0]
        self.assertEqual(7, series_keep.count("- id: SZLHOLDINGS/"))
        self.assertEqual(7, estate_keep.count("- id: SZLHOLDINGS/"))
        self.assertEqual(1, series_keep.count("- id: betterwithage/"))
        self.assertEqual(1, estate_keep.count("- id: betterwithage/"))

    def test_resilience_family_has_one_public_keeper(self) -> None:
        for name, policy in (
            ("series-a", self.series_a),
            ("estate", self.estate),
        ):
            keep_section = policy.split("keep:", 1)[1].split(
                "retire_into_killinchu:", 1
            )[0]
            retire_section = policy.split("retire_into_killinchu:", 1)[1]
            with self.subTest(policy=name):
                self.assertEqual(
                    1, keep_section.count("- id: SZLHOLDINGS/killinchu")
                )
                for legacy in (
                    "SZLHOLDINGS/vessels",
                    "SZLHOLDINGS/sentra",
                    "SZLHOLDINGS/immune",
                    "SZLHOLDINGS/immune-lattice",
                    "SZLHOLDINGS/aegis-assurance",
                ):
                    self.assertNotIn(f"- id: {legacy}", keep_section)
                    self.assertIn(f"- id: {legacy}", retire_section)

    def test_consolidator_consumes_the_canonical_keep_policy(self) -> None:
        self.assertIn(
            'Path("docs/series-a/hf-space-keep-list.yaml")', self.consolidator
        )
        self.assertIn("if rid in keep", self.consolidator)
        self.assertIn('row["operations"].append("set_private")', self.consolidator)
        self.assertIn(
            'row["operations"].append("pause_if_supported")', self.consolidator
        )
        self.assertIn('row["operations"].append("restart")', self.consolidator)

    def test_guardian_is_bounded_and_recovers_exact_creator_contract(self) -> None:
        for contract in (
            'cron: "*/30 * * * *"',
            "SPACE_ID: betterwithage/anatomy",
            "SPACE_ORIGIN: https://betterwithage-anatomy.hf.space",
            "SOURCE_REPOSITORY: szl-holdings/anatomy",
            "private=False",
            "api.restart_space(",
            "api.set_space_sleep_time(repo_id=SPACE, sleep_time=-1)",
            'current_hardware not in {',
            "/api/anatomy/v1/living-health?refresh=1",
            "/api/anatomy/v1/brain/health?refresh=1",
            'int(brain.get("chunk_count") or 0) != 575',
            'brain.get("private_graph_nodes_loaded") != 0',
            'brain.get("content_access") != "HANDLES_ONLY"',
            'source.get("alignment_state") != "SOURCE_BOUND_DEPLOYMENT"',
            'source.get("source", {}).get("repository") != SOURCE_REPOSITORY',
            "anatomy_revision != source_main",
            "deployed_hf_revision != current_hf_revision",
            '"hardware_mutation": "FORBIDDEN"',
        ):
            self.assertIn(contract, self.guardian)
        self.assertNotIn("request_space_hardware", self.guardian)
        self.assertNotIn("request_space_storage", self.guardian)
        self.assertNotIn("SZLHOLDINGS/anatomy", self.guardian)
        self.assertNotIn("szlholdings-anatomy.hf.space", self.guardian)

    def test_site_uses_the_same_creator_profile_runtime(self) -> None:
        self.assertIn("https://betterwithage-anatomy.hf.space#estate", self.site)
        self.assertIn("https://betterwithage-anatomy.hf.space", self.site)
        self.assertIn('const ANATOMY="https://betterwithage-anatomy.hf.space"', self.site)
        self.assertNotIn("https://szlholdings-anatomy.hf.space", self.site)

    def test_site_defaults_to_same_origin_holo_brain(self) -> None:
        self.assertIn('src="/holographic#brain"', self.site)
        self.assertIn('const HOLO="/holographic#brain"', self.site)
        self.assertIn('const A="/api/a11oy/v1"', self.site)
        self.assertIn('A+"/second-brain"', self.site)
        self.assertIn('A+"/brain"', self.site)
        self.assertIn('A+"/formulas"', self.site)
        self.assertIn('A+"/ouroboros"', self.site)
        self.assertIn('A+"/codex"', self.site)
        self.assertIn('id="c_brain"', self.site)
        self.assertIn('id="c_formulas"', self.site)
        self.assertIn('id="c_ouro"', self.site)
        self.assertNotIn("Extra text starts", self.site)
        self.assertIn("Λ = Conjecture 1", self.site)
        self.assertIn("{F1,F4,F7,F11,F12,F18,F19,F22}", self.site)


class LivingAnatomyBackendAliasContract(unittest.TestCase):
    def test_serve_registers_honest_aliases(self) -> None:
        serve = (ROOT / "serve.py").read_text(encoding="utf-8")
        for route in (
            '@app.get("/api/a11oy/v1/second-brain")',
            '@app.get("/api/a11oy/v1/codex")',
            '@app.get("/api/a11oy/v1/anatomy")',
        ):
            self.assertIn(route, serve)
        self.assertIn('"alias_of": "/api/a11oy/v1/brain"', serve)
        self.assertIn('"alias_of": "/api/a11oy/v1/formulas"', serve)
        self.assertIn("This path is an alias, not a second index", serve)
        self.assertIn("Locked-8 stays 8", serve)
        self.assertIn("Does not claim the creator-profile anatomy Space is LIVE", serve)
        self.assertIn("Lambda remains Conjecture 1", serve)


if __name__ == "__main__":
    unittest.main(verbosity=2)
