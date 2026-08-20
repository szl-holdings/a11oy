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
- Match the surrounding file's style; keep the dark-ground / gold `#c9b787` + teal `#5fb3a3`
  house style for any UI.
- Comments explain *why*, not *what*. Default to none.
</content>
