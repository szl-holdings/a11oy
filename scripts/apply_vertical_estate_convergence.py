#!/usr/bin/env python3
"""Converge A11oy's public vertical estate on the active runtime topology."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_exact(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one occurrence, found {count}: {old[:120]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")
    print(f"UPDATED {path.relative_to(ROOT)}")


def main() -> None:
    landing = ROOT / "a11oy_landing.html"
    publisher = ROOT / "scripts" / "hf_publish_vertical_flagships_v4_impl.py"

    old_defend = '''    <article class="body-card" id="body-sentra" data-index="02"><p class="body-domain">Cyber and defensive intelligence</p><h3>Aegis / Sentra</h3><p>An evidence-linked entity and attack-path body. Detection becomes a bounded containment proposal, then human approval, independent verification, rollback state and receipt.</p><div class="body-flow"><span>DETECT</span><span>CORRELATE</span><span>CONTAIN</span><span>VERIFY</span><span>RECEIPT</span></div><div class="body-truth"><span>COMPLETE LOCKED-8</span><span>CONTROLLED SOURCE</span></div><div class="body-links"><a href="https://huggingface.co/spaces/SZLHOLDINGS/sentra" rel="noopener">Body surface ↗</a><a href="/console">Governed action →</a></div></article>'''
    new_defend = '''    <article class="body-card" id="body-defend" data-index="02"><p class="body-domain">Cyber-physical resilience</p><h3>Killinchu / Defend</h3><p>Aegis is the portfolio name and Sentra is the source-bound defensive engine. Both operate through Killinchu’s same-origin Defend plane: detection becomes a bounded proposal, independent human approval, simulation-only rehearsal, rollback state and a verifiable receipt.</p><div class="body-flow"><span>DETECT</span><span>CORRELATE</span><span>APPROVE</span><span>REHEARSE</span><span>VERIFY</span></div><div class="body-truth"><span>COMPLETE LOCKED-8</span><span>EFFECTORS DISABLED</span></div><div class="body-links"><a href="https://github.com/szl-holdings/szl-defensive-control-plane" rel="noopener">Engine source ↗</a><a href="https://szlholdings-killinchu.hf.space/defend" rel="noopener">Open Defend →</a></div></article>'''
    replace_exact(landing, old_defend, new_defend)

    old_maritime = '''    <article class="body-card" id="body-vessels" data-index="05"><p class="body-domain">Maritime and mission intelligence</p><h3>Vessels / Killinchu</h3><p>A fleet and mission body fusing track, ownership, sanctions, behavior, routing and voyage economics. Killinchu is the public product home; Vessels remains its source-bound maritime body.</p><div class="body-flow"><span>TRACK</span><span>SCREEN</span><span>ROUTE</span><span>ECONOMICS</span><span>VERIFY</span></div><div class="body-truth"><span>COMPLETE LOCKED-8</span><span>EFFECTORS SIMULATED</span></div><div class="body-links"><a href="https://github.com/szl-holdings/killinchu" rel="noopener">Source ↗</a><a href="https://huggingface.co/spaces/SZLHOLDINGS/killinchu" rel="noopener">Product surface ↗</a></div></article>'''
    new_maritime = '''    <article class="body-card" id="body-maritime" data-index="05"><p class="body-domain">Maritime and mission intelligence</p><h3>Killinchu / Maritime</h3><p>The Vessels capability is a mission plane inside Killinchu, joining track, ownership, sanctions, behavior, routing and voyage economics without maintaining a second product Space.</p><div class="body-flow"><span>TRACK</span><span>SCREEN</span><span>ROUTE</span><span>ECONOMICS</span><span>VERIFY</span></div><div class="body-truth"><span>COMPLETE LOCKED-8</span><span>EFFECTORS SIMULATED</span></div><div class="body-links"><a href="https://github.com/szl-holdings/killinchu" rel="noopener">Source ↗</a><a href="https://szlholdings-killinchu.hf.space/elite/maritime" rel="noopener">Open Maritime →</a></div></article>'''
    replace_exact(landing, old_maritime, new_maritime)

    replace_exact(
        publisher,
        'KILLINCHU = "https://szlholdings-killinchu.hf.space"\n',
        'KILLINCHU = "https://szlholdings-killinchu.hf.space"\n'
        'VERTICAL_SERVICES = "https://szlholdings-vertical-services.hf.space"\n',
    )
    replacements = {
        '"upstream": f"{A11OY}/api/a11oy/v1/vert/realestate/feed",':
            '"upstream": f"{VERTICAL_SERVICES}/api/verticals/terra/intelligence",',
        '"upstream": f"{A11OY}/api/a11oy/v1/vert/legal/feed",':
            '"upstream": f"{VERTICAL_SERVICES}/api/verticals/counsel/intelligence",',
        '"upstream": f"{A11OY}/api/a11oy/v1/vert/finance/feed",':
            '"upstream": f"{VERTICAL_SERVICES}/api/verticals/finance/intelligence",',
        '"upstream": f"{A11OY}/api/a11oy/v1/observability/summary",':
            '"upstream": f"{VERTICAL_SERVICES}/api/verticals/lyte/intelligence",',
    }
    for old, new in replacements.items():
        replace_exact(publisher, old, new)

    replace_exact(
        publisher,
        '        return {"status":"LIVE" if r.is_success else "UNAVAILABLE","http_status":r.status_code,"latency_ms":round((time.time()-started)*1000,1),"source":CFG["upstream"],"data":body}',
        '        return {"status":"LIVE" if r.is_success else "UNAVAILABLE","http_status":r.status_code,"latency_ms":round((time.time()-started)*1000,1),"source":CFG["upstream"],"runtime":"SZLHOLDINGS/vertical-services","data":body}',
    )
    replace_exact(
        publisher,
        '        return {"status":"UNAVAILABLE","error":type(exc).__name__,"source":CFG["upstream"],"data":None}',
        '        return {"status":"UNAVAILABLE","error":type(exc).__name__,"source":CFG["upstream"],"runtime":"SZLHOLDINGS/vertical-services","data":None}',
    )
    replace_exact(
        publisher,
        '<p class="lede">A governed vertical interface over the SZL evidence fabric. The live panel reports observed upstream data when reachable and remains <b>UNAVAILABLE</b> when evidence cannot be obtained.</p>',
        '<p class="lede">A governed vertical interface over the shared SZL runtime. The live panel reads this domain’s source-bound intelligence contract, model and kernel state, evidence requirements and authority boundary from <b>SZLHOLDINGS/vertical-services</b>; it remains <b>UNAVAILABLE</b> when that runtime cannot be observed.</p>',
    )
    replace_exact(
        publisher,
        '<b>Product portfolio</b><a href="https://a-11-oy.com/products/" target="_blank" rel="noopener">a-11-oy.com/products/</a><b>Truth vocabulary</b>',
        '<b>Operational runtime</b><a href="https://szlholdings-vertical-services.hf.space" target="_blank" rel="noopener">SZLHOLDINGS/vertical-services</a><b>Product portfolio</b><a href="https://a-11-oy.com/products/" target="_blank" rel="noopener">a-11-oy.com/products/</a><b>Truth vocabulary</b>',
    )

    note = ROOT / "docs" / "estate" / "PUBLIC_VERTICAL_TOPOLOGY.md"
    note.write_text(
        """# Public Vertical Topology\n\n"
        "The independent public vertical Spaces are `killinchu`, `terra`, `counsel`, "
        "`finance`, `lyte`, and `david-leads`. Aegis, Sentra, Immune and Vessels are "
        "capability or mission planes inside Killinchu. `vertical-services` is the shared "
        "source-bound engine runtime used by the domain-native Terra, Counsel, Finance and "
        "Lyte front doors.\n\n"
        "A public vertical wrapper reports `LIVE` only when its exact bounded upstream "
        "contract answers successfully. Missing or unreachable evidence remains "
        "`UNAVAILABLE`; no placeholder data is promoted.\n",
        encoding="utf-8",
    )
    print("UPDATED docs/estate/PUBLIC_VERTICAL_TOPOLOGY.md")


if __name__ == "__main__":
    main()
