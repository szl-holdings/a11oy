#!/usr/bin/env python3
"""Converge the public taxonomy on Killinchu without changing engine truth."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LANDING = ROOT / "a11oy_landing.html"
MANIFEST = ROOT / "docs" / "strategy" / "living-command-fabric.v1.json"
CONTRACT = ROOT / "tests" / "test_living_command_fabric_frontdoor.py"

VERTICAL_SERVICES_REVISION = "e08231a110fd80f85a61fba82d72ab7f1fe23836"
KILLINCHU_CONSOLIDATION_REVISION = "928a6dace657f8f9e067773d23d5686fe3dcc716"
LOCKED_EIGHT = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
INTERNAL_ENGINES = ["sentra", "lyte", "killinchu", "finance", "terra", "counsel"]
PUBLIC_BODIES = ["terra", "killinchu", "counsel", "finance", "lyte"]


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def regex_once(text: str, pattern: str, replacement: str, *, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return updated


def patch_landing() -> None:
    text = LANDING.read_text(encoding="utf-8")
    replacements = (
        (
            'content="One governed intelligence fabric with six source-bound domain bodies. A11oy connects Living Anatomy, the locked-eight formula kernel, Second Brain evidence handles, qualified inference, policy gates, human approval and verifiable receipts."',
            'content="One governed intelligence fabric with five public domain bodies backed by six internal engines. A11oy connects Living Anatomy, the locked-eight formula kernel, Second Brain evidence handles, qualified inference, policy gates, human approval and verifiable receipts."',
            "meta description",
        ),
        (
            'content="One governed intelligence fabric. Six source-bound domain bodies. Eight locked-proven formula bindings. Every consequential action remains evidence-bound, policy-gated and receipt-verifiable."',
            'content="One governed intelligence fabric. Five public domain bodies. Six internal engines. Eight locked-proven formula bindings. Every consequential action remains evidence-bound, policy-gated and receipt-verifiable."',
            "Open Graph description",
        ),
        ("SIX DOMAIN BODIES", "FIVE PUBLIC DOMAIN BODIES", "hero taxonomy signal"),
        (
            "One intelligence fabric. Six domain bodies. One evidence bloodstream.",
            "One intelligence fabric. Five public domain bodies. Six internal engines. One evidence bloodstream.",
            "Living Fabric heading",
        ),
        (
            "The same governed organism, specialized for six decision environments.",
            "Five public domain bodies, backed by six internal engines.",
            "domain-body heading",
        ),
        (
            "Each body keeps its own domain objects and workflow while sharing evidence handles, policy gates, the complete locked-eight Anatomy binding, proposal-only model authority, human approval, verification and receipts. A reachable link is not automatically marked ready; live state remains a runtime proof.",
            "Each public body keeps its own domain objects and workflow while sharing evidence handles, policy gates, the complete locked-eight Anatomy binding, proposal-only model authority, human approval, verification and receipts. Sentra remains an internal defensive engine inside Killinchu rather than a competing public product. A reachable link is not automatically marked ready; live state remains a runtime proof.",
            "domain-body explanation",
        ),
        (
            "Three commercial flagships anchor the public line. Six source-bound domain bodies inherit the same evidence contract and graduate only when canonical source, runtime revision, domain probes and claim labels agree. Hub cards remain artifacts rather than automatic products. Λ uniqueness is <b>Conjecture&nbsp;1</b> — advisory, never a theorem, never green.",
            "Three commercial flagships anchor the public line. Five public domain bodies, backed by six internal engines, inherit the same evidence contract and graduate only when canonical source, runtime revision, domain probes and claim labels agree. Aegis is an internal Killinchu capability plane; Sentra, Immune and Vessels do not become competing public products. Hub cards remain artifacts rather than automatic products. Λ uniqueness is <b>Conjecture&nbsp;1</b> — advisory, never a theorem, never green.",
            "flagship graduation explanation",
        ),
        ('id="body-lyte" data-index="06"', 'id="body-lyte" data-index="05"', "Lyte index"),
    )
    for old, new, label in replacements:
        text = replace_once(text, old, new, label=label)

    killinchu_card = (
        '    <article class="body-card" id="body-killinchu" data-index="02">'
        '<p class="body-domain">Cyber-physical resilience intelligence</p><h3>Killinchu</h3>'
        '<p>One public resilience product with five capability planes: Aegis is the portfolio lens; Sentra / Defend is the defensive engine; IMMUNE carries admission, tripwires and signed authority; Vessels / Maritime carries fleet intelligence; Counter-UAS / Airspace carries the mission pack. Every path remains evidence-bound, human-authorized and independently verified.</p>'
        '<div class="body-flow"><span>DETECT</span><span>CORRELATE</span><span>TRACK</span><span>SCREEN</span><span>AUTHORIZE</span><span>VERIFY</span><span>RECEIPT</span></div>'
        '<div class="body-truth"><span>COMPLETE LOCKED-8</span><span>FIVE CAPABILITY PLANES</span><span>ONE PUBLIC RUNTIME</span></div>'
        '<div class="body-links"><a href="https://github.com/szl-holdings/killinchu" rel="noopener">Source ↗</a><a href="https://huggingface.co/spaces/SZLHOLDINGS/killinchu" rel="noopener">Product surface ↗</a></div></article>\n'
    )
    text = regex_once(
        text,
        r'    <article class="body-card" id="body-sentra"[^\n]*</article>\n',
        killinchu_card,
        label="replace standalone Aegis/Sentra card",
    )
    text = regex_once(
        text,
        r'    <article class="body-card" id="body-vessels"[^\n]*</article>\n',
        "",
        label="remove duplicate Vessels public card",
    )

    if 'id="body-sentra"' in text or 'id="body-vessels"' in text:
        raise RuntimeError("legacy standalone body identifiers survived convergence")
    if text.count('class="body-card"') != 5:
        raise RuntimeError("public body-card count is not exactly five")
    LANDING.write_text(text, encoding="utf-8")


def clone(value: Any) -> Any:
    return json.loads(json.dumps(value))


def patch_manifest() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    verticals = manifest.get("verticals")
    if not isinstance(verticals, list):
        raise RuntimeError("manifest verticals is not a list")
    by_slug = {row.get("slug"): row for row in verticals if isinstance(row, dict)}
    expected = {"terra", "sentra", "counsel", "finance", "vessels", "lyte"}
    if set(by_slug) != expected:
        raise RuntimeError(f"unexpected pre-convergence vertical set: {sorted(by_slug)}")

    killinchu = {
        "slug": "killinchu",
        "brand": "Killinchu",
        "domain": "cyber_physical_resilience_intelligence",
        "canonical_source": "szl-holdings/killinchu",
        "canonical_revision": KILLINCHU_CONSOLIDATION_REVISION,
        "service_source": "szl-holdings/vertical-services",
        "service_revision": VERTICAL_SERVICES_REVISION,
        "runtime": "https://szlholdings-killinchu.hf.space",
        "workflow": [
            "DETECT",
            "CORRELATE",
            "TRACK",
            "SCREEN",
            "AUTHORIZE",
            "VERIFY",
            "RECEIPT",
        ],
        "decision_surface": [
            "resilience operating picture",
            "attack and mission paths",
            "fleet and airspace watch",
            "human authority queue",
            "evidence ledger",
        ],
        "capability_planes": {
            "aegis": "internal portfolio and assurance lens",
            "sentra_defend": "defensive control-plane engine",
            "immune": "admission, tripwires, signed authority and tamper-evident evidence",
            "vessels_maritime": "fleet, sanctions, ownership, route and voyage intelligence",
            "counter_uas_airspace": "counter-UAS and airspace mission pack",
        },
        "internal_engines": ["sentra", "killinchu"],
        "aliases": ["aegis", "immune", "vessels"],
        "formula_binding": "complete_locked_eight_via_shared_anatomy",
        "public_product_boundary": "sole_public_cyber_physical_resilience_runtime",
        "effectors": "SIMULATED_OR_OPERATOR_OWNED_UNLESS_SEPARATELY_PROVED",
    }

    manifest["verticals"] = [
        clone(by_slug["terra"]),
        killinchu,
        clone(by_slug["counsel"]),
        clone(by_slug["finance"]),
        clone(by_slug["lyte"]),
    ]
    manifest["public_product_taxonomy"] = {
        "public_domain_body_count": 5,
        "public_domain_bodies": PUBLIC_BODIES,
        "internal_engine_count": 6,
        "internal_engines": INTERNAL_ENGINES,
        "independent_domain_spaces": ["terra", "counsel", "finance", "lyte"],
        "resilience_product_space": "killinchu",
        "folded_into_killinchu": ["aegis", "sentra", "immune", "vessels"],
        "rule": "A capability alias or engine is not a separate public product authority.",
    }
    authorities = manifest.setdefault("authorities", {})
    authorities.setdefault("vertical_services", {})["revision"] = VERTICAL_SERVICES_REVISION
    authorities["killinchu"] = {
        "repository": "szl-holdings/killinchu",
        "revision": KILLINCHU_CONSOLIDATION_REVISION,
        "role": "sole public cyber-physical resilience runtime; Aegis, Sentra/Defend, IMMUNE, Vessels/Maritime and Counter-UAS/Airspace are capability planes",
    }
    lean = authorities.get("lean_kernel", {})
    if lean.get("locked_proven_ids") != LOCKED_EIGHT:
        raise RuntimeError("locked-eight authority changed unexpectedly")

    wave = manifest.setdefault("wave_1", {})
    wave["site"] = (
        "Expose Living Anatomy and five public domain bodies backed by six internal engines, "
        "while preserving the buyer hero and runtime evidence instrument."
    )
    wave["publisher_repair"] = (
        "Bind the frontier-v3 canonical writer to vertical-services@"
        + VERTICAL_SERVICES_REVISION
        + " and fold Aegis/Sentra/Immune/Vessels into Killinchu public authority."
    )
    wave["next_vertical_order"] = [
        "killinchu_resilience",
        "lyte",
        "terra",
        "prism_counsel",
        "puriq_finance",
        "carlota_jo_incubation",
    ]
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def patch_contract() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    replacements = (
        (
            'PUBLISHER = ROOT / "scripts" / "hf_publish_vertical_services.py"',
            'PUBLISHER = ROOT / "scripts" / "hf_publish_vertical_services_frontier_v3.py"',
            "publisher target",
        ),
        (
            'PUBLISHER_TEST = ROOT / "tests" / "test_hf_publish_vertical_flagships_v4.py"',
            'PUBLISHER_TEST = ROOT / "tests" / "test_hf_frontier_v3_rebase.py"',
            "publisher contract target",
        ),
        (
            'VERTICALS = ["terra", "sentra", "counsel", "finance", "vessels", "lyte"]',
            'VERTICALS = ["terra", "killinchu", "counsel", "finance", "lyte"]',
            "public vertical list",
        ),
        (
            'VERTICAL_REVISION = "1c6d941da172e2132d3c7818911bd8669ca28f00"',
            f'VERTICAL_REVISION = "{VERTICAL_SERVICES_REVISION}"',
            "vertical source revision",
        ),
        (
            '"One intelligence fabric. Six domain bodies. One evidence bloodstream.",',
            '"One intelligence fabric. Five public domain bodies. Six internal engines. One evidence bloodstream.",',
            "heading assertion",
        ),
        ('"SIX DOMAIN BODIES",', '"FIVE PUBLIC DOMAIN BODIES",', "hero signal assertion"),
        (
            "def test_six_domain_bodies_match_the_machine_readable_manifest(self) -> None:",
            "def test_five_public_bodies_match_six_internal_engines(self) -> None:",
            "test name",
        ),
        (
            "self.assertEqual(self.html.count('class=\"body-card\"'), 6)",
            "self.assertEqual(self.html.count('class=\"body-card\"'), 5)",
            "body-card count assertion",
        ),
    )
    for old, new, label in replacements:
        text = replace_once(text, old, new, label=label)

    anchor = """            self.assertTrue(vertical[\"canonical_source\"])
            self.assertTrue(vertical[\"service_source\"])

    def test_clean_room_policy_rejects_proprietary_source_copying(self) -> None:
"""
    injected = """            self.assertTrue(vertical[\"canonical_source\"])
            self.assertTrue(vertical[\"service_source\"])

        taxonomy = self.manifest[\"public_product_taxonomy\"]
        self.assertEqual(taxonomy[\"public_domain_body_count\"], 5)
        self.assertEqual(taxonomy[\"public_domain_bodies\"], VERTICALS)
        self.assertEqual(taxonomy[\"internal_engine_count\"], 6)
        self.assertEqual(
            taxonomy[\"internal_engines\"],
            [\"sentra\", \"lyte\", \"killinchu\", \"finance\", \"terra\", \"counsel\"],
        )
        self.assertEqual(
            taxonomy[\"folded_into_killinchu\"],
            [\"aegis\", \"sentra\", \"immune\", \"vessels\"],
        )
        self.assertNotIn('id=\"body-sentra\"', self.html)
        self.assertNotIn('id=\"body-vessels\"', self.html)
        killinchu = next(row for row in self.manifest[\"verticals\"] if row[\"slug\"] == \"killinchu\")
        self.assertEqual(killinchu[\"internal_engines\"], [\"sentra\", \"killinchu\"])
        self.assertEqual(
            set(killinchu[\"capability_planes\"]),
            {\"aegis\", \"sentra_defend\", \"immune\", \"vessels_maritime\", \"counter_uas_airspace\"},
        )

    def test_clean_room_policy_rejects_proprietary_source_copying(self) -> None:
"""
    text = replace_once(text, anchor, injected, label="taxonomy test insertion")
    CONTRACT.write_text(text, encoding="utf-8")


def main() -> int:
    patch_landing()
    patch_manifest()
    patch_contract()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
