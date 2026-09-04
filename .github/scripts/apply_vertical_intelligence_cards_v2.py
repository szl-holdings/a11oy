#!/usr/bin/env python3
"""Apply the source-native vertical intelligence card overhaul once.

The transform is deliberately narrow and fail-closed. It replaces only the
existing domain-card CSS block and the five-card HTML block between stable
markers. It adds no runtime dependency, iframe, CDN, copied vendor asset, or
client-side data claim.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LANDING = ROOT / "a11oy_landing.html"
MARKER = 'data-szl-vertical-intelligence-cards-v2="true"'

NEW_CSS = r'''  .body-grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:14px;margin-top:30px}
  .body-card{--card-line:rgba(255,255,255,.18);position:relative;grid-column:span 4;min-height:430px;
    border:1px solid var(--border);background:#050506;display:flex;flex-direction:column;overflow:hidden;
    transition:transform .32s cubic-bezier(.16,1,.3,1),border-color .32s ease,box-shadow .32s ease}
  .body-card:hover{transform:translateY(-4px);border-color:rgba(255,255,255,.48);
    box-shadow:0 24px 70px -42px rgba(255,255,255,.38)}
  .body-card::before{content:attr(data-index);position:absolute;right:17px;top:13px;z-index:4;
    color:rgba(255,255,255,.24);font:600 10px/1 var(--mono);letter-spacing:.14em}
  #body-terra{grid-column:span 5}#body-killinchu{grid-column:span 7}
  .body-visual{position:relative;isolation:isolate;height:176px;overflow:hidden;border-bottom:1px solid var(--border);
    background:linear-gradient(155deg,rgba(255,255,255,.065),rgba(255,255,255,.008) 66%)}
  .body-visual::before,.body-visual::after{content:"";position:absolute;pointer-events:none}
  .body-visual-label{position:absolute;left:17px;top:14px;z-index:5;color:rgba(255,255,255,.58);
    font:600 9.5px/1.25 var(--mono);letter-spacing:.13em;text-transform:uppercase}
  .body-signal{position:absolute;z-index:3;width:8px;height:8px;border:1px solid rgba(255,255,255,.72);
    border-radius:50%;background:#050506;box-shadow:0 0 0 4px rgba(255,255,255,.055)}
  .body-signal::after{content:"";position:absolute;left:50%;top:50%;width:2px;height:2px;border-radius:50%;
    background:#fff;transform:translate(-50%,-50%)}
  .body-card-copy{position:relative;z-index:2;display:flex;flex:1;flex-direction:column;padding:22px}
  .body-card .body-domain{margin:0 0 12px;color:var(--ghost);font:600 10px/1.35 var(--mono);
    letter-spacing:.13em;text-transform:uppercase}
  .body-card h3{margin:0 0 9px;font-size:clamp(1.42rem,2.25vw,2rem);letter-spacing:-.025em}
  .body-card p{margin:0;color:var(--sub);font-size:.93rem;text-wrap:pretty}
  .body-edge{margin:15px 0 0;padding:12px 13px;border-left:1px solid rgba(255,255,255,.55);
    background:rgba(255,255,255,.025);color:var(--ink)!important;font-size:.84rem!important}
  .body-stack-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;margin:17px 0 0;
    border:1px solid var(--border);background:var(--border)}
  .body-stack-grid>div{min-height:74px;padding:11px 12px;background:#070708}
  .body-stack-grid span{display:block;color:var(--ghost);font:600 8.5px/1.3 var(--mono);
    letter-spacing:.11em;text-transform:uppercase}
  .body-stack-grid strong{display:block;margin-top:7px;color:var(--sub);font:500 10.5px/1.45 var(--mono);
    overflow-wrap:anywhere}
  .body-flow{display:flex;flex-wrap:wrap;gap:5px;margin:16px 0 0}
  .body-flow span{display:inline-flex;align-items:center;min-height:27px;padding:4px 7px;border:1px solid var(--border);
    color:var(--sub);font:600 9px/1.2 var(--mono);letter-spacing:.055em}
  .body-truth{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
  .body-truth span{display:inline-flex;align-items:center;min-height:27px;padding:4px 8px;border:1px solid var(--border);
    color:var(--sub);font:600 9px/1.2 var(--mono);letter-spacing:.065em}
  .body-card .body-links{display:flex;flex-wrap:wrap;gap:7px;margin-top:auto;padding-top:17px}
  .body-card .body-links a{display:inline-flex;align-items:center;justify-content:center;min-height:46px;padding:9px 12px;
    border:1px solid var(--border);color:var(--ink);font:600 10.5px/1.3 var(--mono);text-align:center}
  .body-card .body-links a:first-child{background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.42)}
  .body-card .body-links a:hover{background:rgba(255,255,255,.13);border-color:rgba(255,255,255,.58)}

  /* Terra / parcel loom */
  #body-terra .body-visual{background-image:linear-gradient(rgba(255,255,255,.09) 1px,transparent 1px),
    linear-gradient(90deg,rgba(255,255,255,.09) 1px,transparent 1px),
    radial-gradient(circle at 74% 34%,rgba(255,255,255,.10),transparent 28%);background-size:44px 44px,44px 44px,auto}
  #body-terra .body-visual::before{inset:38px 11% 25px 9%;transform:skewX(-8deg) rotate(-3deg);
    border:1px solid rgba(255,255,255,.58);clip-path:polygon(0 8%,45% 0,43% 43%,100% 34%,94% 100%,38% 84%,0 92%)}
  #body-terra .body-signal:nth-of-type(1){left:24%;top:40%}#body-terra .body-signal:nth-of-type(2){left:58%;top:60%}
  #body-terra .body-signal:nth-of-type(3){right:17%;top:29%}

  /* Killinchu / common operating picture */
  #body-killinchu .body-visual{background:radial-gradient(circle at 68% 50%,rgba(255,255,255,.075),transparent 42%),#040405}
  #body-killinchu .body-visual::before{width:260px;height:260px;right:7%;top:-45px;border:1px solid rgba(255,255,255,.43);
    border-radius:50%;background:repeating-radial-gradient(circle,transparent 0 31px,rgba(255,255,255,.095) 32px 33px)}
  #body-killinchu .body-visual::after{width:130px;height:1px;right:19%;top:50%;transform-origin:right center;
    background:linear-gradient(90deg,transparent,rgba(255,255,255,.85));animation:szl-radar-sweep 8s linear infinite}
  #body-killinchu .body-signal:nth-of-type(1){right:23%;top:29%}#body-killinchu .body-signal:nth-of-type(2){right:39%;top:64%}
  #body-killinchu .body-signal:nth-of-type(3){right:13%;top:70%}

  /* Counsel / authority chain */
  #body-counsel .body-visual{background-image:linear-gradient(90deg,transparent 49.8%,rgba(255,255,255,.17) 50%,transparent 50.2%)}
  #body-counsel .body-visual::before{left:18%;right:18%;top:50%;height:1px;background:rgba(255,255,255,.36)}
  #body-counsel .body-signal:nth-of-type(1){left:18%;top:47%}#body-counsel .body-signal:nth-of-type(2){left:49%;top:47%}
  #body-counsel .body-signal:nth-of-type(3){right:18%;top:47%}
  #body-counsel .body-signal:nth-of-type(2)::before{content:"";position:absolute;left:3px;top:-53px;width:1px;height:52px;background:rgba(255,255,255,.36)}

  /* Finance / probability orbit */
  #body-finance .body-visual{background:radial-gradient(circle at 50% 50%,rgba(255,255,255,.10),transparent 12%),#040405}
  #body-finance .body-visual::before{inset:32px 17%;border:1px solid rgba(255,255,255,.48);border-radius:50%;transform:rotate(-13deg)}
  #body-finance .body-visual::after{inset:55px 27%;border:1px solid rgba(255,255,255,.18);border-radius:50%;transform:rotate(18deg)}
  #body-finance .body-signal:nth-of-type(1){left:23%;top:35%}#body-finance .body-signal:nth-of-type(2){right:23%;top:62%}
  #body-finance .body-signal:nth-of-type(3){left:50%;top:49%}

  /* Lyte / service lattice */
  #body-lyte .body-visual{background-image:linear-gradient(rgba(255,255,255,.07) 1px,transparent 1px),
    linear-gradient(90deg,rgba(255,255,255,.07) 1px,transparent 1px);background-size:34px 34px}
  #body-lyte .body-visual::before{left:18%;right:18%;top:50%;height:1px;background:linear-gradient(90deg,transparent,#fff,transparent);transform:rotate(-7deg)}
  #body-lyte .body-signal:nth-of-type(1){left:16%;top:56%}#body-lyte .body-signal:nth-of-type(2){left:47%;top:38%}
  #body-lyte .body-signal:nth-of-type(3){right:17%;top:57%}

  @keyframes szl-radar-sweep{to{transform:rotate(360deg)}}
  .fabric-note{margin:20px 0 0;padding:16px 18px;border-left:2px solid rgba(255,255,255,.48);
    background:rgba(255,255,255,.025);color:var(--sub)}
  @media(max-width:980px){.fabric-rail{grid-template-columns:repeat(2,minmax(0,1fr))}
    .organ-cell:last-child{grid-column:1/-1}.body-card,#body-terra,#body-killinchu{grid-column:span 6}}
  @media(max-width:680px){.fabric-rail,.fabric-rule{grid-template-columns:minmax(0,1fr)}
    .body-grid{grid-template-columns:minmax(0,1fr)}.body-card,#body-terra,#body-killinchu{grid-column:1;min-height:auto}
    .organ-cell:last-child{grid-column:auto}.organ-cell{min-height:auto}.vision-kicker{gap:5px}.vision-kicker span{width:100%}}
  @media(max-width:430px){.body-stack-grid{grid-template-columns:1fr}.body-visual{height:154px}}
  @media(prefers-reduced-motion:reduce){.body-card{transition:none!important}.body-card:hover{transform:none}
    #body-killinchu .body-visual::after{animation:none!important}}
  @media(forced-colors:active){.organ-cell,.body-card,.fabric-rule>div{forced-color-adjust:auto}.body-visual{border:1px solid CanvasText}}
'''

NEW_CARDS = r'''  <div class="body-grid" data-szl-vertical-intelligence-cards-v2="true">
    <article class="body-card" id="body-terra" data-index="01" data-vertical="terra" data-motif="parcel-grid">
      <div class="body-visual" aria-hidden="true"><span class="body-visual-label">PARCEL · CAPITAL · CONSTRAINT</span><i class="body-signal"></i><i class="body-signal"></i><i class="body-signal"></i></div>
      <div class="body-card-copy"><p class="body-domain">Real-estate intelligence</p><h3>Terra</h3><p>A parcel-to-capital evidence twin joining ownership, lease obligations, condition, permitting, climate constraints, underwriting assumptions and approval lineage.</p><p class="body-edge"><b>Unserved job:</b> expose every valuation assumption and constraint before a deal reaches approval.</p><div class="body-stack-grid"><div><span>Model route</span><strong>Khipu 1.5B · ReceiptAgent</strong></div><div><span>Kernel route</span><strong>kernel-suite · invariants · receipt-attn</strong></div></div><div class="body-flow"><span>DISCOVER</span><span>DILIGENCE</span><span>UNDERWRITE</span><span>APPROVE</span><span>REPLAY</span></div><div class="body-truth"><span>PUBLIC DATA ONLY</span><span>HUMAN BIND</span><span>NO PERSON PROSPECTING</span></div><div class="body-links"><a href="https://szlholdings-vertical-services.hf.space/intelligence/terra" rel="noopener">Enter Terra intelligence →</a><a href="https://szlholdings-terra.hf.space/" rel="noopener">Open flagship surface ↗</a></div></div>
    </article>
    <article class="body-card" id="body-killinchu" data-index="02" data-vertical="killinchu" data-motif="voyage-radar">
      <div class="body-visual" aria-hidden="true"><span class="body-visual-label">TRUTH DISAGREEMENT · MISSION REHEARSAL</span><i class="body-signal"></i><i class="body-signal"></i><i class="body-signal"></i></div>
      <div class="body-card-copy"><p class="body-domain">Cyber-physical resilience intelligence</p><h3>Killinchu</h3><p>One public resilience product unifying Aegis assurance, Sentra defense, IMMUNE admission, Vessels maritime intelligence and Counter-UAS airspace review.</p><p class="body-edge"><b>Unserved job:</b> preserve conflicting observations, uncertainty, policy and decision lineage inside one bounded common operating picture.</p><div class="body-stack-grid"><div><span>Model route</span><strong>A11OY-MINI · Khipu 1.5B · ReceiptAgent</strong></div><div><span>Kernel route</span><strong>blocked · invariants · lambda-gate · block-kv</strong></div></div><div class="body-flow"><span>DETECT</span><span>FUSE</span><span>REHEARSE</span><span>AUTHORIZE</span><span>VERIFY</span><span>DEBRIEF</span></div><div class="body-truth"><span>FIVE CAPABILITY PLANES</span><span>SIMULATED EFFECTS</span><span>HUMAN AUTHORITY</span></div><div class="body-links"><a href="https://szlholdings-vertical-services.hf.space/intelligence/killinchu" rel="noopener">Enter Killinchu intelligence →</a><a href="https://szlholdings-killinchu.hf.space/" rel="noopener">Open flagship surface ↗</a></div></div>
    </article>
    <article class="body-card" id="body-counsel" data-index="03" data-vertical="counsel" data-motif="authority-chain">
      <div class="body-visual" aria-hidden="true"><span class="body-visual-label">AUTHORITY · ARGUMENT · OBLIGATION</span><i class="body-signal"></i><i class="body-signal"></i><i class="body-signal"></i></div>
      <div class="body-card-copy"><p class="body-domain">Legal matter intelligence</p><h3>PRISM Counsel</h3><p>An attorney-reviewable matter twin joining authority passages, treatment state, deadlines, obligations, adverse evidence, work product and approvals.</p><p class="body-edge"><b>Unserved job:</b> keep supporting and adverse authority visible together instead of hiding uncertainty inside generated prose.</p><div class="body-stack-grid"><div><span>Model route</span><strong>ReceiptAgent · Khipu 1.5B</strong></div><div><span>Kernel route</span><strong>blocked · receipt-attn · block-kv</strong></div></div><div class="body-flow"><span>INTAKE</span><span>RESEARCH</span><span>MAP</span><span>DRAFT</span><span>VERIFY</span></div><div class="body-truth"><span>AUTHORITY-BOUND</span><span>ATTORNEY-LED</span><span>NO FILING AUTHORITY</span></div><div class="body-links"><a href="https://szlholdings-vertical-services.hf.space/intelligence/counsel" rel="noopener">Enter PRISM intelligence →</a><a href="https://szlholdings-counsel.hf.space/" rel="noopener">Open flagship surface ↗</a></div></div>
    </article>
    <article class="body-card" id="body-finance" data-index="04" data-vertical="finance" data-motif="probability-orbit">
      <div class="body-visual" aria-hidden="true"><span class="body-visual-label">THESIS · SCENARIO · CONTRADICTION</span><i class="body-signal"></i><i class="body-signal"></i><i class="body-signal"></i></div>
      <div class="body-card-copy"><p class="body-domain">Financial intelligence</p><h3>PURIQ Finance</h3><p>A source-linked thesis and scenario system connecting filings, market observations, assumptions, contradictory evidence, probability changes and decision quality.</p><p class="body-edge"><b>Unserved job:</b> measure thesis decay and decision quality separately from whether the market happened to move in your favor.</p><div class="body-stack-grid"><div><span>Model route</span><strong>Khipu 1.5B · ReceiptAgent · A11OY-MINI</strong></div><div><span>Kernel route</span><strong>invariants · lambda-gate · block-kv</strong></div></div><div class="body-flow"><span>INGEST</span><span>RESEARCH</span><span>STRESS</span><span>DECIDE</span><span>AUDIT</span></div><div class="body-truth"><span>NO TRADE EXECUTION</span><span>NO CUSTODY</span><span>HUMAN REVIEW</span></div><div class="body-links"><a href="https://szlholdings-vertical-services.hf.space/intelligence/finance" rel="noopener">Enter PURIQ intelligence →</a><a href="https://szlholdings-finance.hf.space/" rel="noopener">Open flagship surface ↗</a></div></div>
    </article>
    <article class="body-card" id="body-lyte" data-index="05" data-vertical="lyte" data-motif="service-lattice">
      <div class="body-visual" aria-hidden="true"><span class="body-visual-label">TRACE · DECISION · BUSINESS OUTCOME</span><i class="body-signal"></i><i class="body-signal"></i><i class="body-signal"></i></div>
      <div class="body-card-copy"><p class="body-domain">Business and agent observability</p><h3>Lyte</h3><p>A business-causality braid linking services, traces, agents, tool calls, customer journeys, cost, risk, decisions and measurable outcomes.</p><p class="body-edge"><b>Unserved job:</b> prove whether technical recovery actually restored the customer journey and business result.</p><div class="body-stack-grid"><div><span>Model route</span><strong>Khipu 1.5B · A11OY-MINI · ReceiptAgent</strong></div><div><span>Kernel route</span><strong>kernel-suite · receipt-attn · block-kv</strong></div></div><div class="body-flow"><span>OBSERVE</span><span>TRACE</span><span>DIAGNOSE</span><span>REPLAY</span><span>VERIFY</span></div><div class="body-truth"><span>OTEL-NATIVE DIRECTION</span><span>OUTCOME RECEIPTS</span><span>HUMAN BIND</span></div><div class="body-links"><a href="https://szlholdings-vertical-services.hf.space/intelligence/lyte" rel="noopener">Enter Lyte intelligence →</a><a href="https://szlholdings-lyte.hf.space/" rel="noopener">Open flagship surface ↗</a></div></div>
    </article>
  </div>
'''

OLD_INTRO = (
    "  <p class=\"intro\">Each public body keeps its own domain objects and workflow while sharing evidence handles, policy gates, the complete locked-eight Anatomy binding, proposal-only model authority, human approval, verification and receipts. Sentra remains an internal defensive engine inside Killinchu rather than a competing public product. A reachable link is not automatically marked ready; live state remains a runtime proof.</p>"
)
NEW_INTRO = (
    "  <p class=\"intro\">Each public body now has a distinct command grammar, signature instrument, bounded model route and explicit kernel path. Open a card to enter the source-bound Python intelligence room; no card grants execution authority, and a reachable link is never promoted into a readiness claim.</p>"
)


def fail(message: str) -> None:
    raise SystemExit(f"vertical intelligence card transform refused: {message}")


def main() -> int:
    text = LANDING.read_text(encoding="utf-8")
    if MARKER in text:
        print("vertical intelligence cards v2 already present")
        return 0

    if text.count('class="body-card"') != 5:
        fail("expected exactly five existing public body cards")
    if OLD_INTRO not in text:
        fail("domain-body intro drifted")

    css_start_marker = "  .body-grid{display:grid;"
    css_end_marker = "  .fabric-note{"
    css_start = text.find(css_start_marker)
    css_end = text.find(css_end_marker, css_start)
    if css_start < 0 or css_end < 0 or css_end <= css_start:
        fail("domain-card CSS markers not found in order")

    section_start = text.find('id="vertical-bodies"')
    html_start = text.find('  <div class="body-grid">', section_start)
    html_end_marker = '  <p class="fabric-note">'
    html_end = text.find(html_end_marker, html_start)
    if section_start < 0 or html_start < 0 or html_end < 0:
        fail("domain-card HTML markers not found")

    updated = text[:css_start] + NEW_CSS + text[css_end:]
    delta = len(NEW_CSS) - (css_end - css_start)
    html_start += delta
    html_end += delta
    updated = updated[:html_start] + NEW_CARDS + updated[html_end:]
    updated = updated.replace(OLD_INTRO, NEW_INTRO, 1)

    if updated.count(MARKER) != 1:
        fail("version marker is not unique")
    if updated.count('class="body-card"') != 5:
        fail("transformed card count is not exactly five")
    for vertical, motif in (
        ("terra", "parcel-grid"),
        ("killinchu", "voyage-radar"),
        ("counsel", "authority-chain"),
        ("finance", "probability-orbit"),
        ("lyte", "service-lattice"),
    ):
        if f'id="body-{vertical}"' not in updated:
            fail(f"missing {vertical} card identity")
        if f'data-motif="{motif}"' not in updated:
            fail(f"missing {vertical} motif")
        room = f"https://szlholdings-vertical-services.hf.space/intelligence/{vertical}"
        if room not in updated:
            fail(f"missing {vertical} intelligence-room route")

    section = updated[updated.find('id="vertical-bodies"'):updated.find("<!-- ====================== FLAGSHIPS", updated.find('id="vertical-bodies"'))]
    lowered = section.lower()
    for forbidden in ("<script", "<iframe", "unpkg", "jsdelivr", "cdn."):
        if forbidden in lowered:
            fail(f"forbidden runtime dependency in card section: {forbidden}")
    for boundary in (
        "SIMULATED EFFECTS",
        "NO TRADE EXECUTION",
        "ATTORNEY-LED",
        "NO PERSON PROSPECTING",
        "HUMAN BIND",
    ):
        if boundary not in section:
            fail(f"missing authority boundary: {boundary}")

    LANDING.write_text(updated, encoding="utf-8")
    print("applied five source-native vertical intelligence cards v2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
