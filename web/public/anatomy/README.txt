Anatomy bundle — vendored mirror (read-only)
=============================================

This directory ships the 7-chakra anatomy figure set consumed by the
A11oy `/anatomy` viewer.

State: VENDORED — deterministic local render
(bundle_kind="vendored" in VENDOR.json).

Upstream publication: https://github.com/szl-holdings/ouroboros-thesis
Canonical concept DOI: 10.5281/zenodo.19944926 (always resolves to the
latest published version of the Ouroboros thesis; see
upstream CITATION.cff). v13 release DOI: 10.5281/zenodo.20195368.

Note on the bytes: the upstream repo currently ships a different
8-figure "SZL Agent Anatomy" series under `docs/anatomy/figures/`
(brain, wires, full_body, heart, blood_immune, skeleton, nervous,
body_graph) — not the 7-chakra root→crown naming this viewer
expects. Until upstream publishes chakra-named binaries, the bytes
here are the deterministic local render produced by
`services/amaru/scripts/vendor_anatomy.py`, and `VENDOR.json::upstream_sha`
is pinned to that render's bundle hash so the in-browser drift check
stays green.

The 14 binaries (7 chakras × {pdf, png}) listed in
`VENDOR.json::expected_files` are present. They are rendered
deterministically by `services/amaru/scripts/vendor_anatomy.py`
(reportlab Canvas with `invariant=True` + PIL default PNG save) so
re-runs reproduce the same bytes and the same bundle hash.

Bundle hash algorithm (see `VENDOR.json::drift_detection`):

    sha256( sorted (filename || NUL || bytes || NUL)
            for each entry in expected_files )

`upstream_sha` and `drift_detection.expected_hash` are pinned to that
value. The A11oy `/anatomy` viewer recomputes the same hash in-browser
on every page load and surfaces a drift banner the moment any file is
added, removed, or modified without re-pinning.

To replace the bundle with the upstream-published canonical figures:

  1. Drop the new 14 binaries into this directory verbatim,
     overwriting the existing files.
  2. Re-pin VENDOR.json:

        python services/amaru/scripts/vendor_anatomy.py --repin-only

     This rewrites `upstream_sha`, `drift_detection.expected_hash`,
     `vendored_at`, and `vendored_by` without re-rendering.

DOI + LinkedIn explainer text per chakra is delivered separately from
`src/data/anatomy-citations.json` in the A11oy artifact.
