# spaces/immune — provenance (reverse-imported for governance)

**What:** the deployed contents of the standalone HuggingFace Space
`SZLHOLDINGS/immune` ("IMMUNE — Verifiable AI"), reverse-imported here so GitHub is its
source of truth. Previously the Space had **no GitHub source** = ungoverned drift risk.

**Why reverse-import (not redirect-to-a11oy):** unlike a stale duplicate, this Space is a
**functionally distinct, live** surface. It serves its **own** API that the a11oy-served
`/immune` route does **not** expose:

```
# standalone SZLHOLDINGS/immune (live, 2026-06-30):
GET /api/immune/state         -> 200 {"mode":"PASS","ledgerCount":5,"lastHash":"bdb245a0…"}
GET /api/immune/ledger/verify -> 200 {"ok":true,"count":5,"issues":[],"firstBadSeq":null}

# a11oy /immune route:
GET /api/immune/state         -> 404 {"error":"not found"}
```

a11oy `/immune` is a different surface ("Immune (Hukulla) — fail-closed egress gate").
Redirecting this Space would **break a working API-backed demo**, so the honest fill is to
govern it from GitHub.

**Deploy model:** Node app (`node:20-alpine`), per-file `COPY dist/immune-server.js`,
`COPY dist/public`, `COPY dist/data`. Not a per-file-`COPY`-of-source chain the reusable
deployer can derive (it copies built `dist/` directories), so this folder is the governed
source and the Space is rebuilt from it.

**Honest limitations:**
- These are **built artifacts** (`dist/immune-server.js` is a 1.45 MB bundle;
  `dist/public/assets/index-*.js` is the vite build). The **upstream TypeScript/vite
  source and `build-standalone.sh`** referenced in the `Dockerfile` are **not present in
  the Space** and so are not captured here — this governs the *shipped image*, not the
  pre-build source. Tracking down and committing the true build source is honest follow-up.
- `dist/data/immune/ledger.jsonl` (+ `huklla_evidence.jsonl`) is **runtime-mutable**: the
  live `/api/immune/*` endpoints append to it (live `ledgerCount` was 5 at import). The
  committed copy is the **shipped seed/baseline**; live divergence from this file is
  expected runtime state, **not** a governance violation. A drift-check should exclude the
  ledger path or compare only the immutable bundle/public assets.

**Imported from:** `https://huggingface.co/spaces/SZLHOLDINGS/immune` @ `main` on
2026-06-30. Files are faithful copies (real content; LFS patterns in `.gitattributes`
match only model/binary types not present here).
