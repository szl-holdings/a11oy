# A11oy /anatomy — LiveOps update (2026-05-25)

  This drop reflects the live-ops work we shipped today in the a11oy web
  artifact (Vite + React, in the SZL monorepo on Replit), and provides the
  CTO-facing LinkedIn pack — including a Warhacker (Defense Unicorns)
  appendix fit to LinkedIn's 3,000-char limit — for distribution.

  ## What changed in /anatomy

  1. **Removed the AI-generated chakra hero images.** The page now shows
     only operational truth — vendored upstream PDFs, the SHA-256 integrity
     banner, and live tripwire dots. Nothing rendered that we can't prove.

  2. **New LiveOpsPanel.** The /anatomy page now embeds a read-only live
     operational panel that polls the amaru sidecar through the api-server
     proxy on four allowlisted endpoints and renders the actual runtime
     state of the cockpit:

     - `/api/amaru/state` (5s)            — chakras registered, receipts
       counter (append-only), scheduler tick count, bus publishes/failures.
     - `/api/amaru/tripwires` (10s)        — HUKLLA T01–T10 with
       pass/warn/trip status dots and per-tripwire detail.
     - `/api/amaru/overwatch/snapshot` (15s) — R0513 invariants I1–I6 (KL
       drift, joint-margin envelope, mid-execution regate, M=0 rigidity,
       hash-chain integrity) with live kernel + brain hashes.
     - `/api/amaru/scheduler/wiring` (30s) — chakana 21-edge lattice with
       the doctrine-permitted ouroboros edge highlighted in gold.

     Same proxy + allowlist would expose drone-side state to a UDS-deployed
     dashboard with zero new auth surface — directly relevant to Warhacker.

  ## What's in this PR

  - `docs/anatomy-linkedin/a11oy_anatomy_linkedin_post.docx` — copy-paste
    pack: ≤140-char and ≤210-char hooks, full post (2,653 chars), short
    post (1,126 chars), Warhacker appendix (exactly 3,000 chars — fits the
    LinkedIn body limit), hashtags, first-comment link drop, image stack,
    posting tips.
  - `docs/anatomy-linkedin/make_docx.py` — deterministic generator for
    the docx above. Run `python3 make_docx.py` to regenerate.

  ## DOIs (unchanged)

  - Concept DOI (always latest): `10.5281/zenodo.19944926`
  - v13 release DOI: `10.5281/zenodo.20195368`
  