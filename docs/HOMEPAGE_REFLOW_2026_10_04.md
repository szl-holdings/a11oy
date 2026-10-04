<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->
# Homepage reflow at 320px

The retained public-experience run `37208869323` reported 56px of horizontal
overflow on the product's 320px case. Its screenshot also showed the full SZL
identity colliding with the Menu button. The native homepage cascade kept the
identity subtitle visible while inheriting `white-space: nowrap` from an older
navigation rule.

The compact navigation now allocates a shrinkable text column beside a fixed
31px mark and a full 48px Menu target. The subtitle wraps at ordinary word
boundaries, the product wordmark stays on one line, and the full identity remains
available. This changes no navigation destination, approved copy, backend route,
provider authority, or runtime claim.

The source browser comparison also found that the instrument footer kept its
explanation and status on one flex line. The UNAVAILABLE status extended to
385.6px at both 320px and 375px, even where document overflow was clipped by
existing styles. The footer now wraps whole items onto another line when needed,
preserving both the complete explanation and the honest status.

`tests/browser_landing_reflow.cjs` serves the exact committed landing HTML and
its local CSS/JavaScript assets. Provider requests receive explicit unavailable
fixtures, so the check cannot infer a live deployment or capability. It measures
both text ranges and document width at 320, 375, 768 and 1440px, checks that the
identity does not overlap the 48px Menu target, and exercises opening and closing
the compact navigation. On a PR it retains the same measurements for the base
HTML as a before/after control. Instrument screenshots retain the status footer
at both compact widths in addition to the header screenshots.

The job fetches its exact event base commit explicitly. A moving main branch can
put that commit beyond a shallow merge checkout; comparison must retain the
recorded baseline rather than silently substituting another revision.

The read-only `Homepage source reflow` job in `frontend-flow-shell-contract.yml`
retains JSON measurements and screenshots. Its candidate result must pass before
merge; live publisher and postdeployment evidence remain separate.

After installing Playwright and its Chromium binary, reproduce locally with:

```sh
LANDING_EVIDENCE_DIR=/tmp/landing-browser-evidence node tests/browser_landing_reflow.cjs
```

Set `LANDING_BASE_SHA` to the exact base commit to include a comparison. The
test accepts a full hexadecimal commit SHA and never executes ref text as shell
code.
