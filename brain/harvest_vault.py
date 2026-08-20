#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11 LOCKED
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""brain/harvest_vault.py — the vault that writes itself.

Harvests the LIVE a11oy estate into a dated, YAML-frontmatter, backlinked
markdown knowledge vault under brain/vault/. This is the SZL "Self-Writing
Vault": one command turns the real estate (frontier surfaces, PURIQ formulas
incl. the locked-8, active org repos, topic clusters) plus the workspace
knowledge docs into Obsidian-style notes wired as a neural-net brain.

SZL adaptation of the leaked "8 rules" (see brain/README.md):
  1. one capture inbox        -> workspace docs land in vault/inbox/
  2. auto-file by topic       -> notes filed under vault/{formulas,surfaces,repos,topics}/
  3. morning digest           -> vault/digest/<date>.md, regenerated each run
  4. session-aware context    -> every note carries the harvest date + provenance
  5. backlinks                -> notes cross-link with [[wikilinks]]
  6. graph-is-the-pulse       -> vault/index.md mirrors the /brain/graph counts

HONESTY (Doctrine v11):
  * Every note traces to a REAL source (a module, an endpoint, a file on disk).
  * Counts are the ACTUAL harvested totals (NOT the leaked 8,893).
  * Λ (F23) = Conjecture 1, never a theorem. Locked-8 flagged, adds nothing.
  * Nothing is signed here — a harvest is a read, and receipts belong on writes.

USAGE
  python3 brain/harvest_vault.py            # harvest into brain/vault/
  python3 brain/harvest_vault.py --check    # harvest to a temp dir; print counts
  # optional workspace-doc capture (best-effort; skipped if absent):
  #   SZL_KNOWLEDGE_DIRS=/path/a:/path/b python3 brain/harvest_vault.py
"""

import argparse
import datetime
import os
import pathlib
import sys
import tempfile

# brain/ lives one level under the repo root; the graph module is at the root.
_BRAIN_DIR = pathlib.Path(__file__).resolve().parent
_REPO_ROOT = _BRAIN_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import a11oy_brain_graph as brain_graph  # noqa: E402

# Default workspace knowledge-doc roots (the "capture inbox" sources). These live
# OUTSIDE the repo and are read best-effort — absent -> skipped, never fabricated.
_DEFAULT_KNOWLEDGE_DIRS = [
    "/home/user/workspace/research",
    "/home/user/workspace/audit",
]


def _today() -> str:
    return datetime.date.today().isoformat()


def _slug(text: str) -> str:
    keep = [c.lower() if c.isalnum() else "-" for c in text]
    s = "".join(keep)
    while "--" in s:
        s = s.replace("--", "-")
    return s.strip("-") or "note"


def _frontmatter(title: str, kind: str, date: str, tags, links, extra=None) -> str:
    lines = ["---", f"title: {title}", f"kind: {kind}", f"harvested: {date}",
             "source: a11oy self-writing vault (brain/harvest_vault.py)",
             f"tags: [{', '.join(tags)}]"]
    for k, v in (extra or {}).items():
        lines.append(f"{k}: {v}")
    lines.append("backlinks:")
    for lk in links:
        lines.append(f"  - \"[[{lk}]]\"")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _capture_knowledge_docs(dirs) -> list:
    """Best-effort read of workspace knowledge docs (the capture inbox).

    Returns [(name, topic_guess, rel_dir)]; never fabricates — absent dir skipped."""
    out = []
    for d in dirs:
        root = pathlib.Path(d)
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*.md")):
            topic = "research" if "research" in str(p) else \
                    ("audit" if "audit" in str(p) else "knowledge")
            out.append((p.name, topic, root.name))
    return out


def harvest(vault_dir: pathlib.Path, knowledge_dirs=None, ns: str = "a11oy") -> dict:
    """Run one full harvest. Writes the vault; returns a summary dict."""
    date = _today()
    g = brain_graph.build_brain_graph(ns)
    knowledge_dirs = knowledge_dirs if knowledge_dirs is not None else _DEFAULT_KNOWLEDGE_DIRS
    docs = _capture_knowledge_docs(knowledge_dirs)

    nodes = g["nodes"]
    by_id = {n["id"]: n for n in nodes}
    # adjacency for backlinks
    adj = {n["id"]: set() for n in nodes}
    for lk in g["links"]:
        adj[lk["source"]].add(lk["target"])
        adj[lk["target"]].add(lk["source"])

    def note_name(nid: str) -> str:
        n = by_id[nid]
        kind = n["kind"]
        if kind == "formula":
            return f"formula-{n['formula_id']}"
        if kind == "surface":
            return f"surface-{_slug(nid.split(':', 1)[1])}"
        if kind == "repo":
            return f"repo-{_slug(n['title'])}"
        if kind == "topic":
            return f"topic-{_slug(n['title'])}"
        if kind == "endpoint":
            return f"endpoint-{_slug(n['path'])}"
        return _slug(nid)

    written = 0

    # ---- formulas (auto-filed) ------------------------------------------- #
    for n in nodes:
        if n["kind"] != "formula":
            continue
        fid = n["formula_id"]
        back = [note_name(t) for t in sorted(adj[n["id"]]) if t in by_id]
        extra = {"formula_id": fid, "proof_status": n["proof_status"],
                 "locked": str(n["locked"]).lower()}
        if n.get("conjecture"):
            extra["conjecture"] = n["conjecture"]
        fm = _frontmatter(n["title"], "formula", date,
                          ["formula", "puriq", n["organ"].replace("/", "-")],
                          back, extra)
        body = [f"# {fid} — {n['title']}", "",
                f"- **Organ:** {n['organ']}",
                f"- **Primitive:** {n['primitive']}",
                f"- **Proof status:** `{n['proof_status']}`",
                f"- **Locked-8:** {'YES — flagged; adds nothing (locked_count_eight)' if n['locked'] else 'no'}"]
        if fid == "F23":
            body.append("- **Λ:** Conjecture 1 — NEVER a theorem.")
        body += ["", "Harvested from `szl_puriq_formulas.FORMULA_META` via "
                 f"`/api/{ns}/v1/brain/graph`.", ""]
        if back:
            body.append("## Backlinks")
            body += [f"- [[{b}]]" for b in back]
        _write(vault_dir / "formulas" / f"formula-{fid}.md", fm + "\n" + "\n".join(body) + "\n")
        written += 1

    # ---- surfaces (auto-filed) ------------------------------------------- #
    for n in nodes:
        if n["kind"] != "surface":
            continue
        back = [note_name(t) for t in sorted(adj[n["id"]]) if t in by_id]
        fm = _frontmatter(n["title"], "surface", date,
                          ["surface", "frontier"], back,
                          {"honesty_label": n["label"], "present": str(n["present"]).lower()})
        body = [f"# {n['title']}", "",
                f"- **Honesty label:** `{n['label']}` (verbatim from surface source)",
                f"- **Asset:** `{n.get('asset')}`",
                "", f"Harvested from the frontier surfaces manifest "
                f"(`/api/{ns}/v1/frontier/surfaces`).", ""]
        if back:
            body.append("## Backlinks")
            body += [f"- [[{b}]]" for b in back]
        _write(vault_dir / "surfaces" / f"{note_name(n['id'])}.md",
               fm + "\n" + "\n".join(body) + "\n")
        written += 1

    # ---- repos (auto-filed) ---------------------------------------------- #
    for n in nodes:
        if n["kind"] != "repo":
            continue
        back = [note_name(t) for t in sorted(adj[n["id"]]) if t in by_id]
        fm = _frontmatter(n["title"], "repo", date, ["repo", "org"], back,
                          {"org": n["org"]})
        body = [f"# {n['org']}/{n['title']}", "",
                f"- Active (non-archived) org repo, snapshot "
                f"{brain_graph.ORG_REPOS_SNAPSHOT['captured']}.", ""]
        if back:
            body.append("## Backlinks")
            body += [f"- [[{b}]]" for b in back]
        _write(vault_dir / "repos" / f"{note_name(n['id'])}.md",
               fm + "\n" + "\n".join(body) + "\n")
        written += 1

    # ---- topics (auto-filed) --------------------------------------------- #
    for n in nodes:
        if n["kind"] != "topic":
            continue
        back = [note_name(t) for t in sorted(adj[n["id"]]) if t in by_id]
        fm = _frontmatter(n["title"], "topic", date, ["topic", "organ"], back)
        body = [f"# Topic — {n['title']}", "",
                "Topic cluster derived from the distinct formula organs "
                "(`FORMULA_META.organ`).", ""]
        if back:
            body.append("## Backlinks")
            body += [f"- [[{b}]]" for b in back]
        _write(vault_dir / "topics" / f"{note_name(n['id'])}.md",
               fm + "\n" + "\n".join(body) + "\n")
        written += 1

    # ---- capture inbox: workspace knowledge docs -------------------------- #
    inbox = [f"# Capture inbox — workspace knowledge docs", "",
             f"Auto-filed {date}. {len(docs)} doc(s) captured from the workspace "
             "knowledge roots (read-only; content stays in place, the vault keeps a "
             "backlinked pointer).", ""]
    if docs:
        for name, topic, root in docs:
            inbox.append(f"- `{root}/{name}` — topic: {topic} (see [[topic-{_slug(topic)}]])")
    else:
        inbox.append("- (no workspace knowledge roots present in this environment — "
                     "skipped honestly, nothing fabricated)")
    _write(vault_dir / "inbox" / "knowledge-docs.md", "\n".join(inbox) + "\n")

    # ---- morning digest --------------------------------------------------- #
    s = g["summary"]
    digest = [f"# Morning digest — {date}", "",
              "Regenerated each harvest. The pulse of the estate brain.", "",
              "## Pulse (graph-is-the-pulse)",
              f"- **Nodes:** {g['node_count']}  ·  **Links:** {g['link_count']}",
              f"- By kind: {s['by_kind']}",
              f"- By layer: {s['by_layer']}",
              f"- Locked-8 flagged: {s['locked_flagged']} (Λ = Conjecture 1)", "",
              "## Real sources harvested",
              f"- Frontier surfaces: {g['sources']['surfaces']['count']} "
              f"(`{g['sources']['surfaces']['endpoint']}`)",
              f"- PURIQ formulas: {g['sources']['formulas']['count']} "
              f"(`{g['sources']['formulas']['endpoint']}`)",
              f"- Active org repos: {g['sources']['repos']['count']} "
              f"(snapshot {g['sources']['repos']['captured']})",
              f"- Topic clusters: {g['sources']['topics']['count']}",
              f"- Workspace docs captured: {len(docs)}", "",
              "See [[index]] for the full pulse and [[knowledge-docs]] for the inbox.", ""]
    _write(vault_dir / "digest" / f"{date}.md", "\n".join(digest) + "\n")

    # ---- index (the pulse mirror) ---------------------------------------- #
    idx = [f"# a11oy self-writing brain vault", "",
           f"Harvested {date} — canonical domain **{brain_graph.CANONICAL_DOMAIN}**.",
           "Top label: **MODELED** (a derived view over the real estate).", "",
           "## Pulse",
           f"- Nodes: **{g['node_count']}**  ·  Links: **{g['link_count']}**",
           f"- By kind: {s['by_kind']}",
           f"- Live view: `/api/{ns}/v1/brain/graph`", "",
           "## Sections",
           "- [[knowledge-docs]] — capture inbox",
           f"- `formulas/` — {s['by_kind'].get('formula', 0)} notes",
           f"- `surfaces/` — {s['by_kind'].get('surface', 0)} notes",
           f"- `repos/` — {s['by_kind'].get('repo', 0)} notes",
           f"- `topics/` — {s['by_kind'].get('topic', 0)} notes",
           f"- `digest/{date}.md` — morning digest", "",
           "## Doctrine",
           "- Λ = Conjecture 1 (never a theorem). Locked-8 exactly 8, flagged, adds nothing.",
           "- Counts are the ACTUAL harvested totals — NOT the leaked 8,893.", ""]
    _write(vault_dir / "index.md", "\n".join(idx) + "\n")

    return {"date": date, "vault": str(vault_dir), "notes_written": written + 3,
            "node_count": g["node_count"], "link_count": g["link_count"],
            "by_kind": s["by_kind"], "docs_captured": len(docs)}


def main() -> int:
    ap = argparse.ArgumentParser(description="a11oy self-writing vault harvester")
    ap.add_argument("--check", action="store_true",
                    help="harvest into a temp dir and print counts (no vault write)")
    ap.add_argument("--vault", default=str(_BRAIN_DIR / "vault"),
                    help="vault output dir (default: brain/vault)")
    args = ap.parse_args()

    env_dirs = os.environ.get("SZL_KNOWLEDGE_DIRS")
    kdirs = env_dirs.split(":") if env_dirs else None

    if args.check:
        with tempfile.TemporaryDirectory() as td:
            r = harvest(pathlib.Path(td), knowledge_dirs=kdirs)
    else:
        r = harvest(pathlib.Path(args.vault), knowledge_dirs=kdirs)
    print(f"[harvest_vault] {r['date']} — {r['node_count']} nodes / "
          f"{r['link_count']} links; wrote {r['notes_written']} note groups to "
          f"{r['vault']}; {r['docs_captured']} workspace docs captured.")
    print(f"[harvest_vault] by_kind={r['by_kind']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
