# a11oy README lead — PR patch instructions

This is a **lead-only patch** of `szl-holdings/a11oy` `README.md`.
It is **not** a full rewrite. Nothing below the splice is in scope.
No later work is lost.

Patch source: `A11OY_README_LEAD.md` (this directory).
Live base: `https://github.com/szl-holdings/a11oy/blob/main/README.md`
(captured 2026-08-29, SHA `6a3e3c0cc2428f4e1b4f8e1ab78552021c01ac46`,
commit `f79c4715d544f2d8809a757ed25a55f31a093bd6`).

## What to change

Replace the live README **from the start of the file through the end of
`## What it does`** (through the `---` that currently sits just above
`## The proof backbone`).

Keep everything from this heading onward, byte-for-byte:

```
## The proof backbone
```

That preserves, unchanged:

- The proof backbone (Lean 4, locked-8, Λ, SLSA)
- Verify it yourself
- The later Live surfaces section (governance, energy ledger, classifiers)
- Persistent receipt storage (HF Space)
- Honest status
- Shared modules (must not drift)
- Governed Delta Workspace
- Learn more
- Footer and estate organ list

The new lead already carries the first-screen Live surfaces table
(console + `/api/a11oy/v1/honest`). The later, longer Live surfaces
section stays where it is. Do not merge, delete, or restyle it in
this PR. A follow-up may reconcile the two tables; this PR must not.

## How to apply

1. Open `README.md` on a branch off current `main`.
2. Delete from line 1 through the `---` immediately before
   `## The proof backbone`.
3. Insert the full contents of `A11OY_README_LEAD.md` in that place.
4. Confirm the file continues with `## The proof backbone` and that
   no later heading, table, code fence, or footer moved.
5. Diff should be **front-of-file only**. If the diff touches GDW,
   shared-module hashes, Series-A storage, or Learn more, you have
   gone too far. Abort and re-apply.

The lead file ends with:

```
<!-- LEAD END. Existing README continues from ## The proof backbone. Do not rewrite past this marker in the lead-only PR. -->
```

Leave that marker in the committed README. It is the contract that
this PR stops here.

## First-screen doctrine (do not relax)

- This repository is **SOURCE** for the product origin
  `https://a-11-oy.com`.
- Proof lives on `https://a11oy.net`.
- Point to `a-11-oy.com` first, then `a11oy.net`.
- Never `a11oy.com`. Do not link it. Do not list it as a surface.
- `receipts.in ≡ receipts.out` is an invariant, not a slogan.
- First-screen Live surfaces table is only:
  - console → `https://a-11-oy.com/console`
  - doctrine posture → `https://a-11-oy.com/api/a11oy/v1/honest`
- Factory is a **bind**, not a second flagship.
- Λ = Conjecture 1; kernel `c7c0ba17`; locked-8; trust 0.97.
- Warhacker v1.0.0 is ARCHIVED. Mention it **once**, as that archive
  line, and nowhere else in the first screen.
- No hero screenshot collage. No five superpowers. No emoji in
  visible body copy. Do not market. No “try it now”, no “Open a11oy”,
  no Hugging Face CTA in the lead.

## Deliberate omissions (do not restore in this PR)

Removed from the first screen on purpose:

- The `SZL-ESTATE-CARD:v2` banner collage and badge row.
- The investor-readable centered hero, badge wall, and three CTAs.
- The “What a11oy is” / “What it does” marketing blocks, including
  the WILLAY curl demo.
- Any screenshot grid.

If estate-card policy still requires the `SZL-ESTATE-CARD:v2` block
in this file, that is a **later PR**, and the block goes **below**
`LEAD END`, never above `# a11oy`.

Hugging Face YAML frontmatter stays at the top of the lead because
this README is also the Space card. The `emoji` field is a Space icon
key, not README body copy. Do not add emoji below the frontmatter.

The YAML `short_description` is factual (source / origin / proof).
Do not change it back to a pitch.

## Out of scope (do not “fix” in this PR)

- GitHub repository description (still names Five Superpowers and
  Warhacker). Separate metadata PR.
- `a11oy_landing.html`, Hub Space copy, org profile README.
- Factory repo README, lutar-lean, szl-formulas.
- Rulesets, deployments, DNS, Hub visibility.
- Reordering or rewriting any section after `## The proof backbone`.

## Review checklist

- [ ] Diff is lead-only. `## The proof backbone` and everything after
      it is identical to `main`.
- [ ] First product URL is `https://a-11-oy.com`. Second is
      `https://a11oy.net`.
- [ ] `a11oy.com` does not appear as a link or a live surface.
- [ ] `receipts.in ≡ receipts.out` is present.
- [ ] Live surfaces table in the lead has exactly two rows: console
      and `/api/a11oy/v1/honest`.
- [ ] Factory is named as a bind, not a flagship.
- [ ] Λ = Conjecture 1, kernel `c7c0ba17`, locked-8, trust 0.97.
- [ ] Warhacker appears once in the lead, as the v1.0.0 ARCHIVED line.
- [ ] No screenshots, no superpowers, no emoji in body copy, no CTAs.
- [ ] Later Live surfaces, GDW, shared modules, and Learn more still
      present.

## Why this shape

The live lead mixed origin, proof, Hub demo, estate banner, and a
pitch. The first screen of a source repository should say what the
tree is, where the product runs, where proof is checked, and which
pins are locked. Everything else already exists further down the
same file. Leave it there.
