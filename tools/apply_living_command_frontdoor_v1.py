#!/usr/bin/env python3
"""Apply the Living Command Fabric front-door convergence as an exact, fail-closed patch."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING = ROOT / "a11oy_landing.html"
PUBLISHER = ROOT / "scripts" / "hf_publish_vertical_services.py"
PUBLISHER_TEST = ROOT / "tests" / "test_hf_publish_vertical_flagships_v4.py"

OLD_VERTICAL_REVISION = "96c4ffa8b9a8948c9ba84dc57c0c45885feaf5de"
NEW_VERTICAL_REVISION = "1c6d941da172e2132d3c7818911bd8669ca28f00"


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def patch_landing() -> None:
    text = LANDING.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '<html lang="en" data-szl-public-experience-v3="true" data-szl-space-holo-v2="true" data-szl-zoom-tier="normal">',
        '<html lang="en" data-szl-public-experience-v3="true" data-szl-space-holo-v2="true" data-szl-living-command-fabric-v1="true" data-szl-zoom-tier="normal">',
        label="document contract marker",
    )
    text = replace_once(
        text,
        "<title>a11oy — AI that proves its receipt state and refuses to lie</title>",
        "<title>a11oy — The Living Command Fabric</title>",
        label="document title",
    )
    text = replace_once(
        text,
        '<meta name="description" content="Governed agent change management: AI that exposes receipt integrity, signer state, evidence, and refusal behavior. State-changing actions produce hash-chained receipts; DSSE signing is claimed only when persistent signer evidence is active and independently verified." />',
        '<meta name="description" content="One governed intelligence fabric with six source-bound domain bodies. A11oy connects Living Anatomy, the locked-eight formula kernel, Second Brain evidence handles, qualified inference, policy gates, human approval and verifiable receipts." />',
        label="meta description",
    )
    text = replace_once(
        text,
        '<meta property="og:title" content="a11oy — Governed Agent Change Management" />',
        '<meta property="og:title" content="a11oy — The Living Command Fabric" />',
        label="Open Graph title",
    )
    text = replace_once(
        text,
        '<meta property="og:description" content="AI that exposes receipt integrity and signer state, shows its evidence, and refuses when it cannot support an answer." />',
        '<meta property="og:description" content="One governed intelligence fabric. Six source-bound domain bodies. Eight locked-proven formula bindings. Every consequential action remains evidence-bound, policy-gated and receipt-verifiable." />',
        label="Open Graph description",
    )
    text = replace_once(
        text,
        '<span>a11oy<span class="sub" style="margin-left:9px">Governed Agent Change Management</span></span>',
        '<span>a11oy<span class="sub" style="margin-left:9px">Living Command Fabric</span></span>',
        label="brand subtitle",
    )
    text = replace_once(
        text,
        """      <a class="hide-sm" href="#products">Products</a>
      <a class="hide-sm" href="#catalog">Catalog</a>
      <a class="hide-sm" href="/lyte">LYTE</a>""",
        """      <a class="hide-sm" href="#anatomy">Anatomy</a>
      <a class="hide-sm" href="#vertical-bodies">Domain bodies</a>
      <a class="hide-sm" href="#products">Products</a>""",
        label="primary navigation",
    )
    text = replace_once(
        text,
        '      <span class="eyebrow"><span class="dot"></span> Governed agent change management · verifiable by anyone, offline</span>',
        """      <p class="vision-kicker" aria-label="One fabric, six domain bodies, eight locked formula bindings">
        <span>ONE FABRIC</span><span>SIX DOMAIN BODIES</span><span>EIGHT LOCKED FORMULA BINDINGS</span>
      </p>
      <span class="eyebrow"><span class="dot"></span> Policy-gated · evidence-bound · offline-verifiable</span>""",
        label="hero vision signal",
    )

    css_marker = """</style>
  <link rel="stylesheet" href="/assets/szl-flow.css" data-szl-flow-asset="style" />"""
    css = r"""
  /* ---- Living Command Fabric v1: original SZL synthesis, no vendor trade dress ---- */
  .vision-kicker{display:flex;flex-wrap:wrap;gap:7px 14px;margin:0 0 14px;
    color:var(--ghost);font:600 10.5px/1.4 var(--mono);letter-spacing:.14em}
  .vision-kicker span{display:inline-flex;align-items:center;min-height:30px;padding:4px 9px;
    border-left:1px solid rgba(255,255,255,.38);background:rgba(0,0,0,.42)}
  .fabric-map{isolation:isolate}
  .fabric-map::before{content:"";position:absolute;inset:8% 0 auto;height:64%;
    background:radial-gradient(ellipse at 50% 35%,rgba(255,255,255,.055),transparent 62%);
    pointer-events:none;z-index:-1}
  .fabric-rail{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:1px;
    background:var(--border);border:1px solid var(--border);margin-top:30px}
  .organ-cell{position:relative;min-height:208px;padding:22px;background:rgba(0,0,0,.86);
    display:flex;flex-direction:column;gap:9px}
  .organ-cell::after{content:"";position:absolute;left:22px;right:22px;bottom:18px;height:1px;
    background:linear-gradient(90deg,rgba(255,255,255,.4),transparent)}
  .organ-index{font:600 10px/1.2 var(--mono);letter-spacing:.13em;color:var(--ghost)}
  .organ-cell h3{margin:0;font-size:clamp(1rem,1.5vw,1.2rem)}
  .organ-cell p{margin:0;color:var(--sub);font-size:.9rem}
  .formula-bind{margin-top:auto;padding-bottom:13px;color:var(--ink);
    font:600 12px/1.45 var(--mono);letter-spacing:.06em}
  .fabric-rule{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(250px,.65fr);
    gap:1px;margin-top:1px;background:var(--border);border:1px solid var(--border)}
  .fabric-rule>div{padding:22px;background:rgba(0,0,0,.86)}
  .fabric-rule strong{display:block;margin-bottom:7px;font-family:var(--head)}
  .fabric-rule p{margin:0;color:var(--sub)}
  .fabric-links{display:flex;flex-wrap:wrap;align-content:center;gap:8px}
  .fabric-links a{display:inline-flex;align-items:center;min-height:44px;padding:8px 12px;
    border:1px solid var(--border);font:600 11px/1.3 var(--mono);color:var(--sub)}
  .fabric-links a:hover{border-color:rgba(255,255,255,.55);color:var(--ink)}
  .body-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-top:28px}
  .body-card{position:relative;min-height:330px;padding:24px;border:1px solid var(--border);
    background:linear-gradient(160deg,rgba(255,255,255,.05),rgba(255,255,255,.012) 55%);
    display:flex;flex-direction:column;overflow:hidden}
  .body-card::before{content:attr(data-index);position:absolute;right:18px;top:14px;
    color:rgba(255,255,255,.13);font:600 clamp(2rem,4vw,4rem)/1 var(--mono)}
  .body-card .body-domain{position:relative;z-index:1;margin:0 0 24px;color:var(--ghost);
    font:600 10.5px/1.35 var(--mono);letter-spacing:.12em;text-transform:uppercase}
  .body-card h3{position:relative;z-index:1;margin:0 0 8px;font-size:clamp(1.25rem,2vw,1.65rem)}
  .body-card p{position:relative;z-index:1;margin:0;color:var(--sub);font-size:.93rem}
  .body-flow{display:flex;flex-wrap:wrap;gap:5px;margin:18px 0}
  .body-flow span{display:inline-flex;align-items:center;min-height:28px;padding:4px 7px;
    border:1px solid var(--border);color:var(--sub);font:600 9.5px/1.2 var(--mono);letter-spacing:.06em}
  .body-card .body-links{display:flex;flex-wrap:wrap;gap:7px;margin-top:auto;padding-top:14px}
  .body-card .body-links a{display:inline-flex;align-items:center;min-height:44px;padding:8px 11px;
    border:1px solid var(--border);color:var(--ink);font:600 10.5px/1.3 var(--mono)}
  .body-card .body-links a:hover{background:rgba(255,255,255,.07)}
  .body-truth{display:flex;flex-wrap:wrap;gap:7px;margin-top:12px}
  .body-truth span{display:inline-flex;align-items:center;min-height:28px;padding:4px 8px;
    border:1px solid var(--border);color:var(--sub);font:600 9.5px/1.2 var(--mono);letter-spacing:.07em}
  .fabric-note{margin:20px 0 0;padding:16px 18px;border-left:2px solid rgba(255,255,255,.48);
    background:rgba(255,255,255,.025);color:var(--sub)}
  @media(max-width:980px){.fabric-rail{grid-template-columns:repeat(2,minmax(0,1fr))}
    .organ-cell:last-child{grid-column:1/-1}.body-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
  @media(max-width:680px){.fabric-rail,.body-grid,.fabric-rule{grid-template-columns:minmax(0,1fr)}
    .organ-cell:last-child{grid-column:auto}.organ-cell,.body-card{min-height:auto}
    .vision-kicker{gap:5px}.vision-kicker span{width:100%}}
  @media(prefers-reduced-motion:reduce){.body-card,.organ-cell{transition:none!important}}
  @media(forced-colors:active){.organ-cell,.body-card,.fabric-rule>div{forced-color-adjust:auto}}
"""
    text = replace_once(text, css_marker, css + "\n" + css_marker, label="fabric stylesheet")

    section_marker = "<!-- ====================== FLAGSHIPS — three products max ====================== -->"
    sections = r"""<!-- ====================== LIVING COMMAND FABRIC ====================== -->
<section class="band wrap fabric-map" id="anatomy" aria-labelledby="anatomy-title">
  <p class="kick">Living command fabric · exact authority map</p>
  <h2 id="anatomy-title">One intelligence fabric. Six domain bodies. One evidence bloodstream.</h2>
  <p class="intro">The estate is not 112 unrelated products. A11oy is the governed action and proof fabric;
    Living Anatomy makes the shared organs visible; Second Brain returns evidence handles; Forge qualifies
    inference; Hatun and policy gates can veto; every promoted body inherits the same locked-eight formula
    kernel and must end in a verifiable receipt or an honest <b>BLOCKED</b>.</p>
  <div class="fabric-rail" aria-label="Living Anatomy formula bindings">
    <article class="organ-cell"><span class="organ-index">01 · BRAIN</span><h3>Evidence synthesis</h3><p>Second Brain handles and qualified inference assemble a cited proposal without publishing private memory.</p><span class="formula-bind">F1</span></article>
    <article class="organ-cell"><span class="organ-index">02 · HEART</span><h3>Trust pulse</h3><p>Hatun and A11oy admission apply policy, refusal and human approval before a consequential transition.</p><span class="formula-bind">F4 · F11</span></article>
    <article class="organ-cell"><span class="organ-index">03 · CIRCULATION</span><h3>Evidence transport</h3><p>State and provenance move through the fabric without severing the source, decision or outcome chain.</p><span class="formula-bind">F7 · F22</span></article>
    <article class="organ-cell"><span class="organ-index">04 · NERVOUS SYSTEM</span><h3>Signals and response</h3><p>Observations, tool proposals and verifier outcomes travel through one explicit response path.</p><span class="formula-bind">F12</span></article>
    <article class="organ-cell"><span class="organ-index">05 · SKELETON</span><h3>Structural integrity</h3><p>Parity, integrity and receipt checks keep each body inspectable under failure rather than cosmetically green.</p><span class="formula-bind">F18 · F19</span></article>
  </div>
  <div class="fabric-rule">
    <div><strong>Locked kernel: exactly 8 · Λ remains Conjecture 1</strong><p>Every domain body inherits {F1,F4,F7,F11,F12,F18,F19,F22}. No vertical invents a new F-number meaning. Any required organ DOWN—or a WILLAY/policy veto—blocks the body. Λ is advisory and never authorizes an action by itself.</p></div>
    <div class="fabric-links" aria-label="Canonical architecture sources"><a href="https://github.com/szl-holdings/anatomy" rel="noopener">Anatomy source ↗</a><a href="https://github.com/szl-holdings/szl-formulas" rel="noopener">Formula authority ↗</a><a href="https://github.com/szl-holdings/szl-second-brain" rel="noopener">Second Brain ↗</a><a href="/static/3d/holographic.html">Enter spatial view →</a></div>
  </div>
</section>

<div class="wrap"><div class="divider"></div></div>

<!-- ====================== DOMAIN BODIES ====================== -->
<section class="band wrap" id="vertical-bodies" aria-labelledby="vertical-bodies-title">
  <p class="kick">Domain bodies · source-bound, not disconnected apps</p>
  <h2 id="vertical-bodies-title">The same governed organism, specialized for six decision environments.</h2>
  <p class="intro">Each body keeps its own domain objects and workflow while sharing evidence handles, policy gates, the complete locked-eight Anatomy binding, proposal-only model authority, human approval, verification and receipts. A reachable link is not automatically marked ready; live state remains a runtime proof.</p>
  <div class="body-grid">
    <article class="body-card" id="body-terra" data-index="01"><p class="body-domain">Real-estate intelligence</p><h3>Terra</h3><p>A parcel-to-portfolio asset twin: ownership, geospatial context, underwriting assumptions, approvals and outcomes remain attached to their source lineage.</p><div class="body-flow"><span>DISCOVER</span><span>OWNERSHIP</span><span>UNDERWRITE</span><span>APPROVE</span><span>TRACK</span></div><div class="body-truth"><span>COMPLETE LOCKED-8</span><span>SOURCE-BOUND</span></div><div class="body-links"><a href="https://github.com/szl-holdings/szl-real-estate" rel="noopener">Source ↗</a><a href="https://huggingface.co/spaces/SZLHOLDINGS/terra" rel="noopener">Body surface ↗</a></div></article>
    <article class="body-card" id="body-sentra" data-index="02"><p class="body-domain">Cyber and defensive intelligence</p><h3>Aegis / Sentra</h3><p>An evidence-linked entity and attack-path body. Detection becomes a bounded containment proposal, then human approval, independent verification, rollback state and receipt.</p><div class="body-flow"><span>DETECT</span><span>CORRELATE</span><span>CONTAIN</span><span>VERIFY</span><span>RECEIPT</span></div><div class="body-truth"><span>COMPLETE LOCKED-8</span><span>CONTROLLED SOURCE</span></div><div class="body-links"><a href="https://huggingface.co/spaces/SZLHOLDINGS/sentra" rel="noopener">Body surface ↗</a><a href="/console">Governed action →</a></div></article>
    <article class="body-card" id="body-counsel" data-index="03"><p class="body-domain">Legal matter intelligence</p><h3>PRISM Counsel</h3><p>A matter-centered workspace with chronology, authority rail, research provenance, work-product versions, citation verification and explicit human sign-off.</p><div class="body-flow"><span>INTAKE</span><span>RESEARCH</span><span>ANALYZE</span><span>DRAFT</span><span>VERIFY</span></div><div class="body-truth"><span>COMPLETE LOCKED-8</span><span>AUTHORITY-BOUND</span></div><div class="body-links"><a href="https://github.com/szl-holdings/a11oy/tree/main/verticals/counsel" rel="noopener">Source ↗</a><a href="https://huggingface.co/spaces/SZLHOLDINGS/counsel" rel="noopener">Body surface ↗</a></div></article>
    <article class="body-card" id="body-finance" data-index="04"><p class="body-domain">Financial intelligence</p><h3>PURIQ Finance</h3><p>A decision and exposure twin: positions, scenarios, stresses, exceptions and approvals stay connected to market/reference-data provenance and the final audit tape.</p><div class="body-flow"><span>INGEST</span><span>PRICE</span><span>STRESS</span><span>DECIDE</span><span>AUDIT</span></div><div class="body-truth"><span>COMPLETE LOCKED-8</span><span>NO PERFORMANCE CLAIM</span></div><div class="body-links"><a href="https://github.com/szl-holdings/puriq-live" rel="noopener">Source ↗</a><a href="https://huggingface.co/spaces/SZLHOLDINGS/finance" rel="noopener">Body surface ↗</a></div></article>
    <article class="body-card" id="body-vessels" data-index="05"><p class="body-domain">Maritime and mission intelligence</p><h3>Vessels / Killinchu</h3><p>A fleet and mission body fusing track, ownership, sanctions, behavior, routing and voyage economics. Killinchu is the public product home; Vessels remains its source-bound maritime body.</p><div class="body-flow"><span>TRACK</span><span>SCREEN</span><span>ROUTE</span><span>ECONOMICS</span><span>VERIFY</span></div><div class="body-truth"><span>COMPLETE LOCKED-8</span><span>EFFECTORS SIMULATED</span></div><div class="body-links"><a href="https://github.com/szl-holdings/killinchu" rel="noopener">Source ↗</a><a href="https://huggingface.co/spaces/SZLHOLDINGS/killinchu" rel="noopener">Product surface ↗</a></div></article>
    <article class="body-card" id="body-lyte" data-index="06"><p class="body-domain">Business and agent observability</p><h3>Lyte</h3><p>A trace-to-decision-to-proof body: service and agent topology, investigation hypotheses, replay, evaluations and action proposals share one evidence timeline.</p><div class="body-flow"><span>OBSERVE</span><span>TRACE</span><span>DIAGNOSE</span><span>ACT</span><span>VERIFY</span></div><div class="body-truth"><span>COMPLETE LOCKED-8</span><span>OTEL-NATIVE DIRECTION</span></div><div class="body-links"><a href="https://github.com/szl-holdings/lyte-lattice" rel="noopener">Source ↗</a><a href="/lyte">Open Lyte →</a></div></article>
  </div>
  <p class="fabric-note"><b>Carlota Jo remains an incubation lane.</b> The visual system recognizes the brand, but the current six-engine publisher does not expose a canonical source/runtime authority for it. It will not be promoted as operational until that authority, domain object and measurable workflow are explicit.</p>
</section>

<div class="wrap"><div class="divider"></div></div>

"""
    text = replace_once(text, section_marker, sections + section_marker, label="fabric sections")
    text = replace_once(
        text,
        'The public product line is three flagships — not nine surfaces, not five verticals, and not forty Hub SKUs. Insurance, finance, and real-estate cards are not products. Λ uniqueness is <b>Conjecture&nbsp;1</b> — advisory, never a theorem, never green.',
        'Three commercial flagships anchor the public line. Six source-bound domain bodies inherit the same evidence contract and graduate only when canonical source, runtime revision, domain probes and claim labels agree. Hub cards remain artifacts rather than automatic products. Λ uniqueness is <b>Conjecture&nbsp;1</b> — advisory, never a theorem, never green.',
        label="flagship graduation copy",
    )
    text = replace_once(text, '<p class="kick">Bound packages · not flagships</p>', '<p class="kick">Shared organs · bound into the fabric</p>', label="bound package eyebrow")
    text = replace_once(text, '<h2>Cited in. Not a fourth product.</h2>', '<h2>Capabilities flow through the same governed body.</h2>', label="bound package heading")
    text = replace_once(
        text,
        'These tabs bind onto a-11-oy.com as packages. They are not flagships and they do not certify the product. Hugging Face stays the artifact registry, not the front door.',
        'These organs and packages bind into a-11-oy.com without creating competing authorities. They do not independently certify the product. Hugging Face remains the artifact registry; source/runtime proof and A11oy admission determine readiness.',
        label="bound package copy",
    )
    LANDING.write_text(text, encoding="utf-8")


def patch_vertical_source_pin() -> None:
    for path in (PUBLISHER, PUBLISHER_TEST):
        text = path.read_text(encoding="utf-8")
        count = text.count(OLD_VERTICAL_REVISION)
        if count != 1:
            raise RuntimeError(f"{path.relative_to(ROOT)}: expected one stale source pin, found {count}")
        path.write_text(text.replace(OLD_VERTICAL_REVISION, NEW_VERTICAL_REVISION), encoding="utf-8")


def main() -> int:
    patch_landing()
    patch_vertical_source_pin()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
