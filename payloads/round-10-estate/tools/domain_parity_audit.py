#!/usr/bin/env python3
"""tools/domain_parity_audit.py — READ_ONLY parity + lexicon audit of
a-11-oy.com and a11oy.net (turn-16 payload §4 D1).

Zero-dependency beyond urllib. sitemap.xml first, then same-origin links
discovered from the homepage only (no guessing at undocumented paths).
Enforces the canonical-lexicon ban on public surfaces.

Outputs:
  audits/domain_parity_report.json
  audits/domain_parity_report.md
"""
from __future__ import annotations

import datetime
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDITS = ROOT / "audits"
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
DOMAINS = ["https://a-11-oy.com", "https://a11oy.net"]
UA = {"User-Agent": "szl-domain-parity-audit/1.0 (+read-only)"}

# "Alloy" is a retired legacy brand. "a11oy" contains the substring "alloy" —
# so we match the legacy term only when it is NOT immediately preceded by an
# 'a' (case-insensitive) and NOT immediately followed by a digit (i.e. not 'a11oy').
BANNED_TERMS = [
    "Agentic Orchestrator", "Governed substrate",
    "Governed execution fabric", "Governed AI Operating System",
    "Governed Inference", "EU AI Act compliant", "EU AI Act certified",
    "fully compliant", "unhackable", "cannot be tampered", "impossible to forge",
    "guaranteed secure", "military-grade", "fully autonomous", "no human in the loop",
]
LEGACY_ALLOY = re.compile(r"(?<![aA])alloy(?!\d)")
# A self-referential retirement notice ("Former subtitle 'Alloy' … retired")
# is honest disclosure, not a violation. Whitelist that exact pattern.
ALLOY_RETIREMENT_WHITELIST = re.compile(r"former subtitle[^.]*retired", re.IGNORECASE)


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for k, v in attrs:
                if k == "href" and v:
                    self.links.append(v)


def fetch(url: str) -> dict:
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=25) as r:
            return {"url": url, "status": r.status, "body": r.read().decode("utf-8", "replace"),
                    "final_url": r.geturl()}
    except urllib.error.HTTPError as e:
        return {"url": url, "error": f"HTTP {e.code}"}
    except Exception as e:  # noqa: BLE001
        return {"url": url, "error": f"{type(e).__name__}: {e}"}


def sitemap_paths(domain: str) -> list[str]:
    res = fetch(domain.rstrip("/") + "/sitemap.xml")
    if "body" not in res:
        return []
    try:
        root_el = ET.fromstring(res["body"])
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locs = [e.text for e in root_el.findall(".//sm:loc", ns)] or \
               [e.text for e in root_el.iter() if e.tag.endswith("loc")]
        base = urllib.parse.urlparse(domain)
        return sorted({urllib.parse.urlparse(l).path for l in locs if l
                       and urllib.parse.urlparse(l).netloc == base.netloc})
    except ET.ParseError:
        return []


def homepage_paths(domain: str) -> list[str]:
    res = fetch(domain)
    if "body" not in res:
        return []
    p = LinkParser()
    try:
        p.feed(res["body"])
    except Exception:  # noqa: BLE001
        pass
    base = urllib.parse.urlparse(domain)
    out = set()
    for href in p.links:
        pr = urllib.parse.urlparse(urllib.parse.urljoin(domain, href))
        if pr.netloc in ("", base.netloc) and not pr.path.startswith(("//", "mailto:")):
            path = pr.path or "/"
            if not re.search(r"\.(png|jpg|jpeg|svg|css|js|ico|json|woff2?|txt|xml)$", path):
                out.add(path if path == "/" else path.rstrip("/"))
    return sorted(out)


def lexicon_scan(body: str) -> list[str]:
    hits = []
    # strip script/style so we scan VISIBLE copy, not code comments
    text = re.sub(r"<script[\s\S]*?</script>", " ", body)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    for term in BANNED_TERMS:
        if term.strip() and re.search(re.escape(term.strip()), text, re.IGNORECASE):
            hits.append(term.strip())
    for m in LEGACY_ALLOY.finditer(text):
        ctx = text[max(0, m.start() - 60):m.end() + 60]
        if not ALLOY_RETIREMENT_WHITELIST.search(ctx):
            if "Alloy" not in hits:
                hits.append("Alloy")
    return hits


def main() -> int:
    AUDITS.mkdir(parents=True, exist_ok=True)
    report = {"generated_at": NOW, "domains": [], "parity_gaps": [], "lexicon_findings": []}
    path_sets: dict[str, set] = {}
    for domain in DOMAINS:
        sm = sitemap_paths(domain)
        hp = homepage_paths(domain)
        paths = sorted(set(sm) | set(hp))
        home = fetch(domain)
        entry = {"domain": domain, "reachable": "error" not in home,
                 "error": home.get("error"), "sitemap_paths": len(sm),
                 "homepage_links": len(hp), "routes": paths}
        lex_hits = {p: lexicon_scan(fetch(urllib.parse.urljoin(domain, p)).get("body", ""))
                    for p in paths[:25]}
        entry["lexicon_hits"] = {p: h for p, h in lex_hits.items() if h}
        for p, h in entry["lexicon_hits"].items():
            report["lexicon_findings"].append({"domain": domain, "route": p, "terms": h})
        report["domains"].append(entry)
        path_sets[domain] = set(paths)
    a, b = DOMAINS
    only_a = sorted(path_sets.get(a, set()) - path_sets.get(b, set()))
    only_b = sorted(path_sets.get(b, set()) - path_sets.get(a, set()))
    report["parity_gaps"] = ({"route": p, "present_on": a, "absent_on": b} for p in only_a)
    report["parity_gaps"] = [{"route": p, "present_on": a, "absent_on": b} for p in only_a] + \
                            [{"route": p, "present_on": b, "absent_on": a} for p in only_b]
    (AUDITS / "domain_parity_report.json").write_text(json.dumps(report, indent=2))
    md = ["# Domain Parity + Lexicon Audit", f"Generated: {NOW} · READ_ONLY", ""]
    for d in report["domains"]:
        md.append(f"## {d['domain']} — {'REACHABLE' if d['reachable'] else 'ERROR: ' + str(d['error'])}")
        md.append(f"- sitemap paths: {d['sitemap_paths']} · homepage routes: {d['homepage_links']}")
        md.append(f"- lexicon hits: {sum(len(v) for v in d['lexicon_hits'].values())}")
        md.append("")
    md.append(f"## Parity gaps ({len(report['parity_gaps'])})")
    md += [f"- `{g['route']}` on {g['present_on']} but not {g['absent_on']}" for g in report["parity_gaps"][:20]] or ["- none"]
    md.append("")
    md.append(f"## Lexicon findings ({len(report['lexicon_findings'])})")
    md += [f"- {f['domain']}{f['route']}: {', '.join(f['terms'])}" for f in report["lexicon_findings"]] or ["- none — both public surfaces are lexicon-clean"]
    (AUDITS / "domain_parity_report.md").write_text("\n".join(md) + "\n")
    reachable = sum(1 for d in report["domains"] if d["reachable"])
    print(f"domain_parity_audit: reachable={reachable}/{len(DOMAINS)} "
          f"parity_gaps={len(report['parity_gaps'])} lexicon_findings={len(report['lexicon_findings'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main() if not ("--help" in sys.argv) else (print(__doc__) or 2))
