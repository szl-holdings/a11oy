# Command Centre v2 ship path

Product origin: `https://a-11-oy.com`

The surface is additive at `/command-v2`. `/command` and `/console` remain unchanged.

## Source and image contract

- `web/command_v2.html` is committed source.
- `a11oy_command_center.py` registers GET and HEAD before the `/command/{rest:path}` catch-all.
- `Dockerfile` copies the exact HTML into `/app/web/command_v2.html`.
- A missing file returns an honest HTTP 503 `UNAVAILABLE`; it is never represented as a successful HTML surface.
- The candidate reads existing same-origin A11oy and Hatun evidence routes and grants no execution authority.

## Accessibility boundary

The page preserves 44-pixel controls, visible keyboard focus, responsive two-column and one-column collapse, reduced-motion handling, forced-colors handling, and zero third-party CDN dependencies.

## Promotion boundary

Do not move this candidate onto `/command` without a separate reviewed release decision and live exact-source verification.
