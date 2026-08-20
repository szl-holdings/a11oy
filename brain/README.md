<!--
SPDX-License-Identifier: Apache-2.0
© 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11 LOCKED
Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
-->

# `brain/` — the SZL self-writing knowledge vault

This is the user's own answer to the leaked "Self-Writing Vault" (an Obsidian
graph wired as a neural-net brain). Instead of a $10 third-party app pointed at a
private notes folder, this is the **real a11oy estate** turned into a living,
self-writing, self-rendering brain that SZL **owns**, on the canonical domain
**a-11-oy.com**, governed by Doctrine v11 and honest by construction.

Two layers ship together:

1. **Substrate (this directory)** — a markdown vault under `brain/vault/` plus the
   generator `brain/harvest_vault.py` that harvests the live estate into dated,
   YAML-frontmatter, backlinked notes. The vault "writes itself."
2. **Graph endpoint** — `GET /api/a11oy/v1/brain/graph` (module
   `a11oy_brain_graph.py`), the MODELED derived view that harvests the same estate
   into a layered node/link graph for the 3D brain render. The vault and the
   endpoint read the **same** real sources, so the pulse is always consistent.

## What it harvests (all REAL — no invented nodes)

| Source | Count | Origin |
| --- | --- | --- |
| Frontier surfaces | 64 | `a11oy_frontier_page.build_surfaces_manifest()` (parsed from `static/3d/holographic.html`) |
| PURIQ formulas F1–F23 | 23 | `szl_puriq_formulas.FORMULA_META` — the wave formula substrate |
| Locked-8 (flagged) | 8 | `{F1,F4,F7,F11,F12,F18,F19,F22}` (`EXPERIMENTAL_WAVES.locked_ids`) |
| Active org repos | 34 | static snapshot of `gh repo list szl-holdings --no-archived` (non-fork) |
| Topic clusters | 8 | distinct `FORMULA_META.organ` values |
| Workspace knowledge docs | best-effort | `/home/user/workspace/{research,audit}` (read-only capture inbox) |

## The "8 rules", adapted to SZL

The leaked app sells eight rules for letting an agent run your Obsidian. Here is
the honest SZL adaptation, implemented by `harvest_vault.py`:

1. **One capture inbox.** Workspace knowledge docs are captured into
   `vault/inbox/knowledge-docs.md` as backlinked pointers — the content stays in
   place, nothing is copied or fabricated.
2. **Auto-file by topic.** Every harvested node is filed under
   `vault/{formulas,surfaces,repos,topics}/` by kind, and cross-tagged by organ.
3. **Morning digest.** `vault/digest/<date>.md` is regenerated on every run — the
   day's pulse (node/link counts, sources, locked-8, Λ status).
4. **Session-aware context.** Every note carries the harvest date and a
   provenance line pointing back at the module/endpoint it came from.
5. **Backlinks.** Notes cross-link with `[[wikilinks]]` derived from the real
   graph edges (formula↔surface, repo↔surface, formula↔topic, …).
6. **Graph-is-the-pulse.** `vault/index.md` mirrors `/api/a11oy/v1/brain/graph`
   exactly, so the vault and the 3D render never disagree.
7. **Own it.** The vault lives in a repo SZL owns; the render is served from
   a-11-oy.com with 0 runtime CDN — no third-party app, no external host.
8. **Honest by design.** Counts are the ACTUAL harvested totals (this is
   explicitly **not** the leaked "8,893 nodes"). Λ = Conjecture 1, never a
   theorem. The locked-8 are flagged but add nothing to the proof count. A harvest
   is a read — it signs nothing (receipts belong on writes).

## Run it

```bash
# harvest into brain/vault/ (writes the notes)
python3 brain/harvest_vault.py

# dry-run: harvest to a temp dir and print the counts only
python3 brain/harvest_vault.py --check

# point the capture inbox at custom knowledge roots
SZL_KNOWLEDGE_DIRS=/path/a:/path/b python3 brain/harvest_vault.py
```

Daily re-filing is design-only for now — see [`REFRESH.md`](REFRESH.md).

## Layout

```
brain/
  README.md            # this file
  REFRESH.md           # daily-cron refresh design (design only)
  harvest_vault.py     # the self-writing generator
  vault/
    index.md           # the pulse (mirrors /brain/graph)
    digest/<date>.md   # morning digest
    inbox/             # capture inbox (workspace docs)
    formulas/          # 23 formula notes (locked-8 flagged)
    surfaces/          # 64 frontier-surface notes
    repos/             # 34 active-org-repo notes
    topics/            # 8 topic-cluster notes
```
