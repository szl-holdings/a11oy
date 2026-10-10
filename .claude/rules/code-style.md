<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->

# Rule: code-style

## Every new file carries the SZL header

Python (matches the existing repo convention, e.g. `szl_codename_gate.py`):

```python
#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
```

Markdown / other:

```
<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->
```

## Rules

- **No new top-level module without a taxonomy home.** State which layer
  (`agents`/`tools`/`services`/`provenance`/`governance`/`energy`/`supply-chain`) a new module
  belongs to in the PR description. See `AGENTS.md` → *Where things live*.
- **Add a Dockerfile `COPY` line for every new `.py`** that serves a route — the Dockerfile uses
  per-file `COPY` (no `COPY . .`); a missing line means a silent 404 (see `KNOWN_GOTCHAS.md`).
- **Do not use `from __future__ import annotations`** in files defining FastAPI route handlers or
  Pydantic models — it breaks model validation at runtime.
- **Register new API routes before the SPA catch-all** or they fall through to an HTML 200.
- Match the surrounding file's style. UI follows the founder **SZL KANCHAY** design system
  (szl-brand `kanchay/` 1.3.0 and its `DESIGN_DIRECTION.md`): vendor `szl-design-system.css`
  (plus `szl-console.css` on operator surfaces) byte-for-byte into one `szl/` folder per served
  root (main Space: `console/assets/szl/`, served at `/assets/szl/`), link it before the page's
  own sheet, and build with its tokens and classes. Dark operator is `:root` (graphite); light
  editorial is `<html data-surface="light">` (warm paper). A dark panel inside a light page (or the reverse) declares
  `data-surface="dark"` (or `"light"`) on its own root so its text, links and focus follow its
  ground; console aliases re-resolve there via `szl-console-focus.css`. One coral moment per
  view, gold only for premium, teal only for links and focus, status never colour-only. No colour or font-name literals, no webfonts, no
  CDN. The legacy dark-ground / gold + teal house style is retired.
- Comments explain *why*, not *what*. Default to none.
</content>
