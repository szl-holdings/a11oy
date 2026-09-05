# Mobile CTA hit-area fix (issue #1359)

## Measured failure

Canary run 33988320849 (protected source 9123dc28) — page failures dropped 2 -> 1
after #2000's shell port. The sole remaining blocker:

- Control: `Book an evidence pilot` (`mailto:` link), class `btn btn-ghost`
- Viewport: 360x800
- Rendered height: 43.17px against the 44px floor (width 311.73px)
- Code: PRIMARY_TARGET_UNDERSIZED
- 15/15 render checks pass; 0 console errors otherwise

## Root cause

`a11oy_landing.html` already carries the mobile hit-area floor on nav CTAs:
`.nav nav .btn{padding:9px 12px;font-size:12px;max-width:154px;min-height:44px}`.
The failing control is the hero CTA (outside `.nav`), so the rule never reaches it.

## Fix

`ops/patches/mobile-cta-hit-area-44px.patch` adds one rule extending the same
44px floor to hero/action buttons at <=480px (flex-centered so the text does not
shift). Desktop breakpoints are untouched.

## Verification

1. Apply the patch: `git apply ops/patches/mobile-cta-hit-area-44px.patch`
2. Run the canary (the workflow that files #1359) — expect page_failures 0, all
   viewports pass.
3. Confirm the canary issue reports PASS on the next scheduled run.

This is a one-rule CSS change with no backend, provider, or authority change.