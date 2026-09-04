#!/usr/bin/env python3
"""Apply the Killinchu defense-product convergence as an exact, fail-closed patch."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING = ROOT / "a11oy_landing.html"
VISION = ROOT / "docs" / "strategy" / "living-command-fabric.v1.json"
THEME_REGISTRY = ROOT / "docs" / "holographic-experience-v2" / "theme-registry.json"
HOLO_JS = ROOT / "console" / "assets" / "szl-holo-v2.js"
PUBLISHER = ROOT / "scripts" / "hf_publish_vertical_flagships_v4_impl.py"
LIVING_TEST = ROOT / "tests" / "test_living_command_fabric_frontdoor.py"
CONVERGENCE = ROOT / "docs" / "strategy" / "killinchu-defense-convergence.v1.json"


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def replace_between(text: str, start: str, end: str, replacement: str, *, label: str) -> str:
    if text.count(start) != 1 or text.count(end) < 1:
        raise RuntimeError(f"{label}: section boundaries are not unique/present")
    before, rest = text.split(start, 1)
    _, after = rest.split(end, 1)
    return before + replacement + end + after


def patch_landing() -> None:
    text = LANDING.read_text(encoding="utf-8")
    required = (
        'data-szl-living-command-fabric-v1="true"',
        "SIX DOMAIN BODIES",
        'id="body-sentra"',
        'id="body-vessels"',
        "One intelligence fabric. Six domain bodies. One evidence bloodstream.",
    )
    for literal in required:
        if literal not in text:
            raise RuntimeError(f"landing prerequisite missing: {literal}")

    text = replace_once(text, "SIX DOMAIN BODIES", "FIVE DOMAIN BODIES", label="hero body count")
    text = replace_once(
        text,
        "One intelligence fabric. Six domain bodies. One evidence bloodstream.",
        "One intelligence fabric. Five domain bodies. One evidence bloodstream.",
        label="anatomy headline",
    )
    text = replace_once(
        text,
        "presents six source-bound domain bodies: Terra, Aegis/Sentra, PRISM Counsel, PURIQ Finance, Vessels/Killinchu and Lyte;",
        "presents five source-bound domain bodies: Terra, PRISM Counsel, PURIQ Finance, Killinchu and Lyte;",
        label="embedded summary copy",
    ) if "presents six source-bound domain bodies:" in text else text

    start = "<!-- ====================== DOMAIN BODIES ====================== -->"
    end = "<!-- ====================== FLAGSHIPS — three products max ====================== -->"
    replacement = r'''<!-- ====================== DOMAIN BODIES ====================== -->
<section class="band wrap" id="vertical-bodies" aria-labelledby="vertical-bodies-title">
  <p class="kick">Domain bodies · source-bound, not disconnected apps</p>
  <h2 id="vertical-bodies-title">The same governed organism, specialized for five decision environments.</h2>
  <p class="intro">Each body keeps its own domain objects and workflow while sharing evidence handles, policy gates, the complete locked-eight Anatomy binding, proposal-only model authority, human approval, verification and receipts. <b>Killinchu is the canonical defense product:</b> Aegis is its defensive/cyber lobe and Vessels is its maritime lobe. Compatibility routes remain evidence-labelled aliases, not competing flagships.</p>
  <div class="body-grid">
    <article class="body-card" id="body-terra" data-index="01"><p class="body-domain">Real-estate intelligence</p><h3>Terra</h3><p>A parcel-to-portfolio asset twin: ownership, geospatial context, underwriting assumptions, approvals and outcomes remain attached to their source lineage.</p><div class="body-flow"><span>DISCOVER</span><span>OWNERSHIP</span><span>UNDERWRITE</span><span>APPROVE</span><span>TRACK</span></div><div class="body-truth"><span>COMPLETE LOCKED-8</span><span>SOURCE-BOUND</span></div><div class="body-links"><a href="https://github.com/szl-holdings/szl-real-estate" rel="noopener">Source ↗</a><a href="https://huggingface.co/spaces/SZLHOLDINGS/terra" rel="noopener">Body surface ↗</a></div></article>
    <article class="body-card" id="body-counsel" data-index="02"><p class="body-domain">Legal matter intelligence</p><h3>PRISM Counsel</h3><p>A matter-centered workspace with chronology, authority rail, research provenance, work-product versions, citation verification and explicit human sign-off.</p><div class="body-flow"><span>INTAKE</span><span>RESEARCH</span><span>ANALYZE</span><span>DRAFT</span><span>VERIFY</span></div><div class="body-truth"><span>COMPLETE LOCKED-8</span><span>AUTHORITY-BOUND</span></div><div class="body-links"><a href="https://github.com/szl-holdings/a11oy/tree/main/verticals/counsel" rel="noopener">Source ↗</a><a href="https://huggingface.co/spaces/SZLHOLDINGS/counsel" rel="noopener">Body surface ↗</a></div></article>
    <article class="body-card" id="body-finance" data-index="03"><p class="body-domain">Financial intelligence</p><h3>PURIQ Finance</h3><p>A decision and exposure twin: positions, scenarios, stresses, exceptions and approvals stay connected to market/reference-data provenance and the final audit tape.</p><div class="body-flow"><span>INGEST</span><span>PRICE</span><span>STRESS</span><span>DECIDE</span><span>AUDIT</span></div><div class="body-truth"><span>COMPLETE LOCKED-8</span><span>NO PERFORMANCE CLAIM</span></div><div class="body-links"><a href="https://github.com/szl-holdings/puriq-live" rel="noopener">Source ↗</a><a href="https://huggingface.co/spaces/SZLHOLDINGS/finance" rel="noopener">Body surface ↗</a></div></article>
    <article class="body-card" id="body-killinchu" data-index="04"><p class="body-domain">Defense, cyber, maritime and mission intelligence</p><h3>Killinchu</h3><p>One defense product with a shared mission object, authority rail and receipt chain. <b>Aegis</b> is the defensive/cyber lobe; <b>Vessels</b> is the maritime lobe. Detection, identity, ownership, sanctions, behavior, mission context and bounded response proposals converge without granting autonomous destructive authority.</p><div class="body-flow"><span>DETECT</span><span>IDENTIFY</span><span>FUSE</span><span>AUTHORIZE</span><span>VERIFY</span><span>RECEIPT</span></div><div class="body-truth"><span>COMPLETE LOCKED-8</span><span>AEGIS · CYBER LOBE</span><span>VESSELS · MARITIME LOBE</span><span>EFFECTORS SIMULATED</span></div><div class="body-links"><a href="https://github.com/szl-holdings/killinchu" rel="noopener">Canonical source ↗</a><a href="https://huggingface.co/spaces/SZLHOLDINGS/killinchu" rel="noopener">Canonical product ↗</a><a href="https://huggingface.co/spaces/SZLHOLDINGS/sentra" rel="noopener">Aegis compatibility ↗</a><a href="https://huggingface.co/spaces/SZLHOLDINGS/vessels" rel="noopener">Vessels compatibility ↗</a></div></article>
    <article class="body-card" id="body-lyte" data-index="05"><p class="body-domain">Business and agent observability</p><h3>Lyte</h3><p>A trace-to-decision-to-proof body: service and agent topology, investigation hypotheses, replay, evaluations and action proposals share one evidence timeline.</p><div class="body-flow"><span>OBSERVE</span><span>TRACE</span><span>DIAGNOSE</span><span>ACT</span><span>VERIFY</span></div><div class="body-truth"><span>COMPLETE LOCKED-8</span><span>OTEL-NATIVE DIRECTION</span></div><div class="body-links"><a href="https://github.com/szl-holdings/lyte-lattice" rel="noopener">Source ↗</a><a href="/lyte">Open Lyte →</a></div></article>
  </div>
  <p class="fabric-note"><b>Carlota Jo remains an incubation lane.</b> The visual system recognizes the brand, but the current service authority does not expose a canonical source/runtime contract for it. It will not be promoted as operational until that authority, domain object and measurable workflow are explicit.</p>
</section>

<div class="wrap"><div class="divider"></div></div>

'''
    text = replace_between(text, start, end, replacement, label="domain body section")
    text = text.replace(
        "Three commercial flagships anchor the public line. Six source-bound domain bodies inherit",
        "Three commercial flagships anchor the public line. Five source-bound domain bodies inherit",
    )
    text = text.replace(
        "Counter-UAS and maritime vertical on the same receipt substrate.",
        "Canonical defense product spanning Aegis defensive/cyber and Vessels maritime lobes on the same receipt substrate.",
    )
    LANDING.write_text(text, encoding="utf-8")


def patch_manifest() -> None:
    data = json.loads(VISION.read_text(encoding="utf-8"))
    rows = data.get("verticals")
    if not isinstance(rows, list):
        raise RuntimeError("living-command manifest has no vertical list")
    by_slug = {row.get("slug"): row for row in rows}
    expected = {"terra", "sentra", "counsel", "finance", "vessels", "lyte"}
    if set(by_slug) != expected:
        raise RuntimeError(f"unexpected pre-convergence verticals: {sorted(by_slug)}")

    killinchu = dict(by_slug["vessels"])
    killinchu.update(
        {
            "slug": "killinchu",
            "brand": "Killinchu",
            "domain": "defense_cyber_maritime_and_mission_intelligence",
            "canonical_source": "szl-holdings/killinchu",
            "runtime": "https://szlholdings-killinchu.hf.space",
            "workflow": ["DETECT", "IDENTIFY", "FUSE", "AUTHORIZE", "VERIFY", "RECEIPT"],
            "decision_surface": [
                "mission object",
                "Aegis defensive/cyber lobe",
                "Vessels maritime lobe",
                "authority rail",
                "receipt chain",
            ],
            "formula_binding": "complete_locked_eight_via_shared_anatomy",
            "lobes": [
                {
                    "id": "aegis",
                    "role": "defensive_and_cyber_intelligence",
                    "compatibility_slug": "sentra",
                    "compatibility_runtime": "https://szlholdings-sentra.hf.space",
                    "standalone_product": False,
                },
                {
                    "id": "vessels",
                    "role": "maritime_intelligence",
                    "compatibility_slug": "vessels",
                    "compatibility_runtime": "https://szlholdings-vessels.hf.space",
                    "standalone_product": False,
                },
            ],
            "consolidation": "Killinchu is the only public defense product. Aegis and Vessels remain source-preserving lobes and compatibility aliases, never competing flagships.",
            "effectors": "SIMULATED_UNLESS_INDEPENDENTLY_PROVED",
        }
    )
    ordered = [by_slug["terra"], by_slug["counsel"], by_slug["finance"], killinchu, by_slug["lyte"]]
    data["verticals"] = ordered
    data.setdefault("estate", {})["domain_body_count"] = 5
    data["consolidation"] = {
        "canonical_product": "killinchu",
        "absorbed_public_brands": ["aegis", "vessels"],
        "compatibility_surfaces": ["sentra", "vessels"],
        "rule": "Compatibility surfaces identify their Killinchu lobe and link to the canonical product; they cannot claim independent flagship status.",
        "source_preservation": True,
        "destructive_or_offensive_autonomy": False,
    }
    wave = data.setdefault("wave_1", {})
    wave["site"] = "Expose Living Anatomy and five current domain bodies; present Aegis and Vessels only as Killinchu lobes while preserving buyer and runtime evidence contracts."
    wave["next_vertical_order"] = [
        "killinchu_aegis_vessels",
        "lyte",
        "terra",
        "prism_counsel",
        "puriq_finance",
        "carlota_jo_incubation",
    ]
    VISION.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def patch_hologram() -> None:
    text = HOLO_JS.read_text(encoding="utf-8")
    marker = "  const ROUTE_HINTS = ["
    alias = """  const CONSOLIDATED_SURFACES = Object.freeze({\n    aegis: \"killinchu\",\n    sentra: \"killinchu\",\n    vessels: \"killinchu\",\n  });\n\n"""
    text = replace_once(text, marker, alias + marker, label="hologram alias registry")
    old = """  function resolveTheme() {\n    const id = surfaceCandidate();\n    const curated = CURATED[id];"""
    new = """  function resolveTheme() {\n    const requestedId = surfaceCandidate();\n    const id = CONSOLIDATED_SURFACES[requestedId] || requestedId;\n    const curated = CURATED[id];"""
    text = replace_once(text, old, new, label="hologram canonical resolver")
    HOLO_JS.write_text(text, encoding="utf-8")

    registry = json.loads(THEME_REGISTRY.read_text(encoding="utf-8"))
    registry["consolidated_surfaces"] = {
        "aegis": {"canonical_surface": "killinchu", "role": "defensive_and_cyber_lobe"},
        "sentra": {"canonical_surface": "killinchu", "role": "aegis_compatibility_alias"},
        "vessels": {"canonical_surface": "killinchu", "role": "maritime_lobe"},
    }
    registry["consolidation_rule"] = "Aegis, Sentra and Vessels resolve to Killinchu's governed visual identity; route labels may preserve lobe context without creating another product authority."
    THEME_REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def patch_publisher() -> None:
    text = PUBLISHER.read_text(encoding="utf-8")
    sentra_pattern = re.compile(
        r'    \{\n        "slug": "sentra",.*?\n    \},\n',
        re.DOTALL,
    )
    vessels_pattern = re.compile(
        r'    \{\n        "slug": "vessels",.*?\n    \},\n',
        re.DOTALL,
    )
    sentra_matches = sentra_pattern.findall(text)
    vessels_matches = vessels_pattern.findall(text)
    if len(sentra_matches) != 1 or len(vessels_matches) != 1:
        raise RuntimeError(
            f"publisher source shape changed: sentra={len(sentra_matches)} vessels={len(vessels_matches)}"
        )
    sentra = '''    {\n        "slug": "sentra",\n        "title": "Killinchu · Aegis",\n        "vertical": "DEFENSIVE / CYBER LOBE",\n        "short": "Aegis defensive cyber lobe consolidated into Killinchu",\n        "source": "https://github.com/szl-holdings/killinchu",\n        "upstream": f"{A11OY}/api/a11oy/v1/vert/cyber/feed",\n        "workflow": ("DETECT", "CORRELATE", "PROPOSE", "AUTHORIZE", "VERIFY"),\n        "lens": "attack",\n        "labels": ("Entity graph", "Attack paths", "Authority queue"),\n        "canonical_product": "killinchu",\n        "lobe": "aegis",\n        "standalone_product": False,\n    },\n'''
    vessels = '''    {\n        "slug": "vessels",\n        "title": "Killinchu · Vessels",\n        "vertical": "MARITIME LOBE",\n        "short": "Vessels maritime lobe consolidated into Killinchu",\n        "source": "https://github.com/szl-holdings/killinchu",\n        "upstream": f"{KILLINCHU}/api/killinchu/v1/maritime/risk/fleet",\n        "workflow": ("TRACK", "SCREEN", "ROUTE", "ECONOMICS", "VERIFY"),\n        "lens": "fleet",\n        "labels": ("Fleet chart", "Voyage lanes", "Risk watch"),\n        "canonical_product": "killinchu",\n        "lobe": "vessels",\n        "standalone_product": False,\n    },\n'''
    text = sentra_pattern.sub(sentra, text, count=1)
    text = vessels_pattern.sub(vessels, text, count=1)
    constant_marker = "PUBLIC_EXPERIENCE_MARKER = 'data-szl-domain-experience-v4=\"true\"'\n"
    constant = '''CONSOLIDATED_ALIASES: dict[str, dict[str, str]] = {\n    "sentra": {"canonical_product": "killinchu", "lobe": "aegis"},\n    "vessels": {"canonical_product": "killinchu", "lobe": "vessels"},\n}\n'''
    text = replace_once(text, constant_marker, constant_marker + constant, label="publisher alias constant")
    PUBLISHER.write_text(text, encoding="utf-8")


def patch_living_test() -> None:
    text = LIVING_TEST.read_text(encoding="utf-8")
    text = replace_once(
        text,
        'VERTICALS = ["terra", "sentra", "counsel", "finance", "vessels", "lyte"]',
        'VERTICALS = ["terra", "counsel", "finance", "killinchu", "lyte"]',
        label="test vertical list",
    )
    text = replace_once(text, "SIX DOMAIN BODIES", "FIVE DOMAIN BODIES", label="test hero marker")
    text = replace_once(
        text,
        "One intelligence fabric. Six domain bodies. One evidence bloodstream.",
        "One intelligence fabric. Five domain bodies. One evidence bloodstream.",
        label="test anatomy heading",
    )
    text = replace_once(
        text,
        "self.assertEqual(self.html.count('class=\"body-card\"'), 6)",
        "self.assertEqual(self.html.count('class=\"body-card\"'), 5)",
        label="test body count",
    )
    LIVING_TEST.write_text(text, encoding="utf-8")


def write_convergence_contract() -> None:
    if CONVERGENCE.exists():
        raise RuntimeError("convergence contract already exists")
    payload = {
        "schema": "szl.killinchu-defense-convergence/v1",
        "effective_date": "2026-09-03",
        "canonical_product": {
            "id": "killinchu",
            "source": "szl-holdings/killinchu",
            "product_surface": "https://huggingface.co/spaces/SZLHOLDINGS/killinchu",
            "governance_surface": "https://a-11-oy.com",
            "proof_surface": "https://a11oy.net",
        },
        "lobes": [
            {
                "id": "aegis",
                "domain": "defensive_and_cyber_intelligence",
                "compatibility_surface": "SZLHOLDINGS/sentra",
                "standalone_product": False,
            },
            {
                "id": "vessels",
                "domain": "maritime_intelligence",
                "compatibility_surface": "SZLHOLDINGS/vessels",
                "standalone_product": False,
            },
        ],
        "shared_contract": {
            "formula_ids": ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
            "lambda": "CONJECTURE_1_ADVISORY",
            "pipeline": ["INGEST", "TRANSFORM", "ANALYZE", "DECIDE", "APPROVE", "EXECUTE", "VERIFY", "AUDIT", "DELIVER"],
            "consequential_actions": "HUMAN_AUTHORITY_REQUIRED",
            "destructive_or_offensive_autonomy": False,
            "effectors": "SIMULATED_UNLESS_INDEPENDENTLY_PROVED",
            "receipt_required": True,
        },
        "compatibility_policy": {
            "delete_source": False,
            "present_as_independent_flagship": False,
            "link_to_canonical_product": True,
            "preserve_source_and_receipts": True,
        },
    }
    CONVERGENCE.parent.mkdir(parents=True, exist_ok=True)
    CONVERGENCE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    patch_landing()
    patch_manifest()
    patch_hologram()
    patch_publisher()
    patch_living_test()
    write_convergence_contract()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
