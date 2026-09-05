# Homepage shell current-main successor

- `workcell_id`: `A11OY-HOMEPAGE-SHELL-CURRENT-MAIN-20260905`
- `source_base`: `94e129d016a7e82e0b22f11c00ea877b5cc430f5`
- `supersedes_candidate`: `#1973`
- `state`: `OPEN_REPAIR`

## Objective

Port the reviewed homepage navigation/responsive shell improvements from #1973 onto current protected main, preserving the runtime/Command corrections merged through #1986, and close the unresolved mobile-menu P1.

## Scope

Frontend shell only: homepage markup/style/script and the existing shared Holo/Flow enhancement scripts plus focused tests/repair script as needed. No backend endpoint, provider, credential, DNS, deployment, or execution authority change.

## Required P1 correction

When a visitor opens the mobile menu after scrolling, the expanded header/menu must remain visible and anchored; toggling the menu must not convert the sticky header to a document-flow position above the current viewport.

## Acceptance

One primary navigation, one accessible menu control and skip link; mobile destinations preserved; Escape/focus/outside close behavior; no horizontal overflow at 320/390/768/1280; conditional signing language retained; focused shell contracts plus current-main command/navigation tests; exact-head hosted matrix and independent review.
