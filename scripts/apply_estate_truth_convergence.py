#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Converge public identity, deployment pins, monitors, and estate manifests.

This is an exact, fail-closed migration transaction. It does not mutate provider
state. Provider consolidation is a separate, receipt-bound operation after this
source truth lands and deploys.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERTICAL_SERVICES_REVISION = "c24ef61716f173e48d95dad61408d9fa065f0204"
KILLINCHU_REVISION = "c797b4d1ea336c02f08ddaf72c01b152f3c04d4d"
OLD_VERTICAL_SERVICES_REVISION = "83edba5c5e730c91d8f5f0a6531213fb860677af"
ANATOMY_REPOSITORY = "betterwithage/anatomy"
ANATOMY_ORIGIN = "https://betterwithage-anatomy.hf.space"
OLD_ANATOMY_REPOSITORY = "SZLHOLDINGS/anatomy"
OLD_ANATOMY_ORIGIN = "https://szlholdings-anatomy.hf.space"


def path(name: str) -> Path:
    return ROOT / name


def read(name: str) -> str:
    return path(name).read_text(encoding="utf-8")


def write(name: str, value: str) -> None:
    path(name).write_text(value, encoding="utf-8")
    print(f"UPDATED {name}")


def replace_exact(
    name: str,
    old: str,
    new: str,
    *,
    expected: int = 1,
) -> None:
    value = read(name)
    observed = value.count(old)
    if observed != expected:
        raise SystemExit(
            f"{name}: expected {expected} occurrence(s), observed {observed}: {old!r}"
        )
    write(name, value.replace(old, new, expected))


def replace_all_required(name: str, old: str, new: str) -> None:
    value = read(name)
    observed = value.count(old)
    if observed < 1:
        raise SystemExit(f"{name}: required anchor absent: {old!r}")
    write(name, value.replace(old, new))


def rewrite_policies() -> None:
    series_a = '''as_of: "2026-09-04T03:45:00Z"
state: APPLY
action: pause_and_private_then_gated_delete
product: https://a-11-oy.com/products/
proof: https://a11oy.net
hub: https://huggingface.co/SZLHOLDINGS
counts:
  spaces_total_observed: 57
  spaces_public_target: 8
  spaces_private_target: 49
keep:
  - id: SZLHOLDINGS/a11oy
    role: command
    dest: https://a-11-oy.com
  - id: SZLHOLDINGS/killinchu
    role: cyber_physical_resilience
    dest: https://szlholdings-killinchu.hf.space
    source: szl-holdings/killinchu
    portfolio_labels:
      - aegis
    operational_capability_planes:
      - defend
      - maritime
      - counter-uas
      - evidence
    migration_gated:
      - immune
      - immune-lattice
  - id: SZLHOLDINGS/terra
    role: real_estate
  - id: SZLHOLDINGS/counsel
    role: legal
  - id: SZLHOLDINGS/finance
    role: finance
  - id: SZLHOLDINGS/lyte
    role: business_observability
  - id: SZLHOLDINGS/david-leads
    role: insurance
  - id: SZLHOLDINGS/vertical-services
    role: shared_vertical_runtime
    dest: https://szlholdings-vertical-services.hf.space
    source: szl-holdings/vertical-services
creator_profile_surface:
  repository: betterwithage/anatomy
  role: living_system_atlas
  dest: https://a-11-oy.com/living-anatomy
  runtime: https://betterwithage-anatomy.hf.space
  source: szl-holdings/anatomy
  dependencies:
    - szl-holdings/szl-second-brain
retire_into_killinchu:
  - id: SZLHOLDINGS/vessels
    state: RETIRED_VERIFIED
    target_route: https://szlholdings-killinchu.hf.space/vessels
  - id: SZLHOLDINGS/aegis-assurance
    state: RETIRED_VERIFIED
    target_route: https://szlholdings-killinchu.hf.space/resilience
  - id: SZLHOLDINGS/sentra
    state: FOLD_PRIVATE_PAUSED_AFTER_LIVE_DEFEND_GATE
    target_route: https://szlholdings-killinchu.hf.space/defend
  - id: SZLHOLDINGS/immune
    state: MIGRATION_REQUIRED
    target_route: https://szlholdings-killinchu.hf.space/immune
  - id: SZLHOLDINGS/immune-lattice
    state: PARITY_AUDIT_REQUIRED
    target_route: https://szlholdings-killinchu.hf.space/immune
org_card: SZLHOLDINGS/README
previous_execution:
  workflow_run: 33687884541
  attempt: 2
  artifact: hf-nine-flagship-consolidation-33687884541-2
  artifact_sha256: 043aba51a8386038620aca8ecbb122795d51e4317d46d2f513c437413312d916
  terminal_green_for_previous_policy: true
retirement_gate:
  - source_captured
  - product_captured
  - evidence_captured
  - publisher_removed
  - replacement_verified
  - no_unique_secret_dependency
  - secret_free_retirement_receipt
note: "Owner decision 2026-09-04: Killinchu is the sole public cyber-physical resilience product. Aegis is a portfolio label. Defend/Sentra, Maritime/Vessels, Counter-UAS/Airspace, and Evidence/receipts are operational capability planes. IMMUNE remains migration-gated until its distinct admission, tripwire, and signed-authority contracts pass parity. The creator-profile Living Anatomy surface remains source-bound and public/running with a handles-only Second Brain projection."
'''
    estate = '''as_of: "2026-09-04"
state: APPLY
policy_version: cyber-resilience-consolidation-v2
product: https://a-11-oy.com/products/
proof: https://a11oy.net
keep:
  - id: SZLHOLDINGS/a11oy
    role: command
  - id: SZLHOLDINGS/killinchu
    role: cyber_physical_resilience
    source: szl-holdings/killinchu
    portfolio_labels:
      - aegis
    operational_capability_planes:
      - defend
      - maritime
      - counter-uas
      - evidence
    migration_gated:
      - immune
      - immune-lattice
  - id: SZLHOLDINGS/terra
    role: real_estate
  - id: SZLHOLDINGS/counsel
    role: legal
  - id: SZLHOLDINGS/finance
    role: finance
  - id: SZLHOLDINGS/lyte
    role: business_observability
  - id: SZLHOLDINGS/david-leads
    role: insurance
  - id: SZLHOLDINGS/vertical-services
    role: shared_vertical_runtime
    source: szl-holdings/vertical-services
creator_profile_surface:
  repository: betterwithage/anatomy
  role: living_system_atlas
  dest: https://a-11-oy.com/living-anatomy
  runtime: https://betterwithage-anatomy.hf.space
  source: szl-holdings/anatomy
  dependencies:
    - szl-holdings/szl-second-brain
retire_into_killinchu:
  - id: SZLHOLDINGS/vessels
    state: RETIRED_VERIFIED
  - id: SZLHOLDINGS/aegis-assurance
    state: RETIRED_VERIFIED
  - id: SZLHOLDINGS/sentra
    state: FOLD_PRIVATE_PAUSED_AFTER_LIVE_DEFEND_GATE
  - id: SZLHOLDINGS/immune
    state: MIGRATION_REQUIRED
  - id: SZLHOLDINGS/immune-lattice
    state: PARITY_AUDIT_REQUIRED
'''
    write("docs/series-a/hf-space-keep-list.yaml", series_a)
    write("docs/estate/hf-nine-flagship-keep.yaml", estate)


def rewrite_anatomy_operational_references() -> None:
    operational_files = (
        "README.md",
        "web/living-anatomy.html",
        "a11oy_landing.html",
        "docs/state-plane-continuity.v1.json",
        "a11oy_ecosystem_atlas.py",
        "pages/organs-integrity.html",
        "pages/atelier.html",
        "docs/estate/HF_FLAGSHIP_MIGRATION.md",
        "docs/series-a/HF_SPACE_CONSOLIDATION.md",
        ".github/workflows/hf-living-anatomy-guardian.yml",
    )
    for name in operational_files:
        value = read(name)
        updated = value.replace(OLD_ANATOMY_ORIGIN, ANATOMY_ORIGIN)
        updated = updated.replace(OLD_ANATOMY_REPOSITORY, ANATOMY_REPOSITORY)
        if updated == value:
            raise SystemExit(f"{name}: no current Anatomy target was replaced")
        write(name, updated)

    guardian = read(".github/workflows/hf-living-anatomy-guardian.yml")
    old_order = '''          TOKEN_KEYS = (
              "HF_ORG_TOKEN",
              "HF_WRITE_TOKEN",
              "HF_TOKEN",
              "HUGGINGFACE_TOKEN",
              "HUGGING_FACE_HUB_TOKEN",
          )'''
    new_order = '''          TOKEN_KEYS = (
              "HF_TOKEN",
              "HUGGINGFACE_TOKEN",
              "HUGGING_FACE_HUB_TOKEN",
              "HF_WRITE_TOKEN",
              "HF_ORG_TOKEN",
          )'''
    if guardian.count(old_order) != 1:
        raise SystemExit("guardian: creator-profile token priority anchor drifted")
    guardian = guardian.replace(old_order, new_order)
    guardian = guardian.replace(
        '"schema": "szl.hf-living-anatomy-guardian/v1"',
        '"schema": "szl.hf-living-anatomy-guardian/v2"',
    )
    guardian = guardian.replace(
        '"User-Agent": "szl-living-anatomy-guardian/1.0"',
        '"User-Agent": "szl-living-anatomy-guardian/2.0"',
    )
    write(".github/workflows/hf-living-anatomy-guardian.yml", guardian)

    hologram = read("szl3d_holographic.py")
    old_block = '''    "organ:killinchu": "https://szlholdings-killinchu.hf.space/healthz",
    "organ:anatomy": "https://szlholdings-anatomy.hf.space/healthz",
    "organ:amaru": "https://szlholdings-amaru.hf.space/healthz",
    "organ:sentra": "https://szlholdings-sentra.hf.space/healthz",'''
    new_block = '''    "organ:killinchu": "https://szlholdings-killinchu.hf.space/api/killinchu/healthz",
    "plane:defend": "https://szlholdings-killinchu.hf.space/api/defend/readyz",
    "organ:anatomy": "https://betterwithage-anatomy.hf.space/api/anatomy/v1/living-health?refresh=1",
    "fabric:vertical-services": "https://szlholdings-vertical-services.hf.space/healthz",'''
    if hologram.count(old_block) != 1:
        raise SystemExit("szl3d_holographic.py: live URL block drifted")
    write("szl3d_holographic.py", hologram.replace(old_block, new_block))


def rewrite_smoke_monitor() -> None:
    workflow = '''# SPDX-License-Identifier: Apache-2.0
name: Synthetic Runtime Monitor

"on":
  schedule:
    - cron: "7 */6 * * *"
  workflow_dispatch:
    inputs:
      reason:
        description: Manual trigger reason
        required: false
        default: manual check

permissions:
  contents: read

concurrency:
  group: synthetic-runtime-monitor
  cancel-in-progress: true

jobs:
  smoke:
    name: Exact public runtime probes
    runs-on: ubuntu-24.04
    timeout-minutes: 12
    steps:
      - name: Harden runner
        uses: step-security/harden-runner@05e31511f85b41b11d1cf0ef85d0992719546e2c # v2.21.0
        with:
          egress-policy: audit

      - name: Probe public product, capability, fabric, and Anatomy contracts
        shell: bash
        run: |
          set -u
          PASS=0
          FAIL=0
          CRITICAL_FAIL=0
          FAILURES=""

          check() {
            local name="$1"
            local url="$2"
            local critical="$3"
            local code="000"
            for attempt in 1 2 3; do
              code=$(curl -L -o /dev/null -sS -w '%{http_code}' --max-time 15 \
                -H 'Accept: application/json,text/html;q=0.8' \
                -H 'Cache-Control: no-cache' \
                "${url}${url#*\?}" >/dev/null 2>&1 && true)
              # The command above is deliberately not used for the result because
              # shell redirection can swallow curl's formatter on some runners.
              code=$(curl -L -o /dev/null -s -w '%{http_code}' --max-time 15 \
                -H 'Accept: application/json,text/html;q=0.8' \
                -H 'Cache-Control: no-cache' "$url" || printf '000')
              if [ "$code" = "200" ]; then
                echo "PASS $name => 200 (attempt $attempt)"
                PASS=$((PASS+1))
                return 0
              fi
              sleep 8
            done
            echo "FAIL $name => $code (sustained)"
            FAIL=$((FAIL+1))
            FAILURES="$FAILURES\n- $name: HTTP $code"
            if [ "$critical" = "critical" ]; then
              CRITICAL_FAIL=$((CRITICAL_FAIL+1))
            fi
            return 0
          }

          check "A11oy product root" "https://a-11-oy.com/" critical
          check "A11oy runtime readiness" "https://szlholdings-a11oy.hf.space/api/a11oy/readyz" critical
          check "A11oy command console" "https://szlholdings-a11oy.hf.space/console" advisory
          check "Killinchu product root" "https://szlholdings-killinchu.hf.space/" critical
          check "Killinchu health" "https://szlholdings-killinchu.hf.space/api/killinchu/healthz" critical
          check "Killinchu Defend" "https://szlholdings-killinchu.hf.space/defend" critical
          check "Killinchu Defend readiness" "https://szlholdings-killinchu.hf.space/api/defend/readyz" critical
          check "Vertical-services health" "https://szlholdings-vertical-services.hf.space/healthz" critical
          check "Vertical-services readiness" "https://szlholdings-vertical-services.hf.space/readyz" critical
          check "Living Anatomy root" "https://betterwithage-anatomy.hf.space/" critical
          check "Living Anatomy combined readiness" "https://betterwithage-anatomy.hf.space/api/anatomy/v1/living-health?refresh=1" critical
          check "Living Anatomy Second Brain" "https://betterwithage-anatomy.hf.space/api/anatomy/v1/brain/health?refresh=1" critical

          {
            echo "## Synthetic runtime monitor"
            echo
            echo "- Passed: $PASS"
            echo "- Failed: $FAIL"
            echo "- Critical failures: $CRITICAL_FAIL"
            if [ "$FAIL" -gt 0 ]; then
              printf '%b\n' "$FAILURES"
            fi
          } >> "$GITHUB_STEP_SUMMARY"

          if [ "$CRITICAL_FAIL" -gt 0 ]; then
            echo "::error::$CRITICAL_FAIL critical public contract(s) failed:$FAILURES"
            exit 1
          fi
          if [ "$FAIL" -gt 0 ]; then
            echo "::warning::$FAIL advisory probe(s) failed:$FAILURES"
          fi
'''
    # Remove an accidental no-op probe from the rendered workflow while keeping
    # the human-readable function compact and deterministic.
    workflow = workflow.replace(
        '''            for attempt in 1 2 3; do
              code=$(curl -L -o /dev/null -sS -w '%{http_code}' --max-time 15 \\
                -H 'Accept: application/json,text/html;q=0.8' \\
                -H 'Cache-Control: no-cache' \\
                "${url}${url#*\\?}" >/dev/null 2>&1 && true)
              # The command above is deliberately not used for the result because
              # shell redirection can swallow curl's formatter on some runners.
              code=$(curl -L -o /dev/null -s -w '%{http_code}' --max-time 15 \\
''',
        '''            for attempt in 1 2 3; do
              code=$(curl -L -o /dev/null -s -w '%{http_code}' --max-time 15 \\
''',
    )
    write(".github/workflows/smoke-monitor.yml", workflow)


def rewrite_landing() -> None:
    name = "a11oy_landing.html"
    text = read(name)
    start = text.index('<article class="body-card" id="body-killinchu"')
    end = text.index("</article>", start) + len("</article>")
    article = text[start:end]

    p_anchor = "<h3>Killinchu</h3><p>"
    p_start = article.index(p_anchor) + len(p_anchor)
    p_end = article.index("</p>", p_start)
    paragraph = (
        "One public cyber-physical resilience product. Aegis is the portfolio "
        "lens; Sentra powers the live Defend capability; Vessels powers the live "
        "Maritime capability; Counter-UAS powers the live Airspace mission pack; "
        "and the evidence plane binds decisions to receipts. IMMUNE remains "
        "migration-gated until its distinct admission, tripwire and signed-authority "
        "contracts pass parity. Consequential effects remain simulated or "
        "operator-owned, human-authorized and independently verified."
    )
    article = article[:p_start] + paragraph + article[p_end:]

    truth_start = article.index('<div class="body-truth">')
    truth_end = article.index("</div>", truth_start) + len("</div>")
    truth = (
        '<div class="body-truth"><span>4 OPERATIONAL PLANES</span>'
        '<span>IMMUNE MIGRATION-GATED</span><span>SIMULATED EFFECTS</span>'
        '<span>ONE PUBLIC RUNTIME</span></div>'
    )
    article = article[:truth_start] + truth + article[truth_end:]

    links_start = article.index('<div class="body-links">')
    links_end = article.index("</div>", links_start)
    if "https://szlholdings-killinchu.hf.space/defend" not in article:
        defend_link = (
            '<a href="https://szlholdings-killinchu.hf.space/defend" '
            'rel="noopener">Open Defend →</a>'
        )
        article = article[:links_end] + defend_link + article[links_end:]

    text = text[:start] + article + text[end:]
    text = text.replace(
        '<span class="chip down" id="kc-runtime"><span class="dot"></span>RUNTIME UNAVAILABLE</span>',
        '<span class="chip software" id="kc-runtime"><span class="dot"></span>SOURCE-VERIFIED · c797b4d</span>',
        1,
    )
    note_start = text.index('<p class="kc-note" id="kc-runtime-note">')
    note_end = text.index("</p>", note_start) + len("</p>")
    note = (
        '<p class="kc-note" id="kc-runtime-note">Protected deployment gates '
        'verified Killinchu revision <b>c797b4d</b>, including <code>/defend</code> '
        'and its readiness/source contracts. This browser independently probes '
        'current reachability; a failed visit reports UNAVAILABLE without erasing '
        'the last exact-source deployment witness.</p>'
    )
    text = text[:note_start] + note + text[note_end:]
    text = text.replace(OLD_ANATOMY_ORIGIN, ANATOMY_ORIGIN)
    text = text.replace(OLD_ANATOMY_REPOSITORY, ANATOMY_REPOSITORY)
    write(name, text)


def rewrite_publishers() -> None:
    v4 = "scripts/hf_publish_vertical_services_intelligence_v4.py"
    replace_exact(v4, OLD_VERTICAL_SERVICES_REVISION, VERTICAL_SERVICES_REVISION)
    replace_exact(v4, '    "immune": "sentra",\n', '    "defend": "sentra",\n')
    replace_exact(
        v4,
        '    "/api/verticals/sentra/intelligence",\n',
        '    "/api/verticals/sentra/intelligence",\n    "/api/verticals/defend/intelligence",\n',
    )
    replace_exact(
        v4,
        '    "/intelligence/sentra",\n',
        '    "/intelligence/sentra",\n    "/intelligence/defend",\n',
    )

    v3 = "scripts/hf_publish_vertical_services_frontier_v3.py"
    replace_exact(v3, "e08231a110fd80f85a61fba82d72ab7f1fe23836", VERTICAL_SERVICES_REVISION)
    replace_exact(v3, 'EXPECTED_VERSION = "2.1.0"', 'EXPECTED_VERSION = "2.2.0"')
    replace_exact(v3, '    "/api/verticals/immune/frontier",\n', '    "/api/verticals/defend/frontier",\n')
    replace_exact(v3, '    "/experience/aegis",\n', '    "/experience/defend",\n')
    replace_exact(v3, '    "immune": "sentra",\n', '    "defend": "sentra",\n')
    replace_exact(
        v3,
        '    "aegis": ("Aegis Immune Cell", "threat-shield"),\n',
        '    "defend": ("Killinchu Defend Plane", "threat-shield"),\n',
    )


def rewrite_strategy() -> None:
    name = "docs/strategy/living-command-fabric.v1.json"
    data = json.loads(read(name))
    authorities = data["authorities"]
    authorities["vertical_services"]["revision"] = VERTICAL_SERVICES_REVISION
    authorities["vertical_services"].pop("publisher_merge_revision", None)
    authorities["vertical_services"]["publisher_source_binding"] = (
        "runtime /.well-known/szl-source.json plus hf-vertical-services receipt"
    )
    authorities["killinchu"]["revision"] = KILLINCHU_REVISION
    authorities["killinchu"]["role"] = (
        "sole public cyber-physical resilience runtime; Aegis is a portfolio label; "
        "Defend/Sentra, Maritime/Vessels, Counter-UAS/Airspace and Evidence/receipts "
        "are operational capability planes; IMMUNE is migration-gated"
    )
    authorities["anatomy"]["space_repository"] = ANATOMY_REPOSITORY
    authorities["anatomy"]["runtime"] = ANATOMY_ORIGIN

    for vertical in data["verticals"]:
        vertical["service_revision"] = VERTICAL_SERVICES_REVISION
        if vertical["slug"] == "killinchu":
            vertical["canonical_revision"] = KILLINCHU_REVISION
            vertical["role"] = "sole public cyber-physical resilience product"
            vertical["portfolio_labels"] = {
                "aegis": "portfolio and assurance lens; not a separate runtime"
            }
            vertical["capability_planes"] = {
                "sentra_defend": "operational defensive analysis, approval, simulation and receipts",
                "vessels_maritime": "operational fleet, voyage, sanctions and ownership intelligence",
                "counter_uas_airspace": "operational mission-pack and airspace command surface",
                "evidence_receipts": "operational evidence, verification and immutable receipt plane",
            }
            vertical["migration_gated"] = {
                "immune": "distinct admission, tripwire and signed-authority parity required",
                "immune-lattice": "parity audit required before consolidation",
            }
            vertical["aliases"] = ["aegis", "defend", "vessels"]

    taxonomy = data["public_product_taxonomy"]
    taxonomy["resilience_product_space"] = "killinchu"
    taxonomy["folded_into_killinchu"] = ["aegis", "sentra", "vessels"]
    taxonomy["operational_capability_planes"] = [
        "defend",
        "maritime",
        "counter-uas",
        "evidence",
    ]
    taxonomy["migration_gated"] = ["immune", "immune-lattice"]
    taxonomy["portfolio_labels"] = ["aegis"]

    intelligence = data["intelligence_fabric"]
    intelligence["source_revision"] = VERTICAL_SERVICES_REVISION
    intelligence["killinchu_capability_aliases"] = {
        "aegis": "sentra",
        "defend": "sentra",
        "vessels": "killinchu",
    }
    intelligence["migration_gated"] = ["immune", "immune-lattice"]

    data["wave_1"]["site"] = (
        "Expose Living Anatomy and five public domain bodies backed by six internal "
        "engines; show four operational Killinchu planes and IMMUNE as migration-gated."
    )
    data["wave_1"]["publisher_repair"] = (
        f"Bind the canonical single writer to vertical-services@{VERTICAL_SERVICES_REVISION} "
        "/ runtime 2.2.0; keep Aegis as a portfolio label, Defend and Maritime inside "
        "Killinchu, and IMMUNE migration-gated until parity is proven."
    )
    write(name, json.dumps(data, indent=2, sort_keys=False) + "\n")


def rewrite_manifest_generator() -> None:
    name = "scripts/audit_huggingface_ecosystem.py"
    value = read(name)
    old_names = '["kora", "lumina", "paragon", "lyte"]'
    if value.count(old_names) != 1:
        raise SystemExit("manifest generator stale-name anchor drifted")
    value = value.replace(old_names, '["kora", "lumina", "paragon"]')
    old_guardrails = '''        "guardrails": [
            "Do not present Counsel, Terra, or Carlota Jo as active demo surfaces.",
            "Do not use KORA, LUMINA, PARAGON, or active Lyte framing.",
            "Do not claim zero-sorry or all-green Lean proof status without current machine-readable proof evidence.",
            "Do not claim signed UDS release assets exist unless tarball, signature, sha256, and public key assets are present and verify.",
        ],'''
    new_guardrails = '''        "guardrails": [
            "Present a public product as operational only when live readiness and exact-source proof pass.",
            "Aegis is a portfolio label; Sentra/Defend and Vessels/Maritime live inside Killinchu; IMMUNE remains migration-gated.",
            "Carlota Jo remains incubation until canonical source, runtime authority, and measurable workflow are explicit.",
            "Do not claim zero-sorry or all-green Lean proof status without current machine-readable proof evidence.",
            "Do not claim signed UDS release assets exist unless tarball, signature, sha256, and public key assets are present and verify.",
        ],'''
    if value.count(old_guardrails) != 1:
        raise SystemExit("manifest generator guardrail block drifted")
    write(name, value.replace(old_guardrails, new_guardrails))


def rewrite_tests() -> None:
    anatomy_test = '''from __future__ import annotations

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
'''
    write("tests/test_living_anatomy_flagship_policy.py", anatomy_test)

    frontdoor = read("tests/test_living_command_fabric_frontdoor.py")
    frontdoor = frontdoor.replace(OLD_VERTICAL_SERVICES_REVISION, VERTICAL_SERVICES_REVISION)
    frontdoor = frontdoor.replace(
        '["aegis", "sentra", "immune", "vessels"]',
        '["aegis", "sentra", "vessels"]',
    )
    frontdoor = frontdoor.replace(
        '{"aegis", "sentra_defend", "immune", "vessels_maritime", "counter_uas_airspace"}',
        '{"sentra_defend", "vessels_maritime", "counter_uas_airspace", "evidence_receipts"}',
    )
    frontdoor = frontdoor.replace(
        '{"aegis": "sentra", "immune": "sentra", "vessels": "killinchu"}',
        '{"aegis": "sentra", "defend": "sentra", "vessels": "killinchu"}',
    )
    old_assertion = '''        self.assertEqual(
            set(killinchu["capability_planes"]),
            {"sentra_defend", "vessels_maritime", "counter_uas_airspace", "evidence_receipts"},
        )'''
    new_assertion = old_assertion + '''
        self.assertEqual(set(killinchu["migration_gated"]), {"immune", "immune-lattice"})
        self.assertEqual(set(killinchu["portfolio_labels"]), {"aegis"})
        self.assertIn("IMMUNE MIGRATION-GATED", self.html)
        self.assertIn("https://szlholdings-killinchu.hf.space/defend", self.html)
        self.assertNotIn("FIVE CAPABILITY PLANES", self.html)'''
    if frontdoor.count(old_assertion) != 1:
        raise SystemExit("frontdoor test capability assertion drifted")
    write(
        "tests/test_living_command_fabric_frontdoor.py",
        frontdoor.replace(old_assertion, new_assertion),
    )

    for name in (
        "tests/test_hf_frontier_v3_rebase.py",
        "tests/test_hf_publish_vertical_flagships_v4.py",
    ):
        value = read(name).replace(OLD_VERTICAL_SERVICES_REVISION, VERTICAL_SERVICES_REVISION)
        value = value.replace('"immune": "sentra"', '"defend": "sentra"')
        value = value.replace("Aegis Immune Cell", "Killinchu Defend Plane")
        write(name, value)

    cards = read("tests/test_vertical_intelligence_cards_v2.py")
    anchor = '''        "HUMAN BIND",
    ):'''
    replacement = '''        "HUMAN BIND",
        "4 OPERATIONAL PLANES",
        "IMMUNE MIGRATION-GATED",
        "ONE PUBLIC RUNTIME",
        "https://szlholdings-killinchu.hf.space/defend",
    ):'''
    if cards.count(anchor) != 1:
        raise SystemExit("vertical card boundary assertion drifted")
    write("tests/test_vertical_intelligence_cards_v2.py", cards.replace(anchor, replacement))


def verify_source_truth() -> None:
    keep_pattern = re.compile(r"^\s*- id: (SZLHOLDINGS/[A-Za-z0-9._-]+)$", re.MULTILINE)
    expected_keep = {
        "SZLHOLDINGS/a11oy",
        "SZLHOLDINGS/killinchu",
        "SZLHOLDINGS/terra",
        "SZLHOLDINGS/counsel",
        "SZLHOLDINGS/finance",
        "SZLHOLDINGS/lyte",
        "SZLHOLDINGS/david-leads",
        "SZLHOLDINGS/vertical-services",
    }
    for name in (
        "docs/series-a/hf-space-keep-list.yaml",
        "docs/estate/hf-nine-flagship-keep.yaml",
    ):
        value = read(name)
        keep_section = value.split("keep:", 1)[1].split("creator_profile_surface:", 1)[0]
        observed = set(keep_pattern.findall(keep_section))
        if observed != expected_keep:
            raise SystemExit(f"{name}: unexpected keep set {sorted(observed)}")
        if "- id: betterwithage/anatomy" in value:
            raise SystemExit(f"{name}: foreign creator-profile id leaked into org keep parser")

    operational_files = (
        "README.md",
        "web/living-anatomy.html",
        "a11oy_landing.html",
        "docs/state-plane-continuity.v1.json",
        "a11oy_ecosystem_atlas.py",
        "pages/organs-integrity.html",
        "pages/atelier.html",
        "docs/estate/HF_FLAGSHIP_MIGRATION.md",
        "docs/series-a/HF_SPACE_CONSOLIDATION.md",
        ".github/workflows/hf-living-anatomy-guardian.yml",
        ".github/workflows/smoke-monitor.yml",
        "szl3d_holographic.py",
    )
    for name in operational_files:
        value = read(name)
        if OLD_ANATOMY_ORIGIN in value or OLD_ANATOMY_REPOSITORY in value:
            raise SystemExit(f"{name}: stale operational Anatomy target remains")

    v4 = read("scripts/hf_publish_vertical_services_intelligence_v4.py")
    v3 = read("scripts/hf_publish_vertical_services_frontier_v3.py")
    for name, value in (("v4", v4), ("v3", v3)):
        if VERTICAL_SERVICES_REVISION not in value:
            raise SystemExit(f"publisher {name}: current vertical-services revision absent")
        if '"immune": "sentra"' in value:
            raise SystemExit(f"publisher {name}: IMMUNE is still silently aliased")
        if '"defend": "sentra"' not in value:
            raise SystemExit(f"publisher {name}: Defend alias absent")

    landing = read("a11oy_landing.html")
    for required in (
        "4 OPERATIONAL PLANES",
        "IMMUNE MIGRATION-GATED",
        "SOURCE-VERIFIED · c797b4d",
        "https://szlholdings-killinchu.hf.space/defend",
        ANATOMY_ORIGIN,
    ):
        if required not in landing:
            raise SystemExit(f"landing: missing {required}")
    if "FIVE CAPABILITY PLANES" in landing:
        raise SystemExit("landing: stale five-plane claim remains")

    strategy = json.loads(read("docs/strategy/living-command-fabric.v1.json"))
    killinchu = next(row for row in strategy["verticals"] if row["slug"] == "killinchu")
    if strategy["intelligence_fabric"]["source_revision"] != VERTICAL_SERVICES_REVISION:
        raise SystemExit("strategy: vertical-services source pin mismatch")
    if killinchu["canonical_revision"] != KILLINCHU_REVISION:
        raise SystemExit("strategy: Killinchu source pin mismatch")
    if set(killinchu["migration_gated"]) != {"immune", "immune-lattice"}:
        raise SystemExit("strategy: IMMUNE migration gate missing")


def main() -> int:
    rewrite_policies()
    rewrite_anatomy_operational_references()
    rewrite_smoke_monitor()
    rewrite_landing()
    rewrite_publishers()
    rewrite_strategy()
    rewrite_manifest_generator()
    rewrite_tests()
    verify_source_truth()
    print("ESTATE TRUTH CONVERGENCE SOURCE TRANSACTION PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
